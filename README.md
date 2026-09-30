# TradePro

โปรแกรมสแกนหุ้นหาจุดเข้า/ออกจากกราฟราคา ตามแนวคิด price action ของ Al Brooks (Brooks Trading Course)

- **ความรู้ที่ใช้**: [`docs/brooks_knowledge.md`](docs/brooks_knowledge.md) ทุกกฎมีรหัส (เช่น `HL-2`) ที่อ้างในโค้ด
  ให้ตรวจแต่ละข้อกับ NotebookLM แล้วปรับค่าใน [`tradepro/config.py`](tradepro/config.py)
- **กลยุทธ์ Wave 3 + CDC Action Zone (ลุงโฉลก)**: setup `W3` ดู [`docs/chaloke_wave3.md`](docs/chaloke_wave3.md)
- **ตลาด**: หุ้นไทย SET และหุ้นสหรัฐ (`--market set | us | all`, ค่าเริ่มต้น `set`), daily chart, ข้อมูลจาก Yahoo Finance
  รายชื่อหุ้นตั้งต้น SET100 (และ SET50) และ US50 อยู่ใน `tradepro/watchlists.py` หุ้นไทยทั้งหมด (SET + mai) อยู่ใน `tradepro/set_all.csv`
  อัปเดตรายชื่อจากไฟล์ของ SET ด้วย `python -m tradepro.setlist` และสแกนด้วย `python -m tradepro scan --watchlist set_all` ส่วน tick size และค่าคอมแต่ละตลาดอยู่ใน `tradepro/markets.py`

## เว็บแอป (พอร์ต + สแกน) สำหรับรันบน server

มี 3 หน้า
- **พอร์ตของฉัน**: ใส่หุ้นที่ถือ (ตลาด, ชื่อหุ้น, จำนวน, ต้นทุนเฉลี่ย) แล้วแสดงราคาล่าสุด กำไร/ขาดทุน
  คำแนะนำ **ถือต่อ / เฝ้าระวัง / ควรขาย** พร้อมเหตุผลและราคา stop ที่ควรขาย (กฎ EXIT-1..4 ใน docs)
- **สแกนหุ้นน่าซื้อ**: หุ้น SET100 / หุ้นไทยทั้งหมด / US50 (และหุ้นในพอร์ต) ที่วันล่าสุดเกิด setup ฝั่งซื้อ พร้อมราคาเข้า, stop, เป้า
  สแกนอัตโนมัติทุก 6 ชั่วโมง หรือกดปุ่ม "สแกนใหม่"
- **กราฟ**: กดชื่อหุ้นเพื่อดูแท่งเทียน + EMA20 + จุดสัญญาณ + เส้น stop + เส้นต้นทุน

### ลองในเครื่อง

```bash
pip install -r requirements.txt
python -m tradepro.web            # เปิด http://127.0.0.1:8000
TRADEPRO_SOURCE=synthetic python -m tradepro.web   # ข้อมูลจำลอง ไม่ต้องใช้เน็ต
```

### ขึ้น server (VPS ที่มี Docker เช่น DigitalOcean, AWS Lightsail, Google Cloud)

```bash
git clone https://github.com/orange24/tradepro.git && cd tradepro
echo "TRADEPRO_PASSWORD=ตั้งรหัสผ่านที่เดายาก" > .env
docker compose up -d --build
```

เปิด `http://<IP ของ server>:8000` ใส่ username อะไรก็ได้ + รหัสผ่านที่ตั้งไว้
ข้อมูลพอร์ตเก็บใน `data/tradepro.db` บน server (สำรองไฟล์นี้ไว้)
ถ้าจะใช้ผ่านอินเทอร์เน็ตจริงจัง ควรตั้งโดเมน + HTTPS (เช่น Caddy หรือ Cloudflare Tunnel) เพราะรหัสผ่านส่งแบบ Basic auth

| ตัวแปร | ความหมาย | ค่าเริ่มต้น |
|---|---|---|
| `TRADEPRO_PASSWORD` | รหัสผ่านเข้าเว็บ (ไม่ตั้ง = ไม่ถาม) | – |
| `TRADEPRO_DB` | ไฟล์ฐานข้อมูล SQLite | `data/tradepro.db` |
| `TRADEPRO_SOURCE` | `yahoo` / `csv` / `synthetic` | `yahoo` |
| `TRADEPRO_MIN_VALUE` | แท็บหุ้นไทยทั้งหมด: ข้ามหุ้นที่มูลค่าซื้อขายเฉลี่ย 20 วันต่ำกว่านี้ (บาท/วัน, 0 = ไม่กรอง) | `1000000` |
| `TRADEPRO_SCAN_HOURS` | สแกนใหม่เมื่อผลเก่ากว่ากี่ชั่วโมง (0 = ปิด) | `6` |

