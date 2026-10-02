"""Tunable parameters for the ChalokeDotCom rules (W3-* in docs/chaloke_wave3.md)."""

from dataclasses import dataclass


@dataclass
class Config:
    atr_period: int = 14
    big_body: float = 0.6             # body / range of a "big white" / "big black" bar (W3-7)

    # Wave 3 + CDC Action Zone (W3-1..W3-8)
    w3_pivot_bars: int = 5            # swing high = highest of 5 bars each side
    w3_min_atr: float = 3.0           # wave 1 must rise at least this many ATRs
    w3_max_wave1_bars: int = 60       # look this far back from the wave 1 top for its base
    w3_max_wave2_bars: int = 60       # wave 2 (top to first green) must finish within this many bars
    w3_retrace_min: float = 0.618
    w3_retrace_max: float = 0.942
    w3_max_bars_after_low: int = 20   # first green must come within this many bars of the wave 2 low
    w3_max_hold_bars: int = 120       # time exit in the backtest
    w3_min_rr: float = 2.0            # W3-6: reward/risk to the 161.8% target, from the signal close
    w3_recent_bars: int = 5           # scan keeps a W3 for this many days if it has not run away (W3-8)

    max_hold_bars: int = 120          # backtest time exit for signals without their own max_hold
    cost_pct: float = 0.2             # round-trip commission + slippage, percent of price
    market: str = "set"               # "set" or "us": tick sizes (see markets.py)


DEFAULT = Config()
