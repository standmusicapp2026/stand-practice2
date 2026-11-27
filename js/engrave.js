// Engraved music for the notebook pages: a staff, its clef, key signature and time, notes with their
// accidentals, ledger lines, stems, flags and beams, bar lines and little words under the notes —
// drawn with the music font Bravura (SMuFL), so it looks like printed music at any size.
//
// A piece of music is a small description (m), kept with the page item that shows it:
//   { clef: 'treble' | 'bass' | 'alto' | 'tenor' | 'treble8', key: fifths (-7..7) or null,
//     time: '4/4' | 'C' | null, staff: 5 | 1, ws: width in staff spaces, even: equal bars,
//     title: words above the staff, notes: [...] }
// and each of the notes is one of
//   { p: 'F#4' or ['C4', 'E4', 'G4'], d: 'w' | 'h' | 'q' | '8' | '16', dot, lab: words under it, b: '[' or ']' (beam) }
//   { r: 'q' }  a rest      { bar: '|' | '||' | '|.' }  a bar line      { brk: 1 } a new line
// Everything is laid out in staff spaces first (the distance between two staff lines), then drawn
// at whatever size the page item has, keeping its shape.

// ---------- pitches ----------
const LET = 'CDEFGAB';
const NAT = [0, 2, 4, 5, 7, 9, 11];
const ACC_STR = { '-2': 'bb', '-1': 'b', 0: '', 1: '#', 2: '##' };
export const pitchStr = (L, a, o) => LET[L] + ACC_STR[a] + o;
export function parsePitch(s) {
  const r = /^([A-G])(bb|b|##|#|x|n)?(-?\d)$/.exec(String(s).trim());
  if (!r) return null;
  const a = { bb: -2, b: -1, '##': 2, '#': 1, x: 2, n: 0 }[r[2]] ?? 0;
  return { L: LET.indexOf(r[1]), a, o: +r[3], force: r[2] === 'n' };
}
export const midiOf = (L, a, o) => 12 * (o + 1) + NAT[L] + a;
const diat = (L, o) => o * 7 + L;

// ---------- clefs and key signatures ----------
// bottom: the note on the bottom line, counted in letters from C0 (E4 for the treble clef);
// y: the line the clef sits on (0 bottom line … 4 top line); sh/fl: where each sharp and flat of a
// key signature goes, in half spaces above the bottom line, in the order they are written. The tenor
// clef's sharps are the exception musicians know: they start low (F on the second line) so the
// G sharp does not climb above the staff.
export const CLEFS = {
  treble: { g: '\uE050', y: 1, bottom: 30, w: 2.684, sh: [8, 5, 9, 6, 3, 7, 4], fl: [4, 7, 3, 6, 2, 5, 1], label: 'Treble' },
  bass: { g: '\uE062', y: 3, bottom: 18, w: 2.756, sh: [6, 3, 7, 4, 1, 5, 2], fl: [2, 5, 1, 4, 0, 3, -1], label: 'Bass' },
  alto: { g: '\uE05C', y: 2, bottom: 24, w: 2.796, sh: [7, 4, 8, 5, 2, 6, 3], fl: [3, 6, 2, 5, 1, 4, 0], label: 'Alto' },
  tenor: { g: '\uE05C', y: 3, bottom: 22, w: 2.796, sh: [2, 6, 3, 7, 4, 8, 5], fl: [5, 8, 4, 7, 3, 6, 2], label: 'Tenor' },
  // (the treble clef with a small 8 below: guitar and tenor voice, sounding an octave lower)
  treble8: { g: '\uE052', y: 1, bottom: 23, w: 2.684, sh: [8, 5, 9, 6, 3, 7, 4], fl: [4, 7, 3, 6, 2, 5, 1], label: 'Treble 8vb' },
};
const SHARP_ORDER = [3, 0, 4, 1, 5, 2, 6];   // F C G D A E B
const FLAT_ORDER = [6, 2, 5, 1, 4, 0, 3];    // B E A D G C F
export function keyAccs(fifths) {
  const k = [0, 0, 0, 0, 0, 0, 0];
  if (fifths > 0) for (let i = 0; i < fifths; i++) k[SHARP_ORDER[i]] = 1;
  if (fifths < 0) for (let i = 0; i < -fifths; i++) k[FLAT_ORDER[i]] = -1;
  return k;
}
// the number of sharps (+) or flats (−) of the major key on a note
export const majorFifths = (L, a) => [0, 2, 4, -1, 1, 3, 5][L] + 7 * a;

// ---------- the font: code points and sizes (Bravura's own metrics, in staff spaces) ----------
const GL = {
  // (quavers and semiquavers have the black head of a crotchet)
  head: { w: '\uE0A2', h: '\uE0A3', q: '\uE0A4', 8: '\uE0A4', 16: '\uE0A4' }, headW: { w: 1.688, h: 1.18, q: 1.18, 8: 1.18, 16: 1.18 },
  acc: { '-2': '\uE264', '-1': '\uE260', 0: '\uE261', 1: '\uE262', 2: '\uE263' }, accW: { '-2': 1.644, '-1': 0.904, 0: 0.672, 1: 0.996, 2: 0.988 },
  rest: { w: '\uE4E3', h: '\uE4E4', q: '\uE4E5', 8: '\uE4E6', 16: '\uE4E7' }, restW: { w: 1.128, h: 1.128, q: 1.08, 8: 1.0, 16: 1.28 },
  flagUp: { 8: '\uE240', 16: '\uE242' }, flagDown: { 8: '\uE241', 16: '\uE243' },
  dot: '\uE1E7', time: (d) => String.fromCharCode(0xE080 + d), common: '\uE08A', cut: '\uE08B', perc: '\uE069',
};
const STAFF_T = 0.13, LEDGER_T = 0.16, LEDGER_X = 0.4, STEM_T = 0.12, STEM_L = 3.5, BAR_T = 0.16, THICK_T = 0.5, BEAM_T = 0.5;
const BEATS = { w: 4, h: 2, q: 1, 8: 0.5, 16: 0.25 };
const TEXT = '"Iowan Old Style", "Palatino", Georgia, serif';

// ---------- layout ----------
const CACHE = new Map();
export function engrave(m) {
  const key = JSON.stringify(m);
  let L = CACHE.get(key);
  if (!L) { L = layout(m); if (CACHE.size > 300) CACHE.clear(); CACHE.set(key, L); }
  return L;
}

function layout(m) {
  const clef = CLEFS[m.clef] || CLEFS.treble, one = m.staff === 1;
  const key = one || m.key == null ? 0 : Math.max(-7, Math.min(7, m.key | 0));
  const kacc = keyAccs(key);
  // 1. which accidentals are printed: against the key signature and what came before in the bar
  //    (an accidental holds for the rest of its bar, at its own octave; after a bar line a note that
  //    was altered in the bar before gets a reminder)
  let state = new Map(), prev = new Map();
  const ev = [];
  for (const n of m.notes || []) {
    if (n.bar) { ev.push({ kind: 'bar', bar: n.bar }); prev = state; state = new Map(); continue; }
    if (n.brk) { ev.push({ kind: 'brk' }); continue; }
    if (n.sp) { ev.push({ kind: 'sp', w: n.sp }); continue; }
    const d = BEATS[n.d] ? n.d : n.r ? n.r : 'w';
    // (a hidden rest: an empty place in a bar, for the answer, that can still have words under it)
    if (n.r) { ev.push({ kind: 'rest', d: BEATS[n.r] ? n.r : 'q', dot: n.dot, lab: n.lab, hide: n.hide }); continue; }
    const ps = (Array.isArray(n.p) ? n.p : [n.p]).map(parsePitch).filter(Boolean);
    if (!ps.length) continue;
    const heads = ps.map((p) => {
      const k = p.L + '/' + p.o;
      const cur = state.has(k) ? state.get(k) : kacc[p.L];
      const show = one ? false : p.force || p.a !== cur || (!state.has(k) && prev.has(k) && prev.get(k) !== p.a);
      return { ...p, s: one ? 4 : diat(p.L, p.o) - clef.bottom, show };
    });
    for (const p of ps) state.set(p.L + '/' + p.o, p.a);
    ev.push({ kind: 'note', d, dot: n.dot, lab: n.lab, beam: n.b, stem: n.stem, heads });
  }
  // (the notes inside a beamed group, which get their stems from the beam)
  let inB = false;
  for (const e of ev) if (e.kind === 'note') { if (e.beam === '[') inB = true; e.inBeam = inB; if (e.beam === ']') inB = false; }
  // 2. the width each thing needs (its accidentals on the left, the head, and its least room after)
  for (const e of ev) {
    if (e.kind === 'bar') { e.bw = e.bar === '|.' ? BAR_T + 0.4 + THICK_T : e.bar === '||' ? BAR_T * 2 + 0.36 : BAR_T; e.lw = 0; e.hw = e.bw; e.rw = 1.1; e.spring = 0; continue; }
    if (e.kind === 'sp') { e.lw = 0; e.hw = 0; e.rw = e.w; e.spring = 0.5; continue; }
    if (e.kind === 'brk') { e.lw = e.hw = e.rw = 0; e.spring = 0; continue; }
    const beats = BEATS[e.d] * (e.dot ? 1.5 : 1);
    e.rw = 0.9 + 1.0 * Math.sqrt(beats); e.spring = e.rw;
    if (e.kind === 'rest') { e.lw = 0; e.hw = GL.restW[e.d] + (e.dot ? 0.8 : 0); continue; }
    const hw = GL.headW[e.d];
    const hs = e.heads.slice().sort((a, b) => a.s - b.s);
    // stem: away from the farthest note (the middle line goes down)
    if (e.d !== 'w') {
      const hi = hs[hs.length - 1].s, lo = hs[0].s;
      e.up = e.stem ? e.stem > 0 : one ? true : hi - 4 < 4 - lo;
    }
    // seconds in a chord: one of the two heads sits on the other side of the stem
    for (const h of hs) h.dx = 0;
    if (e.d === 'w' || e.up) { for (let i = 1; i < hs.length; i++) if (hs[i].s - hs[i - 1].s === 1 && !hs[i - 1].dx) hs[i].dx = hw - (e.d === 'w' ? 0.04 : STEM_T); }
    else { for (let i = hs.length - 2; i >= 0; i--) if (hs[i + 1].s - hs[i].s === 1 && !hs[i + 1].dx) hs[i].dx = -(hw - STEM_T); }
    e.hs = hs; e.headW = hw;
    const left = Math.min(0, ...hs.map((h) => h.dx)), right = Math.max(...hs.map((h) => h.dx + hw));
    // accidentals in columns, from the top down; two in a column at least a seventh apart
    const accs = hs.filter((h) => h.show).sort((a, b) => b.s - a.s), cols = [];
    for (const h of accs) {
      const w = GL.accW[h.a];
      let c = cols.find((col) => col.items.every((o) => Math.abs(o.s - h.s) >= 6));
      if (!c) { c = { items: [], w: 0 }; cols.push(c); }
      c.items.push(h); c.w = Math.max(c.w, w);
    }
    let ax = left - 0.22;
    for (const c of cols) { ax -= c.w; for (const h of c.items) h.ax = ax + (c.w - GL.accW[h.a]); ax -= 0.14; }
    e.lw = -(cols.length ? ax + 0.14 : left);
    e.hw = right + (e.dot ? 0.75 : 0);
  }
  // 3. the beginning of a line: clef, key signature, and (on the first line) the time
  const keyW = Math.abs(key) ? Math.abs(key) * (key > 0 ? 1.1 : 1.0) + 0.3 : 0;
  const pre = (first) => {
    let x = one ? 0.8 + 2.4 : 0.6 + clef.w + 0.8;
    x += keyW;
    if (first && m.time) x += 3;
    return x + 0.6;
  };
  // 4. lines: break where asked, else where the music no longer fits (at a bar line when one is near)
  const need = (e) => e.lw + e.hw + e.rw;
  const lines = [[]];
  let ws = Math.max(m.ws || 0, 10), used = pre(true);
  for (const e of ev) {
    if (e.kind === 'brk') { if (lines[lines.length - 1].length) { lines.push([]); used = pre(false); } continue; }
    const cur = lines[lines.length - 1];
    // (bars of equal width never wrap: they share the line, and the line widens if it must)
    if (m.wrap !== false && !m.even && cur.length && used + need(e) - (e.kind === 'bar' ? e.rw : 0) > ws) {
      const lastBar = cur.map((x) => x.kind).lastIndexOf('bar');
      const nl = lastBar >= cur.length * 0.4 && lastBar < cur.length - 1 ? cur.splice(lastBar + 1) : [];
      lines.push(nl); used = pre(false) + nl.reduce((s, x) => s + need(x), 0);
    }
    lines[lines.length - 1].push(e); used += need(e);
  }
  // (a line that cannot fit even alone widens the music instead)
  lines.forEach((ln, i) => { const nat = pre(i === 0) + ln.reduce((s, x) => s + need(x), 0) - (ln.length && ln[ln.length - 1].kind === 'bar' ? ln[ln.length - 1].rw : 0); ws = Math.max(ws, nat); });
  // 5. each line spread to the full width, then drawn
  const ops = [], systems = [];
  let Y = 0;
  lines.forEach((ln, li) => {
    const sys = { ops: [], top: 4, bot: 0, cols: [] };
    const P = (o) => { sys.ops.push(o); };
    const gl = (c, x, y, s = 1) => P({ k: 'g', c, x, y, s });
    const line = (x1, y1, x2, y2, t) => P({ k: 'l', x1, y1, x2, y2, t });
    const ext = (a, b) => { sys.top = Math.max(sys.top, a, b); sys.bot = Math.min(sys.bot, a, b); };
    const last = ln[ln.length - 1], endsBar = last && last.kind === 'bar';
    const nat = pre(li === 0) + ln.reduce((s, x) => s + need(x), 0) - (endsBar ? last.rw : 0);
    // the staff
    const x0 = 0, x1 = ws;
    if (one) line(x0, 2, x1, 2, STAFF_T); else for (let l = 0; l < 5; l++) line(x0, l, x1, l, STAFF_T);
    let x = 0;
    if (one) { gl(GL.perc, 0.8, 2); x = 0.8 + 2.4; }
    else { gl(clef.g, 0.6, clef.y); x = 0.6 + clef.w + 0.8; ext(clef.y - (clef.g === '\uE052' ? 3.6 : 2.6), clef.y + (clef.g === '\uE050' || clef.g === '\uE052' ? 4.4 : 2.0)); }
    if (key) {
      const pos = key > 0 ? clef.sh : clef.fl, g = key > 0 ? GL.acc[1] : GL.acc[-1];
      for (let i = 0; i < Math.abs(key); i++) { gl(g, x, pos[i] / 2); x += key > 0 ? 1.1 : 1.0; }
      x += 0.3;
    }
    if (li === 0 && m.time) {
      const [a, b] = String(m.time).split('/');
      if (!b) P({ k: 'g', c: a === 'C|' ? GL.cut : GL.common, x: x + 0.3, y: 2 });
      else for (const [t, y] of [[a, 3], [b, 1]]) { const cs = [...t].map((d) => GL.time(+d)).join(''); P({ k: 'g', c: cs, x: x + 1.4, y, al: 'center' }); }
      x += 3;
    }
    x += 0.6;
    // the extra room goes to the notes (in equal bars, every bar the same width)
    const extra = Math.max(0, ws - nat);
    const springs = ln.reduce((s, e) => s + e.spring, 0);
    let barW = null;
    if (m.even) {
      const nBars = Math.max(1, ln.filter((e) => e.kind === 'bar').length + (endsBar ? 0 : 1));
      const fixed = ln.filter((e) => e.kind === 'bar').reduce((s, e) => s + e.bw, 0);
      barW = (ws - x - fixed) / nBars;
    }
    const placeBar = (e) => {
      const xb = x;
      if (e.bar === '|.') { line(xb + BAR_T / 2, 0, xb + BAR_T / 2, 4, BAR_T); line(xb + BAR_T + 0.4 + THICK_T / 2, 0, xb + BAR_T + 0.4 + THICK_T / 2, 4, THICK_T); }
      else if (e.bar === '||') { line(xb + BAR_T / 2, 0, xb + BAR_T / 2, 4, BAR_T); line(xb + BAR_T * 1.5 + 0.36, 0, xb + BAR_T * 1.5 + 0.36, 4, BAR_T); }
      else line(xb + BAR_T / 2, one ? 1 : 0, xb + BAR_T / 2, one ? 3 : 4, BAR_T);
      sys.cols.push({ kind: 'bar', x: xb + e.bw / 2 });
    };
    if (m.even) {
      // bars of equal width, the notes of each spread evenly inside it
      let bar = [];
      const flush = () => {
        const n = bar.length, w0 = barW;
        bar.forEach((e, i) => { const cx = x + w0 * (i + 0.5) / n; drawEvent(e, cx - (e.kind === 'rest' ? GL.restW[e.d] : e.headW) / 2); });
        x += w0; bar = [];
      };
      for (const e of ln) {
        if (e.kind === 'bar') { flush(); placeBar(e); x += e.bw; } else if (e.kind === 'note' || e.kind === 'rest') bar.push(e);
      }
      if (bar.length) flush();
    } else {
      ln.forEach((e, i) => {
        const add = springs ? extra * (e.spring / springs) : 0;
        if (e.kind === 'bar') {
          // (the last bar line sits right at the end of the staff)
          if (i === ln.length - 1) x = ws - e.bw;
          placeBar(e); x += e.bw + e.rw + add; return;
        }
        if (e.kind === 'sp') { x += e.rw + add; return; }
        x += e.lw; drawEvent(e, x); x += e.hw + e.rw + add;
      });
    }
    function drawEvent(e, hx) {
      if (e.kind === 'rest') {
        const y = one ? 2 : e.d === 'w' ? 3 : 2;
        if (!e.hide) gl(GL.rest[e.d], hx, y);
        if (e.dot && !e.hide) gl(GL.dot, hx + GL.restW[e.d] + 0.35, 2.5);
        sys.cols.push({ kind: 'rest', x: hx + GL.restW[e.d] / 2, lab: e.lab });
        ext(y - 1.5, y + 1.5); return;
      }
      const hw = e.headW, hs = e.hs;
      // ledger lines: every line between the staff and the note, a little wider than the head
      const hi = hs[hs.length - 1].s, lo = hs[0].s;
      const lxR = Math.max(...hs.map((h) => h.dx + hw));
      if (!one) {
        for (let l = 10; l <= hi; l += 2) { const on = hs.filter((h) => h.s >= l - 1); const a = Math.min(...on.map((h) => h.dx)), b = Math.max(...on.map((h) => h.dx + hw)); line(hx + a - LEDGER_X, l / 2, hx + b + LEDGER_X, l / 2, LEDGER_T); }
        for (let l = -2; l >= lo; l -= 2) { const on = hs.filter((h) => h.s <= l + 1); const a = Math.min(...on.map((h) => h.dx)), b = Math.max(...on.map((h) => h.dx + hw)); line(hx + a - LEDGER_X, l / 2, hx + b + LEDGER_X, l / 2, LEDGER_T); }
      }
      for (const h of hs) {
        gl(GL.head[e.d], hx + h.dx, h.s / 2);
        if (h.show) gl(GL.acc[h.a], hx + h.ax, h.s / 2);
        if (e.dot) { const dy = h.s % 2 === 0 ? 0.5 : 0; gl(GL.dot, hx + lxR + 0.3, h.s / 2 + dy); }
        ext(h.s / 2 - (h.show ? 1.5 : 0.6), h.s / 2 + (h.show ? 1.8 : 0.6));
      }
      e.hx = hx; e.cx = hx + hw / 2;
      if (e.d !== 'w') {
        const yHi = hi / 2, yLo = lo / 2;
        if (e.up) { e.sx = hx + hw - STEM_T / 2; e.sy0 = yLo + 0.168; e.sy1 = Math.max(yHi + STEM_L, one ? 2 + STEM_L : 2); }
        else { e.sx = hx + STEM_T / 2; e.sy0 = yHi - 0.168; e.sy1 = Math.min(yLo - STEM_L, 2); }
        if (!e.inBeam) {
          line(e.sx, e.sy0, e.sx, e.sy1, STEM_T);
          if (e.d === '8' || e.d === '16') gl(e.up ? GL.flagUp[e.d] : GL.flagDown[e.d], e.sx - STEM_T / 2, e.sy1);
        }
        ext(e.sy1, e.sy0);
      }
      sys.cols.push({ kind: 'note', x: hx + hw / 2, lab: e.lab });
    }
    // beams: the stems of a group end on one straight beam
    let grp = null;
    for (const e of ln) {
      if (e.kind !== 'note') continue;
      if (e.beam === '[') grp = [e]; else if (grp) grp.push(e);
      if (e.beam === ']' && grp && grp.length > 1) {
        const up = grp.filter((g) => g.up).length * 2 >= grp.length;
        // (the group shares one stem direction; the beam sits beyond the farthest note)
        for (const g of grp) {
          const yHi = g.hs[g.hs.length - 1].s / 2, yLo = g.hs[0].s / 2;
          g.up = up; g.sx = up ? g.hx + g.headW - STEM_T / 2 : g.hx + STEM_T / 2; g.sy0 = up ? yLo + 0.168 : yHi - 0.168;
        }
        const by = up ? Math.max(...grp.map((g) => g.hs[g.hs.length - 1].s / 2 + STEM_L), one ? 2 + STEM_L - 0.5 : 2) : Math.min(...grp.map((g) => g.hs[0].s / 2 - STEM_L), 2);
        for (const g of grp) line(g.sx, g.sy0, g.sx, by, STEM_T);
        const xa = grp[0].sx - STEM_T / 2, xb = grp[grp.length - 1].sx + STEM_T / 2;
        const dir = up ? -1 : 1;
        P({ k: 'r', x: xa, y: by + (up ? 0 : BEAM_T), w: xb - xa, h: BEAM_T });
        // a second beam over the sixteenths (a short one for a lone sixteenth)
        for (let i = 0; i < grp.length; i++) {
          if (grp[i].d !== '16') continue;
          const j = i + 1 < grp.length && grp[i + 1].d === '16' ? i + 1 : -1;
          if (j < 0 && i > 0 && grp[i - 1].d === '16') continue;
          const a = grp[i].sx - STEM_T / 2, b = j > 0 ? grp[j].sx + STEM_T / 2 : (i === grp.length - 1 ? grp[i].sx - 1.1 : grp[i].sx + 1.1);
          const y2 = by + dir * (BEAM_T + 0.25);
          P({ k: 'r', x: Math.min(a, b), y: y2 + (up ? 0 : BEAM_T), w: Math.abs(b - a), h: BEAM_T });
          if (j > 0) i = j;
        }
        ext(by + 1, by - 1);
        grp = null;
      } else if (e.beam === ']') grp = null;
    }
    // words under the notes, all on one line below the lowest thing
    const labs = sys.cols.filter((c) => c.lab);
    if (labs.length) {
      const ly = Math.min(sys.bot, -1.2) - 1.7;
      for (const c of labs) P({ k: 't', txt: String(c.lab), x: c.x, y: ly, s: 1.45, al: 'center' });
      sys.bot = ly - 0.5;
    }
    if (li === 0 && m.title) { const ty = Math.max(sys.top, 5.2) + 1.4; P({ k: 't', txt: m.title, x: 0, y: ty, s: 1.75, al: 'left', it: 1 }); sys.top = ty + 1.6; }
    // (every staff gets the same least room above and below, so staves on a page line up)
    sys.top = Math.max(sys.top, one ? 5 : 6) + 0.6; sys.bot = Math.min(sys.bot, one ? -1 : -2.2) - 0.6;
    systems.push(sys);
  });
  // stack the lines; turn music y (up) into page y (down)
  for (const sys of systems) {
    const base = Y + sys.top;
    for (const o of sys.ops) {
      if (o.k === 'l') ops.push({ ...o, y1: base - o.y1, y2: base - o.y2 });
      else if (o.k === 'r') ops.push({ ...o, y: base - o.y });
      else ops.push({ ...o, y: base - o.y });
    }
    sys.base = base; sys.y0 = Y; Y = base - sys.bot + 0.6; sys.y1 = Y;
    delete sys.ops;
  }
  return { ws, hs: Math.max(1, Y - 0.6), ops, systems };
}

// the music drawn into a box w × h centred on the origin (as the page's shapes are), in colour col
export function drawMusic(ctx, m, w, h, col) {
  const L = engrave(m);
  const k = Math.min(w / L.ws, h / L.hs);
  if (!(k > 0)) return;
  ctx.save();
  ctx.translate(-(L.ws * k) / 2, -(L.hs * k) / 2);
  ctx.fillStyle = col; ctx.strokeStyle = col;
  ctx.textBaseline = 'alphabetic';
  const font = `${4 * k}px Bravura`;
  for (const o of L.ops) {
    if (o.k === 'l') {
      // (lines as thin filled boxes: crisp, and as thick as the font asks)
      const t = o.t * k;
      if (o.y1 === o.y2) ctx.fillRect(o.x1 * k, o.y1 * k - t / 2, (o.x2 - o.x1) * k, t);
      else ctx.fillRect(o.x1 * k - t / 2, Math.min(o.y1, o.y2) * k, t, Math.abs(o.y2 - o.y1) * k);
    } else if (o.k === 'r') ctx.fillRect(o.x * k, o.y * k, o.w * k, o.h * k);
    else if (o.k === 'g') { ctx.font = font; ctx.textAlign = o.al || 'left'; ctx.fillText(o.c, o.x * k, o.y * k); }
    else if (o.k === 't') { ctx.font = `${o.it ? 'italic ' : ''}${o.s * k}px ${TEXT}`; ctx.textAlign = o.al || 'left'; ctx.fillText(o.txt, o.x * k, o.y * k); }
  }
  ctx.restore();
}
// the shape of the music: its height for each unit of width
export const musicAspect = (m) => { const L = engrave(m); return L.hs / L.ws; };

// ---------- scales ----------
// Each scale is spelled the way musicians write it: one letter per step (F sharp major has E sharp,
// not F), the harmonic minor's raised seventh and the melodic minor's raised sixth and seventh going
// up, lowered again coming down.
const SC = {
  major: { st: [0, 2, 4, 5, 7, 9, 11], le: [0, 1, 2, 3, 4, 5, 6], key: 0 },
  natural: { st: [0, 2, 3, 5, 7, 8, 10], le: [0, 1, 2, 3, 4, 5, 6], key: -3 },
  harmonic: { st: [0, 2, 3, 5, 7, 8, 11], le: [0, 1, 2, 3, 4, 5, 6], key: -3 },
  melodic: { st: [0, 2, 3, 5, 7, 9, 11], down: [0, 2, 3, 5, 7, 8, 10], le: [0, 1, 2, 3, 4, 5, 6], key: -3 },
  dorian: { st: [0, 2, 3, 5, 7, 9, 10], le: [0, 1, 2, 3, 4, 5, 6], key: -2 },
  mixolydian: { st: [0, 2, 4, 5, 7, 9, 10], le: [0, 1, 2, 3, 4, 5, 6], key: -1 },
  pentatonic: { st: [0, 2, 4, 7, 9], le: [0, 1, 2, 4, 5], key: 0 },
  majArp: { st: [0, 4, 7], le: [0, 2, 4], key: 0 },
  minArp: { st: [0, 3, 7], le: [0, 2, 4], key: -3 },
  // (the dominant seventh belongs to the key a fourth above: G B D F is in C major)
  dom7: { st: [0, 4, 7, 10], le: [0, 2, 4, 6], key: -1 },
  dim7: { st: [0, 3, 6, 9], le: [0, 2, 4, 6], key: null },
  wholetone: { st: [0, 2, 4, 6, 8, 10], le: null, key: null },
  chromatic: { st: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11], le: null, key: null },
};
export const SCALE_KINDS = Object.keys(SC);
// one step of a scale spelled on a letter (L0 + le letters up from the tonic)
function spell(L0, o0, base, semis, le) {
  const Ln = (L0 + le) % 7, o = o0 + Math.floor((L0 + le) / 7);
  return { L: Ln, o, a: base + semis - midiOf(Ln, 0, o) };
}
// the whole tone scale: the six letters (one is left out) with the plainest accidentals
function wholeToneLetters(a0, L0) {
  let best = null;
  for (let skip = 1; skip <= 6; skip++) {
    const le = [0, 1, 2, 3, 4, 5, 6].filter((x) => x !== skip);
    const accs = le.map((l, i) => { const Ln = (L0 + l) % 7, up = Math.floor((L0 + l) / 7); return 2 * i + a0 + NAT[L0] - (NAT[Ln] + 12 * up); });
    if (accs.some((x) => Math.abs(x) > 1)) continue;
    const cost = accs.reduce((s, x) => s + Math.abs(x), 0) + (accs.some((x) => x > 0) && accs.some((x) => x < 0) ? 3 : 0);
    if (!best || cost < best.cost) best = { le, cost };
  }
  return best ? best.le : [0, 1, 2, 3, 4, 5];
}
export function scaleNotes({ L, a = 0, o = 4, type = 'major', octaves = 1, dir = 'updown' }) {
  const S = SC[type] || SC.major, base = midiOf(L, a, o);
  const one = (st, le, oc) => spell(L, o + oc, base + 12 * oc, st, le);
  const up = [], down = [];
  if (type === 'chromatic') {
    // up with sharps, down with flats; the key note keeps its own name
    // (a black key is never C or B, so the sharp of the letter below and the flat of the letter
    // above stay in the same octave)
    const name = (semi, oc, flat) => {
      if (semi === 0) return { L, a, o: o + oc };
      const mm = base + 12 * oc + semi, pc = ((mm % 12) + 12) % 12, oo = Math.floor(mm / 12) - 1;
      if (NAT.includes(pc)) return { L: NAT.indexOf(pc), a: 0, o: oo };
      return flat ? { L: NAT.indexOf(pc + 1), a: -1, o: oo } : { L: NAT.indexOf(pc - 1), a: 1, o: oo };
    };
    for (let oc = 0; oc < octaves; oc++) for (let s = 0; s < 12; s++) up.push(name(s, oc, false));
    for (let oc = octaves - 1; oc >= 0; oc--) for (let s = 11; s >= 0; s--) down.push(name(s, oc, true));
  } else {
    const le = S.le || wholeToneLetters(a, L);
    for (let oc = 0; oc < octaves; oc++) S.st.forEach((st, i) => up.push(one(st, le[i], oc)));
    const dst = S.down || S.st;
    for (let oc = octaves - 1; oc >= 0; oc--) for (let i = dst.length - 1; i >= 0; i--) down.push(one(dst[i], le[i], oc));
  }
  const top = { L, a, o: o + octaves };
  if (dir === 'up') return { up: [...up, top], down: [] };
  if (dir === 'down') return { up: [], down: [top, ...down] };
  return { up: [...up, top], down };
}
// the key signature a scale is written with (null: none, the accidentals by the notes)
export function scaleKey(L, a, type) {
  const S = SC[type] || SC.major;
  if (S.key == null) return null;
  const k = majorFifths(L, a) + S.key;
  return Math.abs(k) > 7 ? null : k;
}
// the notes of a scale as written on one clef: how far they go outside the staff (fewer ledger lines is better)
// (up: how much a note below the staff counts; a player reads the tenor or treble clef for the high
// notes, so on a second clef the scale leans upwards)
function ledgerCost(ns, clef, up = 1) {
  const b = (CLEFS[clef] || CLEFS.treble).bottom;
  return ns.reduce((s, p) => { const st = diat(p.L, p.o) - b; return s + (st > 8 ? st - 8 : st < 0 ? -st * up : 0); }, 0);
}
// the octave to start on: inside the instrument's range, with the fewest ledger lines on its clef
export function bestOctave({ L, a = 0, type, octaves, clef, lo = 21, hi = 108, second = false }) {
  let best = null;
  for (let o = 0; o <= 7; o++) {
    const { up } = scaleNotes({ L, a, o, type, octaves, dir: 'up' });
    const ms = up.map((p) => midiOf(p.L, p.a, p.o));
    const inside = Math.min(...ms) >= lo && Math.max(...ms) <= hi;
    const cost = ledgerCost(up, clef, second ? 1.5 : 1) + (inside ? 0 : 1000 + Math.max(0, lo - Math.min(...ms)) + Math.max(0, Math.max(...ms) - hi));
    if (!best || cost < best.cost) best = { o, cost };
  }
  return best.o;
}
// the scale as music for the page: up to the top, a bar line, and down again; on two lines when long
// sc: { L, a, o, type, octaves, dir, clef, ks (key signature), names (note names under), title }
export function scaleMusic(sc, { nameOf = null, title = '' } = {}) {
  const { up, down } = scaleNotes(sc);
  const key = sc.ks === false ? null : scaleKey(sc.L, sc.a, sc.type);
  const n = (p) => ({ p: pitchStr(p.L, p.a, p.o), d: 'w', ...(sc.names && nameOf ? { lab: nameOf(p.L, p.a) } : {}) });
  const notes = [];
  up.forEach((p) => notes.push(n(p)));
  if (up.length && down.length) notes.push({ bar: '|' });
  const long = up.length + down.length > 17;
  if (long && up.length && down.length) notes.push({ brk: 1 });
  down.forEach((p) => notes.push(n(p)));
  notes.push({ bar: '|.' });
  const half = Math.max(up.length, down.length, 8);
  const ws = Math.round(Math.max(64, 10 + Math.abs(key || 0) * 1.1 + (long ? half : up.length + down.length) * 4.3));
  return { clef: sc.clef || 'treble', key, ws, notes, title: sc.title === false ? '' : title, wrap: false };
}

