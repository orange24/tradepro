"""Ticker lists. SET50 membership changes every half year; check against set.or.th."""

SET50 = [
    "ADVANC", "AOT", "AWC", "BANPU", "BBL", "BCP", "BDMS", "BEM", "BGRIM", "BH",
    "BJC", "BTS", "CBG", "CCET", "CENTEL", "COM7", "CPALL", "CPF", "CPN", "CRC",
    "DELTA", "EGCO", "GLOBAL", "GPSC", "GULF", "HMPRO", "IVL", "KBANK", "KKP", "KTB",
    "KTC", "LH", "MINT", "MTC", "OR", "OSP", "PTT", "PTTEP", "PTTGC", "RATCH",
    "SCB", "SCC", "SCGP", "TCAP", "TIDLOR", "TISCO", "TLI", "TOP", "TRUE", "TTB", "WHA",
]

WATCHLISTS = {"set50": SET50}

# Large, liquid US stocks (mega caps across sectors). Edit freely.
US50 = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "BRK-B", "JPM",
    "LLY", "V", "MA", "UNH", "XOM", "JNJ", "PG", "HD", "COST", "ABBV",
    "WMT", "NFLX", "BAC", "CRM", "ORCL", "AMD", "KO", "PEP", "MRK", "CVX",
    "ADBE", "TMO", "CSCO", "ACN", "MCD", "LIN", "ABT", "WFC", "INTU", "QCOM",
    "TXN", "DIS", "CAT", "GE", "IBM", "AMGN", "PFE", "GS", "UBER", "NOW",
]

WATCHLISTS["us50"] = US50
