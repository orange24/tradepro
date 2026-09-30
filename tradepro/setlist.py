"""All stocks listed on SET and mai, from the SET's public "listed companies" file.

Refresh:  python -m tradepro.setlist   (rewrites tradepro/set_all.csv)
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
            out.append({"symbol": cells[0], "market": cells[2], "industry": cells[3], "sector": cells[4]})
    return out


def refresh() -> list[dict]:
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        rows = parse(r.read().decode("utf-8", errors="replace"))
    if len(rows) < 500:
        raise RuntimeError(f"only {len(rows)} stocks parsed; SET changed the file format?")
    with FILE.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["symbol", "market", "industry", "sector"])
        w.writeheader()
        w.writerows(rows)
    return rows


def load() -> list[dict]:
    with FILE.open(newline="") as fh:
        return list(csv.DictReader(fh))


if __name__ == "__main__":
    rows = refresh()
    print(f"{len(rows)} stocks written to {FILE}")
