"""Bar anatomy and ATR used by the ChalokeDotCom rules (big white / big black bars, ATR spikes)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Config


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def atr(df: pd.DataFrame, period: int) -> pd.Series:
    prev_close = df["close"].shift()
    tr = pd.concat([df["high"] - df["low"], (df["high"] - prev_close).abs(),
                    (df["low"] - prev_close).abs()], axis=1).max(axis=1)
    return tr.rolling(period, min_periods=1).mean()


def add_features(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    out = df.copy()
    rng = (out["high"] - out["low"]).replace(0, np.nan)
    out["range"] = out["high"] - out["low"]
    out["body_ratio"] = ((out["close"] - out["open"]).abs() / rng).fillna(0)
    out["close_pos"] = ((out["close"] - out["low"]) / rng).fillna(0.5)  # 0 = at low, 1 = at high
    out["atr"] = atr(out, cfg.atr_period)
    return out
