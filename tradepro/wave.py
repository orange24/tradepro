"""Wave 2 end -> Wave 3 entry with CDC Action Zone (ChalokeDotCom style). Rule codes W3-* are in
docs/chaloke_wave3.md.

  W3-1  Wave 1 = a clear up leg from a base low B to a confirmed swing high H (at least w1_min_atr ATRs).
  W3-2  Wave 2 retraces 61.8%-94.2% of wave 1 (sweet spot 78.6%-88.7%) and stays above B.
  W3-3  Entry on the first CDC Action Zone green bar after the wave 2 low ("ยังไม่เขียว ยังไม่ซื้อ"),
        buying at the next day's open.
  W3-4  Stop just below the wave 2 low.
  W3-5  Targets: Fibonacci extensions of wave 1 from the wave 2 low: 161.8%, 261.8%, 423.6%.
  W3-6  Good stock: reward/risk to the 161.8% target of at least w3_min_rr (1:2).
  W3-7  Confirmations (shown, not required): break of the wave 2 down channel, runaway gap + big white,
        panic selling ("แมงเม่า") at the wave 2 low (gap down + big black, or an ATR spike), the first
        green bar itself a big white.
  RF-1  Running Flat (setup "RF"): wave 2 inside a bigger wave 3 retraces less than 61.8% (wave A),
        wave B makes a new high above the wave 1 top (Strong B), wave C pulls back without breaking
        the wave 1 base; buy at the open after the first CDC green after the C low, stop under C.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Config
from .indicators import ema
from .ticks import round_to_tick, tick_size


def cdc_action_zone(df: pd.DataFrame) -> pd.DataFrame:
    """CDC Action Zone V3: AP = EMA2(OHLC4), fast = EMA12(AP), slow = EMA26(AP).
    Green = fast > slow and AP > fast; red = fast < slow and AP < fast."""
    src = (df["open"] + df["high"] + df["low"] + df["close"]) / 4
    ap = ema(src, 2)
    fast, slow = ema(ap, 12), ema(ap, 26)
    green = (fast > slow) & (ap > fast)
    red = (fast < slow) & (ap < fast)
    bull = fast > slow
    # the six CDC zones: green / yellow / orange in a bull state, red / light blue / blue in a bear state
    zone = np.select(
        [green, bull & (ap < fast) & (ap > slow), bull & (ap <= slow),
         red, ~bull & (ap > fast) & (ap < slow), ~bull & (ap >= slow)],
        ["green", "yellow", "orange", "red", "lblue", "blue"], "")
    return pd.DataFrame({"cdc_ap": ap, "cdc_fast": fast, "cdc_slow": slow, "cdc_green": green, "cdc_red": red,
                         "cdc_zone": zone}, index=df.index)


def detect_wave3(f: pd.DataFrame, ticker: str, cfg: Config, signal_cls) -> list:
    """f: output of indicators.add_features. Returns long signals (setup "W3") entered at the next open."""
    z = cdc_action_zone(f)
    op, hi, lo, close, atr = (f[k].to_numpy() for k in ("open", "high", "low", "close", "atr"))
    body = f["body_ratio"].to_numpy()
    rng = hi - lo
    big = (body >= cfg.big_body) & (rng >= atr)
    big_white = big & (close > op)
    big_black = big & (close < op)
    gap_up = np.r_[False, op[1:] > hi[:-1]]
    gap_down = np.r_[False, op[1:] < lo[:-1]]
    prev_close = np.r_[close[0], close[:-1]]
    tr = np.maximum(hi, prev_close) - np.minimum(lo, prev_close)
    atr_prev = np.r_[atr[0], atr[:-1]]
    green = z["cdc_green"].to_numpy()
    k, n = cfg.w3_pivot_bars, len(f)
    m = cfg.market
    # swing high at j: highest high of j-k..j+k (only known k bars later)
    is_ph = np.zeros(n, bool)
    for j in range(k, n - k):
        is_ph[j] = hi[j] == hi[j - k:j + k + 1].max()

    out, used = [], set()
    for i in range(1, n):
        if not green[i] or green[i - 1]:
            continue                                      # W3-3: first green bar only
        cand = [j for j in range(max(0, i - cfg.w3_max_wave2_bars), i - k + 1) if is_ph[j]]
        if not cand:
            continue
        h = cand[-1]                                      # most recent confirmed swing high = wave 1 top
        top = hi[h]
        if (h in used and not cfg.w3_reentry) or hi[h + 1:i + 1].max(initial=-np.inf) > top:
            continue                                      # already traded, or price already above wave 1 top
        b0 = max(0, h - cfg.w3_max_wave1_bars)
        b = b0 + int(np.argmin(lo[b0:h + 1]))
        base = lo[b]
        w1 = top - base
        if b == h or not np.isfinite(atr[h]) or w1 < cfg.w3_min_atr * atr[h]:
            continue                                      # W3-1: wave 1 must be a real leg
        w2i = h + int(np.argmin(lo[h:i + 1]))
        w2 = lo[w2i]
        retr = (top - w2) / w1
        if not (cfg.w3_retrace_min <= retr <= cfg.w3_retrace_max) or w2 <= base:
            continue                                      # W3-2
        if i - w2i > cfg.w3_max_bars_after_low:
            continue                                      # green came too long after the wave 2 low
        ref = base if cfg.w3_stop_ref == "base" else w2
        stop = round_to_tick(ref - tick_size(ref, m), up=False, market=m)                   # W3-4
        t1, t2, t3 = (w2 + x * w1 for x in (1.618, 2.618, 4.236))                            # W3-5
        rr = (t1 - close[i]) / (close[i] - stop) if close[i] > stop else 0.0
        if rr < cfg.w3_min_rr:
            continue                                      # W3-6: stop too far for the reward (or ran away)
        used.add(h)

        # W3-7 confirmations
        conf = []
        seg = hi[h + k:i]                                 # lower highs of wave 2 after the top
        if len(seg):
            j2 = h + k + int(np.argmax(seg))
            line = top + (hi[j2] - top) / (j2 - h) * (i - h)
            if close[i] > line:
                conf.append("breakout กรอบขาลง")
        if any(gap_up[j] and big_white[j] for j in range(w2i + 1, i + 1)):
            conf.append("runaway gap + big white")
        if big_white[i]:
            conf.append("เขียวแรกเป็นแท่งเขียวยาว (big white)")
        near = range(max(1, w2i - 3), min(n, w2i + 2))
        if any((gap_down[j] and big_black[j]) or (close[j] < op[j] and tr[j] >= 2 * atr_prev[j]) for j in near):
            conf.append("แมงเม่า panic sell ที่ปลาย W2")
        zone = "sweet spot" if 0.786 <= retr <= 0.887 else ""
        note = (f"W1 {base:,.2f}→{top:,.2f} · ย่อ {retr * 100:.1f}%{' (' + zone + ')' if zone else ''}"
                f" · เป้า 261.8% {t2:,.2f} · 423.6% {t3:,.2f}"
                + (f" · ยืนยัน: {', '.join(conf)}" if conf else ""))
        out.append(signal_cls(ticker, f.index[i], "W3", "long", round(float(close[i]), 4), stop,
                              round(float(t1), 4), str(z["cdc_zone"].iloc[i]), note, order="open",
                              max_hold=cfg.w3_max_hold_bars,
                              levels={"w1_base": round(float(base), 4), "w1_top": round(float(top), 4),
                                      "w2_low": round(float(w2), 4), "retrace": round(float(retr), 3),
                                      "fib_786": round(float(top - 0.786 * w1), 4),
                                      "fib_887": round(float(top - 0.887 * w1), 4),
                                      "t2": round(float(t2), 4), "t3": round(float(t3), 4),
                                      "sweet": bool(zone), "confirm": conf}))
    return out


def detect_running_flat(f: pd.DataFrame, ticker: str, cfg: Config, signal_cls) -> list:
    """RF-1: 1-A-B-C running flat (Strong B), entered like W3 on the first green bar after the C low.
    Targets are wave 1 extensions from the C low (161.8 / 261.8 / 423.6%)."""
    z = cdc_action_zone(f)
    op, hi, lo, close, atr = (f[k].to_numpy() for k in ("open", "high", "low", "close", "atr"))
    big_white = (f["body_ratio"].to_numpy() >= cfg.big_body) & ((hi - lo) >= atr) & (close > op)
    green = z["cdc_green"].to_numpy()
    k, n, m = cfg.w3_pivot_bars, len(f), cfg.market
    is_ph = np.zeros(n, bool)
    for j in range(k, n - k):
        is_ph[j] = hi[j] == hi[j - k:j + k + 1].max()

    out, used = [], set()
    for i in range(1, n):
        if not green[i] or green[i - 1]:
            continue
        cand = [j for j in range(max(0, i - cfg.w3_max_wave2_bars), i - k + 1) if is_ph[j]]
        if not cand:
            continue
        hb = cand[-1]                                     # B top: latest swing high, not exceeded since
        if hb in used or hi[hb + 1:i + 1].max(initial=-np.inf) > hi[hb]:
            continue
        ci = hb + int(np.argmin(lo[hb:i + 1]))            # C low
        c = lo[ci]
        if i - ci > cfg.w3_max_bars_after_low:
            continue
        # wave 1 top: an earlier swing high below B; between them a shallow wave A
        for h1 in (j for j in range(hb - 1, max(0, hb - cfg.w3_max_wave2_bars), -1) if is_ph[j]):
            if hi[h1] >= hi[hb]:
                break                                     # B must be a new high above wave 1
            b0 = max(0, h1 - cfg.w3_max_wave1_bars)
            b = b0 + int(np.argmin(lo[b0:h1 + 1]))
            base, top = lo[b], hi[h1]
            w1 = top - base
            if b == h1 or not np.isfinite(atr[h1]) or w1 < cfg.w3_min_atr * atr[h1]:
                continue
            ai = h1 + int(np.argmin(lo[h1:hb + 1]))
            a_retr = (top - lo[ai]) / w1
            if not (0 < a_retr < cfg.w3_retrace_min) or c <= base:
                break                                     # A too deep (a normal wave 2) or C broke the base
            stop = round_to_tick(c - tick_size(c, m), up=False, market=m)
            t1, t2, t3 = (c + x * w1 for x in (1.618, 2.618, 4.236))
            rr = (t1 - close[i]) / (close[i] - stop) if close[i] > stop else 0.0
            if rr < cfg.w3_min_rr:
                break
            used.add(hb)
            conf = ["เขียวแรกเป็นแท่งเขียวยาว (big white)"] if big_white[i] else []
            note = (f"Running Flat: W1 {base:,.2f}→{top:,.2f} · A ย่อ {a_retr * 100:.1f}% · Strong B {hi[hb]:,.2f}"
                    f" · C {c:,.2f} · เป้า 261.8% {t2:,.2f} · 423.6% {t3:,.2f}"
                    + (f" · ยืนยัน: {', '.join(conf)}" if conf else ""))
            out.append(signal_cls(ticker, f.index[i], "RF", "long", round(float(close[i]), 4), stop,
                                  round(float(t1), 4), str(z["cdc_zone"].iloc[i]), note, order="open",
                                  max_hold=cfg.w3_max_hold_bars,
                                  levels={"w1_base": round(float(base), 4), "w1_top": round(float(top), 4),
                                          "b_top": round(float(hi[hb]), 4), "w2_low": round(float(c), 4),
                                          "retrace": round(float(a_retr), 3),
                                          "fib_786": round(float(top - 0.786 * w1), 4),
                                          "fib_887": round(float(top - 0.887 * w1), 4),
                                          "t2": round(float(t2), 4), "t3": round(float(t3), 4),
                                          "sweet": False, "confirm": conf}))
            break
    return out
