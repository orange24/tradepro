# TradePro

โปรแกรมสแกนหุ้นหาจุดเข้า/ออก ตามแนว **Wave 3 + CDC Action Zone ของลุงโฉลก (ChalokeDotCom)**

- **กฎที่ใช้**: [`docs/chaloke_wave3.md`](docs/chaloke_wave3.md) ทุกกฎมีรหัส (เช่น `W3-2`, `EXIT-1`) ที่อ้างในโค้ด
  ปรับตัวเลขได้ใน [`tradepro/config.py`](tradepro/config.py)
- **ตลาด**: หุ้นไทย SET, หุ้นสหรัฐ และคริปโต / ทองคำ (Bitcoin `BTC-USD`, Ethereum, ทองคำ `GC=F`, แร่เงิน `SI=F`)
  (`--market set | us | asset | all`, ค่าเริ่มต้น `set`) พิมพ์ BTC, GOLD หรือ ทอง ในช่องค้นหาได้เลย, daily chart, ข้อมูลจาก Yahoo Finance
  รายชื่อหุ้นตั้งต้น SET100 (และ SET50) และ US50 อยู่ใน `tradepro/watchlists.py` หุ้นไทยทั้งหมด (SET + mai) อยู่ใน `tradepro/set_all.csv`
  อัปเดตรายชื่อจากไฟล์ของ SET ด้วย `python -m tradepro.setlist` และสแกนด้วย `python -m tradepro scan --watchlist set_all` ส่วน tick size และค่าคอมแต่ละตลาดอยู่ใน `tradepro/markets.py`

## เว็บแอป (พอร์ต + สแกน) สำหรับรันบน server

มี 3 หน้า
- **พอร์ตของฉัน**: ใส่หุ้นที่ถือ (ตลาด, ชื่อหุ้น, จำนวน, ต้นทุนเฉลี่ย) แล้วแสดงราคาล่าสุด กำไร/ขาดทุน
  คำแนะนำ **ถือต่อ / เฝ้าระวัง / ควรขาย** จาก CDC Action Zone และ Previous Low (กฎ EXIT-1..4 ใน docs)
- **สแกนหุ้นน่าซื้อ**: หุ้น SET100 / หุ้นไทยทั้งหมด / US50 (และหุ้นในพอร์ต) ที่เกิด Wave 3 เขียวแรก พร้อม stop และเป้า Fibonacci
  สแกนอัตโนมัติทุก 6 ชั่วโมง หรือกดปุ่ม "สแกนใหม่"
- **กราฟ**: แท่งเทียนรายวัน / สัปดาห์ / เดือน / ปี + เส้น CDC + แถบสี CDC + Wave 1 / Fibonacci + เครื่องมือวาด
  และการ์ดวิเคราะห์ตามลุงโฉลกที่อัปเดตทุก 1 นาที

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
# สแกนหา W3 (เขียวแรก) บนแท่งล่าสุดของหุ้น SET100 -> ซื้อที่ราคาเปิดวันทำการถัดไป พร้อม stop / เป้า
python -m tradepro scan

# สแกนทั้งหุ้นไทยและหุ้นสหรัฐ
python -m tradepro scan --market all

# หุ้นสหรัฐบางตัว
python -m tradepro scan AAPL NVDA MSFT --market us

# เฉพาะบางตัว ย้อนดู 5 แท่งล่าสุด
python -m tradepro scan PTT KBANK CPALL --recent 5

# backtest ตั้งแต่ 2015 แยกผลตามตลาด (ผลรายเทรดบันทึกที่ trades.csv)
python -m tradepro backtest --market all --start 2015-01-01

# ดาวน์โหลดเก็บเป็น CSV (data/cache/set, data/cache/us) แล้วใช้ซ้ำแบบ offline
python -m tradepro download --market all
python -m tradepro backtest --market all --source csv

# ข้อมูลจำลอง (ไว้ลองโปรแกรมตอนไม่มีเน็ต — ผลไม่มีความหมายทางการเทรด)
python -m tradepro backtest --source synthetic
```

## Backtest

- สัญญาณ W3 ซื้อที่ราคาเปิดของแท่งถัดจากแท่งเขียวแรก (gap ลงต่ำกว่า stop = ข้าม)
- Stop ใต้ปลาย Wave 2 เป้าแรก Fibonacci extension 161.8% ถ้าแท่งเดียวแตะทั้ง stop และเป้า นับว่าโดน stop (มองแง่ร้าย)
- ถือไม่เกิน 120 แท่ง (`--hold`), หักค่าคอม+slippage ต่อรอบ 0.2% (SET) / 0.05% (US), ถือได้ทีละ 1 position ต่อหุ้น
- ผลวัดเป็น **R** (จำนวนเท่าของความเสี่ยงเริ่มต้น) `avg_r` > 0 = ระบบได้เปรียบ

## โครงสร้าง

```
tradepro/
  data.py        แหล่งข้อมูล (Yahoo / CSV / synthetic) — เปลี่ยนตลาดหรือผู้ให้บริการได้ที่นี่
  indicators.py  ATR และลักษณะแท่งเทียน (big white / big black)
  wave.py        CDC Action Zone และตัวหา Wave 1–2 → สัญญาณ W3
  chaloke.py     เช็กลิสต์ตามลุงโฉลกของหุ้นหนึ่งตัว ณ ตอนนี้ (การ์ดบนหน้ากราฟ)
  setups.py      Signal และ detect() (เรียก wave.py)
  scanner.py     สแกนหลายหุ้นหาสัญญาณล่าสุด
  backtest.py    จำลองการเทรดและสรุปผล
  markets.py     ค่าต่อตลาด (suffix ของ Yahoo, watchlist, ค่าคอม)
  ticks.py       tick size ของ SET และ US
  advisor.py     คำแนะนำถือ/ขายสำหรับหุ้นในพอร์ต
  store.py       เก็บพอร์ตและผลสแกน (SQLite)
  web/           เว็บแอป Flask + กราฟ (TradingView Lightweight Charts, Apache-2.0)
```

> ไม่ใช่คำแนะนำการลงทุน ใช้เพื่อศึกษาและทดสอบระบบก่อนใช้เงินจริง
