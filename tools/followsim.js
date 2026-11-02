// Score following, simulated: a composed melody engraved over several pages, "played" as a stream
// of heard notes (with wrong, missing and extra notes), and the eyes (good, rough, elsewhere).
// window.__followSim(opts) -> per run: turns on time / early / late / missed
window.__followSim = async function ({ seeds = [1, 2, 3], audio = 'clean', gazeMode = 'none', bars = 72, staffMm = 8.5, when = 'bar' } = {}) {
  const M = await import('/js/compose/model.js');
  const E = await import('/js/compose/engrave.js');
  const F = await import('/js/follow.js');
  const { loadMusicFont } = await import('/js/ink.js'); await loadMusicFont();
  await document.fonts.load('100px Bravura').catch(() => {});
  const rnd = (seed) => { let s = seed >>> 0; return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; }; };
  const out = [];
  for (const seed of seeds) {
    const R = rnd(seed), pick = (a) => a[Math.floor(R() * a.length)];
    const key = pick([0, 1, 2, -1, -2, -3]);
    const S = M.newScore({ title: 'Study ' + seed, insts: ['violin'], time: [4, 4], key, bars });
    const st = S.parts[0].staves[0];
    let s0 = 34;
    // music repeats itself: phrases of four bars, used again and again
    const phrases = [];
    for (let m = 0; m < bars; m++) {
      if (m % 4 === 0 && phrases.length >= 2 && R() < 0.55) { const ph = pick(phrases); for (let q = 0; q < 4 && m + q < bars; q++) st.bars[m + q] = ph[q].map((ev) => ({ ...ev, id: M.newId(), notes: ev.notes.map((x) => ({ ...x })) })); m += 3; continue; }
      const evs = [];
      let left = 1920;
      while (left > 0) {
        const t = left >= 960 && R() < 0.15 ? 2 : left >= 480 && R() < 0.45 ? 4 : 8;
        s0 = Math.max(27, Math.min(43, s0 + pick([-2, -1, -1, 1, 1, 2, 0, -3, 3, 4, -4])));
        evs.push({ id: M.newId(), t, dots: 0, notes: [{ s: s0, a: M.keyAlter(key, s0) }] });
        left -= 1920 / t;
      }
      st.bars[m] = evs;
      if (m % 4 === 3) phrases.push([st.bars[m - 3], st.bars[m - 2], st.bars[m - 1], st.bars[m]]);
    }
    S.layout.staffMm = staffMm;
    const lay = E.layoutScore(S, {});
    // the truth: every note, its pitch class, page, line and place along the line
    const truth = [];
    lay.pages.forEach((pg, pi) => pg.systems.forEach((sy) => {
      const ms = []; for (const g of sy.groups) for (let m = g.m; m <= g.end; m++) ms.push(m);
      ms.forEach((m, k) => {
        const evs = st.bars[m]; let p = 0;
        evs.forEach((ev, q) => { if (ev.notes) truth.push({ m, pg: pi, yn: (sy.top + sy.height / 2) / lay.H, xn: 0.08 + 0.9 * (k + q / evs.length) / ms.length, pc: ((M.midiOf(ev.notes[0].s, ev.notes[0].a) % 12) + 12) % 12, lastBar: false }); p++; });
      });
    }));
    // the last bar of each page
    for (let i = 0; i < truth.length; i++) { const nx = truth.find((q, j) => j > i && q.pg !== truth[i].pg); const lastM = Math.max(...truth.filter((q) => q.pg === truth[i].pg).map((q) => q.m)); truth[i].lastBar = truth[i].m === lastM; void nx; }
    const pages = lay.pages.length;
    let page = 0; const turns = []; let k = 0; let gazeNow = null;
    const f = new F.PageFollower({
      render: async (i, c, w) => { const h = Math.round(w * lay.H / lay.W); c.width = w; c.height = h; const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, w, h); g.scale(w / lay.W, h / lay.H); E.drawPage(g, lay, i); },
      pages: () => pages,
      turn: () => { page++; turns.push({ k, page }); f.setPages(page, page); },
      onState: () => {},
      gaze: gazeMode === 'none' ? null : () => gazeNow,
      when: () => when,
    });
    await f.prepare();
    const G = rnd(seed * 31 + 7);
    const gauss = () => { let u = 0, v = 0; while (!u) u = G(); v = G(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); };
    const noise = { clean: [0, 0, 0], noisy: [0.15, 0.12, 0.06], bad: [0.3, 0.25, 0.1] }[audio];
    const bias = gazeMode === 'biased' ? 0.12 : 0;
    let t = 0, fixed = { page: 0, yn: 0.15, xn: 0.5 };
    for (k = 0; k < truth.length; k++) {
      const n = truth[k];
      // the eyes: a note or two ahead of the playing
      const ah = truth[Math.min(truth.length - 1, k + 2 + Math.floor(G() * 3))];
      const sg = gazeMode === 'good' ? 0.035 : gazeMode === 'rough' || gazeMode === 'biased' ? 0.09 : 0.05;
      if (gazeMode === 'away') gazeNow = G() < 0.03 ? null : { page: page, yn: fixed.yn + gauss() * 0.05, xn: fixed.xn, q: 0.8, sig: 0.08 };
      else if (gazeMode !== 'none') {
        // where the eyes are, on the pages on show (the next page is not on show until turned)
        let gp = ah.pg, gy = ah.yn + gauss() * sg + bias, gx = ah.xn + gauss() * 0.12;
        if (gp > page) { gp = page; gy = 0.95; gx = 0.9; }        // looking at the bottom, waiting for the turn
        if (gp < page) { gp = page; gy = 0.08; }
        gazeNow = G() < 0.08 ? null : { page: gp, yn: Math.max(0, Math.min(1, gy)), xn: gx, q: 0.8, sig: 0.08 };
      }
      // the sound: the note, maybe wrong, missing, or with an extra one
      const r = G();
      if (r < noise[1]) { t += 300; continue; }
      const pc = r < noise[1] + noise[0] ? (n.pc + 1 + Math.floor(G() * 11)) % 12 : n.pc;
      await f._heard({ mono: true, pc, t }); t += 300;
      if (G() < noise[2]) { await f._heard({ mono: true, pc: Math.floor(G() * 12), t }); t += 150; }
      // the player turns by hand if the page should have turned long ago
      const firstNext = truth.findIndex((q) => q.pg > page);
      if (firstNext >= 0 && k > firstNext + 10) { turns.push({ k, page: page + 1, hand: true }); page++; f.setPages(page, page); }
    }
    // judge each turn: from the start of the last bar up to two notes into the next page is right
    let good = 0, early = 0, late = 0, missed = 0; const det = [];
    for (let p = 0; p < pages - 1; p++) {
      const tr = turns.find((q) => q.page === p + 1);
      const lastStart = truth.findIndex((q) => q.pg === p && q.lastBar), firstNext = truth.findIndex((q) => q.pg === p + 1);
      if (!tr || tr.hand) { missed++; continue; }
      det.push(tr.k - firstNext);
      const from = when === 'line' ? truth.findIndex((q) => q.pg === p && q.yn >= Math.max(...truth.filter((z) => z.pg === p).map((z) => z.yn)) - 1e-6) : when === 'end' ? Math.max(lastStart, firstNext - 4) : lastStart;
      if (tr.k < from) early++; else if (tr.k > firstNext + 2) late++; else good++;
    }
    out.push({ seed, pages, notes: truth.length, good, early, late, missed, trust: +f.trust.toFixed(2), det });
  }
  return out;
};
