"""Hold / sell advice for a stock you own, following ChalokeDotCom (docs/chaloke_wave3.md, EXIT-*).

  EXIT-1  Stop at the Previous Low (the latest swing low). A close below it means the wave count is
          wrong or the up move is over: cut / sell.
  EXIT-2  Lower high together with CDC Action Zone red or orange: the uptrend is over, sell.
  EXIT-3  CDC not green (yellow / orange / red / blue): watch, do not add.
  EXIT-4  "แมงเม่า" chase at the top: gap up + big white bar far above the CDC slow line: watch / take profit.

Action for the holding (what to do now):
  add   a fresh W3 first green on this stock that has not run away: buy more at the next open
  trim  price reached 161.8 / 261.8 / 423.6% of the live W3 wave: sell a third per target (W3-5),
        or a "แมงเม่า" chase at the top
  sell  status is sell
  hold  nothing to do
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .chaloke import CDC_TH
from .config import DEFAULT, Config
from .indicators import add_features
from .setups import detect
from .ticks import round_to_tick, tick_size
from .wave import cdc_action_zone

HOLD, WATCH, SELL = "hold", "watch", "sell"


@dataclass
class Advice:
    status: str
    price: float
    stop: float
    resistance: float | None
    context: str                      # CDC Action Zone colour
    reasons: list[str] = field(default_factory=list)
    buy_signals: list[str] = field(default_factory=list)
    as_of: pd.Timestamp | None = None
    action: str = "hold"              # add / trim / sell / hold
    action_text: str = ""


def swing_low(f: pd.DataFrame, lookback: int = 30, side: int = 2) -> float:
    """Most recent pivot low (lower than `side` bars on each side) in the last `lookback` bars."""
    low = f["low"].to_numpy()
    n = len(low)
    for i in range(n - 1 - side, max(side, n - lookback) - 1, -1):
        window = low[i - side:i + side + 1]
        if low[i] == window.min():
            return float(low[i])
    return float(low[-10:].min())


def swing_highs(f: pd.DataFrame, side: int = 3) -> list[float]:
    """Confirmed pivot highs, oldest first."""
    hi = f["high"].to_numpy()
    return [float(hi[i]) for i in range(side, len(hi) - side) if hi[i] == hi[i - side:i + side + 1].max()]


def advise(df: pd.DataFrame, cfg: Config = DEFAULT, recent_bars: int = 3) -> Advice:
    f = add_features(df, cfg)
    z = cdc_action_zone(f)
    last = f.iloc[-1]
    price = float(last.close)
    m = cfg.market
    zone = str(z["cdc_zone"].iloc[-1])
    cdc_name, cdc_meaning = CDC_TH.get(zone, ("-", ""))
    stop = round_to_tick(swing_low(f) - tick_size(price, m), up=False, market=m)          # EXIT-1
    highs = [h for h in swing_highs(f) if h > price]
    resistance = highs[-1] if highs else None
    sh = swing_highs(f)
    lower_high = len(sh) >= 2 and sh[-1] < sh[-2]
    prev = f.iloc[-2] if len(f) > 1 else last
    chase = (last.open > prev.high and last.close > last.open and last.body_ratio >= cfg.big_body
             and np.isfinite(last.atr) and price > float(z["cdc_slow"].iloc[-1]) + 2.5 * last.atr)
    recent = set(f.index[-recent_bars:])
    w3s = detect(df, "", cfg)
    buys = sorted({s.setup for s in w3s if s.date in recent})

    sell, watch = [], []
    if price < stop:
        sell.append("ราคาปิดหลุด Previous Low (swing low ล่าสุด) ลุงโฉลก: นับเวฟผิดหรือขาขึ้นจบ ต้อง cut")    # EXIT-1
    if zone in ("red", "orange") and lower_high:
        sell.append(f"CDC Action Zone เป็น{cdc_name} และเกิด lower high (ยอดต่ำลง) ขาขึ้นจบแล้ว")            # EXIT-2
    elif zone != "green":
        watch.append(f"CDC Action Zone เป็น{cdc_name}: {cdc_meaning}")                                    # EXIT-3
    if chase:
        watch.append("Gap ขึ้น + แท่งเขียวใหญ่ ณ ราคาที่วิ่งไกลจากเส้น CDC ระวังแมงเม่าไล่ราคาที่ยอดดอย")       # EXIT-4

    if sell:
        status, reasons = SELL, sell + watch
    elif watch:
        status, reasons = WATCH, watch
    else:
        status, reasons = HOLD, ["CDC Action Zone เขียว ขาขึ้น ถือต่อได้"]
    reasons.append(f"ขายถ้าราคาปิดต่ำกว่า {stop:,.2f} (ใต้ Previous Low)")
    if resistance:
        reasons.append(f"แนวต้าน/ยอดเดิม ~{resistance:,.2f} (swing high ก่อนหน้า)")
    action, action_text = _action(f, w3s, status, zone, chase, cfg)
    return Advice(status, price, stop, resistance, zone, reasons, buys, f.index[-1], action, action_text)


def _action(f: pd.DataFrame, w3s: list, status: str, zone: str, chase: bool, cfg: Config) -> tuple[str, str]:
    close, high = f["close"], f["high"]
    price = float(close.iloc[-1])
    if status == SELL:
        return "sell", "ขายทั้งหมดตามกฎ (ดูเหตุผล)"
    # the latest W3 wave still alive: no close below its stop since the signal
    live = None
    for s in reversed(w3s):
        after = close[close.index > s.date]
        if not (after < s.stop).any():
            live = s
        break
    recent = f.index[-cfg.w3_recent_bars:]
    if live is not None and live.date in recent and zone == "green" and price > live.stop:
        rr = (live.target - price) / (price - live.stop)
        if rr >= cfg.w3_min_rr:
            return "add", (f"W3 เขียวแรกเมื่อ {live.date:%Y-%m-%d} ซื้อเพิ่มได้ที่ราคาเปิดวันถัดไป stop {live.stop:,.2f} "
                           f"(R/R 1:{rr:.1f}) คำนวณจำนวนหุ้นจาก Maximum Damage ในหน้ากราฟ")
    if live is not None:
        t = [(161.8, live.target), (261.8, live.levels.get("t2")), (423.6, live.levels.get("t3"))]
        top = float(high[high.index > live.date].max()) if (high.index > live.date).any() else price
        hit = [(pct, px) for pct, px in t if px and top >= px]
        nxt = next(((pct, px) for pct, px in t if px and top < px), None)
        if hit:
            pct, px = hit[-1]
            return "trim", (f"ราคาถึงเป้า {pct}% ({px:,.2f}) ของ Wave 3 แล้ว ลุงโฉลก: ขายริน 1/3 ต่อเป้า "
                            f"รวมควรขายไปแล้ว {len(hit)} ใน 3 ส่วน"
                            + (f" · เป้าถัดไป {nxt[0]}% ที่ {nxt[1]:,.2f}" if nxt else " · ครบทุกเป้าแล้ว"))
        if nxt:
            return "hold", f"อยู่ใน Wave 3 (เขียวแรก {live.date:%Y-%m-%d}) ถือรอเป้าแรก 161.8% ที่ {live.target:,.2f} แล้วขาย 1/3"
    if chase:
        return "trim", "แมงเม่าไล่ราคาที่ยอด (gap + แท่งเขียวใหญ่ ไกลจากเส้น CDC) พิจารณาขายรินทำกำไรบางส่วน"
    if zone != "green":
        return "hold", "ยังไม่เขียว ไม่ซื้อเพิ่ม ถือตาม stop"
    return "hold", "ไม่มีจังหวะซื้อเพิ่มตามลุงโฉลก (รอ W3 เขียวแรกรอบใหม่) ถือตาม stop"
