"""Live checklist for one stock, following ChalokeDotCom's Wave 3 method (docs/chaloke_wave3.md).

Unlike setups.detect (which only fires on the first green bar), this describes where the stock is
right now: is there a wave 1-2 structure, how deep is wave 2, what colour is CDC Action Zone, what
the reward/risk would be if bought now, and which confirmations or warnings are present.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Config
from .indicators import add_features
from .ticks import round_to_tick, tick_size
from .wave import cdc_action_zone

CDC_TH = {
    "green": ("เขียว", "ขาขึ้น ซื้อ / ถือได้"),
    "yellow": ("เหลือง", "ขาขึ้นเริ่มอ่อนแรง ราคาหลุดเส้นเร็ว ระวัง"),
    "orange": ("ส้ม", "ขาขึ้นเสียทรง ราคาหลุดเส้นช้า เตรียมขาย"),
    "red": ("แดง", "ขาลง ห้ามซื้อ"),
    "lblue": ("ฟ้า", "ขาลงเริ่มฟื้น ราคาขึ้นเหนือเส้นเร็ว"),
    "blue": ("น้ำเงิน", "ขาลงฟื้นแรง ราคาเหนือเส้นช้า ใกล้เขียว"),
}
FIB = (0.618, 0.786, 0.887, 0.942)


def analyze(df: pd.DataFrame, cfg: Config) -> dict:
    f = add_features(df, cfg)
    z = cdc_action_zone(f)
    op, hi, lo, close, atr = (f[k].to_numpy() for k in ("open", "high", "low", "close", "atr"))
    n, k, m = len(f), cfg.w3_pivot_bars, cfg.market
    px = float(close[-1])
    zone = z["cdc_zone"].to_numpy()
    green = z["cdc_green"].to_numpy()

    # CDC: current zone, how long, and when the latest green run started
    since = 1
    while since < n and zone[-1 - since] == zone[-1]:
        since += 1
    first_green = None
    for i in range(n - 1, 0, -1):
        if green[i] and not green[i - 1]:
            first_green = i
            break
    cdc = {"zone": str(zone[-1]), "name": CDC_TH.get(zone[-1], ("-", ""))[0], "meaning": CDC_TH.get(zone[-1], ("", "-"))[1],
           "bars": since, "first_green": f.index[first_green].strftime("%Y-%m-%d") if first_green is not None else None,
           "first_green_ago": n - 1 - first_green if first_green is not None else None}

    # Wave 1: the most recent confirmed swing high that no later bar has exceeded, with a real leg below it
    wave = None
    for h in range(n - 1 - k, k - 1, -1):
        if hi[h] != hi[h - k:h + k + 1].max():
            continue
        if hi[h + 1:].max(initial=-np.inf) > hi[h]:
            break                              # price has made a higher high since: no wave 2 in progress
        b0 = max(0, h - cfg.w3_max_wave1_bars)
        b = b0 + int(np.argmin(lo[b0:h + 1]))
        top, base = float(hi[h]), float(lo[b])
        w1 = top - base
        if b < h and np.isfinite(atr[h]) and w1 >= cfg.w3_min_atr * atr[h]:
            w2i = h + int(np.argmin(lo[h:]))
            wave = {"h": h, "b": b, "top": top, "base": base, "w1": w1, "w2i": w2i, "w2": float(lo[w2i])}
        break

    checks, warnings, confirms = [], [], []
    out = {"price": px, "date": f.index[-1].strftime("%Y-%m-%d"), "cdc": cdc,
           "bar": {"time": f.index[-1].strftime("%Y-%m-%d"), "open": float(op[-1]), "high": float(hi[-1]),
                   "low": float(lo[-1]), "close": px}}

    # warnings that apply whatever the wave count (EXIT-5 / EXIT-6, "แมงเม่า" at the top)
    ph = [i for i in range(3, n - 3) if hi[i] == hi[i - 3:i + 4].max()]
    if zone[-1] in ("red", "orange") and len(ph) >= 2 and hi[ph[-1]] < hi[ph[-2]]:
        warnings.append("Lower high + CDC " + cdc["name"] + ": ขาขึ้นจบแล้ว ถ้าถืออยู่ควรขาย")
    last = f.iloc[-1]
    if (len(f) > 1 and op[-1] > hi[-2] and close[-1] > op[-1] and last.body_ratio >= cfg.trend_bar_body
            and np.isfinite(last.atr) and px > last.ema + 2.5 * last.atr):
        warnings.append("Gap ขึ้น + แท่งเขียวใหญ่ ณ ราคาที่วิ่งไกลจาก EMA ระวังแมงเม่าไล่ราคาที่ยอดดอย")

    if wave is None:
        status = ("new_high", "ราคาทำ high ใหม่ ไม่มี Wave 2 ให้รอ (อาจอยู่ใน Wave 3 หรือ Wave 1 ใหม่)") \
            if n > k and hi[-k:].max() >= hi[:-k].max(initial=-np.inf) else \
            ("no_wave", "ยังหาโครงสร้าง Wave 1–2 ที่ชัดไม่เจอ ห้ามรับมีด")
        out.update(status=status[0], status_text=status[1], wave=None, checks=checks, warnings=warnings,
                   confirms=confirms)
        return out

    top, base, w1, w2, w2i, h = (wave[x] for x in ("top", "base", "w1", "w2", "w2i", "h"))
    retr = (top - w2) / w1
    now_retr = (top - px) / w1
    stop = round_to_tick(w2 - tick_size(w2, m), up=False, market=m)
    t1, t2, t3 = (w2 + x * w1 for x in (1.618, 2.618, 4.236))
    rr = (t1 - px) / (px - stop) if px > stop else 0.0
    in_zone = cfg.w3_retrace_min <= retr <= cfg.w3_retrace_max
    broke_base = w2 <= base
    green_after_low = first_green is not None and first_green >= w2i
    fresh = green_after_low and first_green - w2i <= cfg.w3_max_bars_after_low

    checks.append((True, f"Wave 1: {base:,.2f} → {top:,.2f} (+{w1 / base * 100:.1f}%)"))
    checks.append((not broke_base, "ไม่หลุดฐาน Wave 1" if not broke_base else
                   f"หลุดฐาน Wave 1 ({w2:,.2f} < {base:,.2f}) นับเวฟผิด ต้องหาฐานใหม่"))
    checks.append((in_zone, f"Wave 2 ย่อ {retr * 100:.1f}% (ต่ำสุด {w2:,.2f})"
                   + (" · อยู่ใน sweet spot 78.6–88.7%" if 0.786 <= retr <= 0.887 else
                      " · อยู่ในโซน 61.8–94.2%" if in_zone else
                      " · ยังไม่ถึง 61.8%" if retr < cfg.w3_retrace_min else " · ลึกเกิน 94.2%")))
    checks.append((cdc["zone"] == "green", f"CDC Action Zone: {cdc['name']} ({cdc['bars']} แท่ง) — {cdc['meaning']}"))
    checks.append((rr >= cfg.w3_min_rr, f"ถ้าซื้อที่ราคานี้ R/R = 1:{rr:.1f} (ต้อง ≥ 1:{cfg.w3_min_rr:g})"))

    # confirmations (W3-7), same rules as setups
    body = f["body_ratio"].to_numpy()
    big = (body >= cfg.trend_bar_body) & ((hi - lo) >= atr)
    prev_close = np.r_[close[0], close[:-1]]
    tr = np.maximum(hi, prev_close) - np.minimum(lo, prev_close)
    atr_prev = np.r_[atr[0], atr[:-1]]
    seg = hi[h + k:n - 1]
    if len(seg):
        j2 = h + k + int(np.argmax(seg))
        if px > top + (hi[j2] - top) / (j2 - h) * (n - 1 - h):
            confirms.append("ราคา breakout เส้นแนวโน้มขาลงของ Wave 2")
    if any(op[j] > hi[j - 1] and big[j] and close[j] > op[j] for j in range(w2i + 1, n)):
        confirms.append("มี runaway gap + big white หลังปลาย Wave 2")
    for j in range(max(1, w2i - 3), min(n, w2i + 2)):
        if (op[j] < lo[j - 1] and big[j] and close[j] < op[j]) or (close[j] < op[j] and tr[j] >= 2 * atr_prev[j]):
            confirms.append("แมงเม่า panic sell ที่ปลาย Wave 2 (backtest: สัญญาณยืนยันที่ได้ผลดีที่สุด)")
            break

    if broke_base:
        status = ("broken", "หลุดฐาน Wave 1 การนับเวฟนี้ใช้ไม่ได้ รอฐานใหม่")
    elif retr < cfg.w3_retrace_min:
        status = ("shallow", f"Wave 2 ย่อแค่ {retr * 100:.1f}% ยังไม่ถึงโซนซื้อ รอดูต่อ (หรืออาจเป็น Running Flat)")
    elif retr > cfg.w3_retrace_max:
        status = ("deep", f"Wave 2 ย่อลึก {retr * 100:.1f}% เกิน 94.2% ระวังหลุดฐาน")
    elif not green_after_low:
        status = ("wait_green", "อยู่ในโซนซื้อ Wave 2 แล้ว รอ CDC เขียวแรก (ยังไม่เขียว ยังไม่ซื้อ)")
    elif rr < cfg.w3_min_rr:
        status = ("missed", f"เขียวแรกไปแล้วเมื่อ {cdc['first_green']} ราคาวิ่งไปไกล R/R เหลือ 1:{rr:.1f} ตกรถ ไม่ควรตาม")
    elif zone[-1] != "green":
        status = ("lost_green", f"เขียวแรกเมื่อ {cdc['first_green']} แต่ตอนนี้ CDC เป็น{cdc['name']}แล้ว รอเขียวใหม่")
    elif fresh:
        status = ("buy", f"เขียวแรกเมื่อ {cdc['first_green']} ({cdc['first_green_ago']} แท่งก่อน) "
                         "เข้าซื้อได้ที่ราคาเปิดแท่งถัดไป")
    else:
        status = ("late_green", f"เขียวมา {cdc['first_green_ago']} แท่งแล้ว ห่างปลาย Wave 2 นาน เข้าได้แต่ความได้เปรียบลดลง")

    checks = [(bool(ok), text) for ok, text in checks]
    out.update(status=status[0], status_text=status[1], checks=checks, warnings=warnings, confirms=confirms,
               wave={"base": base, "top": top, "w2": w2, "retrace": round(float(retr), 4),
                     "now_retrace": round(float(now_retr), 4),
                     "base_date": f.index[wave["b"]].strftime("%Y-%m-%d"),
                     "top_date": f.index[h].strftime("%Y-%m-%d"), "w2_date": f.index[w2i].strftime("%Y-%m-%d"),
                     "fib": {str(r): round(top - r * w1, 4) for r in FIB},
                     "stop": float(stop), "t1": round(float(t1), 4), "t2": round(float(t2), 4),
                     "t3": round(float(t3), 4), "rr": round(float(rr), 2)})
    return out
