"""Tunable parameters. Rule codes (CTX-1, BAR-3, ...) refer to docs/brooks_knowledge.md."""

from dataclasses import dataclass


@dataclass
class Config:
    # Context (CTX-2..CTX-4)
    ema_period: int = 20
    context_window: int = 20          # bars used to judge trend vs range
    trend_frac: float = 0.70          # share of closes on one side of the EMA for a trend
    strong_trend_frac: float = 0.85   # ... for a strong trend (H1/L1 allowed, HL-4)
    slope_bars: int = 5               # EMA slope measured over this many bars
    min_slope_atr: float = 0.15       # EMA move over slope_bars, in ATRs, for a trend
    strong_slope_atr: float = 0.6
    atr_period: int = 14

    pb_reset_on_breakout: bool = False  # HL-8: also reset the H/L count on a strong breakout bar (backtest: worse)
    pb_breakout_bars: int = 5         # ... a strong bar closing above this many bars' highs

    # Bars (BAR-1..BAR-5)
    trend_bar_body: float = 0.6       # body / range for a trend bar
    doji_body: float = 0.25
    signal_close_pos: float = 0.5     # bull signal bar closes at least above its midpoint (BAR-3)
    max_signal_bar_atr: float = 2.0   # skip signal bars bigger than this many ATRs

    # Breakouts (BO-1..BO-3)
    range_lookback: int = 20          # bars defining the range being broken
    bo_close_pos: float = 0.75
    bo_min_range_atr: float = 1.0
    bo_follow_through: bool = False   # BO-6: wait for a follow-through bar before entering (backtest: worse)

    # Risk (RISK-1..RISK-5)
    reward_r: float = 2.0             # target for pullback setups, in multiples of risk
    min_reward_r: float = 1.0         # skip setups whose target is closer than this
    max_hold_bars: int = 20
    cost_pct: float = 0.2             # round-trip commission + slippage, percent of price
    # Wave 3 + CDC Action Zone, ChalokeDotCom (W3-1..W3-5, docs/chaloke_wave3.md)
    wave3: bool = True
    w3_pivot_bars: int = 5            # swing high = highest of 5 bars each side
    w3_min_atr: float = 3.0           # wave 1 must rise at least this many ATRs
    w3_max_wave1_bars: int = 60       # look this far back from the wave 1 top for its base
    w3_max_wave2_bars: int = 60       # wave 2 (top to first green) must finish within this many bars
    w3_retrace_min: float = 0.618
    w3_retrace_max: float = 0.942
    w3_max_bars_after_low: int = 20   # first green must come within this many bars of the wave 2 low
    w3_max_hold_bars: int = 120       # wave 3 takes longer than a Brooks swing
    w3_min_rr: float = 2.0            # W3-6: reward/risk to the 161.8% target, from the signal close
    w3_recent_bars: int = 5           # scan keeps a W3 for this many days if it has not run away (W3-8)
    market: str = "set"               # "set" or "us": tick sizes (see markets.py)
    long_only: bool = False           # SET retail short selling is limited (SBL only)


DEFAULT = Config()
