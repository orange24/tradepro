"""Per-market settings: Yahoo ticker suffix, default watchlist, tick sizes and costs."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Market:
    name: str
    yahoo_suffix: str
    watchlist: str
    cost_pct: float        # round-trip commission + slippage, percent of price


MARKETS = {
    # SET: ~0.157% commission each side + VAT, plus slippage
    "set": Market("set", ".BK", "set100", 0.2),
    # US: zero-commission brokers; cost is mostly spread/slippage
    "us": Market("us", "", "us50", 0.05),
}


def markets_for(name: str) -> list[Market]:
    name = name.lower()
    if name in ("all", "both"):
        return list(MARKETS.values())
    return [MARKETS[name]]
