# องค์ความรู้ Price Action ตามแนว Al Brooks (Brooks Trading Course)

> ไฟล์นี้สรุปแนวคิดที่โปรแกรมใช้ตรวจหา setup เขียนจากความรู้ทั่วไปเรื่อง Brooks price action
> **ยังไม่ได้ตรวจกับวิดีโอจริง** ให้เอาแต่ละหัวข้อไปถาม NotebookLM (ที่โหลดวิดีโอ Brooks ไว้)
> แล้วแก้ไฟล์นี้ + ค่าใน `tradepro/config.py` ให้ตรงกับคำตอบ
> ช่อง "ตรวจแล้ว" ให้ติ๊ก `[x]` เมื่อยืนยันกับ NotebookLM แล้ว

แต่ละกฎมีรหัส (เช่น `CTX-1`) ซึ่งอ้างถึงในโค้ดเป็นคอมเมนต์ จะได้ตามกลับมาหาได้ว่าโค้ดส่วนไหนมาจากกฎข้อไหน

---

## 1. บริบทตลาด (Market Context) — สำคัญที่สุด

Brooks เน้นว่า "context ก่อน setup" setup เดียวกันอาจดีในเทรนด์แต่แย่ในกรอบ

| รหัส | กฎ | ในโค้ด | ตรวจแล้ว |
|---|---|---|---|
| CTX-1 | ตลาดอยู่ในสภาวะ **เทรนด์** หรือ **กรอบ (trading range)** เสมอ และส่วนใหญ่ (~80%) ของความพยายาม breakout จากกรอบจะล้มเหลว | `indicators.add_features` (คอลัมน์ context) | [ ] |
| CTX-2 | **เทรนด์ขาขึ้น**: ราคาปิดเหนือ EMA 20 เป็นส่วนใหญ่, EMA ชันขึ้น, ทำ higher high / higher low | `indicators.py` (ใช้สัดส่วนแท่งที่ปิดเหนือ EMA + ความชัน EMA) | [ ] |
| CTX-3 | **เทรนด์ขาลง**: กลับด้านกับ CTX-2 | `indicators.py` | [ ] |
| CTX-4 | **กรอบ**: แท่งเทียนซ้อนทับกันมาก (overlap), EMA แบน, ราคาข้ามไปมา EMA บ่อย | `indicators.py` (ตอนนี้ใช้ EMA แบน + ราคาข้าม EMA; ยังไม่วัด overlap) | [ ] |
| CTX-5 | "Always in long / always in short" — ถ้าต้องอยู่ในตลาดตลอดเวลา ตอนนี้ควรถือฝั่งไหน ใช้ตัดสินทิศทางหลัก | ใช้ทิศของ context เป็นตัวกรองทิศ setup | [ ] |
| CTX-6 | ในกรอบ ให้ "buy low, sell high, scalp" ไม่ไล่ซื้อที่ขอบบน / ไม่ไล่ขายที่ขอบล่าง | setup `FAILED_BO` | [ ] |

## 2. แท่งเทียน (Bars)

| รหัส | กฎ | ในโค้ด | ตรวจแล้ว |
|---|---|---|---|
| BAR-1 | **Trend bar** = ตัวแท่ง (body) ใหญ่เมื่อเทียบกับช่วงราคา (range) แสดงว่าฝั่งหนึ่งคุมตลาด | `indicators.add_features` (body_ratio) ≥ `trend_bar_body` | [ ] |
| BAR-2 | **Doji** = body เล็ก ไม่มีใครคุม ไม่ใช่ signal bar ที่ดี | `doji_body` ใน config | [ ] |
| BAR-3 | **Bull signal bar ที่ดี**: ปิดขึ้น (close > open), ปิดใกล้ high (ส่วนบนของแท่ง), ไส้ล่างพอสมควร, ไส้บนเล็ก, ขนาดไม่ใหญ่ผิดปกติ | `indicators.is_good_bull_signal` | [ ] |
| BAR-4 | **Bear signal bar ที่ดี**: กลับด้านกับ BAR-3 | `indicators.is_good_bear_signal` | [ ] |
| BAR-5 | Signal bar ที่ใหญ่มากทำให้ stop ไกล ความเสี่ยงสูง Brooks มักแนะนำให้ระวัง | `max_signal_bar_atr` | [ ] |
| BAR-6 | **Inside bar / Outside bar** — ii, ioi เป็นรูปแบบกรอบเล็ก ใช้เป็น breakout mode | ยังไม่ใช้ (งานถัดไป) | [ ] |

