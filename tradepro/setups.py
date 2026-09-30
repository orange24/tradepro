"""Rule-based Brooks setups. Each signal is a stop order for the bar after the signal bar."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from .config import DEFAULT, Config
from .indicators import BEAR, BULL, RANGE, add_features, is_good_bear_signal, is_good_bull_signal
from .ticks import round_to_tick, tick_size


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


def count_highs(high: np.ndarray, reset: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Brooks High 1 / High 2 bar counting (HL-1, HL-2, HL-8).

    reset marks strong bull breakout bars: they end the pullback and start a new leg,
    so the count starts again from that bar (HL-8).

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
        if high[i] > leg_high or (reset is not None and reset[i]):   # new trend high or strong breakout (HL-8)
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


def _long(ticker, row, setup, target, context, note, m):
    entry = round_to_tick(row.high + tick_size(row.high, m), up=True, market=m)   # HL-7: 1 tick above
    stop = round_to_tick(row.low - tick_size(row.low, m), up=False, market=m)     # RISK-1: 1 tick below
    return Signal(ticker, row.Index, setup, "long", entry, stop, target(entry, entry - stop), context, note)


def _short(ticker, row, setup, target, context, note, m):
    entry = round_to_tick(row.low - tick_size(row.low, m), up=False, market=m)
    stop = round_to_tick(row.high + tick_size(row.high, m), up=True, market=m)
    return Signal(ticker, row.Index, setup, "short", entry, stop, target(entry, stop - entry), context, note)


def detect(df: pd.DataFrame, ticker: str = "", cfg: Config = DEFAULT) -> list[Signal]:
    """Scan every bar of df and return all setups found (signal bar = that bar)."""
    f = add_features(df, cfg)
    big = ((f["range"] >= cfg.bo_min_range_atr * f["atr"]) & (f["body_ratio"] >= cfg.trend_bar_body)).to_numpy()
    strong_bull = big & (f["close"] > f["open"]).to_numpy() & (f["close_pos"] >= cfg.bo_close_pos).to_numpy()
    strong_bear = big & (f["close"] < f["open"]).to_numpy() & (f["close_pos"] <= 1 - cfg.bo_close_pos).to_numpy()
    # HL-8: a strong bar that also closes beyond the last few bars' extremes breaks out of the pullback
    K = cfg.pb_breakout_bars
    pb_break_up = strong_bull & (f["close"] > f["high"].shift(1).rolling(K, min_periods=1).max()).to_numpy()
    pb_break_down = strong_bear & (f["close"] < f["low"].shift(1).rolling(K, min_periods=1).min()).to_numpy()
    reset_up, reset_down = (pb_break_up, pb_break_down) if cfg.pb_reset_on_breakout else (None, None)
    hc, harmed, hpb = count_highs(f["high"].to_numpy(), reset_up)
    lc, larmed, lpb = count_highs(-f["low"].to_numpy(), reset_down)
    L = cfg.range_lookback
    prior_hi = f["high"].shift(1).rolling(L, min_periods=L).max().to_numpy()
    prior_lo = f["low"].shift(1).rolling(L, min_periods=L).min().to_numpy()
    close = f["close"].to_numpy()
    bo_up = strong_bull & (close > prior_hi)      # BO-1: strong bull bar closing above the range
    bo_down = strong_bear & (close < prior_lo)
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
                signals.append(_long(ticker, row, "H2", long_r, ctx, "EMA pullback" if near_ema else "", cfg.market))
            elif hc[i] == 0 and row.strong:
                signals.append(_long(ticker, row, "H1", long_r, ctx, "strong trend", cfg.market))

        # L2 / L1 in a bear trend (HL-6)
        if ctx == BEAR and lpb[i] and larmed[i] and is_good_bear_signal(row, cfg):
            if lc[i] == 1:
                signals.append(_short(ticker, row, "L2", short_r, ctx, "EMA pullback" if near_ema else "", cfg.market))
            elif lc[i] == 0 and row.strong:
                signals.append(_short(ticker, row, "L1", short_r, ctx, "strong trend", cfg.market))

        # Breakouts (BO-1) with a measured-move target from the range height (BO-2).
        # With bo_follow_through the signal bar is the bar after the breakout bar: it must close
        # near its high and leave a gap above the breakout point (BO-6).
        hi, lo = prior_hi[i], prior_lo[i]
        j = i - 1 if cfg.bo_follow_through else i
        if cfg.bo_follow_through:
            ft_up = bo_up[j] and row.close > row.open and row.close_pos >= cfg.bo_close_pos and row.low > prior_hi[j]
            ft_down = bo_down[j] and row.close < row.open and row.close_pos <= 1 - cfg.bo_close_pos and row.high < prior_lo[j]
        else:
            ft_up, ft_down = bo_up[i], bo_down[i]
        if ft_up or ft_down:
            bhi, blo = prior_hi[j], prior_lo[j]
            height = bhi - blo
            if ft_up:
                mm = bhi + height
                signals.append(_long(ticker, row, "BO_BULL", lambda e, r: round(max(mm, e + cfg.min_reward_r * r), 4),
                                     ctx, f"range {blo:.2f}-{bhi:.2f}", cfg.market))
            else:
                mm = blo - height
                signals.append(_short(ticker, row, "BO_BEAR", lambda e, r: round(min(mm, e - cfg.min_reward_r * r), 4),
                                      ctx, f"range {blo:.2f}-{bhi:.2f}", cfg.market))

        if np.isfinite(hi) and np.isfinite(lo):
            # Failed breakouts of a trading range (BO-3, CTX-6); target the middle of the range
            mid = (hi + lo) / 2
            if prev_context[i] == RANGE:
                if row.low < lo and row.close > lo and is_good_bull_signal(row, cfg):
                    s = _long(ticker, row, "FAILED_BO", lambda e, r: round(mid, 4), ctx, "failed bear breakout", cfg.market)
                    if s.target > s.entry and s.reward_r >= cfg.min_reward_r:
                        signals.append(s)
                if row.high > hi and row.close < hi and is_good_bear_signal(row, cfg):
                    s = _short(ticker, row, "FAILED_BO", lambda e, r: round(mid, 4), ctx, "failed bull breakout", cfg.market)
                    if s.target < s.entry and s.reward_r >= cfg.min_reward_r:
                        signals.append(s)
    if cfg.long_only:
        signals = [s for s in signals if s.direction == "long"]
    return signals
