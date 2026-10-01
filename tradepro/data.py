"""Data sources. Every source returns a DataFrame indexed by date with columns
open, high, low, close, volume. Swap the source to change market or provider."""

from __future__ import annotations

from abc import ABC, abstractmethod
import zlib
from pathlib import Path

import numpy as np
import pandas as pd

COLUMNS = ["open", "high", "low", "close", "volume"]


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)
    df = df[[c for c in COLUMNS if c in df.columns]].dropna(subset=["open", "high", "low", "close"])
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df.index.name = "date"
    return df.sort_index()


class DataSource(ABC):
    @abstractmethod
    def get(self, ticker: str, start: str | None = None, end: str | None = None) -> pd.DataFrame:
        ...


class YahooSource(DataSource):
    """Daily bars from Yahoo Finance via yfinance. SET tickers use the .BK suffix."""

    def __init__(self, suffix: str = ".BK", cache_dir: str | None = "data/cache"):
        self.suffix = suffix
        self.cache_dir = Path(cache_dir) if cache_dir else None

    def get(self, ticker, start=None, end=None):
        import yfinance as yf

        symbol = ticker if ticker.endswith(self.suffix) or not self.suffix else ticker + self.suffix
        raw = yf.download(symbol, start=start or "2010-01-01", end=end, progress=False,
                          auto_adjust=True, threads=False)
        df = _normalize(raw)
        if self.cache_dir is not None and not df.empty:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            df.to_csv(self.cache_dir / f"{ticker}.csv")
        return df


class CSVSource(DataSource):
    """Reads <dir>/<TICKER>.csv with a date column and OHLCV columns (any case)."""

    def __init__(self, directory: str = "data/cache"):
        self.directory = Path(directory)

    def get(self, ticker, start=None, end=None):
        path = self.directory / f"{ticker}.csv"
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        df = _normalize(df)
        return df.loc[start:end] if (start or end) else df


class SyntheticSource(DataSource):
    """Random regime-switching prices, for demos and tests when no market data is reachable."""

    def __init__(self, bars: int = 750, seed: int = 0):
        self.bars = bars
        self.seed = seed

    def get(self, ticker, start=None, end=None):
        rng = np.random.default_rng(zlib.crc32(f"{ticker}:{self.seed}".encode()))
        n = self.bars
        drift = np.zeros(n)
        i = 0
        while i < n:
            length = int(rng.integers(20, 80))
            drift[i:i + length] = rng.choice([-0.004, 0.0, 0.004])
            i += length
        rets = drift + rng.normal(0, 0.015, n)
        close = 50 * np.exp(np.cumsum(rets))
        open_ = np.r_[close[0], close[:-1]] * (1 + rng.normal(0, 0.004, n))
        spread = np.abs(rng.normal(0, 0.01, n)) * close
        high = np.maximum(open_, close) + spread * rng.random(n)
        low = np.minimum(open_, close) - spread * rng.random(n)
        idx = pd.bdate_range(end=pd.Timestamp("2026-09-29"), periods=n, name="date")
        return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                             "volume": rng.integers(1e5, 1e7, n)}, index=idx)


def make_source(name: str, csv_dir: str = "data/cache", yahoo_suffix: str = ".BK") -> DataSource:
    """csv_dir is both the CSV source's folder and the Yahoo download cache."""
    name = name.lower()
    if name in ("yahoo", "yf", "yfinance"):
        return YahooSource(suffix=yahoo_suffix, cache_dir=csv_dir)
    if name == "csv":
        return CSVSource(csv_dir)
    if name == "synthetic":
        return SyntheticSource()
    raise ValueError(f"unknown data source: {name}")


TIMEFRAMES = {"D": None, "W": "W-FRI", "M": "ME", "Y": "YE"}


def resample(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    """Daily bars -> weekly / monthly / yearly bars, each dated by its first trading day."""
    rule = TIMEFRAMES[tf]
    if rule is None:
        return df
    g = df.assign(first_day=df.index).groupby(pd.Grouper(freq=rule))
    out = g.agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
                volume=("volume", "sum"), first_day=("first_day", "first")).dropna(subset=["close"])
    out.index = pd.DatetimeIndex(out.pop("first_day"), name="date")
    return out
