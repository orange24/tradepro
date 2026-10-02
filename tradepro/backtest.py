"""Simple bar-by-bar backtest of detected signals, measured in R (multiples of initial risk)."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .config import DEFAULT, Config
from .setups import Signal, detect
from .wave import cdc_action_zone


@dataclass
class Trade:
    ticker: str
    setup: str
    direction: str
    signal_date: pd.Timestamp
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    entry: float
    stop: float
    target: float
    exit: float
    exit_reason: str
    r: float


def simulate(df: pd.DataFrame, signals: list[Signal], cfg: Config = DEFAULT) -> list[Trade]:
    """Rules: the stop order is live only on the bar after the signal bar (cancelled otherwise).
    Gaps fill at the open. If stop and target are both touched in one bar, assume the stop
    (conservative). Exit at the close after max_hold bars. One position per ticker."""
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    dates = df.index
    pos = {d: i for i, d in enumerate(dates)}
    trades: list[Trade] = []
    busy_until = -1
    for s in sorted(signals, key=lambda s: s.date):
        i = pos.get(s.date)
        if i is None or i + 1 >= len(df) or i + 1 <= busy_until:
            continue
        j = i + 1
        long = s.direction == "long"
        if s.order == "open":
            fill = o[j]
        elif long and h[j] >= s.entry:
            fill = max(o[j], s.entry)
        elif not long and l[j] <= s.entry:
            fill = min(o[j], s.entry)
        else:
            continue
        # A gap past the target means the trade is already gone; skip it.
        if (long and fill >= s.target) or (not long and fill <= s.target):
            continue
        risk = (fill - s.stop) if long else (s.stop - fill)
        if risk <= 0:
            continue
        exit_px, reason, k = None, "time", j
        hold = s.max_hold or cfg.max_hold_bars
        last = len(df) - 1 if not hold else min(len(df) - 1, j + hold)
        for k in range(j, last + 1):
            first = k == j
            if long:
                if l[k] <= s.stop:
                    exit_px, reason = (s.stop if first else min(o[k], s.stop)), "stop"
                elif h[k] >= s.target:
                    exit_px, reason = (s.target if first else max(o[k], s.target)), "target"
            else:
                if h[k] >= s.stop:
                    exit_px, reason = (s.stop if first else max(o[k], s.stop)), "stop"
                elif l[k] <= s.target:
                    exit_px, reason = (s.target if first else min(o[k], s.target)), "target"
            if exit_px is not None:
                break
        if exit_px is None:
            exit_px, k = c[last], last
            reason = "time" if hold and last == j + hold else "open"
        pnl = (exit_px - fill) if long else (fill - exit_px)
        pnl -= fill * cfg.cost_pct / 100
        trades.append(Trade(s.ticker, s.setup, s.direction, s.date, dates[j], dates[k],
                            round(fill, 4), s.stop, s.target, round(exit_px, 4), reason, round(pnl / risk, 3)))
        busy_until = k
    return trades


def simulate_w3(df: pd.DataFrame, signals: list[Signal], cfg: Config = DEFAULT) -> list[Trade]:
    """W3 trades managed the ChalokeDotCom way (cfg.w3_*): buy at the open after the first green bar,
    stop on touch or on a close below it, then exit
      "target":  all at 161.8%          "thirds": a third each at 161.8 / 261.8 / 423.6%
      "cdc_red": all when CDC turns red  "half":   half at 161.8%, the rest when CDC turns red
    Exits on a close (stop on close, CDC red, last bar) fill at that close. One position per ticker."""
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    red = (cdc_action_zone(df)["cdc_zone"] == "red").to_numpy()
    dates, n = df.index, len(df)
    pos = {d: i for i, d in enumerate(dates)}
    mode = cfg.w3_exit
    trades, busy_until = [], -1
    for s in sorted(signals, key=lambda s: s.date):
        i = pos.get(s.date)
        if i is None or i + 1 >= n or i + 1 <= busy_until:
            continue
        j = i + 1
        fill = o[j]
        risk = fill - s.stop
        if risk <= 0 or fill >= s.target:
            continue
        lv = s.levels or {}
        targets = {"target": [(1.0, s.target)], "half": [(0.5, s.target)], "cdc_red": [],
                   "thirds": [(1 / 3, s.target), (1 / 3, lv.get("t2", s.target)), (1 / 3, lv.get("t3", s.target))]}[mode]
        hold = s.max_hold or cfg.max_hold_bars
        last = n - 1 if not hold else min(n - 1, j + hold)
        parts, left, reason, k = [], 1.0, "open", last          # parts: (fraction, exit price)

        def take_targets(k):
            nonlocal left
            while targets and h[k] >= targets[0][1]:
                fr, px = targets.pop(0)
                parts.append((fr, max(o[k], px) if k > j else px)); left -= fr

        for k in range(j, last + 1):
            if cfg.w3_stop_on_close:
                take_targets(k)                 # a limit order at the target fills during the day
                if left <= 1e-9:
                    reason = "target"; break
                if c[k] < s.stop:
                    parts.append((left, c[k])); left, reason = 0, "stop"; break
            else:
                if l[k] <= s.stop:              # touched: assume the stop came first (conservative)
                    parts.append((left, s.stop if k == j else min(o[k], s.stop))); left, reason = 0, "stop"; break
                take_targets(k)
                if left <= 1e-9:
                    reason = "target"; break
            if mode in ("cdc_red", "half") and red[k]:
                parts.append((left, c[k])); left, reason = 0, "cdc_red"; break
        if left > 1e-9:
            parts.append((left, c[last]))
            reason = "time" if hold and last == j + hold else reason
        exit_px = sum(fr * px for fr, px in parts)
        pnl = exit_px - fill - fill * cfg.cost_pct / 100
        trades.append(Trade(s.ticker, s.setup, s.direction, s.date, dates[j], dates[k], round(fill, 4), s.stop,
                            s.target, round(exit_px, 4), reason, round(pnl / risk, 3)))
        busy_until = k
    return trades


def run(data: dict[str, pd.DataFrame], cfg: Config = DEFAULT) -> pd.DataFrame:
    rows = []
    for ticker, df in data.items():
        rows += [t.__dict__ for t in simulate_w3(df, detect(df, ticker, cfg), cfg)]
    return pd.DataFrame(rows)


def summarize(trades: pd.DataFrame) -> pd.DataFrame:
    """Per-setup stats. Expectancy (avg R) > 0 means the trader's equation is positive (RISK-2)."""
    if trades.empty:
        return pd.DataFrame()
    closed = trades[trades["exit_reason"] != "open"]

    def stats(g):
        wins, losses = g.loc[g.r > 0, "r"], g.loc[g.r <= 0, "r"]
        return pd.Series({
            "trades": len(g),
            "win_rate": round((g.r > 0).mean() * 100, 1),
            "avg_r": round(g.r.mean(), 3),
            "total_r": round(g.r.sum(), 2),
            "profit_factor": round(wins.sum() / -losses.sum(), 2) if losses.sum() < 0 else float("inf"),
            "hit_target_%": round((g.exit_reason == "target").mean() * 100, 1),
        })

    out = closed.groupby("setup").apply(stats, include_groups=False)
    out.loc["ALL"] = stats(closed)
    return out
