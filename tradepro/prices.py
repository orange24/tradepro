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
    def __init__(self, source: str = "yahoo", cache_dir: str = "data/cache"):
        self.sources = {m.name: make_source(source, str(Path(cache_dir) / m.name), m.yahoo_suffix)
                        for m in MARKETS.values()}
        self._cache: dict[tuple[str, str], tuple[float, pd.DataFrame]] = {}
        self._lock = threading.Lock()

    def history(self, market: str, ticker: str, start: str = "2023-01-01") -> pd.DataFrame:
        key = (market, ticker.upper())
        with self._lock:
            hit = self._cache.get(key)
        if hit and time.time() - hit[0] < TTL_SECONDS:
            return hit[1]
        df = self.sources[market].get(ticker.upper(), start=start)
        if df.empty:
            raise ValueError(f"no price data for {ticker} ({market})")
        with self._lock:
            self._cache[key] = (time.time(), df)
        return df
