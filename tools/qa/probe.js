// QA probe, put into the page before it loads: errors, slow work, dropped frames, memory, and
// the state of the screen, gathered step by step for the QA robot.
(() => {
  const Q = window.__qa = { errors: [], long: [], frames: [], step: null };
  const err = (kind, msg) => Q.errors.push({ t: performance.now(), step: Q.step, kind, msg: String(msg).slice(0, 400) });
  window.addEventListener('error', (e) => err('error', (e.message || e) + (e.filename ? ' @' + e.filename.split('/').pop() + ':' + e.lineno : '')));
  window.addEventListener('unhandledrejection', (e) => err('rejection', (e.reason && (e.reason.stack || e.reason.message)) || e.reason));
  const ce = console.error; console.error = (...a) => { err('console', a.map((x) => (x && x.stack) || x).join(' ')); return ce.apply(console, a); };
  try { new PerformanceObserver((l) => { for (const e of l.getEntries()) Q.long.push({ t: e.startTime, d: Math.round(e.duration), step: Q.step }); }).observe({ entryTypes: ['longtask'] }); } catch {}
  let last = performance.now();
  const tick = (now) => { const d = now - last; last = now; if (d > 50 && !document.hidden) Q.frames.push({ t: now, d: Math.round(d), step: Q.step }); requestAnimationFrame(tick); };
  requestAnimationFrame(tick);
  // the screen, checked after each step
  Q.check = () => {
    const out = [];
    const vis = (el) => { if (!el || !el.isConnected) return false; const r = el.getBoundingClientRect(); if (r.width < 1 || r.height < 1) return false; const s = getComputedStyle(el); return s.visibility !== 'hidden' && s.display !== 'none' && +s.opacity > 0.02; };
    const panels = [...document.querySelectorAll('aside.panel')].filter((p) => !p.hidden && vis(p));
    if (panels.length > 1) out.push({ kind: 'two-panels', msg: panels.map((p) => p.id).join(', ') });
    const se = document.scrollingElement;
    if (se.scrollWidth > innerWidth + 2) out.push({ kind: 'page-scrolls-sideways', msg: se.scrollWidth + ' > ' + innerWidth });
    // buttons and inputs cut off by the screen's edge
    for (const el of document.querySelectorAll('button, input, select, label.btn, a[href]')) {
      if (!vis(el) || el.closest('details:not([open]) > :not(summary)')) continue;
      const r = el.getBoundingClientRect();
      if (r.right > innerWidth + 1 || r.left < -1 || r.bottom > innerHeight + 1) {
        // (inside something that scrolls: reachable by scrolling)
        let sc = el.parentElement, inScroll = false;
        while (sc && sc !== document.body) { const o = getComputedStyle(sc); if (/(auto|scroll)/.test(o.overflowY + o.overflowX) && (sc.scrollHeight > sc.clientHeight + 2 || sc.scrollWidth > sc.clientWidth + 2)) { inScroll = true; break; } sc = sc.parentElement; }
        if (inScroll) continue;
        out.push({ kind: 'offscreen-control', msg: (el.id || el.className || el.tagName) + ' ' + (el.textContent || el.value || '').trim().slice(0, 30) + ` [${Math.round(r.left)},${Math.round(r.top)},${Math.round(r.right)},${Math.round(r.bottom)}]` });
      }
    }
    // words cut off (text wider than its box, hidden)
    for (const el of document.querySelectorAll('button, .ttl, h2, h3, .hint, label, span, b')) {
      if (!vis(el) || el.children.length > 2) continue;
      const s = getComputedStyle(el);
      // (cut off with no '…' to say so; a '…' on purpose is the design)
      if ((s.overflow === 'hidden' || s.overflowX === 'hidden') && s.textOverflow !== 'ellipsis' && el.scrollWidth > el.clientWidth + 3 && !el.closest('#grid .card .ttl, .cmp')) out.push({ kind: 'text-cut', msg: (el.id || el.className || el.tagName) + ': ' + el.textContent.trim().slice(0, 40) });
    }
    // a toast that stays a long time
    const toast = document.querySelector('#toast');
    if (toast && !toast.hidden && vis(toast)) { Q.toastSince = Q.toastSince || performance.now(); if (performance.now() - Q.toastSince > 15000) out.push({ kind: 'toast-stuck', msg: toast.textContent.slice(0, 60) }); } else Q.toastSince = 0;
    return out;
  };
  Q.mem = () => (performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1048576) : null);
  // the page settles: no change on screen for a moment (or gives up after a while)
  Q.settle = (quiet = 180, max = 6000) => new Promise((res) => {
    const t0 = Q.actT || performance.now(); let lastMut = performance.now(); Q.firstChange = null;
    const mo = new MutationObserver(() => { lastMut = performance.now(); if (Q.firstChange === null) Q.firstChange = Math.round(lastMut - t0); });
    mo.observe(document.body, { subtree: true, childList: true, attributes: true, characterData: true });
    const loop = () => { const n = performance.now(); if (n - lastMut >= quiet || n - t0 > max) { mo.disconnect(); res(Math.round(lastMut - t0)); } else requestAnimationFrame(loop); };
    requestAnimationFrame(loop);
  });
})();
