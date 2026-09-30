"""SET tick size table (price bands in THB)."""

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
    for upper, tick in _SET_TICKS:
        if price < upper:
            return tick
    return _SET_TICKS[-1][1]


def round_to_tick(price: float, up: bool) -> float:
    """Round a price to a valid SET tick, up (for buy stops) or down (for sell stops)."""
    import math

    tick = set_tick(price)
    n = price / tick
    n = math.ceil(n - 1e-9) if up else math.floor(n + 1e-9)
    return round(n * tick, 4)