// ---------- instruments: their clef and written range (MIDI) ----------
export const INSTRUMENTS = [
  { k: 'cello', label: 'Cello', clef: 'bass', clefs: ['bass', 'tenor', 'treble'], lo: 36, hi: 88 },
  { k: 'violin', label: 'Violin', clef: 'treble', clefs: ['treble'], lo: 55, hi: 100 },
  { k: 'viola', label: 'Viola', clef: 'alto', clefs: ['alto', 'treble'], lo: 48, hi: 88 },
  { k: 'bass', label: 'Double bass', clef: 'bass', clefs: ['bass', 'tenor', 'treble'], lo: 40, hi: 79 },
  { k: 'piano', label: 'Piano', clef: 'treble', clefs: ['treble', 'bass'], lo: 21, hi: 108 },
  { k: 'guitar', label: 'Guitar', clef: 'treble8', clefs: ['treble8', 'treble'], lo: 40, hi: 88 },
  { k: 'flute', label: 'Flute', clef: 'treble', clefs: ['treble'], lo: 60, hi: 96 },
  { k: 'oboe', label: 'Oboe', clef: 'treble', clefs: ['treble'], lo: 58, hi: 91 },
  { k: 'clarinet', label: 'Clarinet', clef: 'treble', clefs: ['treble'], lo: 52, hi: 91 },
  { k: 'bassoon', label: 'Bassoon', clef: 'bass', clefs: ['bass', 'tenor'], lo: 34, hi: 75 },
  { k: 'sax', label: 'Saxophone', clef: 'treble', clefs: ['treble'], lo: 58, hi: 89 },
  { k: 'trumpet', label: 'Trumpet', clef: 'treble', clefs: ['treble'], lo: 54, hi: 82 },
  { k: 'horn', label: 'Horn', clef: 'treble', clefs: ['treble', 'bass'], lo: 47, hi: 77 },
  { k: 'trombone', label: 'Trombone', clef: 'bass', clefs: ['bass', 'tenor'], lo: 40, hi: 72 },
  { k: 'vhigh', label: 'High voice', clef: 'treble', clefs: ['treble'], lo: 60, hi: 81 },
  { k: 'vlow', label: 'Low voice', clef: 'bass', clefs: ['bass', 'treble8'], lo: 40, hi: 64 },
  { k: 'any', label: 'Any instrument', clef: 'treble', clefs: ['treble', 'bass', 'alto', 'tenor', 'treble8'], lo: 21, hi: 108 },
];
