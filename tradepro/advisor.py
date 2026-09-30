"""Hold / sell advice for a stock you own, from Brooks-style price action on daily bars.

Exit rules (see docs/brooks_knowledge.md, section 6):
  EXIT-1  Trail the protective stop 1 tick below the most recent swing low (higher low).
  EXIT-2  A close below that swing low means the bull leg is broken: sell.
  EXIT-3  Bear context plus a fresh bear signal (L1/L2, bear breakout, failed bull breakout): sell.
  EXIT-4  A fresh bear signal, a close below the EMA, or price at the top of a trading range: watch / take profit.
  EXIT-5  (ChalokeDotCom) Lower high together with CDC Action Zone turning red: the uptrend is over, sell.
          CDC red alone: watch.
  EXIT-6  (ChalokeDotCom) "แมงเม่า" chase at the top: gap up + big white bar far above the EMA: watch / take profit.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd

from .config import DEFAULT, Config
from .indicators import BEAR, BULL, RANGE, add_features
from .setups import detect
from .wave import cdc_action_zone
from .ticks import round_to_tick, tick_size

HOLD, WATCH, SELL = "hold", "watch", "sell"


@dataclass
class Advice:
    status: str
    price: float
    stop: float
    resistance: float | None
    context: str
    reasons: list[str] = field(default_factory=list)
    buy_signals: list[str] = field(default_factory=list)
    as_of: pd.Timestamp | None = None


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
    last = f.iloc[-1]
    price = float(last.close)
    m = cfg.market
    stop = round_to_tick(swing_low(f) - tick_size(price, m), up=False, market=m)        # EXIT-1
    hi20 = float(f["high"].iloc[-21:-1].max())
    resistance = hi20 if hi20 > price else None

    recent = set(f.index[-recent_bars:])
    sigs = [s for s in detect(df.iloc[-250:], "", replace(cfg, long_only=False))
            if s.date in recent]
    bear = sorted({s.setup for s in sigs if s.direction == "short"})
    bull = sorted({s.setup for s in sigs if s.direction == "long"})
    ctx = last.context

    cdc = cdc_action_zone(f)
    cdc_red = bool(cdc["cdc_red"].iloc[-1])
    sh = swing_highs(f)
    lower_high = len(sh) >= 2 and sh[-1] < sh[-2]
    prev = f.iloc[-2] if len(f) > 1 else last
    chase = (last.open > prev.high and last.close > last.open and last.body_ratio >= cfg.trend_bar_body
             and np.isfinite(last.atr) and last.close > last.ema + 2.5 * last.atr)

    sell, watch = [], []
    if cdc_red and lower_high:
        sell.append("CDC Action Zone เป็นสีแดง และเกิด lower high (ยอดต่ำลง) ขาขึ้นจบแล้ว (ลุงโฉลก)")      # EXIT-5
    elif cdc_red:
        watch.append("CDC Action Zone เป็นสีแดง (ลุงโฉลก: ยังแดงอยู่ห้ามซื้อเพิ่ม)")
    if chase:
        watch.append("Gap ขึ้น + แท่งเขียวใหญ่ ณ ราคาที่วิ่งไกลจาก EMA มาก ระวังแมงเม่าไล่ราคาที่ยอดดอย")     # EXIT-6
    if price < stop:
        sell.append("ราคาปิดหลุด swing low ล่าสุด ขาขึ้นเสียโครงสร้าง")                          # EXIT-2
    if ctx == BEAR and bear:
        sell.append(f"เป็นเทรนด์ขาลงและมีสัญญาณขาย ({', '.join(bear)})")                     # EXIT-3
    if bear and ctx != BEAR:
        watch.append(f"มีสัญญาณขายล่าสุด ({', '.join(bear)})")                             # EXIT-4
    if ctx == BEAR and not bear:
        watch.append("ตลาดเป็นเทรนด์ขาลง (ราคาอยู่ใต้ EMA20 เป็นส่วนใหญ่)")
    if price < last.ema and ctx != BEAR:
        watch.append("ราคาปิดต่ำกว่า EMA20")
    if ctx == RANGE and np.isfinite(last.atr) and price >= hi20 - 0.5 * last.atr:
        watch.append("อยู่ในกรอบและราคาใกล้ขอบบน (Brooks: ในกรอบให้ขายที่ขอบบน)")

    if sell:
        status, reasons = SELL, sell + watch
    elif watch:
        status, reasons = WATCH, watch
    else:
        status = HOLD
        reasons = ["เทรนด์ขาขึ้น ราคายังเหนือ EMA20" if ctx == BULL else "ยังไม่มีสัญญาณขาย"]
    reasons.append(f"ขายถ้าราคาปิดต่ำกว่า {stop:,.2f} (ใต้ swing low ล่าสุด)")
    if resistance:
        reasons.append(f"แนวต้าน/จุดทำกำไรแรก ~{resistance:,.2f} (high 20 วัน)")
    return Advice(status, price, stop, resistance, ctx, reasons, bull, f.index[-1])