## 3. การนับขา Pullback: High 1/High 2 และ Low 1/Low 2

| รหัส | กฎ | ในโค้ด | ตรวจแล้ว |
|---|---|---|---|
| HL-1 | ในเทรนด์ขาขึ้น เมื่อเกิด pullback แท่งแรกที่ high สูงกว่า high ของแท่งก่อนหน้า = **High 1 (H1)** | `setups.count_highs` | [ ] |
| HL-2 | ถ้า pullback ไปต่อ (มีแท่งที่ high ต่ำลงอีก) แล้วมีแท่ง high ทะลุแท่งก่อนหน้าอีกครั้ง = **High 2 (H2)** เป็น pullback 2 ขา (ABC) | `setups.count_highs` | [ ] |
| HL-3 | **H2 ในเทรนด์ขาขึ้น** เป็น setup ซื้อที่น่าเชื่อถือที่สุดแบบหนึ่ง โดยเฉพาะ H2 ที่ EMA (20-bar EMA pullback) | setup `H2` | [ ] |
| HL-4 | **H1** ใช้ได้ในเทรนด์ที่แรงมาก (strong trend) เท่านั้น เพราะ pullback สั้น | setup `H1` (ต้อง `strong=True`) | [ ] |
| HL-5 | ถ้า H2 ล้มเหลว (ราคาหลุด low ของ signal bar) อาจกลายเป็นกรอบหรือกลับตัว; H3/H4 = wedge bull flag | ยังไม่ใช้ | [ ] |
| HL-6 | **Low 1 / Low 2** ในเทรนด์ขาลง กลับด้านกับ HL-1..HL-4 | setup `L1`, `L2` | [ ] |
| HL-7 | Entry = **buy stop 1 tick เหนือ high ของ signal bar** (sell stop 1 tick ใต้ low สำหรับ short) | `setups._long` | [ ] |
| HL-8 | ตัวนับ reset เมื่อราคาทำ high ใหม่ของขาเทรนด์ (สำหรับ H) หรือ low ใหม่ (สำหรับ L) | `setups.count_highs` | [ ] |

## 4. Breakout และ Measured Move

| รหัส | กฎ | ในโค้ด | ตรวจแล้ว |
|---|---|---|---|
| BO-1 | **Breakout ที่แข็งแรง**: trend bar ใหญ่ ปิดใกล้ high/low ปิดนอกกรอบเดิม ไม่มี overlap กับแท่งก่อนมาก | setup `BO_BULL` / `BO_BEAR` | [ ] |
| BO-2 | หลัง breakout ที่แรง มักมี **follow-through** และบ่อยครั้งจะไปถึง **measured move** = ความสูงของกรอบ บวกจากจุด breakout | target ของ BO = จุด breakout + ความสูงกรอบ | [ ] |
| BO-3 | Breakout ส่วนใหญ่จากกรอบล้มเหลว (CTX-1) ดังนั้น breakout ที่ไม่มี follow-through → เทรดกลับเข้ากรอบ = **failed breakout** | setup `FAILED_BO` | [ ] |
| BO-4 | **Breakout pullback** — หลัง breakout ราคาย้อนมาทดสอบจุด breakout แล้วไปต่อ มักเป็น H1/H2 | ครอบคลุมบางส่วนโดย H1/H2 | [ ] |
| BO-5 | Measured move อีกแบบ: ขาแรก (leg 1) = ขาสอง (leg 2) ความยาวใกล้กัน | ยังไม่ใช้ | [ ] |

