# องค์ความรู้ Price Action ตามแนว Al Brooks (Brooks Trading Course)

> ไฟล์นี้สรุปแนวคิดที่โปรแกรมใช้ตรวจหา setup เขียนจากความรู้ทั่วไปเรื่อง Brooks price action
> **ยังไม่ได้ตรวจกับวิดีโอจริง** ให้เอาแต่ละหัวข้อไปถาม NotebookLM (ที่โหลดวิดีโอ Brooks ไว้)
> แล้วแก้ไฟล์นี้ + ค่าใน `tradepro/config.py` ให้ตรงกับคำตอบ
> ช่อง "ตรวจแล้ว" ให้ติ๊ก `[x]` เมื่อยืนยันกับ NotebookLM แล้ว
>
> คำตอบจาก NotebookLM ชุดแรก (30 ก.ย. 2569) เก็บไว้ที่ [`notebooklm/2026-09-30_answers.md`](notebooklm/2026-09-30_answers.md)

แต่ละกฎมีรหัส (เช่น `CTX-1`) ซึ่งอ้างถึงในโค้ดเป็นคอมเมนต์ จะได้ตามกลับมาหาได้ว่าโค้ดส่วนไหนมาจากกฎข้อไหน

---

## 1. บริบทตลาด (Market Context) — สำคัญที่สุด

Brooks เน้นว่า "context ก่อน setup" setup เดียวกันอาจดีในเทรนด์แต่แย่ในกรอบ

| รหัส | กฎ | ในโค้ด | ตรวจแล้ว |
|---|---|---|---|
| CTX-1 | ตลาดอยู่ในสภาวะ **เทรนด์** หรือ **กรอบ (trading range)** เสมอ และส่วนใหญ่ (~80%) ของความพยายาม breakout จากกรอบจะล้มเหลว | `indicators.add_features` (คอลัมน์ context) | [x] |
| CTX-2 | **เทรนด์ขาขึ้น**: ราคาปิดเหนือ EMA 20 เป็นส่วนใหญ่, EMA ชันขึ้น, ทำ higher high / higher low | `indicators.py` (ใช้สัดส่วนแท่งที่ปิดเหนือ EMA + ความชัน EMA) | [x] |
| CTX-3 | **เทรนด์ขาลง**: กลับด้านกับ CTX-2 | `indicators.py` | [x] |
| CTX-4 | **กรอบ**: แท่งเทียนซ้อนทับกันมาก (overlap) ไส้ยาวทั้งบนล่าง แท่งเขียวแดงใหญ่สลับกัน ราคาข้ามไปมา EMA บ่อย ใน range EMA20 เป็นแม่เหล็ก (fair value) ราคาวิ่งกลับมาหาเสมอ ส่วนเทรนด์มี micro gap ค้าง แท่งปิดใกล้ขอบ | `indicators.py` (ตอนนี้ใช้ EMA แบน + ราคาข้าม EMA; ยังไม่วัด overlap / micro gap) | [x] |
| CTX-5 | "Always in long / always in short" — ถ้าต้องอยู่ในตลาดตลอดเวลา ตอนนี้ควรถือฝั่งไหน ใช้ตัดสินทิศทางหลัก | ใช้ทิศของ context เป็นตัวกรองทิศ setup | [ ] |
| CTX-6 | ในกรอบ ให้ "buy low, sell high, scalp" ไม่ไล่ซื้อที่ขอบบน / ไม่ไล่ขายที่ขอบล่าง | setup `FAILED_BO` | [x] |

## 2. แท่งเทียน (Bars)

| รหัส | กฎ | ในโค้ด | ตรวจแล้ว |
|---|---|---|---|
| BAR-1 | **Trend bar** = ตัวแท่ง (body) ใหญ่เมื่อเทียบกับช่วงราคา (range) แสดงว่าฝั่งหนึ่งคุมตลาด | `indicators.add_features` (body_ratio) ≥ `trend_bar_body` | [ ] |
| BAR-2 | **Doji** = body เล็ก ไม่มีใครคุม ไม่ใช่ signal bar ที่ดี | `doji_body` ใน config | [x] |
| BAR-3 | **Bull signal bar ที่ดี**: strong bull reversal bar หรือ bull trend bar ที่มี body ชัด, ปิดใกล้ high หรืออย่างน้อยเหนือกึ่งกลางแท่ง, ไส้บนสั้น **ห้ามซื้อเหนือ doji หรือ bear bar** (ความน่าจะเป็นต่ำ) | `indicators.is_good_bull_signal` (close > open, body ≥ `doji_body`, close_pos ≥ `signal_close_pos` = 0.5) | [x] |
| BAR-4 | **Bear signal bar ที่ดี**: กลับด้านกับ BAR-3 | `indicators.is_good_bear_signal` | [x] |
| BAR-5 | Signal bar ที่ใหญ่มากทำให้ stop ไกล ความเสี่ยงสูง Brooks มักแนะนำให้ระวัง | `max_signal_bar_atr` | [ ] |
| BAR-6 | **Inside bar / Outside bar** — ii, ioi เป็นรูปแบบกรอบเล็ก ใช้เป็น breakout mode | ยังไม่ใช้ (งานถัดไป) | [ ] |

