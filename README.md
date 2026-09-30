# TradePro

โปรแกรมสแกนหุ้นหาจุดเข้า/ออกจากกราฟราคา ตามแนวคิด price action ของ Al Brooks (Brooks Trading Course)

- **ความรู้ที่ใช้**: [`docs/brooks_knowledge.md`](docs/brooks_knowledge.md) ทุกกฎมีรหัส (เช่น `HL-2`) ที่อ้างในโค้ด
  ให้ตรวจแต่ละข้อกับ NotebookLM แล้วปรับค่าใน [`tradepro/config.py`](tradepro/config.py)
- **ตลาด**: ค่าเริ่มต้นคือหุ้นไทย SET, daily chart, ข้อมูลจาก Yahoo Finance (ticker `.BK`) รายชื่อ SET50 อยู่ใน `tradepro/watchlists.py`

## ติดตั้ง

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## ใช้งาน

```bash
# สแกนหา setup บนแท่งล่าสุดของหุ้น SET50 -> ได้รายการ entry / stop / target สำหรับวันทำการถัดไป
python -m tradepro scan

# เฉพาะบางตัว ย้อนดู 5 แท่งล่าสุด เฉพาะฝั่งซื้อ
python -m tradepro scan PTT KBANK CPALL --recent 5 --long-only

# backtest ตั้งแต่ 2015 (ผลรายเทรดบันทึกที่ trades.csv)
python -m tradepro backtest --start 2015-01-01 --long-only

# ดาวน์โหลดเก็บเป็น CSV (data/cache/) แล้วใช้ซ้ำแบบ offline
python -m tradepro download
python -m tradepro backtest --source csv

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

Entry = stop order 1 tick เหนือ high (long) / ใต้ low (short) ของ signal bar ใช้ได้เฉพาะแท่งถัดไป
Stop = 1 tick อีกฝั่งของ signal bar

## Backtest

- เข้าเมื่อแท่งถัดไปแตะราคา entry (gap เปิดเกินใช้ราคาเปิด) ไม่แตะ = ยกเลิก
- ถ้าแท่งเดียวแตะทั้ง stop และ target นับว่าโดน stop (มองแง่ร้าย)
- ถือไม่เกิน 20 แท่ง (`--hold`), หักค่าคอม+slippage 0.2% ต่อรอบ, ถือได้ทีละ 1 position ต่อหุ้น
- ผลวัดเป็น **R** (จำนวนเท่าของความเสี่ยงเริ่มต้น) `avg_r` > 0 = trader's equation เป็นบวก

## โครงสร้าง

```
tradepro/
  data.py        แหล่งข้อมูล (Yahoo / CSV / synthetic) — เปลี่ยนตลาดหรือผู้ให้บริการได้ที่นี่
  indicators.py  EMA, ATR, ลักษณะแท่งเทียน, บริบทเทรนด์/กรอบ
  setups.py      นับ H1/H2, L1/L2 และตรวจจับ setup
  scanner.py     สแกนหลายหุ้นหาสัญญาณล่าสุด
  backtest.py    จำลองการเทรดและสรุปผล
  ticks.py       tick size ของ SET
```

> ไม่ใช่คำแนะนำการลงทุน ใช้เพื่อศึกษาและทดสอบระบบก่อนใช้เงินจริง
