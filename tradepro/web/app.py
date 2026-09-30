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
from ..config import DEFAULT
from ..indicators import add_features
from ..markets import MARKETS
from ..prices import PriceService
from ..setups import count_highs, detect
from ..store import Store
from ..watchlists import WATCHLISTS

log = logging.getLogger("tradepro.web")

SETUP_TH = {
    "H2": "High 2: ย่อตัว 2 ขาในเทรนด์ขาขึ้นแล้วกลับขึ้น",
    "H1": "High 1: ย่อตัวขาแรกในเทรนด์ขาขึ้นที่แรงมาก",
    "BO_BULL": "Breakout: แท่งเขียวใหญ่ปิดทะลุกรอบ 20 วัน",
    "FAILED_BO": "Failed breakout: หลุดขอบล่างกรอบแล้วปิดกลับเข้ากรอบ",
    "L2": "Low 2: เด้ง 2 ขาในเทรนด์ขาลงแล้วกลับลง",
    "L1": "Low 1: เด้งขาแรกในเทรนด์ขาลงที่แรงมาก",
    "BO_BEAR": "Breakout ลง: แท่งแดงใหญ่ปิดหลุดกรอบ 20 วัน",
}
STATUS_TH = {"hold": "ถือต่อ", "watch": "เฝ้าระวัง", "sell": "ควรขาย"}
CONTEXT_TH = {"bull": "ขาขึ้น", "bear": "ขาลง", "range": "ไซด์เวย์"}
CURRENCY = {"set": "฿", "us": "$"}
SETUP_ORDER = {"H2": 0, "H1": 1, "BO_BULL": 2, "FAILED_BO": 3}


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

    def _run(self, market: str):
        try:
            cfg = market_cfg(market)
            tickers = list(WATCHLISTS[MARKETS[market].watchlist])
            tickers += [h["ticker"] for h in self.store.holdings() if h["market"] == market and h["ticker"] not in tickers]
            results, errors = [], []

            def one(t):
                df = self.prices.history(market, t)
                last = df.index[-1]
                return [s.as_dict() | {"last_close": round(float(df["close"].iloc[-1]), 4)}
                        for s in detect(df, t, cfg) if s.date == last and s.direction == "long"]

            with ThreadPoolExecutor(max_workers=4) as pool:
                for t, fut in [(t, pool.submit(one, t)) for t in tickers]:
                    try:
                        results += fut.result()
                    except Exception as e:  # keep scanning the rest
                        errors.append(f"{t}: {e}")
            results.sort(key=lambda r: (SETUP_ORDER.get(r["setup"], 9), -r["reward_r"]))
            self.store.save_scan(market, results, errors)
        except Exception:
            log.exception("scan %s failed", market)
        finally:
            with self._lock:
                self.running.discard(market)

    def autoscan_forever(self, every_hours: float):
        while True:
            for market in MARKETS:
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
        return {"STATUS_TH": STATUS_TH, "CONTEXT_TH": CONTEXT_TH, "SETUP_TH": SETUP_TH,
                "CURRENCY": CURRENCY, "MARKETS": MARKETS}

    def evaluate(h: dict) -> dict:
        row = dict(h)
        try:
            df = prices.history(h["market"], h["ticker"])
            a = advise(df, market_cfg(h["market"]))
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
            market, ticker = f["market"], f["ticker"].strip().upper()
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
        market = request.args.get("market", "set")
        if market not in MARKETS:
            abort(404)
        return render_template("scan.html", market=market, scan=store.latest_scan(market),
                               watchlist=WATCHLISTS[MARKETS[market].watchlist],
                               running=market in scanner.running, active="scan")

    @app.post("/scan/run")
    def scan_run():
        market = request.form.get("market", "set")
        if market in MARKETS:
            scanner.start(market)
        return redirect(url_for("scan_page", market=market))

    @app.get("/chart")
    def chart_lookup():
        market = request.args.get("market", "set")
        ticker = request.args.get("ticker", "").strip().upper()
        if market not in MARKETS or not ticker:
            return redirect(url_for("scan_page", market=market if market in MARKETS else "set"))
        return redirect(url_for("chart_page", market=market, ticker=ticker))

    @app.get("/chart/<market>/<ticker>")
    def chart_page(market, ticker):
        if market not in MARKETS:
            abort(404)
        return render_template("chart.html", market=market, ticker=ticker.upper(), active="")

    @app.get("/api/chart/<market>/<ticker>")
    def chart_data(market, ticker):
        if market not in MARKETS:
            abort(404)
        try:
            df = prices.history(market, ticker)
        except Exception as e:
            return jsonify(error=str(e)), 502
        cfg = market_cfg(market)
        full = add_features(df, cfg)
        hc, _, hpb = count_highs(full["high"].to_numpy())
        lc, _, lpb = count_highs(-full["low"].to_numpy())
        f = full.iloc[-250:]
        n0 = len(full) - len(f)
        day = lambda d: d.strftime("%Y-%m-%d")
        num = lambda v: None if v is None or not np.isfinite(v) else round(float(v), 4)
        sigs = [s for s in detect(df.iloc[-300:], ticker, cfg) if s.date >= f.index[0]]
        a = advise(df, cfg)
        held = [h for h in store.holdings() if h["market"] == market and h["ticker"] == ticker.upper()]
        L = cfg.range_lookback
        rng = full.iloc[-L - 1:-1]
        last = full.iloc[-1]
        latest = next((s for s in reversed(sigs) if s.date >= full.index[-3]), None)   # live in the last 3 bars
        bars = []
        for k, (d, r) in enumerate(zip(f.index, f.itertuples())):
            i = n0 + k
            # label the bar that completes a count (the H1 / H2 bar itself)
            count = (f"H{hc[i]}" if hpb[i] and hc[i] > hc[i - 1] else "") or \
                    (f"L{lc[i]}" if lpb[i] and lc[i] > lc[i - 1] else "")
            bars.append({"time": day(d), "ema": num(r.ema), "atr": num(r.atr), "context": r.context,
                         "body": num(r.body_ratio), "close_pos": num(r.close_pos),
                         "strong": bool(r.strong), "count": count})
        return jsonify(
            candles=[{"time": day(d), "open": r.open, "high": r.high, "low": r.low, "close": r.close}
                     for d, r in zip(f.index, f.itertuples())],
            ema=[{"time": day(d), "value": v} for d, v in f["ema"].items()],
            bars=bars,
            swings=[{"time": day(f.index[k]), "kind": kind, "price": num(p)} for k, kind, p in pivots(f)],
            signals=[{"time": day(s.date), "setup": s.setup, "direction": s.direction, "entry": s.entry,
                      "stop": s.stop, "target": s.target, "reward_r": round(s.reward_r, 2), "note": s.note}
                     for s in sigs],
            latest=None if latest is None else {
                "time": day(latest.date), "setup": latest.setup, "direction": latest.direction,
                "entry": latest.entry, "stop": latest.stop, "target": latest.target,
                "reward_r": round(latest.reward_r, 2), "note": latest.note},
            levels={"range_high": num(rng["high"].max()), "range_low": num(rng["low"].min()),
                    "range_mid": num((rng["high"].max() + rng["low"].min()) / 2), "range_bars": L,
                    "ema": num(last.ema), "atr": num(last.atr), "frac_above": num(last.frac_above),
                    "ema_slope_atr": num(last.ema_slope_atr), "strong": bool(last.strong)},
            advice={"status": a.status, "stop": a.stop, "resistance": a.resistance,
                    "context": a.context, "reasons": a.reasons},
            cost=held[0]["cost"] if held else None,
            shares=held[0]["shares"] if held else None,
        )

    return app
