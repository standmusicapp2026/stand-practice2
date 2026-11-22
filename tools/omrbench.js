// Benchmark for the music reader: random but musical passages engraved in several music fonts,
// clean and scanned-looking, read back and compared with what was written.
// Runs in the page: window.__bench(opts) -> results.
window.__bench = async function ({ fonts = ['Bravura'], seeds = [1, 2, 3], looks = ['clean', 'scan'], verbose = false } = {}) {
  const M = await import('/js/compose/model.js');
  const E = await import('/js/compose/engrave.js');
  const O = await import('/js/omr.js');
  const { loadMusicFont } = await import('/js/ink.js'); await loadMusicFont();
  for (const f of fonts) if (f !== 'Bravura') { try { const ff = new FontFace(f, `url(/_fonts/${f}.otf)`); await ff.load(); document.fonts.add(ff); } catch {} }
  await document.fonts.load('100px Bravura').catch(() => {});
  const rnd = (seed) => { let s = seed >>> 0; return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; }; };

  function make(seed) {
    const R = rnd(seed), pick = (a) => a[Math.floor(R() * a.length)];
    const time = pick([[4, 4], [3, 4], [2, 4], [6, 8]]);
    const key = pick([0, 1, 2, -1, -2, -3, 3]);
    const S = M.newScore({ title: '', insts: ['violin'], time, key, bars: 6 });
    const st = S.parts[0].staves[0];
    S.spans = []; S._v2spans = 1;
    let lastS = 30 + 4;
    const note = (t, dots = 0) => {
      lastS = Math.max(27, Math.min(43, lastS + pick([-2, -1, -1, 1, 1, 2, 0, -3, 3])));
      const ev = { id: M.newId(), t, dots, notes: [{ s: lastS, a: M.keyAlter(key, lastS) }] };
      if (R() < 0.08) ev.notes[0].a += pick([1, -1]);
      return ev;
    };
    const barT = M.barTicks(time);
    for (let m = 0; m < 6; m++) {
      const evs = [];
      let left = barT;
      const beat = time[1] === 8 ? 720 : 480;
      while (left > 0) {
        let group;
        const r = R();
        if (time[1] === 8) group = left >= 720 ? pick([[[8], [8], [8]], [[4], [8]], [[4, 1]], [[16], [16], [8], [8]]]) : [[8]];
        else if (left >= 960 && r < 0.15) group = [[2]];
        else if (left >= 960 && r < 0.25) group = [[4, 1], [8]];
        else if (r < 0.45) group = [[8], [8]];
        else if (r < 0.6) group = [[16], [16], [16], [16]];
        else if (r < 0.7 && left >= 480) group = [['r', 4]];
        else if (r < 0.78) group = [[8, 1], [16]];
        else group = [[4]];
        const len = group.reduce((a, g) => a + (g[0] === 'r' ? 1920 / g[1] : (1920 / g[0]) * (g[1] ? 1.5 : 1)), 0);
        if (len > left) group = [['r', 8]].filter(() => left >= 240).concat([]);
        if (!group.length) { group = [[16]]; }
        const gEvs = group.map((g) => (g[0] === 'r' ? { id: M.newId(), rest: true, t: g[1], dots: 0 } : note(g[0], g[1] || 0)));
        const glen = gEvs.reduce((a, e) => a + M.evTicks(e), 0);
        if (glen > left) { evs.push(...M.restsFor(barT - left, left, time)); left = 0; break; }
        evs.push(...gEvs); left -= glen;
      }
      st.bars[m] = evs;
    }
    // marks
    const all = [];
    st.bars.forEach((b, m) => { let p = 0; b.forEach((e) => { all.push({ e, m, pos: p }); p += M.ticksOf(e, time); }); });
    const notes = all.filter((x) => !x.e.rest);
    for (const x of notes) {
      const r = R();
      if (r < 0.12) x.e.art = ['stacc'];
      else if (r < 0.18) x.e.art = ['acc'];
      else if (r < 0.22) x.e.art = ['ten'];
      else if (r < 0.24) x.e.art = [pick(['trill', 'mord', 'prall', 'ferm', 'marc'])];
      if (R() < 0.18) x.e.fing = String(pick([0, 1, 2, 3, 4]));
    }
    // dynamics on a few notes, hairpins, slurs over runs, a tie
    for (let i = 0; i < notes.length; i += 5 + Math.floor(R() * 6)) notes[i].e.dyn = pick(['p', 'pp', 'mf', 'f', 'ff', 'mp', 'sfz']);
    for (let i = 1; i + 2 < notes.length; i += 4 + Math.floor(R() * 5)) {
      const k = R();
      const a = notes[i], b = notes[Math.min(notes.length - 1, i + 1 + Math.floor(R() * 3))];
      if (k < 0.55) S.spans.push({ id: M.newId(), kind: 'slur', st: st.id, v: 1, a: { m: a.m, pos: a.pos }, b: { m: b.m, pos: b.pos } });
      else if (k < 0.8 && !a.e.dyn) S.spans.push({ id: M.newId(), kind: 'hairpin', st: st.id, v: 1, dir: pick(['<', '>']), a: { m: a.m, pos: a.pos }, b: { m: b.m, pos: b.pos } });
    }
    S.layout.staffMm = 7;
    return { S, st, time, key };
  }

  function degrade(c, look, R) {
    if (look === 'clean') return c;
    const d = document.createElement('canvas');
    const k = look === 'small' ? 0.62 : 1;
    d.width = Math.round(c.width * k); d.height = Math.round(c.height * k);
    const g = d.getContext('2d');
    g.fillStyle = '#efe9dc'; g.fillRect(0, 0, d.width, d.height);
    g.filter = `blur(${look === 'small' ? 0.4 : 0.8}px)`;
    g.translate(d.width / 2, d.height / 2); g.rotate(((R() - 0.5) * 1.4 * Math.PI) / 180); g.translate(-d.width / 2, -d.height / 2);
    g.drawImage(c, 0, 0, d.width, d.height);
    g.filter = 'none'; g.setTransform(1, 0, 0, 1, 0, 0);
    const im = g.getImageData(0, 0, d.width, d.height);
    for (let i = 0; i < im.data.length; i += 4) { const n = (R() - 0.5) * 46; for (let j = 0; j < 3; j++) im.data[i + j] = Math.max(0, Math.min(255, im.data[i + j] + n)); }
    g.putImageData(im, 0, 0);
    return d;
  }

  const results = [];
  for (const font of fonts) for (const seed of seeds) for (const look of looks) {
    E.setMusicFont(font);
    const { S, st, time, key } = make(seed);
    const lay = E.layoutScore(S, {});
    const pg0 = lay.pages[0];
    const sys0 = pg0.systems[0], sysN = pg0.systems[pg0.systems.length - 1];
    const px = 15;
    const top = sys0.top - 9, bot = sysN.top + sysN.height + 9;
    const c = document.createElement('canvas'); c.width = Math.round(lay.W * px); c.height = Math.round((bot - top) * px);
    const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height); g.scale(px, px); g.translate(0, -top); E.drawPage(g, lay, 0);
    const pic = degrade(c, look, rnd(seed * 7 + 1));
    E.setMusicFont('Bravura');
    let r = null;
    try { r = await O.recogniseBest(pic, {}); } catch (err) { results.push({ font, seed, look, err: String(err) }); continue; }
    // ---- compare
    const truth = [];
    st.bars.forEach((b, m) => b.forEach((e) => { if (e.full) return; truth.push({ m, rest: !!e.rest, t: e.t, dots: e.dots || 0, s: e.rest ? null : e.notes[0].s, art: e.art || [], dyn: e.dyn || null, fing: e.fing || null, tie: !e.rest && e.notes.some((n) => n.tie) }); }));
    const read = [];
    if (r) r.bars.forEach((b, m) => b.forEach((it) => { if (it.full) return; read.push({ m, rest: !!it.rest, t: it.t, dots: it.dots || 0, s: it.rest ? null : 30 + it.ps[it.ps.length - 1] + ({ treble: 0, bass: -12, alto: -6, tenor: -8 }[r.clef] || 0), art: it.art || [], dyn: it.dyn || null, fing: it.fing || null, tie: !!(it.ties && it.ties.length), slurStart: !!it.slurStart, slurEnd: !!it.slurEnd, hp: it.hp || null }); }));
    // align by order (LCS on rhythm+pitch)
    const key2 = (x) => (x.rest ? 'r' + x.t : x.s + '/' + x.t + '.' + x.dots);
    const n = truth.length, mm = read.length;
    const L = Array.from({ length: n + 1 }, () => new Int16Array(mm + 1));
    for (let i = n - 1; i >= 0; i--) for (let j = mm - 1; j >= 0; j--) L[i][j] = key2(truth[i]) === key2(read[j]) ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
    const pairs = []; { let i = 0, j = 0; while (i < n && j < mm) { if (key2(truth[i]) === key2(read[j])) { pairs.push([i, j]); i++; j++; } else if (L[i + 1][j] >= L[i][j + 1]) i++; else j++; } }
    const exact = pairs.length;
    // marks on matched notes
    const cnt = {};
    const add = (k, tp, fp, fn) => { cnt[k] = cnt[k] || { tp: 0, fp: 0, fn: 0 }; cnt[k].tp += tp; cnt[k].fp += fp; cnt[k].fn += fn; };
    const matched = new Set(pairs.map((p) => p[1]));
    for (const [i, j] of pairs) {
      const a = truth[i], b = read[j];
      const A = new Set(a.art), B = new Set(b.art);
      for (const x of A) add('art', B.has(x) ? 1 : 0, 0, B.has(x) ? 0 : 1);
      for (const x of B) if (!A.has(x)) add('art', 0, 1, 0);
      if (a.dyn || b.dyn) add('dyn', a.dyn && a.dyn === b.dyn ? 1 : 0, b.dyn && a.dyn !== b.dyn ? 1 : 0, a.dyn && a.dyn !== b.dyn ? 1 : 0);
      if (a.fing || b.fing) add('fing', a.fing && a.fing === b.fing ? 1 : 0, b.fing && a.fing !== b.fing ? 1 : 0, a.fing && a.fing !== b.fing ? 1 : 0);
      if (a.tie || b.tie) add('tie', a.tie && b.tie ? 1 : 0, b.tie && !a.tie ? 1 : 0, a.tie && !b.tie ? 1 : 0);
    }
    // unmatched read notes with marks are false marks
    read.forEach((b, j) => { if (matched.has(j)) return; if (b.art.length) add('art', 0, b.art.length, 0); if (b.dyn) add('dyn', 0, 1, 0); if (b.fing) add('fing', 0, 1, 0); });
    // slurs and hairpins: count of starts found near the right notes (by index in truth)
    const tIdx = new Map(); { let k = 0; st.bars.forEach((b, m) => { let p = 0; b.forEach((e) => { if (!e.full) tIdx.set(m + ':' + p, k++); p += M.ticksOf(e, time); }); }); }
    const readOf = new Map(pairs.map(([i, j]) => [i, read[j]]));
    for (const sp of S.spans) {
      const ia = tIdx.get(sp.a.m + ':' + sp.a.pos), ib = tIdx.get(sp.b.m + ':' + sp.b.pos);
      const ra = readOf.get(ia), rb = readOf.get(ib);
      if (sp.kind === 'slur') add('slur', ra && ra.slurStart && rb && rb.slurEnd ? 1 : 0, 0, ra && ra.slurStart && rb && rb.slurEnd ? 0 : 1);
      if (sp.kind === 'hairpin') add('hairpin', ra && ra.hp && ra.hp.start === sp.dir ? 1 : 0, 0, ra && ra.hp && ra.hp.start === sp.dir ? 0 : 1);
    }
    const slurRead = read.filter((x) => x.slurStart).length, slurTrue = S.spans.filter((q) => q.kind === 'slur').length;
    if (slurRead > slurTrue) add('slur', 0, slurRead - slurTrue, 0);
    results.push({ font, seed, look, notes: n, read: mm, exact, acc: n ? exact / n : 0, key: r ? r.key === key : false, time: r ? r.time.join('/') === time.join('/') : false, marks: cnt, ...(verbose ? { truth: truth.map(key2).join(' '), got: read.map(key2).join(' ') } : {}) });
  }
  return results;
};
