"""Tick sizes per market."""

import math

_SET_TICKS = [
    (2, 0.01),
    (5, 0.02),
    (10, 0.05),
    (25, 0.10),
    (100, 0.25),
    (200, 0.50),
    (400, 1.00),
    (float("inf"), 2.00),
]


def set_tick(price: float) -> float:
    """SET tick size by price band (THB)."""
    for upper, tick in _SET_TICKS:
        if price < upper:
            return tick
    return _SET_TICKS[-1][1]


def us_tick(price: float) -> float:
    """US stocks: one cent, sub-penny below $1 (Reg NMS)."""
    return 0.01 if price >= 1 else 0.0001


def tick_size(price: float, market: str = "set") -> float:
    return us_tick(price) if market == "us" else set_tick(price)


def round_to_tick(price: float, up: bool, market: str = "set") -> float:
    """Round a price to a valid tick, up (for buy stops) or down (for sell stops)."""
    tick = tick_size(price, market)
    n = price / tick
    n = math.ceil(n - 1e-9) if up else math.floor(n + 1e-9)
    return round(n * tick, 4)
