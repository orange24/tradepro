"""Find setups on the latest bars across a list of tickers."""

from __future__ import annotations

import pandas as pd

from .config import DEFAULT, Config
from .data import DataSource
from .setups import detect


def scan(source: DataSource, tickers: list[str], recent_bars: int = 1, start: str | None = None,
         cfg: Config = DEFAULT, on_error=None) -> pd.DataFrame:
    """Signals whose signal bar is among the last `recent_bars` bars of each ticker.
    With recent_bars=1 these are orders to place for the next session."""
    rows = []
    for t in tickers:
        try:
            df = source.get(t, start=start)
        except Exception as e:  # one bad ticker should not stop the scan
            if on_error:
                on_error(t, e)
            continue
        if len(df) < 60:
            if on_error:
                on_error(t, ValueError(f"only {len(df)} bars"))
            continue
        recent = set(df.index[-recent_bars:])
        rows += [s.as_dict() | {"last_close": round(df["close"].iloc[-1], 4)}
                 for s in detect(df, t, cfg) if s.date in recent]
    cols = ["ticker", "date", "setup", "direction", "entry", "stop", "target", "risk", "reward_r",
            "last_close", "context", "note"]
    return pd.DataFrame(rows, columns=cols)
