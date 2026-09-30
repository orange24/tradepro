"""Rule-based Brooks setups. Each signal is a stop order for the bar after the signal bar."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from .config import DEFAULT, Config
from .indicators import BEAR, BULL, RANGE, add_features, is_good_bear_signal, is_good_bull_signal
from .ticks import round_to_tick, set_tick


@dataclass
class Signal:
    ticker: str
    date: pd.Timestamp        # signal bar date; order is live on the next bar
    setup: str
    direction: str            # "long" or "short"
    entry: float              # stop order price
    stop: float
    target: float
    context: str
    note: str = ""

    @property
    def risk(self) -> float:
        return abs(self.entry - self.stop)

    @property
    def reward_r(self) -> float:
        return abs(self.target - self.entry) / self.risk if self.risk else 0.0

    def as_dict(self) -> dict:
        d = asdict(self)
        d["risk"] = round(self.risk, 4)
        d["reward_r"] = round(self.reward_r, 2)
        return d


def count_highs(high: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Brooks High 1 / High 2 bar counting (HL-1, HL-2, HL-8).

    Returns per bar:
      count  - H-counts completed in the current pullback (0, 1, 2, ...)
      armed  - pullback is moving down again, so the next bar above this bar's high is the next H
      in_pb  - bar is inside a pullback (below the leg high)
    For Low 1 / Low 2 pass -low.
    """
    n = len(high)
    count = np.zeros(n, dtype=int)
    armed = np.zeros(n, dtype=bool)
    in_pb = np.zeros(n, dtype=bool)
    if n == 0:
        return count, armed, in_pb
    leg_high = high[0]
    c, a = 0, False
    for i in range(1, n):
        if high[i] > leg_high:          # new trend high: reset the count (HL-8)
            leg_high, c, a = high[i], 0, False
        else:
            in_pb[i] = True
            if high[i] > high[i - 1] and a:
                c += 1                  # bar went above the prior bar's high: H1, H2, ...
                a = False
            elif high[i] <= high[i - 1]:
                a = True                # pullback resumed (lower or equal high)
        count[i], armed[i] = c, a
    return count, armed, in_pb


def _long(ticker, row, setup, target, context, note):
    entry = round_to_tick(row.high + set_tick(row.high), up=True)    # HL-7: 1 tick above
    stop = round_to_tick(row.low - set_tick(row.low), up=False)       # RISK-1: 1 tick below
    return Signal(ticker, row.Index, setup, "long", entry, stop, target(entry, entry - stop), context, note)


def _short(ticker, row, setup, target, context, note):
    entry = round_to_tick(row.low - set_tick(row.low), up=False)
    stop = round_to_tick(row.high + set_tick(row.high), up=True)
    return Signal(ticker, row.Index, setup, "short", entry, stop, target(entry, stop - entry), context, note)


def detect(df: pd.DataFrame, ticker: str = "", cfg: Config = DEFAULT) -> list[Signal]:
    """Scan every bar of df and return all setups found (signal bar = that bar)."""
    f = add_features(df, cfg)
    hc, harmed, hpb = count_highs(f["high"].to_numpy())
    lc, larmed, lpb = count_highs(-f["low"].to_numpy())
    L = cfg.range_lookback
    prior_hi = f["high"].shift(1).rolling(L, min_periods=L).max().to_numpy()
    prior_lo = f["low"].shift(1).rolling(L, min_periods=L).min().to_numpy()
    prev_context = f["context"].shift(1).to_numpy()

    signals: list[Signal] = []
    warmup = max(cfg.context_window, cfg.ema_period, L) + cfg.slope_bars
    for i, row in enumerate(f.itertuples()):
        if i < warmup or not np.isfinite(row.atr):
            continue
        ctx = row.context
        long_r = lambda e, r: round(e + cfg.reward_r * r, 4)     # RISK-3
        short_r = lambda e, r: round(e - cfg.reward_r * r, 4)
        near_ema = row.low <= row.ema + 0.25 * row.atr and row.high >= row.ema - 0.25 * row.atr

        # H2 / H1 pullbacks in a bull trend (HL-3, HL-4)
        if ctx == BULL and hpb[i] and harmed[i] and is_good_bull_signal(row, cfg):
            if hc[i] == 1:
                signals.append(_long(ticker, row, "H2", long_r, ctx, "EMA pullback" if near_ema else ""))
            elif hc[i] == 0 and row.strong:
                signals.append(_long(ticker, row, "H1", long_r, ctx, "strong trend"))

        # L2 / L1 in a bear trend (HL-6)
        if ctx == BEAR and lpb[i] and larmed[i] and is_good_bear_signal(row, cfg):
            if lc[i] == 1:
                signals.append(_short(ticker, row, "L2", short_r, ctx, "EMA pullback" if near_ema else ""))
            elif lc[i] == 0 and row.strong:
                signals.append(_short(ticker, row, "L1", short_r, ctx, "strong trend"))

        # Strong breakout bars (BO-1) with a measured-move target (BO-2)
        hi, lo = prior_hi[i], prior_lo[i]
        if np.isfinite(hi) and np.isfinite(lo):
            height = hi - lo
            big = row.range >= cfg.bo_min_range_atr * row.atr and row.body_ratio >= cfg.trend_bar_body
            if big and row.close > hi and row.close_pos >= cfg.bo_close_pos:
                mm = hi + height
                signals.append(_long(ticker, row, "BO_BULL", lambda e, r: round(max(mm, e + cfg.min_reward_r * r), 4),
                                     ctx, f"range {lo:.2f}-{hi:.2f}"))
            elif big and row.close < lo and row.close_pos <= 1 - cfg.bo_close_pos:
                mm = lo - height
                signals.append(_short(ticker, row, "BO_BEAR", lambda e, r: round(min(mm, e - cfg.min_reward_r * r), 4),
                                      ctx, f"range {lo:.2f}-{hi:.2f}"))

            # Failed breakouts of a trading range (BO-3, CTX-6); target the middle of the range
            mid = (hi + lo) / 2
            if prev_context[i] == RANGE:
                if row.low < lo and row.close > lo and is_good_bull_signal(row, cfg):
                    s = _long(ticker, row, "FAILED_BO", lambda e, r: round(mid, 4), ctx, "failed bear breakout")
                    if s.target > s.entry and s.reward_r >= cfg.min_reward_r:
                        signals.append(s)
                if row.high > hi and row.close < hi and is_good_bear_signal(row, cfg):
                    s = _short(ticker, row, "FAILED_BO", lambda e, r: round(mid, 4), ctx, "failed bull breakout")
                    if s.target < s.entry and s.reward_r >= cfg.min_reward_r:
                        signals.append(s)
    if cfg.long_only:
        signals = [s for s in signals if s.direction == "long"]
    return signals