## 5. Stop, Target และการบริหารความเสี่ยง

| รหัส | กฎ | ในโค้ด | ตรวจแล้ว |
|---|---|---|---|
| RISK-1 | **Stop เริ่มต้น** = 1 tick ใต้ low ของ signal bar (long) / เหนือ high (short) | `setups` | [ ] |
| RISK-2 | **Trader's equation**: ความน่าจะเป็น × reward ต้องมากกว่า (1−ความน่าจะเป็น) × risk | backtest รายงาน expectancy (R) | [ ] |
| RISK-3 | Setup ที่ความน่าจะเป็น ~60% ใช้ reward ≥ risk (1R); setup ~40% ต้องการ reward ≥ 2R | `reward_r` ใน config (ค่าเริ่มต้น 2R) | [ ] |
| RISK-4 | ขนาด position คำนวณจากระยะ stop (เสี่ยงเงินเท่ากันทุกเทรด) | `backtest` วัดผลเป็น R | [ ] |
| RISK-5 | ถ้าเข้าเทรดแล้วไม่ไปไหนหลายแท่ง ให้พิจารณาออก | `max_hold_bars` | [ ] |

## 6. รูปแบบกลับตัว (ยังไม่ได้เขียนโค้ด — งานถัดไป)

- **Wedge (3 pushes)** — 3 ขาดันที่อ่อนแรงลงเรื่อย ๆ มักกลับตัวอย่างน้อย 2 ขา
- **Double top / double bottom** และ **double top/bottom bull/bear flag**
- **Major trend reversal (MTR)** — ต้องมีการทะลุเส้นเทรนด์ก่อน แล้วทดสอบจุดสุดขั้วเดิม (higher low / lower high) ถึงเข้าเทรดกลับตัว
- **Final flag**, **climax / exhaustion**, **parabolic wedge**

---

## คำถามแนะนำให้ถาม NotebookLM เพื่อตรวจไฟล์นี้

1. Al Brooks นิยาม High 1 / High 2 อย่างไร นับใหม่ (reset) เมื่อไร?
2. Signal bar ที่ดีสำหรับ H2 ต้องมีลักษณะอย่างไร ปิดที่ส่วนไหนของแท่ง?
3. Brooks แยกเทรนด์กับกรอบด้วยอะไร ใช้ EMA 20 อย่างไร?
4. Measured move หลัง breakout คิดอย่างไร?
5. ใน daily chart ของหุ้น Brooks แนะนำ stop และ target อย่างไร? ใช้ 1R หรือ 2R?
6. ความน่าจะเป็นของ H2 ในเทรนด์ขาขึ้นประมาณเท่าไร?
7. เมื่อไหร่ควรเทรด failed breakout แทน breakout?

## หมายเหตุเรื่องตลาด (SET และหุ้นสหรัฐ)

- โปรแกรมใช้ daily chart เป็นค่าเริ่มต้น (Brooks สอนหลักบน 5-minute E-mini แต่หลักการใช้กับทุก timeframe)
- ราคา entry/stop ปัดตาม tick size ของแต่ละตลาด (`tradepro/ticks.py`): SET ตามช่วงราคา, US ทีละ $0.01
- หุ้นสหรัฐขาย short ได้ง่ายกว่า สัญญาณ L1/L2/BO_BEAR จึงใช้ได้ตรง ๆ
- นักลงทุนรายย่อยขาย short ใน SET ได้จำกัด (ผ่าน SBL เท่านั้น) ใช้ `--long-only` เพื่อดูแค่ฝั่งซื้อ
  หรือมองสัญญาณ short เป็น "สัญญาณขายออก" ของหุ้นที่ถืออยู่