## 3. การนับขา Pullback: High 1/High 2 และ Low 1/Low 2

| รหัส | กฎ | ในโค้ด | ตรวจแล้ว |
|---|---|---|---|
| HL-1 | ในเทรนด์ขาขึ้น เมื่อเกิด pullback แท่งแรกที่ high สูงกว่า high ของแท่งก่อนหน้า = **High 1 (H1)** | `setups.count_highs` | [x] |
| HL-2 | ถ้า pullback ไปต่อ (มีแท่งที่ high ต่ำลงอีก) แล้วมีแท่ง high ทะลุแท่งก่อนหน้าอีกครั้ง = **High 2 (H2)** เป็น pullback 2 ขา (ABC) | `setups.count_highs` | [x] |
| HL-3 | **H2 ในเทรนด์ขาขึ้น** เป็น setup ซื้อที่น่าเชื่อถือที่สุดแบบหนึ่ง โดยเฉพาะ H2 ที่ EMA (20-bar EMA pullback) หรือ **20 EMA gap bar** (ย่อมาใกล้ EMA แต่ low ไม่แตะ แล้วกลับตัวขึ้น) ความน่าจะเป็น ~60–70% ในเทรนด์แรงที่มีแท่งยืนยัน, ~40–50% ในกรอบหรือเมื่อ signal bar เป็น doji / bear bar | setup `H2` (note "EMA pullback"; ยังไม่แยก gap bar) | [x] |
| HL-4 | **H1** ใช้ได้ในเทรนด์ที่แรงมาก (strong trend) เท่านั้น เพราะ pullback สั้น | setup `H1` (ต้อง `strong=True`) | [ ] |
| HL-5 | ถ้า H2 ล้มเหลว (ราคาหลุด low ของ signal bar) อาจกลายเป็นกรอบหรือกลับตัว; H3/H4 = wedge bull flag | ยังไม่ใช้ | [ ] |
| HL-6 | **Low 1 / Low 2** ในเทรนด์ขาลง กลับด้านกับ HL-1..HL-4 | setup `L1`, `L2` | [x] |
| HL-7 | Entry = **buy stop 1 tick เหนือ high ของ signal bar** (sell stop 1 tick ใต้ low สำหรับ short) | `setups._long` | [x] |
| HL-8 | ตัวนับ reset เมื่อ (1) ราคาทำ high ใหม่ของขาเทรนด์ (2) เกิด strong bull breakout (3) เกิด micro channel ขาขึ้นรอบใหม่ (สำหรับ L กลับด้าน) | `setups.count_highs`: (1) ใช้เสมอ, (2) มีใน `pb_reset_on_breakout` แต่ปิดไว้เพราะ backtest แย่ลง (ดูด้านล่าง), (3) ยังไม่ทำ | [x] |

## 4. Breakout และ Measured Move

| รหัส | กฎ | ในโค้ด | ตรวจแล้ว |
|---|---|---|---|
| BO-1 | **Breakout ที่แข็งแรง**: trend bar ใหญ่ ปิดใกล้ high/low ปิดนอกกรอบเดิม ไม่มี overlap กับแท่งก่อนมาก | setup `BO_BULL` / `BO_BEAR` | [x] |
| BO-2 | Measured move มี 3 แบบ: (ก) ความสูงของแท่ง/ชุด breakout (spike) (ข) ความสูงของกรอบ / double bottom / wedge บวกจากจุด breakout (ค) leg 1 = leg 2 | target ของ BO ใช้แบบ (ข) | [x] |
| BO-3 | Breakout ส่วนใหญ่จากกรอบล้มเหลว (CTX-1) ดังนั้น breakout ที่ไม่มี follow-through → เทรดกลับเข้ากรอบ = **failed breakout** | setup `FAILED_BO` | [x] |
| BO-4 | **Breakout pullback** — หลัง breakout ราคาย้อนมาทดสอบจุด breakout แล้วไปต่อ มักเป็น H1/H2 | ครอบคลุมบางส่วนโดย H1/H2 | [ ] |
| BO-5 | Measured move อีกแบบ: ขาแรก (leg 1) = ขาสอง (leg 2) ความยาวใกล้กัน | ยังไม่ใช้ | [x] |
| BO-6 | **เทรดตาม breakout** เฉพาะเมื่อ breakout bar ใหญ่ + มีแท่ง follow-through ปิดใกล้ high + มี micro gap ค้าง + ตลาดเปลี่ยนเป็น always in long ชัด ถ้าไม่ครบและอยู่ในกรอบ / broad channel ให้ fade (failed breakout, BO-3) | `bo_follow_through` (รอแท่ง follow-through ที่ low อยู่เหนือจุด breakout) ปิดไว้เพราะ backtest แย่ลง | [x] |

## 5. Stop, Target และการบริหารความเสี่ยง

