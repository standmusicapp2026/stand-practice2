// Score following, simulated: a composed melody engraved over several pages, "played" as a stream
// of heard notes (with wrong, missing and extra notes), and the eyes (good, rough, elsewhere).
// window.__followSim(opts) -> per run: turns on time / early / late / missed
window.__followCello = async function ({ seeds = [1], bars = 40, staffMm = 8.5, bpm = 100, wrong = 0.06, noise = 0.004, when = 'bar', rubato = 0.06, slur = 0.5, inst = 'cello', lo = 20, hi = 34, startAt = 0, missProb = 0 } = {}) {
  const SM = await import('/js/sampler.js');
  const L = await import('/js/listen.js'); const SY = await import('/js/synth.js');
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
    const S = M.newScore({ title: 'Study ' + seed, insts: [inst], time: [4, 4], key, bars });
    const st = S.parts[0].staves[0];
    let s0 = Math.round((lo + hi) / 2);
    // music repeats itself: phrases of four bars, used again and again
    const phrases = [];
    for (let m = 0; m < bars; m++) {
      if (m % 4 === 0 && phrases.length >= 2 && R() < 0.55) { const ph = pick(phrases); for (let q = 0; q < 4 && m + q < bars; q++) st.bars[m + q] = ph[q].map((ev) => ({ ...ev, id: M.newId(), notes: ev.notes.map((x) => ({ ...x })) })); m += 3; continue; }
      const evs = [];
      let left = 1920;
      while (left > 0) {
        const t = left >= 960 && R() < 0.15 ? 2 : left >= 480 && R() < 0.45 ? 4 : 8;
        s0 = Math.max(lo, Math.min(hi, s0 + pick([-2, -1, -1, 1, 1, 2, 0, -3, 3, 4, -4])));
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
        evs.forEach((ev, q) => { if (ev.notes) truth.push({ midi: M.midiOf(ev.notes[0].s, ev.notes[0].a), dur: 4 / ev.t, m, pg: pi, yn: (sy.top + sy.height / 2) / lay.H, xn: 0.08 + 0.9 * (k + q / evs.length) / ms.length, pc: ((M.midiOf(ev.notes[0].s, ev.notes[0].a) % 12) + 12) % 12, lastBar: false }); p++; });
      });
    }));
    // the last bar of each page
    for (let i = 0; i < truth.length; i++) { const nx = truth.find((q, j) => j > i && q.pg !== truth[i].pg); const lastM = Math.max(...truth.filter((q) => q.pg === truth[i].pg).map((q) => q.m)); truth[i].lastBar = truth[i].m === lastM; void nx; }
    const pages = lay.pages.length;
    let page = 0; const turns = []; let k = 0;
    const f = new F.PageFollower({
      render: async (i, c, w) => { const h = Math.round(w * lay.H / lay.W); c.width = w; c.height = h; const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, w, h); g.scale(w / lay.W, h / lay.H); E.drawPage(g, lay, i); },
      pages: () => pages,
      turn: () => { page++; turns.push({ k, page, dbg: (window.__followDbg || []).slice(-14) }); f.setPages(page, page); },
      onState: () => {},
      when: () => when,
    });
    await f.prepare();
    f.on = true; window.__followDbg = [];
    // the sound: every note played by a bowed voice at the tempo, a few wrong notes, a little hiss
    const { getCtx } = await import('/js/audio.js'); const ctx = getCtx(); await ctx.resume();
    const bus = ctx.createGain(); bus.gain.value = 0.5;
    const hiss = ctx.createBufferSource(); { const b = ctx.createBuffer(1, ctx.sampleRate * 2, ctx.sampleRate); const d = b.getChannelData(0); for (let i = 0; i < d.length; i++) d[i] = (Math.random() * 2 - 1) * noise; hiss.buffer = b; hiss.loop = true; hiss.connect(bus); hiss.start(); }
    const G = rnd(seed * 31 + 7);
    const listener = new L.Listener((o) => f._heard(o));
    listener.attach(ctx, bus);
    // the cello: real recordings, slurred groups without a new bow, a little rubato, some wrong notes
    const smp = new SM.Sampler(); smp.attach(ctx, bus);
    const ch = smp.channel('p', inst, SM.DEFAULT_MIX ? SM.DEFAULT_MIX() : undefined);
    await smp.prepare(truth.map((n) => ({ sid: inst, midi: n.midi, kind: 'sus', vel: 0.7 })));
    const beat = 60 / bpm; let t = ctx.currentTime + 1.0; const at = [];
    let inSlur = false, prevMidi;
    const begin = truth.findIndex((q) => q.pg === 0 && q.m >= startAt);
    for (let i = 0; i < truth.length; i++) {
      if (i < Math.max(0, begin)) { at.push(-1); continue; }
      const n = truth[i]; let midi = n.midi;
      if (G() < wrong) midi += [-2, -1, 1, 2][Math.floor(G() * 4)];
      if (i % 4 === 0) inSlur = G() < slur;
      const connect = inSlur && i % 4 !== 0;
      if (!(G() < missProb)) {
        const sm = await smp.sampleFor(inst, midi, 'sus', 0.7);
        smp.noteOn(ch, sm, midi, t, n.dur * beat * 0.97, 0.6 + G() * 0.3, { connect, legato: connect, from: prevMidi });
      }
      prevMidi = midi;
      at.push(t); t += n.dur * beat * (1 + rubato * Math.sin(i / 7) + rubato * 0.5 * (G() - 0.5));
    }
    // follow along in real time: which note is sounding now (for judging the turns)
    const t0 = ctx.currentTime;
    while (ctx.currentTime < t + 0.5) {
      const now = ctx.currentTime; while (k < at.length - 1 && at[k + 1] <= now) k++; if (at[k] < 0) { await new Promise((r) => setTimeout(r, 40)); continue; }
      // the player turns by hand if the page should have turned long ago
      const firstNext = truth.findIndex((q) => q.pg > page);
      if (firstNext >= 0 && k > firstNext + 10) { turns.push({ k, page: page + 1, hand: true, dbg: (window.__followDbg || []).slice(-30) }); page++; f.setPages(page, page); }
      await new Promise((r) => setTimeout(r, 40));
    }
    listener.detach(); hiss.stop(); try { smp.stopAll(0.05); } catch {} bus.disconnect(); void t0;
    let good = 0, early = 0, late = 0, missed = 0; const det = [];
    for (let p = 0; p < pages - 1; p++) {
      const tr = turns.find((q) => q.page === p + 1);
      const lastStart = truth.findIndex((q) => q.pg === p && q.lastBar), firstNext = truth.findIndex((q) => q.pg === p + 1);
      if (!tr || tr.hand) { missed++; continue; }
      det.push(tr.k - firstNext);
      const lastY = Math.max(...truth.filter((z) => z.pg === p).map((z) => z.yn));
      let from;
      if (typeof when === 'number') {
        const lastM = truth[lastStart].m, prevStart = Math.min(lastStart, Math.max(0, truth.findIndex((q) => q.pg === p && q.m === lastM - 1)));
        const endI = Math.max(lastStart, firstNext - 2);
        const target = when <= 0.5 ? prevStart + (lastStart - prevStart) * (when / 0.5) : lastStart + (endI - lastStart) * ((when - 0.5) / 0.5);
        from = Math.round(target) - 3;
      } else from = when === 'line' ? truth.findIndex((q) => q.pg === p && q.yn >= lastY - 1e-6) : when === 'end' ? Math.max(lastStart, firstNext - 4) : lastStart;
      if (tr.k < from) early++; else if (tr.k > firstNext + 2) late++; else good++;
    }
    out.push({ seed, pages, notes: truth.length, good, early, late, missed, det, shift: f.shift, turns: turns.map((q) => ({ k: q.k, page: q.page, hand: q.hand, dbg: q.dbg })), firstNext: [...new Set(truth.map((q) => q.pg))].map((p) => truth.findIndex((q) => q.pg === p)), lastStart: [...new Set(truth.map((q) => q.pg))].map((p) => truth.findIndex((q) => q.pg === p && q.lastBar)) });
  }
  return out;
};
