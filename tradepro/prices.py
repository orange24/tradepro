"""Cached price history per market, shared by the web app."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import pandas as pd

from .data import make_source
from .markets import MARKETS

TTL_SECONDS = int(os.environ.get("TRADEPRO_PRICE_TTL", "900"))  # Yahoo quotes are delayed anyway


class PriceService:
    # Own cache folder: the web app fetches only recent years and must not overwrite the long
    # histories that `python -m tradepro download` keeps in data/cache for backtests.
    def __init__(self, source: str = "yahoo", cache_dir: str = "data/web-cache"):
        self.sources = {m.name: make_source(source, str(Path(cache_dir) / m.name), m.yahoo_suffix)
                        for m in MARKETS.values()}
        self.source = source
        self._cache: dict[tuple[str, str], tuple[float, pd.DataFrame]] = {}
        self._fx: tuple[float, float] | None = None
        self._lock = threading.Lock()

    def history(self, market: str, ticker: str, start: str = "2023-01-01", max_age: float | None = None) -> pd.DataFrame:
        """max_age: refetch if the cached copy is older than this many seconds (default TTL_SECONDS)."""
        key = (market, ticker.upper(), start)
        with self._lock:
            hit = self._cache.get(key)
        if hit and time.time() - hit[0] < (TTL_SECONDS if max_age is None else max_age):
            return hit[1]
        df = self.sources[market].get(ticker.upper(), start=start)
        if df.empty:
            raise ValueError(f"no price data for {ticker} ({market})")
        with self._lock:
            self._cache[key] = (time.time(), df)
        return df

    def usd_thb(self, max_age: float | None = None) -> float | None:
        """Baht per US dollar from Yahoo (THB=X); None if it cannot be fetched."""
        with self._lock:
            hit = self._fx
        if hit and time.time() - hit[0] < (TTL_SECONDS if max_age is None else max_age):
            return hit[1]
        if self.source != "yahoo":
            rate = 35.0                         # offline sources: a fixed rate so the page still works
        else:
            try:
                import yfinance as yf
                raw = yf.download("THB=X", period="5d", progress=False, auto_adjust=True, threads=False)
                rate = float(raw["Close"].dropna().iloc[-1].squeeze())
            except Exception:
                return hit[1] if hit else None
        with self._lock:
            self._fx = (time.time(), rate)
        return rate
