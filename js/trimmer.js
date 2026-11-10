// A trimmer as in Photos: small pictures of the video along a strip (or the waveform of a sound), a
// frame in the app's colour around the part kept, with a handle at each end. Drag a handle to trim;
// hold it still a moment and the strip opens out around it (a few seconds across the whole width)
// for the exact moment, the handle staying under the finger; let go and it closes again. A touch on
// the strip moves the playhead there.
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const fmt = (t, fine) => { t = Math.max(0, t); const m = Math.floor(t / 60), s = t - m * 60; return m + ':' + (fine ? s.toFixed(2).padStart(5, '0') : s.toFixed(1).padStart(4, '0')); };

export function createTrimmer(host, { dur, videoUrl = null, peaks = null, a = 0, b = null, onChange = () => {}, onSeek = () => {}, onEnd = () => {}, minLen = 0.3 }) {
  const T = { dur: Math.max(0.1, dur), a, b: b == null ? dur : b, view: null, head: 0, pics: [], gone: false };
  host.textContent = '';
  const wrap = document.createElement('div'); wrap.className = 'trimmer';
  wrap.innerHTML = '<canvas class="tr-strip"></canvas><div class="tr-dim l"></div><div class="tr-dim r"></div><div class="tr-box"></div>'
    + '<div class="tr-h l" role="slider" aria-label="Start"><i></i></div><div class="tr-h r" role="slider" aria-label="End"><i></i></div>'
    + '<div class="tr-head"></div><div class="tr-tip" hidden></div>';
  host.append(wrap);
  const $ = (s) => wrap.querySelector(s);
  const strip = $('.tr-strip'), L = $('.tr-h.l'), R = $('.tr-h.r'), box = $('.tr-box'), tip = $('.tr-tip'), headEl = $('.tr-head');
  const view = () => T.view || { a: 0, b: T.dur };
  const W = () => wrap.clientWidth || 300;
  const X = (t) => { const v = view(); return ((t - v.a) / (v.b - v.a)) * W(); };
  const tAt = (clientX) => { const r = wrap.getBoundingClientRect(), v = view(); return clamp(v.a + ((clientX - r.left) / r.width) * (v.b - v.a), 0, T.dur); };

  function place() {
    const w = W(), xa = X(T.a), xb = X(T.b);
    L.style.left = xa + 'px'; R.style.left = xb + 'px';
    L.style.visibility = xa >= -10 && xa <= w + 10 ? '' : 'hidden'; R.style.visibility = xb >= -10 && xb <= w + 10 ? '' : 'hidden';
    const c0 = clamp(xa, 0, w), c1 = clamp(xb, 0, w);
    box.style.left = c0 + 'px'; box.style.width = Math.max(0, c1 - c0) + 'px';
    $('.tr-dim.l').style.width = c0 + 'px'; $('.tr-dim.r').style.left = c1 + 'px';
    const xh = X(T.head); headEl.style.left = xh + 'px'; headEl.hidden = xh < 0 || xh > w;
  }
  function draw() {
    const dpr = Math.min(2, devicePixelRatio || 1), w = W(), h = wrap.clientHeight || 48;
    strip.width = Math.round(w * dpr); strip.height = Math.round(h * dpr);
    const g = strip.getContext('2d'); g.clearRect(0, 0, strip.width, strip.height);
    const v = view(), span = v.b - v.a;
    if (T.pics.length) {
      const ph = strip.height, pw = Math.max(6, Math.round(ph * (T.pics[0].c.width / T.pics[0].c.height)));
      for (let x = 0; x < strip.width; x += pw) {
        const t = v.a + ((x + pw / 2) / strip.width) * span;
        let best = T.pics[0]; for (const p of T.pics) if (Math.abs(p.t - t) < Math.abs(best.t - t)) best = p;
        g.drawImage(best.c, x, 0, pw, ph);
      }
    }
    if (peaks && peaks.length) {
      let max = 1e-4; for (const p of peaks) max = Math.max(max, p);
      const n = Math.floor(strip.width / (3 * dpr)), H = T.pics.length ? strip.height * 0.4 : strip.height * 0.8, base = T.pics.length ? strip.height - 3 * dpr : strip.height / 2;
      const col = getComputedStyle(wrap).getPropertyValue('--tr-wave').trim() || '#888';
      g.fillStyle = T.pics.length ? 'rgba(255,255,255,.85)' : col;
      for (let i = 0; i < n; i++) {
        const t0 = v.a + (i / n) * span, t1 = v.a + ((i + 1) / n) * span;
        const ia = Math.floor((t0 / T.dur) * peaks.length), ib = Math.max(ia + 1, Math.floor((t1 / T.dur) * peaks.length));
        let m = 0; for (let j = Math.max(0, ia); j < Math.min(peaks.length, ib); j++) m = Math.max(m, peaks[j]);
        const hh = Math.max(1.5 * dpr, Math.pow(m / max, 0.8) * H);
        if (T.pics.length) g.fillRect(i * 3 * dpr, base - hh, 2 * dpr, hh); else g.fillRect(i * 3 * dpr, base - hh / 2, 2 * dpr, hh);
      }
    }
    place();
  }
  // the small pictures, in the background (the strip shows them as they come)
  (async () => {
    if (!videoUrl) return;
    const v = document.createElement('video'); v.muted = true; v.playsInline = true; v.preload = 'auto'; v.src = videoUrl;
    await new Promise((res) => { v.onloadeddata = res; v.onerror = res; setTimeout(res, 4000); });
    if (!v.videoWidth) return;
    const ph = 96, pw = Math.max(24, Math.round(ph * (v.videoWidth / v.videoHeight)));
    const n = clamp(Math.round(T.dur * 2), 12, 100);
    for (let k = 0; k < n && !T.gone; k++) {
      const t = ((k + 0.5) / n) * T.dur;
      await new Promise((res) => { const done = () => { v.removeEventListener('seeked', done); res(); }; v.addEventListener('seeked', done); v.currentTime = t; setTimeout(done, 1200); });
      const c = document.createElement('canvas'); c.width = pw; c.height = ph;
      try { c.getContext('2d').drawImage(v, 0, 0, pw, ph); } catch {}
      T.pics.push({ t, c });
      if (k % 5 === 4) draw();
    }
    v.removeAttribute('src'); v.load(); draw();
  })();

  function showTip(side) {
    const t = T[side]; tip.hidden = false;
    tip.textContent = fmt(t, !!T.view) + '  ·  ' + fmt(T.b - T.a);
    // (kept inside the strip at its ends)
    const half = (tip.offsetWidth || 120) / 2; tip.style.left = clamp(X(t), half - 6, W() - half + 6) + 'px';
  }
  // the strip opening out around a handle held still, and closing again (a short glide)
  let raf = 0;
  function zoom(d, open) {
    const from = view();
    let to = { a: 0, b: T.dur };
    if (open) {
      const span = clamp(T.dur / 8, 2, 8); if (span >= T.dur * 0.8) return;
      const h = T[d.side], frac = (h - from.a) / Math.max(1e-3, from.b - from.a);
      const a2 = clamp(h - frac * span, 0, T.dur - span); to = { a: a2, b: a2 + span };
      d.zoomed = true; try { navigator.vibrate && navigator.vibrate(8); } catch {}
    }
    wrap.classList.toggle('zoomed', open); (d.side === 'a' ? L : R).classList.toggle('held', open);
    const t0 = performance.now(); cancelAnimationFrame(raf);
    const step = () => {
      const f = Math.min(1, (performance.now() - t0) / 220), e = 1 - Math.pow(1 - f, 3);
      T.view = open || f < 1 ? { a: from.a + (to.a - from.a) * e, b: from.b + (to.b - from.b) * e } : null;
      draw();
      if (f < 1) raf = requestAnimationFrame(step); else if (open) { d.off = T[d.side] - tAt(d.lastX ?? d.x0); showTip(d.side); }
    };
    step();
  }
  let drag = null;
  wrap.addEventListener('pointerdown', (e) => {
    const h = e.target.closest('.tr-h');
    try { wrap.setPointerCapture(e.pointerId); } catch {}
    e.preventDefault();
    if (h) {
      const side = h === L ? 'a' : 'b';
      drag = { side, x0: e.clientX, off: T[side] - tAt(e.clientX), hold: setTimeout(() => { if (drag && !drag.moved && drag.side) zoom(drag, true); }, 380) };
      showTip(side); return;
    }
    drag = { scrub: true }; T.head = tAt(e.clientX); place(); onSeek(T.head);
  });
  wrap.addEventListener('pointermove', (e) => {
    if (!drag) return;
    if (drag.scrub) { T.head = clamp(tAt(e.clientX), T.a, T.b); place(); onSeek(T.head); return; }
    if (Math.abs(e.clientX - drag.x0) > 6) drag.moved = true;
    drag.lastX = e.clientX;
    const want = tAt(e.clientX) + drag.off;
    if (drag.side === 'a') T.a = clamp(want, 0, T.b - minLen); else T.b = clamp(want, T.a + minLen, T.dur);
    // (opened out: the view follows the handle near an edge)
    if (T.view && drag.zoomed) { const v = T.view, span = v.b - v.a, h = T[drag.side]; if (h < v.a + span * 0.12 || h > v.b - span * 0.12) { const a2 = clamp(h - span / 2, 0, Math.max(0, T.dur - span)); T.view = { a: a2, b: a2 + span }; drag.off = T[drag.side] - tAt(e.clientX); draw(); } }
    T.head = T[drag.side]; place(); showTip(drag.side);
    onChange(T.a, T.b, drag.side); onSeek(T[drag.side]);
  });
  const end = () => {
    if (!drag) return;
    if (drag.side) { clearTimeout(drag.hold); if (drag.zoomed) zoom(drag, false); tip.hidden = true; onEnd(T.a, T.b); }
    drag = null;
  };
  wrap.addEventListener('pointerup', end); wrap.addEventListener('pointercancel', end);
  const ro = new ResizeObserver(() => draw()); ro.observe(wrap);
  draw();
  return {
    get a() { return T.a; }, get b() { return T.b; }, get zoomed() { return !!T.view; },
    set(a2, b2) { T.a = clamp(a2, 0, T.dur); T.b = clamp(b2, T.a + minLen, T.dur); place(); },
    head(t) { T.head = t; place(); },
    destroy() { T.gone = true; ro.disconnect(); host.textContent = ''; },
  };
}
