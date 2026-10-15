"""All stocks listed on SET and mai, from the SET's public "listed companies" file.

Refresh:  python -m tradepro.setlist [saved_file.xls]   (rewrites tradepro/set_all.csv)
"""

from __future__ import annotations

import csv
import html
import re
import urllib.request
from pathlib import Path

URL = "https://weblink.set.or.th/dat/eod/listedcompany/static/listedCompanies_en_US.xls"
FILE = Path(__file__).with_name("set_all.csv")


def parse(text: str) -> list[dict]:
    """The .xls is an HTML table: Symbol, Company, Market, Industry, Sector, ..."""
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.S):
        cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip()
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(cells) >= 5 and cells[2] in ("SET", "mai"):
            out.append({"symbol": cells[0], "company": cells[1], "market": cells[2], "industry": cells[3],
                        "sector": cells[4]})
    return out


def _download() -> str:
    try:  # python.org builds on macOS ship without CA certificates; use certifi's when available
        import certifi, ssl
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = None
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
        return r.read().decode("utf-8", errors="replace")


def refresh(path: str | None = None) -> list[dict]:
    """Rebuild set_all.csv from the SET file (downloaded, or a copy saved from a browser at `path`)."""
    text = Path(path).read_text(encoding="utf-8", errors="replace") if path else _download()
    rows = parse(text)
    if len(rows) < 500:
        raise RuntimeError(f"only {len(rows)} stocks parsed. The SET site may be blocking scripts: open {URL} "
                           "in a browser, save the file, then run python -m tradepro.setlist <saved file>")
    with FILE.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["symbol", "company", "market", "industry", "sector"])
        w.writeheader()
        w.writerows(rows)
    return rows


def load() -> list[dict]:
    with FILE.open(newline="") as fh:
        return list(csv.DictReader(fh))


if __name__ == "__main__":
    import sys

    rows = refresh(sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"{len(rows)} stocks written to {FILE}")
