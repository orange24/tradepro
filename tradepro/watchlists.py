"""Ticker lists. SET50 membership changes every half year; check against set.or.th."""

SET50 = [
    "ADVANC", "AOT", "AWC", "BANPU", "BBL", "BCP", "BDMS", "BEM", "BGRIM", "BH",
    "BJC", "BTS", "CBG", "CCET", "CENTEL", "COM7", "CPALL", "CPF", "CPN", "CRC",
    "DELTA", "EGCO", "GLOBAL", "GPSC", "GULF", "HMPRO", "IVL", "KBANK", "KKP", "KTB",
    "KTC", "LH", "MINT", "MTC", "OR", "OSP", "PTT", "PTTEP", "PTTGC", "RATCH",
    "SCB", "SCC", "SCGP", "TCAP", "TIDLOR", "TISCO", "TLI", "TOP", "TRUE", "TTB", "WHA",
]

# SET100 constituents from set.or.th, 30 Sep 2026 (reviewed every half year)
SET100 = [
    "AAV", "ADVANC", "AEONTS", "AMATA", "AOT", "AP", "AURA", "AWC", "BA", "BAM",
    "BANPU", "BBL", "BCH", "BCP", "BCPG", "BDMS", "BEM", "BGRIM", "BH", "BJC",
    "BLA", "BTG", "BTS", "CBG", "CCET", "CENTEL", "CHG", "CK", "COM7", "CPALL",
    "CPF", "CPN", "CRC", "DELTA", "DOHOME", "EA", "EGCO", "ERW", "GFPT", "GLOBAL",
    "GPSC", "GST", "GULF", "GUNKUL", "HANA", "HMPRO", "ICHI", "IRPC", "IVL", "JMART",
    "JMT", "KBANK", "KCE", "KKP", "KTB", "KTC", "LH", "M", "MEGA", "MINT",
    "MOSHI", "MRDIYT", "MTC", "OR", "OSP", "PLANB", "PR9", "PRM", "PTG", "PTT",
    "PTTEP", "PTTGC", "QH", "RATCH", "RCL", "SAWAD", "SCB", "SCC", "SCGP", "SIRI",
    "SPALI", "SPRC", "STA", "STECON", "STGT", "TASCO", "TCAP", "TFG", "THAI", "TIDLOR",
    "TISCO", "TLI", "TOA", "TOP", "TRUE", "TTB", "TU", "VGI", "WHA", "WHAUP",
]

WATCHLISTS = {"set50": SET50, "set100": SET100}

# Bitcoin, gold and other assets Chaloke follows (Yahoo Finance symbols)
ASSETS = {
    "BTC-USD": ("Bitcoin", "BTCUSD"),
    "ETH-USD": ("Ethereum", "ETHUSD"),
    "GC=F": ("ทองคำ (Gold futures)", "COMEX:GC1!"),
    "SI=F": ("แร่เงิน (Silver futures)", "COMEX:SI1!"),
}
WATCHLISTS["assets"] = list(ASSETS)
ASSET_ALIASES = {"BTC": "BTC-USD", "BITCOIN": "BTC-USD", "ETH": "ETH-USD", "GOLD": "GC=F", "XAU": "GC=F",
                 "XAUUSD": "GC=F", "ทอง": "GC=F", "ทองคำ": "GC=F", "SILVER": "SI=F", "XAG": "SI=F", "เงิน": "SI=F"}


def normalize_ticker(market: str, ticker: str) -> tuple[str, str]:
    """(market, ticker) with asset nicknames resolved: "BTC" or "ทอง" go to the asset market whatever was picked."""
    t = ticker.strip().upper()
    alias = ASSET_ALIASES.get(t) or ASSET_ALIASES.get(ticker.strip())
    if alias or t in ASSETS:
        return "asset", alias or t
    return market, t

# Every SET + mai stock (tradepro/set_all.csv, refresh with `python -m tradepro.setlist`)
try:
    from .setlist import load as _load_set_all
    WATCHLISTS["set_all"] = [r["symbol"] for r in _load_set_all()]
except FileNotFoundError:  # pragma: no cover
    pass

# Large, liquid US stocks (mega caps across sectors). Edit freely.
US50 = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "BRK-B", "JPM",
    "LLY", "V", "MA", "UNH", "XOM", "JNJ", "PG", "HD", "COST", "ABBV",
    "WMT", "NFLX", "BAC", "CRM", "ORCL", "AMD", "KO", "PEP", "MRK", "CVX",
    "ADBE", "TMO", "CSCO", "ACN", "MCD", "LIN", "ABT", "WFC", "INTU", "QCOM",
    "TXN", "DIS", "CAT", "GE", "IBM", "AMGN", "PFE", "GS", "UBER", "NOW",
]

WATCHLISTS["us50"] = US50
