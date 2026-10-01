/* Drawing tools on top of a Lightweight Charts candlestick chart (TradingView-style).
 * Shapes are stored as {date, price} points, so they stay put across timeframes and reloads
 * (localStorage, one list per stock). */
(function () {
  const SVGNS = "http://www.w3.org/2000/svg";
  const FIB = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 0.887, 0.942, 1];
  const FIB_EXT = [0.618, 1, 1.618, 2.618, 4.236];
  const WAVES = ["1", "2", "3", "4", "5", "A", "B", "C"];
  const COLOR = {line: "#2962ff", fib: "#8e5bd6", ext: "#0f8a5f", rect: "#e08a1e", measureUp: "#0f8a5f",
                 measureDown: "#c8373a", text: "#2962ff", wave: "#2458d6", box: "rgba(200,55,58,.14)"};
  const TOOLS = [
    // [id, icon, Thai label, points needed]
    ["cursor", "↖", "เลื่อน / ซูมกราฟ", 0],
    ["hline", "─", "เส้นแนวนอน (แนวรับ / แนวต้าน)", 1],
    ["trend", "╱", "เส้นแนวโน้ม", 2],
    ["fib", "Fib", "Fibonacci Retracement: คลิกจุดเริ่ม แล้วคลิกจุดจบของขา", 2],
    ["ext", "Ext", "Fibonacci Extension: คลิกฐาน W1 → ยอด W1 → ปลาย W2", 3],
    ["rect", "▭", "สี่เหลี่ยม / กล่องโซน", 2],
    ["measure", "↕%", "วัดระยะ: ราคาเปลี่ยนกี่ % และกี่แท่ง", 2],
    ["wave", "①", "ป้ายนับเวฟ 1-2-3-4-5-A-B-C (คลิกต่อกันได้)", 1],
    ["text", "T", "ข้อความ", 1],
    ["erase", "⌫", "ยางลบ: คลิกที่เส้นที่ต้องการลบ", 0],
  ];

  window.initDrawing = function ({chart, series, el, toolbar, candles, tf, storageKey}) {
    const times = candles.map(c => c.time);
    const dayMs = 86400000;
    const periodDays = {D: 1.45, W: 7, M: 30.4, Y: 365.25}[tf] || 1.45;   // calendar days per bar
    const lastIdx = times.length - 1;
    const lastMs = Date.parse(times[lastIdx]);

    // ---- storage
    const load = () => { try { return JSON.parse(localStorage.getItem(storageKey) || "[]"); } catch (e) { return []; } };
    const save = () => { try { localStorage.setItem(storageKey, JSON.stringify(shapes)); } catch (e) { /* private mode */ } };
    let shapes = load();
    let waveNext = 0;

    // ---- coordinates: point = {d: "YYYY-MM-DD", p: price}
    const iso = ms => new Date(ms).toISOString().slice(0, 10);
    function dateToLogical(d) {
      if (d > times[lastIdx]) return lastIdx + (Date.parse(d) - lastMs) / dayMs / periodDays;
      let lo = 0, hi = lastIdx;
      while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (times[mid] <= d) lo = mid; else hi = mid - 1; }
      return lo;
    }
    function toXY(pt) {
      const x = chart.timeScale().logicalToCoordinate(dateToLogical(pt.d));
      const y = series.priceToCoordinate(pt.p);
      return x == null || y == null ? null : [x, y];
    }
    function fromXY(x, y) {
      const logical = chart.timeScale().coordinateToLogical(x);
      const p = series.coordinateToPrice(y);
      if (logical == null || p == null) return null;
      const i = Math.round(logical);
      const d = i <= lastIdx ? times[Math.max(0, i)] : iso(lastMs + (i - lastIdx) * periodDays * dayMs);
      return {d, p};
    }

    // ---- overlay
    const wrap = el.parentElement;
    wrap.style.position = "relative";
    const svg = document.createElementNS(SVGNS, "svg");
    svg.classList.add("draw-layer");
    wrap.appendChild(svg);
    const node = (tag, attrs, parent = svg) => {
      const n = document.createElementNS(SVGNS, tag);
      for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
      parent.appendChild(n);
      return n;
    };
    const fmt = v => Number(v).toLocaleString(undefined, {maximumFractionDigits: v < 10 ? 3 : 2});

    function drawShape(s, preview) {
      const g = node("g", {class: "shape" + (preview ? " preview" : "")});
      g.dataset.id = s.id;
      const pts = s.pts.map(toXY);
      if (pts.some(p => p == null)) return;
      const W = chart.timeScale().width();
      const line = (x1, y1, x2, y2, color, extra = {}) =>
        node("line", {x1, y1, x2, y2, stroke: color, "stroke-width": 1.5, ...extra}, g);
      const label = (x, y, text, color, anchor = "start") =>
        node("text", {x, y, fill: color, "font-size": 11, "text-anchor": anchor, "dominant-baseline": "middle"}, g).textContent = text;
      const [a, b, c] = pts;
      if (s.type === "hline") {
        line(0, a[1], W, a[1], COLOR.line);
        label(4, a[1] - 8, fmt(s.pts[0].p), COLOR.line);
      } else if (s.type === "trend") {
        line(a[0], a[1], b[0], b[1], COLOR.line);
      } else if (s.type === "fib") {
        const [p0, p1] = [s.pts[0].p, s.pts[1].p];
        const x1 = Math.min(a[0], b[0]), x2 = Math.max(W, x1);
        const yOf = r => series.priceToCoordinate(p1 - (p1 - p0) * r);
        const y786 = yOf(0.786), y887 = yOf(0.887);
        if (y786 != null && y887 != null)       // Chaloke's buy box 78.6%-88.7%
          node("rect", {x: x1, y: Math.min(y786, y887), width: x2 - x1, height: Math.abs(y887 - y786), fill: COLOR.box}, g);
        line(a[0], a[1], b[0], b[1], COLOR.fib, {"stroke-dasharray": "3 3", opacity: 0.6});
        for (const r of FIB) {
          const y = yOf(r);
          if (y == null) continue;
          line(x1, y, x2, y, COLOR.fib, {"stroke-dasharray": r === 0 || r === 1 ? "" : "4 3", opacity: 0.85});
          label(x1 + 4, y - 7, `${r} (${fmt(p1 - (p1 - p0) * r)})`, COLOR.fib);
        }
      } else if (s.type === "ext") {
        line(a[0], a[1], b[0], b[1], COLOR.ext, {"stroke-dasharray": "3 3"});
        if (c) line(b[0], b[1], c[0], c[1], COLOR.ext, {"stroke-dasharray": "3 3"});
        if (c) {
          const leg = s.pts[1].p - s.pts[0].p;
          for (const r of FIB_EXT) {
            const price = s.pts[2].p + leg * r, y = series.priceToCoordinate(price);
            if (y == null) continue;
            line(c[0], y, W, y, COLOR.ext, {"stroke-dasharray": "4 3"});
            label(c[0] + 4, y - 7, `${(r * 100).toFixed(1)}% (${fmt(price)})`, COLOR.ext);
          }
        }
      } else if (s.type === "rect") {
        node("rect", {x: Math.min(a[0], b[0]), y: Math.min(a[1], b[1]), width: Math.abs(b[0] - a[0]),
                      height: Math.abs(b[1] - a[1]), fill: "rgba(224,138,30,.12)", stroke: COLOR.rect, "stroke-width": 1.5}, g);
      } else if (s.type === "measure") {
        const up = s.pts[1].p >= s.pts[0].p, color = up ? COLOR.measureUp : COLOR.measureDown;
        node("rect", {x: Math.min(a[0], b[0]), y: Math.min(a[1], b[1]), width: Math.abs(b[0] - a[0]),
                      height: Math.abs(b[1] - a[1]), fill: up ? "rgba(15,138,95,.14)" : "rgba(200,55,58,.14)"}, g);
        line(a[0], a[1], b[0], b[1], color, {"stroke-dasharray": "3 3"});
        const diff = s.pts[1].p - s.pts[0].p, pct = diff / s.pts[0].p * 100;
        const bars = Math.round(dateToLogical(s.pts[1].d) - dateToLogical(s.pts[0].d));
        const tx = (a[0] + b[0]) / 2, ty = up ? Math.min(a[1], b[1]) - 10 : Math.max(a[1], b[1]) + 12;
        label(tx, ty, `${diff >= 0 ? "+" : ""}${fmt(diff)} (${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%) · ${bars} แท่ง`, color, "middle");
      } else if (s.type === "wave" || s.type === "text") {
        const isWave = s.type === "wave";
        const t = node("text", {x: a[0], y: a[1], fill: isWave ? "#fff" : COLOR.text, "font-size": isWave ? 12 : 13,
                                "font-weight": 700, "text-anchor": "middle", "dominant-baseline": "middle"}, g);
        t.textContent = s.text;
        if (isWave) {
          const w = Math.max(18, s.text.length * 8 + 8);
          g.insertBefore(node("rect", {x: a[0] - w / 2, y: a[1] - 10, width: w, height: 20, rx: 3, fill: COLOR.wave}, g), t);
        }
      }
      // a wide invisible stroke so thin lines are easy to hit with the eraser
      g.querySelectorAll("line").forEach(l => {
        const hit = l.cloneNode(); hit.setAttribute("stroke", "transparent"); hit.setAttribute("stroke-width", 10);
        g.appendChild(hit);
      });
    }

    let pending = null, mouse = null;     // shape being placed, last cursor point
    function render() {
      svg.innerHTML = "";
      const W = chart.timeScale().width(), H = el.clientHeight - chart.timeScale().height();
      svg.setAttribute("width", W); svg.setAttribute("height", Math.max(0, H));
      shapes.forEach(s => drawShape(s, false));
      if (pending && mouse) drawShape({...pending, pts: [...pending.pts, mouse]}, true);
    }
    // redraw whenever the view changes (scroll, zoom, price-scale drag, resize)
    let sig = "";
    (function loop() {
      const r = chart.timeScale().getVisibleLogicalRange();
      const s = [r && r.from, r && r.to, series.priceToCoordinate(candles[lastIdx].close), el.clientWidth, el.clientHeight].join();
      if (s !== sig) { sig = s; render(); }
      requestAnimationFrame(loop);
    })();

    // ---- toolbar
    let tool = "cursor";
    const btns = {};
    TOOLS.forEach(([id, icon, title]) => {
      const b = document.createElement("button");
      b.type = "button"; b.className = "tool"; b.title = title; b.textContent = icon; b.setAttribute("aria-label", title);
      b.onclick = () => setTool(id);
      toolbar.appendChild(b); btns[id] = b;
    });
    const sep = document.createElement("span"); sep.className = "tool-sep"; toolbar.appendChild(sep);
    const undo = document.createElement("button");
    undo.type = "button"; undo.className = "tool"; undo.textContent = "↶"; undo.title = "ย้อนกลับ (ลบเส้นล่าสุด)";
    undo.onclick = () => { shapes.pop(); save(); render(); };
    const clear = document.createElement("button");
    clear.type = "button"; clear.className = "tool"; clear.textContent = "🗑"; clear.title = "ลบทุกเส้นของหุ้นตัวนี้";
    clear.onclick = () => { if (shapes.length && confirm("ลบเส้นที่วาดไว้ทั้งหมดของหุ้นตัวนี้?")) { shapes = []; save(); render(); } };
    toolbar.append(undo, clear);
    const hint = document.createElement("div"); hint.className = "tool-hint"; wrap.appendChild(hint);

    function setTool(id) {
      tool = id; pending = null;
      if (id === "wave") waveNext = 0;
      Object.entries(btns).forEach(([k, b]) => b.classList.toggle("on", k === id));
      const drawing = id !== "cursor" && id !== "erase";
      chart.applyOptions({handleScroll: !drawing, handleScale: !drawing});
      svg.classList.toggle("active", drawing);
      svg.classList.toggle("erasing", id === "erase");
      hint.textContent = id === "cursor" ? "" : TOOLS.find(t => t[0] === id)[2] + " · กด Esc เพื่อเลิก";
      render();
    }
    setTool("cursor");

    const local = e => { const r = svg.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
    svg.addEventListener("mousemove", e => {
      if (!pending) return;
      mouse = fromXY(...local(e)); render();
    });
    svg.addEventListener("click", e => {
      if (tool === "erase") {
        const g = e.target.closest("g.shape");
        if (g) { shapes = shapes.filter(s => String(s.id) !== g.dataset.id); save(); render(); }
        return;
      }
      const spec = TOOLS.find(t => t[0] === tool);
      if (!spec || !spec[3]) return;
      const pt = fromXY(...local(e));
      if (!pt) return;
      if (!pending) pending = {id: Date.now(), type: tool, pts: []};
      pending.pts.push(pt);
      if (pending.pts.length < spec[3]) return;
      if (tool === "text") {
        const t = prompt("ข้อความ");
        if (!t) { pending = null; render(); return; }
        pending.text = t;
      }
      if (tool === "wave") { pending.text = WAVES[waveNext % WAVES.length]; waveNext++; }
      shapes.push(pending); pending = null; save(); render();
    });
    document.addEventListener("keydown", e => {
      if (e.key === "Escape") setTool("cursor");
      if ((e.metaKey || e.ctrlKey) && e.key === "z" && document.activeElement === document.body) { shapes.pop(); save(); render(); }
    });
  };
})();
