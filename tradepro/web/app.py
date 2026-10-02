"""Web app: portfolio with sell advice, buy scanner and charts.

Run locally:   python -m tradepro.web
On a server:   gunicorn -w 1 --threads 8 -b 0.0.0.0:8000 "tradepro.web.app:create_app()"

Environment:
  TRADEPRO_PASSWORD   if set, the site asks for this password (any username)
  TRADEPRO_DB         SQLite file (default data/tradepro.db)
  TRADEPRO_SOURCE     yahoo (default) | csv | synthetic
  TRADEPRO_SCAN_HOURS rescan each market when the last scan is older than this (default 6, 0 = off)
"""

from __future__ import annotations

import hmac
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone

import numpy as np
from flask import Flask, Response, abort, jsonify, redirect, render_template, request, url_for

from ..advisor import advise
from ..chaloke import CDC_TH, analyze as analyze_chaloke
from ..config import DEFAULT
from ..data import TIMEFRAMES, resample
from ..indicators import add_features
from ..markets import MARKETS
from ..prices import PriceService
from ..setups import detect
from ..wave import cdc_action_zone
from ..store import Store
from ..watchlists import ASSETS, WATCHLISTS, normalize_ticker

log = logging.getLogger("tradepro.web")

SETUP_TH = {"W3": "Wave 3 (ลุงโฉลก): Wave 2 ย่อ 61.8–94.2% แล้ว CDC Action Zone เขียวแรก"}
STATUS_TH = {"hold": "ถือต่อ", "watch": "เฝ้าระวัง", "sell": "ควรขาย"}
ACTION_TH = {"add": "ซื้อเพิ่มได้", "trim": "ขายรินกำไร", "sell": "ขายทั้งหมด", "hold": "ถือ ยังไม่ต้องทำอะไร"}
CONTEXT_TH = {k: "CDC " + v[0] for k, v in CDC_TH.items()} | {"": "-"}
CURRENCY = {k: m.currency for k, m in MARKETS.items()}
MARKET_TH = {k: m.label for k, m in MARKETS.items()}
SETUP_ORDER = {"W3": 0}


# Scan universes: id -> (market, watchlist, label)
SCANS = {
    "set": ("set", "set100", "หุ้นไทย (SET100)"),
    "setall": ("set", "set_all", "หุ้นไทยทั้งหมด (SET + mai)"),
    "us": ("us", "us50", "หุ้นสหรัฐ (US50)"),
    "asset": ("asset", "assets", "คริปโต / ทองคำ"),
}
LIVE_SECONDS = 60       # the chart's live analysis refetches prices at most this often
MIN_VALUE_THB = float(os.environ.get("TRADEPRO_MIN_VALUE", "1000000"))   # skip illiquid stocks in "setall"


def pivots(f, side: int = 3):
    """Swing highs / lows: bars whose high (low) is the extreme of `side` bars on each side."""
    hi, lo = f["high"].to_numpy(), f["low"].to_numpy()
    out = []
    for k in range(side, len(f) - side):
        if hi[k] == hi[k - side:k + side + 1].max():
            out.append((k, "high", hi[k]))
        if lo[k] == lo[k - side:k + side + 1].min():
            out.append((k, "low", lo[k]))
    return out


def market_cfg(market: str):
    m = MARKETS[market]
    return replace(DEFAULT, market=m.name, cost_pct=m.cost_pct)


class Scanner:
    """Runs market scans in a background thread so pages never wait on them."""

    def __init__(self, store: Store, prices: PriceService):
        self.store, self.prices = store, prices
        self.running: set[str] = set()
        self._lock = threading.Lock()

    def start(self, market: str) -> bool:
        with self._lock:
            if market in self.running:
                return False
            self.running.add(market)
        threading.Thread(target=self._run, args=(market,), daemon=True).start()
        return True

    def _run(self, scan_id: str):
        market, watchlist, _ = SCANS[scan_id]
        try:
            cfg = market_cfg(market)
            tickers = list(WATCHLISTS[watchlist])
            tickers += [h["ticker"] for h in self.store.holdings() if h["market"] == market and h["ticker"] not in tickers]
            results, errors = [], []

            def one(t):
                df = self.prices.history(market, t)
                last, px = df.index[-1], float(df["close"].iloc[-1])
                if scan_id == "setall":
                    value = float((df["close"] * df["volume"]).iloc[-20:].mean())
                    if not value >= MIN_VALUE_THB:
                        return []                       # too thin to trade; skip

                recent = list(df.index[-cfg.w3_recent_bars:])
                green_now = bool(cdc_action_zone(df)["cdc_green"].iloc[-1])
                rows = []
                for s in detect(df, t, cfg):
                    if s.direction != "long":
                        continue
                    if s.date == last:
                        rows.append(s.as_dict() | {"last_close": round(px, 4), "days_ago": 0})
                    elif s.setup == "W3" and s.date in recent and green_now and px > s.stop:
                        # W3 stays buyable for a few days while CDC is still green and the price has not
                        # run away: reward/risk from today's close must still meet w3_min_rr ("ไม่ตกรถ")
                        rr_now = (s.target - px) / (px - s.stop)
                        if rr_now >= cfg.w3_min_rr:
                            rows.append(s.as_dict() | {"last_close": round(px, 4), "reward_r": round(rr_now, 2),
                                                       "days_ago": len(df) - 1 - df.index.get_loc(s.date)})
                return rows

            with ThreadPoolExecutor(max_workers=8 if len(tickers) > 100 else 4) as pool:
                for t, fut in [(t, pool.submit(one, t)) for t in tickers]:
                    try:
                        results += fut.result()
                    except Exception as e:  # keep scanning the rest
                        errors.append(f"{t}: {e}")
            results.sort(key=lambda r: (SETUP_ORDER.get(r["setup"], 9), -r["reward_r"]))
            self.store.save_scan(scan_id, results, errors)
        except Exception:
            log.exception("scan %s failed", scan_id)
        finally:
            with self._lock:
                self.running.discard(scan_id)

    def autoscan_forever(self, every_hours: float):
        while True:
            for market in SCANS:
                last = self.store.latest_scan(market)
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(last["run_at"])).total_seconds() \
                    if last else None
                if age is None or age > every_hours * 3600:
                    self.start(market)
            time.sleep(600)


