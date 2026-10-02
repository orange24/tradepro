"""Per-market settings: Yahoo ticker suffix, default watchlist, tick sizes and costs."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Market:
    name: str
    yahoo_suffix: str
    watchlist: str
    cost_pct: float        # round-trip commission + slippage, percent of price
    label: str = ""
    currency: str = "$"
    lot: float = 1         # buy in multiples of this (SET board lot 100; 0 = fractions allowed)
    running_flat: bool = True   # RF-1 setup on (backtest: weak on SET50, strong on US50 / crypto)


MARKETS = {
    # SET: ~0.157% commission each side + VAT, plus slippage
    "set": Market("set", ".BK", "set100", 0.2, "หุ้นไทย (SET)", "฿", 100, False),
    # US: zero-commission brokers; cost is mostly spread/slippage
    "us": Market("us", "", "us50", 0.05, "หุ้นสหรัฐ (US)", "$", 1),
    # Bitcoin, gold and the like (Yahoo symbols BTC-USD, GC=F ...); fractions allowed
    "asset": Market("asset", "", "assets", 0.1, "คริปโต / ทองคำ", "$", 0),
}


def markets_for(name: str) -> list[Market]:
    name = name.lower()
    if name in ("all", "both"):
        return list(MARKETS.values())
    return [MARKETS[name]]
