"""Dividend stocks: yield, how many years in a row a company has paid, dividend growth and how well
earnings / free cash flow cover the payout.

`profile()` is pure (dividend history + today's price -> numbers) so it can be tested offline;
`fetch()` gets the dividend history, price and fundamentals from Yahoo Finance.
"""

from __future__ import annotations

import json
import threading
import time
import zlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .markets import MARKETS

CACHE_HOURS = 20          # dividends change a few times a year; refetch about once a day


@dataclass(frozen=True)
class DivCriteria:
    min_yield: float        # % trailing 12-month yield, special dividends left out
    min_years: int          # paid a dividend every calendar year for at least this many years
    max_payout: float       # % of earnings paid out (skipped when Yahoo has no figure)


CRITERIA = {
    "set": DivCriteria(min_yield=4.0, min_years=5, max_payout=100.0),
    "us": DivCriteria(min_yield=2.5, min_years=10, max_payout=90.0),
}


def _annual(divs: pd.Series) -> pd.Series:
    return divs.groupby(divs.index.year).sum()


def special_mask(divs: pd.Series) -> pd.Series:
    """True for one-off special dividends: a payment more than 2.5x the median of the 8 before it."""
    v = divs.to_numpy()
    out = np.zeros(len(v), bool)
    for i in range(3, len(v)):
        med = np.median(v[max(0, i - 8):i])
        out[i] = med > 0 and v[i] > 2.5 * med
    return pd.Series(out, index=divs.index)


def profile(divs: pd.Series, price: float, today: pd.Timestamp) -> dict:
    """Numbers that describe a dividend payer. divs: amount per share indexed by ex-dividend date."""
    divs = divs[divs > 0].sort_index()
    idx = pd.DatetimeIndex(divs.index)
    divs.index = idx.tz_localize(None) if idx.tz is not None else idx
    today = pd.Timestamp(today).tz_localize(None) if pd.Timestamp(today).tz is not None else pd.Timestamp(today)
    out = {"price": round(float(price), 4), "ttm_dps": 0.0, "yield": 0.0, "yield_all": 0.0, "avg5_yield": 0.0,
           "years": 0, "no_cut": 0, "growth5": None, "special": False, "last_ex": None, "payments": 0}
    if divs.empty or not price > 0:
        return out
    special = special_mask(divs)
    last12 = divs[divs.index > today - pd.Timedelta(days=365)]
    normal12 = last12[~special.loc[last12.index]]
    out["ttm_dps"] = round(float(normal12.sum()), 4)
    out["yield"] = round(float(normal12.sum()) / price * 100, 2)
    out["yield_all"] = round(float(last12.sum()) / price * 100, 2)
    out["special"] = bool(special.loc[last12.index].any())
    out["payments"] = int(len(last12))
    out["last_ex"] = divs.index[-1].strftime("%Y-%m-%d")

    annual = _annual(divs[~special])
    # count back from last full year; this year counts too once it has paid
    year = today.year if today.year in annual.index else today.year - 1
    streak = 0
    while year - streak in annual.index:
        streak += 1
    out["years"] = streak
    full = annual[annual.index < today.year]
    if len(full) >= 5:
        out["avg5_yield"] = round(float(full.iloc[-5:].mean()) / price * 100, 2)
    if len(full) >= 6 and full.iloc[-6] > 0:
        out["growth5"] = round(((full.iloc[-1] / full.iloc[-6]) ** (1 / 5) - 1) * 100, 1)
    # years in a row the yearly dividend was not cut by more than 10%
    nc, vals = 0, full.to_numpy()
    for i in range(len(vals) - 1, 0, -1):
        if full.index[i] - full.index[i - 1] != 1 or vals[i] < 0.9 * vals[i - 1]:
            break
        nc += 1
    out["no_cut"] = nc
    return out


