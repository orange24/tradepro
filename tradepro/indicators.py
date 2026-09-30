"""Bar features, EMA, ATR and market context (trend vs trading range)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Config

BULL, BEAR, RANGE = "bull", "bear", "range"


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def atr(df: pd.DataFrame, period: int) -> pd.Series:
    prev_close = df["close"].shift()
    tr = pd.concat([df["high"] - df["low"], (df["high"] - prev_close).abs(),
                    (df["low"] - prev_close).abs()], axis=1).max(axis=1)
    return tr.rolling(period, min_periods=1).mean()


def add_features(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Add bar anatomy (BAR-*) and context (CTX-*) columns."""
    out = df.copy()
    rng = (out["high"] - out["low"]).replace(0, np.nan)
    out["range"] = out["high"] - out["low"]
    out["body_ratio"] = ((out["close"] - out["open"]).abs() / rng).fillna(0)
    out["close_pos"] = ((out["close"] - out["low"]) / rng).fillna(0.5)  # 0 = at low, 1 = at high
    out["ema"] = ema(out["close"], cfg.ema_period)
    out["atr"] = atr(out, cfg.atr_period)

    w = cfg.context_window
    above = (out["close"] > out["ema"]).astype(float)
    out["frac_above"] = above.rolling(w, min_periods=w).mean()
    out["ema_slope_atr"] = (out["ema"] - out["ema"].shift(cfg.slope_bars)) / out["atr"]

    bull = (out["frac_above"] >= cfg.trend_frac) & (out["ema_slope_atr"] >= cfg.min_slope_atr)
    bear = (out["frac_above"] <= 1 - cfg.trend_frac) & (out["ema_slope_atr"] <= -cfg.min_slope_atr)
    out["context"] = np.select([bull, bear], [BULL, BEAR], RANGE)
    out["strong"] = (
        (bull & (out["frac_above"] >= cfg.strong_trend_frac) & (out["ema_slope_atr"] >= cfg.strong_slope_atr))
        | (bear & (out["frac_above"] <= 1 - cfg.strong_trend_frac) & (out["ema_slope_atr"] <= -cfg.strong_slope_atr))
    )
    return out


def is_good_bull_signal(row, cfg: Config) -> bool:
    """BAR-3 / BAR-5: bull close in the upper part of the bar, not oversized."""
    return (
        row.close >= row.open
        and row.close_pos >= cfg.signal_close_pos
        and row.range <= cfg.max_signal_bar_atr * row.atr
        and row.range > 0
    )


def is_good_bear_signal(row, cfg: Config) -> bool:
    """BAR-4 / BAR-5."""
    return (
        row.close <= row.open
        and row.close_pos <= 1 - cfg.signal_close_pos
        and row.range <= cfg.max_signal_bar_atr * row.atr
        and row.range > 0
    )
