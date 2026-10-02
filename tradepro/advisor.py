"""Hold / sell advice for a stock you own, following ChalokeDotCom (docs/chaloke_wave3.md, EXIT-*).

  EXIT-1  Stop at the Previous Low = the most significant low: the wave 2 low of the live W3 wave, else
          the wave 2 low of the wave being counted, else the latest clear swing low (5 bars each side). A close below it means the wave count is wrong: cut / sell, no conditions.
  EXIT-2  Lower high together with CDC Action Zone red or orange: the uptrend is over, sell.
  EXIT-3  CDC not green (yellow / orange / red / blue): watch, do not add.
  EXIT-4  "แมงเม่า" chase at the top: gap up + big white bar far above the CDC slow line: watch / take profit.

Action for the holding (what to do now):
  add   a fresh W3 first green on this stock that has not run away, and the holding is in profit
        ("never add to a losing position"): buy more at the next open, same stop
  trim  price reached 161.8 / 261.8 / 423.6% of the live W3 wave: sell a third per target (W3-5),
        or a "แมงเม่า" chase at the top
  sell  status is sell
  hold  nothing to do
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .chaloke import CDC_TH, analyze
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


def live_wave(f: pd.DataFrame, w3s: list):
    """The latest W3 signal whose stop has not been closed below since."""
    if not w3s:
        return None
    s = w3s[-1]
    after = f["close"][f.index > s.date]
    return None if (after < s.stop).any() else s


def significant_low(df: pd.DataFrame, f: pd.DataFrame, live, cfg: Config) -> tuple[float, str]:
    if live is not None:
        return live.levels.get("w2_low", live.stop), "ปลาย Wave 2 ของรอบ W3 นี้"
    wave = analyze(df, cfg).get("wave")
    price = float(f["close"].iloc[-1])
    if wave and wave["base"] < wave["w2"] < price:
        return wave["w2"], "ปลาย Wave 2 ของเวฟที่กำลังนับ"
    low, close = f["low"].to_numpy(), f["close"].to_numpy()
    n, side = len(low), 5
    # no wave to anchor on: trail under the latest clear swing low that price has not closed below,
    # as Chaloke moves the stop up to the previous low of each new sub-wave. A low in the last 5 bars
    # counts too if it is the lowest of the last 11 (not yet confirmed on the right).
    cands = [i for i in range(max(side, n - 60), n - side) if low[i] == low[i - side:i + side + 1].min()]
    k = n - side + int(np.argmin(low[n - side:]))
    if low[k] == low[max(0, n - 2 * side - 1):].min():
        cands.append(k)
    for i in sorted(cands, reverse=True):
        if not (close[i + 1:] < low[i]).any():
            return float(low[i]), "swing low สำคัญล่าสุด"
    return float(low[-60:].min()), "จุดต่ำสุดใน 60 แท่ง"


def advise(df: pd.DataFrame, cfg: Config = DEFAULT, recent_bars: int = 3, cost: float | None = None) -> Advice:
    f = add_features(df, cfg)
    z = cdc_action_zone(f)
    last = f.iloc[-1]
    price = float(last.close)
    m = cfg.market
    zone = str(z["cdc_zone"].iloc[-1])
    cdc_name, cdc_meaning = CDC_TH.get(zone, ("-", ""))
    w3s = detect(df, "", cfg)
    live = live_wave(f, w3s)
    low_px, low_name = significant_low(df, f, live, cfg)
    stop = round_to_tick(low_px - tick_size(low_px, m), up=False, market=m)                 # EXIT-1
    highs = [h for h in swing_highs(f) if h > price]
    resistance = highs[-1] if highs else None
    sh = swing_highs(f)
    lower_high = len(sh) >= 2 and sh[-1] < sh[-2]
    prev = f.iloc[-2] if len(f) > 1 else last
    chase = (last.open > prev.high and last.close > last.open and last.body_ratio >= cfg.big_body
             and np.isfinite(last.atr) and price > float(z["cdc_slow"].iloc[-1]) + 2.5 * last.atr)
    recent = set(f.index[-recent_bars:])
    buys = sorted({s.setup for s in w3s if s.date in recent})

    sell, watch = [], []
    if price < stop:
        sell.append(f"ราคาปิดหลุด Previous Low ({low_name}) ลุงโฉลก: นับเวฟผิด ต้อง cut ทันที")    # EXIT-1
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
    reasons.append(f"Cut ถ้าราคาปิดต่ำกว่า {stop:,.2f} (Previous Low: {low_name})")
    if resistance:
        reasons.append(f"แนวต้าน/ยอดเดิม ~{resistance:,.2f} (swing high ก่อนหน้า)")
    action, action_text = _action(f, live, status, zone, chase, cfg, cost)
    return Advice(status, price, stop, resistance, zone, reasons, buys, f.index[-1], action, action_text)


def _action(f: pd.DataFrame, live, status: str, zone: str, chase: bool, cfg: Config,
            cost: float | None = None) -> tuple[str, str]:
    close, high = f["close"], f["high"]
    price = float(close.iloc[-1])
    if status == SELL:
        return "sell", "ขายทั้งหมดตามกฎ (ดูเหตุผล)"
    recent = f.index[-cfg.w3_recent_bars:]
    if live is not None and live.date in recent and zone == "green" and price > live.stop:
        rr = (live.target - price) / (price - live.stop)
        if rr >= cfg.w3_min_rr and cost is not None and price < cost:
            return "hold", ("มีเขียวแรก W3 แต่ไม้เดิมยังขาดทุน ห้ามถัวเฉลี่ย "
                            "(ลุงโฉลก: Never add to a losing position)")
        if rr >= cfg.w3_min_rr:
            return "add", (f"W3 เขียวแรกเมื่อ {live.date:%Y-%m-%d} ซื้อเพิ่มได้ที่ราคาเปิดวันถัดไป stop {live.stop:,.2f} "
                           f"(R/R 1:{rr:.1f}) ไม้ใหม่ต้องคำนวณจำนวนหุ้นใหม่จาก Maximum Damage ในหน้ากราฟ")
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