def create_app(db_path: str | None = None, source: str | None = None, autoscan: bool = True) -> Flask:
    app = Flask(__name__)
    store = Store(db_path or os.environ.get("TRADEPRO_DB", "data/tradepro.db"))
    prices = PriceService(source or os.environ.get("TRADEPRO_SOURCE", "yahoo"))
    scanner = Scanner(store, prices)
    password = os.environ.get("TRADEPRO_PASSWORD", "")
    every = float(os.environ.get("TRADEPRO_SCAN_HOURS", "6"))
    if autoscan and every > 0:
        threading.Thread(target=scanner.autoscan_forever, args=(every,), daemon=True).start()
    app.config.update(store=store, prices=prices, scanner=scanner)

    @app.before_request
    def require_password():
        if not password or request.endpoint == "static":
            return None
        auth = request.authorization
        if auth and hmac.compare_digest(auth.password or "", password):
            return None
        return Response("ต้องใส่รหัสผ่าน", 401, {"WWW-Authenticate": 'Basic realm="TradePro"'})

    @app.context_processor
    def helpers():
        return {"STATUS_TH": STATUS_TH, "ACTION_TH": ACTION_TH, "CONTEXT_TH": CONTEXT_TH, "SETUP_TH": SETUP_TH,
                "CURRENCY": CURRENCY, "MARKETS": MARKETS, "MARKET_TH": MARKET_TH, "ASSETS": ASSETS}

    def evaluate(h: dict) -> dict:
        row = dict(h)
        try:
            df = prices.history(h["market"], h["ticker"])
            a = advise(df, market_cfg(h["market"]), cost=h["cost"])
            value, basis = a.price * h["shares"], h["cost"] * h["shares"]
            row.update(advice=a, price=a.price, value=value, basis=basis, pnl=value - basis,
                       pnl_pct=(a.price / h["cost"] - 1) * 100 if h["cost"] else 0.0)
        except Exception as e:
            row.update(error=str(e), basis=h["cost"] * h["shares"])
        return row

    @app.get("/")
    def portfolio():
        holdings = store.holdings()
        with ThreadPoolExecutor(max_workers=6) as pool:
            rows = list(pool.map(evaluate, holdings))
        groups = {}
        for m in MARKETS:
            items = [r for r in rows if r["market"] == m]
            if items:
                ok = [r for r in items if "value" in r]
                value, basis = sum(r["value"] for r in ok), sum(r["basis"] for r in ok)
                groups[m] = {"rows": items, "value": value, "basis": basis, "pnl": value - basis,
                             "pnl_pct": (value / basis - 1) * 100 if basis else 0.0}
        return render_template("portfolio.html", groups=groups, active="portfolio")

    @app.post("/holdings")
    def add_holding():
        f = request.form
        try:
            market, ticker = normalize_ticker(f["market"], f["ticker"])
            shares, cost = float(f["shares"]), float(f["cost"])
            if market not in MARKETS or not ticker or shares <= 0 or cost <= 0:
                raise ValueError
        except (KeyError, ValueError):
            abort(400, "ข้อมูลไม่ครบหรือไม่ถูกต้อง")
        store.add_holding(market, ticker, shares, cost, f.get("note", ""))
        return redirect(url_for("portfolio"))

    @app.post("/holdings/<int:hid>/edit")
    def edit_holding(hid):
        f = request.form
        try:
            store.update_holding(hid, float(f["shares"]), float(f["cost"]), f.get("note", ""))
        except (KeyError, ValueError):
            abort(400, "ข้อมูลไม่ถูกต้อง")
        return redirect(url_for("portfolio"))

    @app.post("/holdings/<int:hid>/delete")
    def delete_holding(hid):
        store.delete_holding(hid)
        return redirect(url_for("portfolio"))

    @app.get("/scan")
    def scan_page():
        scan_id = request.args.get("market", "set")
        if scan_id not in SCANS:
            abort(404)
        market, watchlist, _ = SCANS[scan_id]
        return render_template("scan.html", market=market, scan_id=scan_id, scans=SCANS,
                               scan=store.latest_scan(scan_id), watchlist=WATCHLISTS[watchlist],
                               running=scan_id in scanner.running, active="scan")

    @app.post("/scan/run")
    def scan_run():
        market = request.form.get("market", "set")
        if market in SCANS:
            scanner.start(market)
        return redirect(url_for("scan_page", market=market))

    @app.get("/chart")
    def chart_lookup():
        market = request.args.get("market", "set")
        market, ticker = normalize_ticker(market, request.args.get("ticker", ""))
        if market not in MARKETS or not ticker:
            return redirect(url_for("scan_page", market=market if market in MARKETS else "set"))
        return redirect(url_for("chart_page", market=market, ticker=ticker))

    @app.get("/chart/<market>/<ticker>")
    def chart_page(market, ticker):
        if market not in MARKETS:
            abort(404)
        tf = request.args.get("tf", "D")
        if tf not in TIMEFRAMES:
            tf = "D"
        return render_template("chart.html", market=market, ticker=ticker.upper(), tf=tf, active="")

    @app.get("/api/chaloke/<market>/<ticker>")
    def chaloke_data(market, ticker):
        """Live ChalokeDotCom checklist; the chart page polls this every minute."""
        tf = request.args.get("tf", "D")
        if market not in MARKETS or tf not in TIMEFRAMES:
            abort(404)
        try:
            if tf == "D":
                df = prices.history(market, ticker, max_age=LIVE_SECONDS)
            else:
                df = resample(prices.history(market, ticker, start="2000-01-01", max_age=LIVE_SECONDS), tf)
            a = analyze_chaloke(df, market_cfg(market))
        except Exception as e:
            return jsonify(error=str(e)), 502
        return jsonify(a | {"checked_at": datetime.now(timezone.utc).isoformat()})

    @app.get("/api/chart/<market>/<ticker>")
    def chart_data(market, ticker):
        if market not in MARKETS:
            abort(404)
        tf = request.args.get("tf", "D")
        if tf not in TIMEFRAMES:
            abort(404)
        try:
            daily = prices.history(market, ticker)
            # weekly and longer bars need a long history (monthly / yearly back to 2000)
            df = daily if tf == "D" else resample(prices.history(market, ticker, start="2000-01-01"), tf)
        except Exception as e:
            return jsonify(error=str(e)), 502
        cfg = market_cfg(market)
        full = add_features(df, cfg)
        cdc = cdc_action_zone(full)
        f = full.iloc[-250:] if tf in ("D", "W") else full
        z = cdc.loc[f.index]
        day = lambda d: d.strftime("%Y-%m-%d")
        sig_json = lambda s: {"time": day(s.date), "setup": s.setup, "direction": s.direction, "entry": s.entry,
                              "stop": s.stop, "target": s.target, "reward_r": round(s.reward_r, 2),
                              "note": s.note, "order": s.order, "levels": s.levels}
        num = lambda v: None if v is None or not np.isfinite(v) else round(float(v), 4)
        sigs = [s for s in detect(df.iloc[-300:], ticker, cfg) if s.date >= f.index[0]]
        a = advise(daily, cfg)          # hold / sell advice always comes from the daily chart
        held = [h for h in store.holdings() if h["market"] == market and h["ticker"] == ticker.upper()]
        last, zl = full.iloc[-1], cdc.iloc[-1]
        latest = next((s for s in reversed(sigs) if s.date >= full.index[-3]), None)   # live in the last 3 bars
        bars = [{"time": day(d), "atr": num(r.atr), "body": num(r.body_ratio), "close_pos": num(r.close_pos),
                 "cdc": zone} for d, r, zone in zip(f.index, f.itertuples(), z["cdc_zone"])]
        return jsonify(
            candles=[{"time": day(d), "open": r.open, "high": r.high, "low": r.low, "close": r.close}
                     for d, r in zip(f.index, f.itertuples())],
            cdc_fast=[{"time": day(d), "value": v} for d, v in z["cdc_fast"].items()],
            cdc_slow=[{"time": day(d), "value": v} for d, v in z["cdc_slow"].items()],
            bars=bars,
            swings=[{"time": day(f.index[k]), "kind": kind, "price": num(p)} for k, kind, p in pivots(f)],
            signals=[sig_json(s) for s in sigs],
            latest=None if latest is None else sig_json(latest),
            levels={"atr": num(last.atr), "cdc_zone": str(zl["cdc_zone"]), "cdc_fast": num(zl["cdc_fast"]),
                    "cdc_slow": num(zl["cdc_slow"])},
            advice={"status": a.status, "stop": a.stop, "resistance": a.resistance,
                    "context": a.context, "reasons": a.reasons},
            last_date=day(daily.index[-1]),
            cost=held[0]["cost"] if held else None,
            shares=held[0]["shares"] if held else None,
        )

    return app
