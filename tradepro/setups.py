"""Trade signals. The only setup is ChalokeDotCom's Wave 3 entry (W3, see tradepro/wave.py)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import pandas as pd

from .config import DEFAULT, Config
from .indicators import add_features
from .wave import detect_running_flat, detect_wave3


@dataclass
class Signal:
    ticker: str
    date: pd.Timestamp        # signal bar date; the order is for the next bar
    setup: str
    direction: str            # "long"
    entry: float              # for order="open": the signal bar's close (the fill is the next open)
    stop: float
    target: float
    context: str              # CDC Action Zone colour on the signal bar
    note: str = ""
    order: str = "open"       # "open": buy at the next bar's open; "stop": stop order at entry
    max_hold: int | None = None   # bars before a time exit (default cfg.max_hold_bars)
    levels: dict = field(default_factory=dict)   # wave 1 base / top, wave 2 low, Fibonacci levels

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


def detect(df: pd.DataFrame, ticker: str = "", cfg: Config = DEFAULT) -> list[Signal]:
    """Scan every bar of df and return all W3 / RF setups found (signal bar = the first CDC green bar)."""
    f = add_features(df, cfg)
    w3 = detect_wave3(f, ticker, cfg, Signal)
    days = {s.date for s in w3}
    rf = [s for s in detect_running_flat(f, ticker, cfg, Signal) if s.date not in days] if cfg.running_flat else []
    return sorted(w3 + rf, key=lambda s: s.date)