| รหัส | กฎ | ในโค้ด | ตรวจแล้ว |
|---|---|---|---|
| RISK-1 | **Stop เริ่มต้น** = 1 tick ใต้ low ของ signal bar (long) / เหนือ high (short) | `setups` | [x] |
| RISK-2 | **Trader's equation**: ความน่าจะเป็น × reward ต้องมากกว่า (1−ความน่าจะเป็น) × risk | backtest รายงาน expectancy (R) | [x] |
| RISK-3 | Setup ความน่าจะเป็นต่ำ (เช่น ซื้อ H2 ก่อนเห็นแท่งยืนยัน หรือซื้อในกรอบ) ใช้ 2R–3R; setup ความน่าจะเป็นสูง (รอ breakout + follow-through) ใช้ 1R หรือ measured move / แนวต้านถัดไป Stop วางใต้ signal bar หรือใต้ major swing low | H1/H2/L1/L2 ใช้ `reward_r` = 2R; BO ใช้ measured move (อย่างน้อย `min_reward_r` = 1R) | [x] |
| RISK-4 | ขนาด position คำนวณจากระยะ stop (เสี่ยงเงินเท่ากันทุกเทรด) | `backtest` วัดผลเป็น R | [ ] |
| RISK-5 | ถ้าเข้าเทรดแล้วไม่ไปไหนหลายแท่ง ให้พิจารณาออก | `max_hold_bars` | [ ] |

## 6. การขายออก (สำหรับหุ้นที่ถืออยู่ — หน้า "พอร์ตของฉัน")

| รหัส | กฎ | ในโค้ด | ตรวจแล้ว |
|---|---|---|---|
| EXIT-1 | เลื่อน stop ตาม (trailing stop) ไว้ 1 tick ใต้ **swing low ล่าสุด** (higher low ของขาขึ้น) | `advisor.swing_low` | [ ] |
| EXIT-2 | ราคาปิดหลุด swing low ล่าสุด = ขาขึ้นเสียโครงสร้าง (lower low) → **ขาย** | `advisor.advise` | [ ] |
| EXIT-3 | บริบทเป็นขาลงและมีสัญญาณขายใหม่ (L1/L2, breakout ลง, failed breakout ขาขึ้น) → **ขาย** | `advisor.advise` | [ ] |
| EXIT-4 | มีสัญญาณขาย, ปิดใต้ EMA20, หรืออยู่ในกรอบและใกล้ขอบบน → **เฝ้าระวัง / ทยอยทำกำไร** | `advisor.advise` | [ ] |

## 7. รูปแบบกลับตัว (ยังไม่ได้เขียนโค้ด — งานถัดไป)

- **Wedge (3 pushes)** — 3 ขาดันที่อ่อนแรงลงเรื่อย ๆ มักกลับตัวอย่างน้อย 2 ขา
- **Double top / double bottom** และ **double top/bottom bull/bear flag**
- **Major trend reversal (MTR)** — ต้องมีการทะลุเส้นเทรนด์ก่อน แล้วทดสอบจุดสุดขั้วเดิม (higher low / lower high) ถึงเข้าเทรดกลับตัว
- **Final flag**, **climax / exhaustion**, **parabolic wedge**

---

## ผล backtest หลังปรับตามคำตอบ NotebookLM (30 ก.ย. 2569)

SET50 + US50 ตั้งแต่ 2015, ข้อมูล Yahoo, หักค่าคอม (SET 0.2%, US 0.05%) ทดสอบแต่ละ setup แยกกัน หน่วยเป็น R เฉลี่ยต่อเทรด

| การเปลี่ยน | ผล | ใช้เป็นค่าเริ่มต้น? |
|---|---|---|
| BAR-3: ไม่ซื้อเหนือ doji / bear bar, ปิดเหนือกึ่งกลาง | SET H2 +0.16 → +0.23R, SET L2 +0.20 → +0.27R แต่ SET FAILED_BO −0.05 → −0.15R, US H2/H1 แย่ลงเล็กน้อย (จำนวนเทรดน้อย ผลต่างส่วนใหญ่ยังอยู่ในช่วง noise) | ใช้ (ตรงตาม Brooks) |
| HL-8: reset H/L count เมื่อเกิด strong breakout | จำนวน H2 เพิ่มราว 3 เท่า, SET H2 +0.17 → +0.12R, SET L2 +0.20 → +0.07R | ไม่ใช้ (`pb_reset_on_breakout=False`) |
| BO-6: รอแท่ง follow-through ก่อนเข้า breakout | US BO_BULL +0.19 → −0.16R, SET BO_BULL +0.06 → −0.04R (เข้าช้าลง ราคาเข้าสูงขึ้น reward/risk แย่ลง) | ไม่ใช้ (`bo_follow_through=False`) |

คำถามที่ควรถาม NotebookLM ต่อ: Brooks นิยาม "strong bull breakout" ที่ทำให้ reset การนับ H1/H2 อย่างไร (ต้องทะลุอะไร), และบน daily chart ของหุ้นเขาเข้า breakout ตอนไหน (เหนือ breakout bar เลย หรือรอ follow-through) และวาง stop ตรงไหน

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
