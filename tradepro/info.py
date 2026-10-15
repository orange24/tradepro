"""What a stock is: company name, industry / sector (Thai), business summary and website.

Thai stocks: name, industry and sector from the SET list (set_all.csv), business summary from Yahoo.
Other markets: Yahoo Finance. Results are cached on disk for a week.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from .markets import MARKETS
from .setlist import load as load_set
from .watchlists import ASSETS, INDEX_PROXY

CACHE_DAYS = 7

INDUSTRY_TH = {
    "Agro & Food Industry": "เกษตรและอุตสาหกรรมอาหาร", "Consumer Products": "สินค้าอุปโภคบริโภค",
    "Financials": "ธุรกิจการเงิน", "Industrials": "สินค้าอุตสาหกรรม", "Industrial": "สินค้าอุตสาหกรรม",
    "Property & Construction": "อสังหาริมทรัพย์และก่อสร้าง", "Resources": "ทรัพยากร",
    "Services": "บริการ", "Technology": "เทคโนโลยี",
}
SECTOR_TH = {
    "Agribusiness": "ธุรกิจการเกษตร", "Food & Beverage": "อาหารและเครื่องดื่ม", "Fashion": "แฟชั่น",
    "Home & Office Products": "ของใช้ในครัวเรือนและสำนักงาน",
    "Personal Products & Pharmaceuticals": "ของใช้ส่วนตัวและเวชภัณฑ์", "Banking": "ธนาคาร",
    "Finance & Securities": "เงินทุนและหลักทรัพย์", "Insurance": "ประกันภัยและประกันชีวิต",
    "Automotive": "ยานยนต์", "Industrial Materials & Machinery": "วัสดุอุตสาหกรรมและเครื่องจักร",
    "Paper & Printing Materials": "กระดาษและวัสดุการพิมพ์", "Petrochemicals & Chemicals": "ปิโตรเคมีและเคมีภัณฑ์",
    "Packaging": "บรรจุภัณฑ์", "Steel and Metal Products": "เหล็กและผลิตภัณฑ์โลหะ",
    "Construction Materials": "วัสดุก่อสร้าง", "Construction Services": "บริการรับเหมาก่อสร้าง",
    "Property Development": "พัฒนาอสังหาริมทรัพย์", "Property Fund & REITs": "กองทุนอสังหาริมทรัพย์และ REITs",
    "Energy & Utilities": "พลังงานและสาธารณูปโภค", "Mining": "เหมืองแร่", "Commerce": "พาณิชย์",
    "Health Care Services": "การแพทย์", "Media & Publishing": "สื่อและสิ่งพิมพ์",
    "Professional Services": "บริการเฉพาะกิจ", "Tourism & Leisure": "การท่องเที่ยวและสันทนาการ",
    "Transportation & Logistics": "ขนส่งและโลจิสติกส์", "Electronic Components": "ชิ้นส่วนอิเล็กทรอนิกส์",
    "Information & Communication Technology": "เทคโนโลยีสารสนเทศและการสื่อสาร",
}
ASSET_TH = {
    "BTC-USD": "สกุลเงินดิจิทัลตัวแรกของโลก จำนวนจำกัด 21 ล้านเหรียญ ซื้อขายตลอด 24 ชั่วโมงทุกวัน ราคาเป็นดอลลาร์สหรัฐ",
    "ETH-USD": "สกุลเงินดิจิทัลของเครือข่าย Ethereum ใช้จ่ายค่าธรรมเนียมบนบล็อกเชนที่รันสัญญาอัจฉริยะ (smart contract) ราคาเป็นดอลลาร์",
    "GC=F": "สัญญาซื้อขายทองคำล่วงหน้าในตลาด COMEX สหรัฐ ราคาดอลลาร์ต่อออนซ์ ใช้เป็นราคาทองโลก (ไม่ใช่ราคาทองแท่งไทย)",
    "SI=F": "สัญญาซื้อขายแร่เงินล่วงหน้าในตลาด COMEX สหรัฐ ราคาดอลลาร์ต่อออนซ์",
}
_set = None


def _set_row(ticker: str) -> dict | None:
    global _set
    if _set is None:
        try:
            _set = {r["symbol"]: r for r in load_set()}
        except FileNotFoundError:
            _set = {}
    return _set.get(ticker)


def _yahoo(symbol: str) -> dict:
    try:
        import yfinance as yf

        i = yf.Ticker(symbol).info or {}
    except Exception:
        return {}
    return {"name": i.get("longName") or i.get("shortName"), "sector": i.get("sector"),
            "industry": i.get("industry"), "summary": i.get("longBusinessSummary"),
            "website": i.get("website"), "employees": i.get("fullTimeEmployees"),
            "country": i.get("country")}


def company_info(market: str, ticker: str, cache_dir: str | None = "data/web-cache/info",
                 offline: bool = False) -> dict:
    path = Path(cache_dir) / f"{market}_{ticker}.json" if cache_dir else None
    if path and path.exists() and time.time() - path.stat().st_mtime < CACHE_DAYS * 86400:
        return json.loads(path.read_text())
    info: dict = {"ticker": ticker, "market": market}
    proxies = {t: name for t, name in INDEX_PROXY.values()}
    if ticker in proxies:
        info.update(name=proxies[ticker], kind="กองทุน ETF ที่ใช้แทนดัชนี")
    if ticker in ASSETS:
        info.update(name=ASSETS[ticker][0], about_th=ASSET_TH.get(ticker), kind="สินทรัพย์")
    row = _set_row(ticker) if market == "set" else None
    if row:
        info.update(name=row.get("company") or ticker, board=row["market"],
                    industry_th=INDUSTRY_TH.get(row["industry"], row["industry"]),
                    sector_th=SECTOR_TH.get(row["sector"]) if row["sector"] not in ("", "-") else None)
    if not offline and ticker not in ASSETS:
        y = _yahoo(ticker + MARKETS[market].yahoo_suffix)
        for k, v in y.items():
            if v and not info.get(k):
                info[k] = v
    if path and not offline:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(info, ensure_ascii=False))
    return info