## Command line

### ติดตั้ง

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### ใช้งาน

```bash
# สแกนหา setup บนแท่งล่าสุดของหุ้น SET100 -> ได้รายการ entry / stop / target สำหรับวันทำการถัดไป
python -m tradepro scan

# สแกนทั้งหุ้นไทยและหุ้นสหรัฐ
python -m tradepro scan --market all

# หุ้นสหรัฐบางตัว
python -m tradepro scan AAPL NVDA MSFT --market us

# เฉพาะบางตัว ย้อนดู 5 แท่งล่าสุด เฉพาะฝั่งซื้อ
python -m tradepro scan PTT KBANK CPALL --recent 5 --long-only

# backtest ตั้งแต่ 2015 แยกผลตามตลาด (ผลรายเทรดบันทึกที่ trades.csv)
python -m tradepro backtest --market all --start 2015-01-01 --long-only

# ดาวน์โหลดเก็บเป็น CSV (data/cache/set, data/cache/us) แล้วใช้ซ้ำแบบ offline
python -m tradepro download --market all
python -m tradepro backtest --market all --source csv

# ข้อมูลจำลอง (ไว้ลองโปรแกรมตอนไม่มีเน็ต — ผลไม่มีความหมายทางการเทรด)
python -m tradepro backtest --source synthetic
```

## Setup ที่ตรวจจับได้ (เวอร์ชันแรก)

| Setup | ทิศ | เงื่อนไขย่อ | Target |
|---|---|---|---|
| `H2` | long | เทรนด์ขึ้น, pullback 2 ขา, bull signal bar | 2R |
| `H1` | long | เทรนด์ขึ้นแรง, pullback ขาแรก | 2R |
| `L2` / `L1` | short | กลับด้านของ H2 / H1 | 2R |
| `BO_BULL` / `BO_BEAR` | long / short | trend bar ใหญ่ ปิดนอกกรอบ 20 แท่ง | measured move (ความสูงกรอบ) |
| `FAILED_BO` | ทั้งสอง | หลุดขอบกรอบแล้วปิดกลับเข้ากรอบ | กลางกรอบ |

Entry = stop order 1 tick (SET ตามช่วงราคา, US = $0.01) เหนือ high (long) / ใต้ low (short) ของ signal bar ใช้ได้เฉพาะแท่งถัดไป
Stop = 1 tick อีกฝั่งของ signal bar

## Backtest

- เข้าเมื่อแท่งถัดไปแตะราคา entry (gap เปิดเกินใช้ราคาเปิด) ไม่แตะ = ยกเลิก
- ถ้าแท่งเดียวแตะทั้ง stop และ target นับว่าโดน stop (มองแง่ร้าย)
- ถือไม่เกิน 20 แท่ง (`--hold`), หักค่าคอม+slippage ต่อรอบ 0.2% (SET) / 0.05% (US), ถือได้ทีละ 1 position ต่อหุ้น
- ผลวัดเป็น **R** (จำนวนเท่าของความเสี่ยงเริ่มต้น) `avg_r` > 0 = trader's equation เป็นบวก

## โครงสร้าง

```
tradepro/
  data.py        แหล่งข้อมูล (Yahoo / CSV / synthetic) — เปลี่ยนตลาดหรือผู้ให้บริการได้ที่นี่
  indicators.py  EMA, ATR, ลักษณะแท่งเทียน, บริบทเทรนด์/กรอบ
  setups.py      นับ H1/H2, L1/L2 และตรวจจับ setup
  scanner.py     สแกนหลายหุ้นหาสัญญาณล่าสุด
  backtest.py    จำลองการเทรดและสรุปผล
  markets.py     ค่าต่อตลาด (suffix ของ Yahoo, watchlist, ค่าคอม)
  ticks.py       tick size ของ SET และ US
  advisor.py     คำแนะนำถือ/ขายสำหรับหุ้นในพอร์ต
  store.py       เก็บพอร์ตและผลสแกน (SQLite)
  web/           เว็บแอป Flask + กราฟ (TradingView Lightweight Charts, Apache-2.0)
```

> ไม่ใช่คำแนะนำการลงทุน ใช้เพื่อศึกษาและทดสอบระบบก่อนใช้เงินจริง