def passes(p: dict, c: DivCriteria) -> list[str]:
    """Reasons a stock fails the criteria (empty = passes)."""
    why = []
    if p["yield"] < c.min_yield:
        why.append(f"ปันผล {p['yield']:.1f}% < {c.min_yield:g}%")
    if p["years"] < c.min_years:
        why.append(f"จ่ายต่อเนื่อง {p['years']} ปี < {c.min_years}")
    # REITs / property funds pay out cash flow, not accounting profit, so payout vs earnings means little
    if p.get("payout") is not None and p["payout"] > c.max_payout and not p.get("reit"):
        why.append(f"จ่ายเกินกำไร ({p['payout']:.0f}%)")
    return why


def _synthetic(ticker: str) -> tuple[pd.Series, float]:
    """Deterministic fake dividend history for offline tests and demos."""
    rng = np.random.default_rng(zlib.crc32(ticker.encode()))
    price = float(rng.uniform(10, 200))
    years = int(rng.integers(0, 16))
    base = price * rng.uniform(0.01, 0.07) / 2
    dates, amounts = [], []
    for y in range(2026 - years, 2027):
        for m in (3, 9):
            if y == 2026 and m == 9 and rng.random() < 0.5:
                continue
            dates.append(pd.Timestamp(y, m, 10))
            amounts.append(round(base * (1 + rng.normal(0.03, 0.08)) ** (y - 2010), 4))
    return pd.Series(amounts, index=pd.DatetimeIndex(dates), dtype=float), price


_INFO_LOCK = threading.Lock()


def _info(t) -> dict:
    """Yahoo fundamentals. One request at a time: parallel calls trip Yahoo's 401 "Invalid Crumb"."""
    for attempt in range(3):
        with _INFO_LOCK:
            try:
                i = t.info or {}
            except Exception:
                i = {}
        if i.get("quoteType") or i.get("shortName"):
            return i
        time.sleep(1 + attempt)
    return {}


def fetch(market: str, ticker: str, source: str = "yahoo", cache_dir: str | None = "data/web-cache/dividends") -> dict:
    """Dividend history + price + fundamentals for one stock, as profile() plus payout / FCF cover / next XD."""
    path = Path(cache_dir) / f"{market}_{ticker}.json" if cache_dir and source == "yahoo" else None
    if path and path.exists() and time.time() - path.stat().st_mtime < CACHE_HOURS * 3600:
        return json.loads(path.read_text())
    today = pd.Timestamp.now().normalize()
    if source != "yahoo":
        divs, price = _synthetic(ticker)
        p = profile(divs, price, pd.Timestamp("2026-10-01"))
        rng = np.random.default_rng(zlib.crc32(ticker.encode()) + 1)
        p |= {"payout": round(float(rng.uniform(20, 120)), 1), "fcf_cover": round(float(rng.uniform(0.5, 3)), 2),
              "next_xd": None, "value": 5e7}
        return p
    import yfinance as yf

    t = yf.Ticker(ticker + MARKETS[market].yahoo_suffix)
    h = t.history(period="15y", auto_adjust=False, actions=True)
    if h.empty:
        raise ValueError(f"no data for {ticker}")
    h.index = h.index.tz_localize(None)
    price = float(h["Close"].dropna().iloc[-1])
    p = profile(h.get("Dividends", pd.Series(dtype=float)), price, today)
    p["value"] = float((h["Close"] * h["Volume"]).iloc[-20:].mean())      # average daily traded value
    p |= {"payout": None, "fcf_cover": None, "next_xd": None}
    if p["yield"] > 0:
        i = _info(t)
        if i.get("payoutRatio"):
            p["payout"] = round(i["payoutRatio"] * 100, 1)
        same_ccy = (i.get("financialCurrency") or i.get("currency")) == i.get("currency")
        shares = i.get("sharesOutstanding") or (i.get("marketCap") or 0) / price
        if same_ccy and i.get("freeCashflow") and shares and p["ttm_dps"]:
            p["fcf_cover"] = round(i["freeCashflow"] / (shares * p["ttm_dps"]), 2)
        xd = i.get("exDividendDate")
        if xd and pd.Timestamp(xd, unit="s") >= today:
            p["next_xd"] = pd.Timestamp(xd, unit="s").strftime("%Y-%m-%d")
        p["name"] = i.get("shortName") or i.get("longName")
        p["sector"] = i.get("sector")
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(p, ensure_ascii=False))
    return p
