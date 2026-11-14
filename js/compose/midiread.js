// A standard MIDI file (.mid) read into a score, as Sibelius, Dorico and MuseScore do: each track (or
// each channel of a single-track file) becomes an instrument, named from the track or its sound; the
// notes are put on the nearest sixteenth (or triplet: of eighths, sixteenths or quarters, where played in threes),
// chords are gathered (a chord rolled by hand with its arpeggio sign), notes that overlap go to a second voice, a piano is split at middle C into
// two staves; the time, the key and the tempo come from the file.
import { INST } from './instruments.js';
import { WHOLE, newScore, newPart, newId, timeAt, barTicks, decompose, writeEvent, spell, restBar, valueOf, allStaves, voiceView, fitBar } from './model.js';

const GM_TO_INST = (p) => (p <= 5 ? 'piano' : p <= 7 ? 'harpsichord' : p === 8 ? 'celesta' : p === 9 ? 'glockenspiel' : p === 11 ? 'vibraphone' : p === 12 ? 'marimba' : p === 13 ? 'xylophone' : p === 14 ? 'tubularbells'
  : p <= 20 ? 'organ' : p <= 23 ? 'accordion' : p === 24 ? 'guitar' : p === 25 ? 'steelguitar' : p <= 31 ? 'eguitar' : p <= 39 ? 'bassguitar' : p === 40 ? 'violin' : p === 41 ? 'viola' : p === 42 ? 'cello' : p === 43 ? 'contrabass'
  : p <= 45 ? 'violin' : p === 46 ? 'harp' : p === 47 ? 'timpani' : p <= 51 ? 'violin1' : p <= 54 ? 'voice' : p === 56 ? 'trumpet' : p === 57 ? 'trombone' : p === 58 ? 'tuba' : p === 59 ? 'trumpet' : p === 60 ? 'horn' : p <= 63 ? 'horn'
  : p === 64 ? 'sopsax' : p === 65 ? 'altosax' : p === 66 ? 'tenorsax' : p === 67 ? 'barisax' : p === 68 ? 'oboe' : p === 69 ? 'englishhorn' : p === 70 ? 'bassoon' : p === 71 ? 'clarinet' : p === 72 ? 'piccolo' : p <= 79 ? 'flute' : 'piano');
// the drums of General MIDI on a percussion staff: [the place on the staff (a step), the head]
const DRUM = { 35: [31, null], 36: [31, null], 37: [35, 'x'], 38: [35, null], 40: [35, null], 39: [35, 'x'], 41: [33, null], 43: [33, null], 45: [36, null], 47: [36, null], 48: [37, null], 50: [37, null],
  42: [39, 'x'], 44: [29, 'x'], 46: [39, 'circlex'], 49: [40, 'x'], 57: [40, 'x'], 52: [40, 'x'], 55: [40, 'x'], 51: [38, 'x'], 59: [38, 'x'], 53: [38, 'diamond'], 54: [39, 'x'], 56: [38, 'tri'] };

function parse(buf) {
  const d = new DataView(buf); let p = 0;
  const str = (n) => { let s = ''; for (let i = 0; i < n; i++) s += String.fromCharCode(d.getUint8(p + i)); return s; };
  if (str(4) !== 'MThd') throw new Error('This is not a MIDI file.');
  const hl = d.getUint32(4); const format = d.getUint16(8), ntrk = d.getUint16(10), div = d.getUint16(12);
  // (time counted in frames of a second: read as if a quarter note were half a second)
  let ppq = div; if (div & 0x8000) { const fps = 256 - (div >> 8), tpf = div & 0xff; ppq = Math.max(1, Math.round((fps === 29 ? 29.97 : fps) * tpf * 0.5)); }
  p = 8 + hl;
  const tracks = [];
  for (let t = 0; t < ntrk && p + 8 <= buf.byteLength; t++) {
    const id = str(4), len = d.getUint32(p + 4); p += 8;
    const end = Math.min(buf.byteLength, p + len);
    if (id !== 'MTrk') { p = end; continue; }
    const tr = { name: '', notes: [], prog: {}, meta: [] };
    const open = new Map();
    let tick = 0, run = 0;
    const vlq = () => { let v = 0, b; do { b = d.getUint8(p++); v = (v << 7) | (b & 0x7f); } while (b & 0x80 && p < end); return v; };
    try { while (p < end) {
      tick += vlq();
      let st = d.getUint8(p);
      if (st & 0x80) p++; else st = run;
      if (st === 0xff) {
        const type = d.getUint8(p++), l = vlq(); const at = p; p += l;
        if (type === 0x03 && !tr.name) tr.name = new TextDecoder().decode(new Uint8Array(buf, at, l)).replace(/\0/g, '').trim();
        else if (type === 0x51 && l === 3) tr.meta.push({ tick, tempo: 60000000 / ((d.getUint8(at) << 16) | (d.getUint8(at + 1) << 8) | d.getUint8(at + 2)) });
        else if (type === 0x58 && l >= 2) tr.meta.push({ tick, time: [d.getUint8(at), 1 << d.getUint8(at + 1)] });
        else if (type === 0x59 && l >= 2) tr.meta.push({ tick, key: d.getInt8(at) });
        else if (type === 0x2f) break;
        continue;
      }
      if (st === 0xf0 || st === 0xf7) { const l = vlq(); p += l; continue; }
      run = st;
      const kind = st & 0xf0, ch = st & 0x0f;
      const a = d.getUint8(p++), b = kind === 0xc0 || kind === 0xd0 ? 0 : d.getUint8(p++);
      if (kind === 0x90 && b > 0) { const k = ch * 128 + a; if (!open.has(k)) open.set(k, []); open.get(k).push({ tick, vel: b }); }
      else if (kind === 0x80 || (kind === 0x90 && b === 0)) { const k = ch * 128 + a, q = open.get(k); if (q && q.length) { const o = q.shift(); if (tick > o.tick) tr.notes.push({ ch, midi: a, on: o.tick, off: tick, vel: o.vel }); } }
      else if (kind === 0xc0) { if (tr.prog[ch] === undefined) tr.prog[ch] = a; }
    } } catch { /* (a damaged track: what was read of it is kept) */ }
    // (notes never let go end where the track ends)
    for (const [k, q] of open) for (const o of q) if (tick > o.tick) tr.notes.push({ ch: k >> 7, midi: k & 127, on: o.tick, off: tick, vel: o.vel });
    tracks.push(tr);
    p = end;
  }
  return { format, div: ppq, tracks };
}

export function fromMidi(buf, name = '') {
  const { div, tracks } = parse(buf);
  const K = 480 / div;   // file ticks → Stand's ticks (480 a quarter note)
  const meta = tracks.flatMap((t) => t.meta).sort((a, b) => a.tick - b.tick);
  // the instruments: a track for each, or (one track, many channels) a channel for each
  const groups = [];
  for (const tr of tracks) {
    const chans = [...new Set(tr.notes.map((n) => n.ch))];
    for (const ch of chans) groups.push({ name: chans.length > 1 ? '' : tr.name, ch, prog: tr.prog[ch] ?? 0, notes: tr.notes.filter((n) => n.ch === ch) });
  }
  if (!groups.length) throw new Error('There are no notes in this MIDI file.');
  const lastTick = Math.max(...groups.flatMap((g) => g.notes.map((n) => n.off))) * K;
  // bars from the time signatures of the file
  const times = meta.filter((x) => x.time).map((x) => ({ t: x.tick * K, time: x.time }));
  const keys = meta.filter((x) => x.key !== undefined), tempos = meta.filter((x) => x.tempo);
  const bars = []; { let t = 0, cur = (times[0] && times[0].t === 0 ? times[0].time : [4, 4]); while (t < lastTick - 1 || !bars.length) { const ch = times.find((x) => x.t === t); if (ch) cur = ch.time; bars.push({ t, time: cur.slice() }); t += (cur[0] * WHOLE) / cur[1]; if (bars.length > 2000) break; } }
  const title = (tracks[0] && tracks[0].name && !tracks[0].notes.length ? tracks[0].name : '') || String(name).replace(/\.(mid|midi|smf|kar)$/i, '') || 'Imported score';
  const score = newScore({ title, insts: ['piano'], bars: 1 });
  score.parts = []; score.measures = bars.map((b, i) => (i === 0 || b.time.join() !== bars[i - 1].time.join() ? { time: b.time.slice() } : {}));
  const key0 = keys.length ? keys[0].key : 0;
  score.measures[0].key = Math.max(-7, Math.min(7, key0));
  for (const k of keys.slice(1)) { const m = barAt(bars, k.tick * K); if (m > 0) score.measures[m].key = Math.max(-7, Math.min(7, k.key)); }
  score.measures[0].tempo = { bpm: Math.round(tempos.length ? tempos[0].tempo : 120), beat: 4, text: '' };
  for (const tp of tempos.slice(1)) { const m = barAt(bars, tp.tick * K); if (m > 0 && Math.abs(tp.tempo - (score.measures[m - 1] && score.measures[m - 1].tempo ? score.measures[m - 1].tempo.bpm : 0)) > 0.5) score.measures[m].tempo = { bpm: Math.round(tp.tempo), beat: 4, text: '' }; }
  score.measures[score.measures.length - 1].bar = 'final';
  for (const g of groups) {
    const drums = g.ch === 9;
    const guess = globalThis.__guessInst ? globalThis.__guessInst(g.name || '', 0, 1, true) : null;
    const instId = drums ? 'drumset' : (guess && guess.id) || GM_TO_INST(g.prog);
    const inst = INST[instId] || INST.piano;
    const part = newPart(inst.id);
    if (g.name) part.name = g.name;
    const two = !drums && inst.clefs.length >= 2;
    part.staves = part.staves.slice(0, two ? 2 : 1);
    for (const st of part.staves) st.bars = score.measures.map((_, m) => restBar(timeAt(score, m)));
    score.parts.push(part);
    // notes on the grid; the staff they go on
    const notes = g.notes.map((n) => ({ midi: n.midi, on: n.on * K, off: n.off * K, staff: two && n.midi < 60 ? 1 : 0 }));
    for (let si = 0; si < part.staves.length; si++) placeNotes(score, bars, part, part.staves[si], notes.filter((n) => n.staff === si), drums);
    // (every bar of every voice adds up)
    for (const st of part.staves) for (const key of ['bars', 'v2', 'v3', 'v4']) if (st[key]) st[key] = st[key].map((b, m) => fitBar(b || restBar(timeAt(score, m)), timeAt(score, m)));
    if (two) { part.staves[0].clef = 'treble'; part.staves[1].clef = 'bass'; }
    else if (!drums) { const mids = notes.map((n) => n.midi).sort((a, b) => a - b); const med = mids[mids.length >> 1] || 60; if (inst.clefs[0] === 'treble' && med < 55) part.staves[0].clef = 'bass'; }
  }
  const n = score.parts.reduce((a, p) => a + p.staves.length, 0);
  score.layout.staffMm = n <= 2 ? 7 : n <= 4 ? 6.5 : n <= 8 ? 5.5 : 4.8;
  score._v2spans = 1; score.spans = [];
  return score;
}
function barAt(bars, t) { let m = 0; for (let i = 0; i < bars.length; i++) if (bars[i].t <= t + 1) m = i; return m; }

// Each beat is read on a grid of sixteenths, or in threes where its notes fall there: eighth-note
// triplets (three to a beat), sixteenth-note triplets (three to half a beat) or quarter-note triplets
// (three over two beats). A triplet is a group: { start, span } in ticks, three places in its span.
function quantize(bars, notes) {
  const info = notes.map((n) => {
    // (a note played a moment before a barline belongs to the bar it begins)
    const m = barAt(bars, n.on + WHOLE / 96), b = bars[m], beat = WHOLE / b.time[1], tol = beat / 24;
    const ok = b.time[1] <= 4 && !(b.time[1] === 8 && b.time[0] % 3 === 0);
    const rel = n.on - b.t, bi = Math.min(b.time[0] - 1, Math.floor((rel + tol) / beat)), inBeat = rel - bi * beat;
    const err = (x, g) => Math.abs(x - Math.round(x / g) * g);
    const pair = bi - (bi % 2), inPair = rel - pair * beat;
    return { n, m, b, beat, tol, ok, bi, inBeat, e16: err(inBeat, beat / 4), e8t: err(inBeat, beat / 3), e16t: err(inBeat, beat / 6), pair, eQ: err(inPair, (beat * 2) / 3) };
  });
  const groups = new Map();   // 'm:bi' (or 'm:bi:h' for half a beat) → { start, span }
  const byKey = (f) => { const mp = new Map(); for (const x of info) if (x.ok) { const k = f(x); if (!mp.has(k)) mp.set(k, []); mp.get(k).push(x); } return mp; };
  // (quarter-note triplets: two beats whose notes all fall on thirds of them, one off the sixteenths)
  for (const [, xs] of byKey((x) => x.m + ':' + x.pair)) {
    const x0 = xs[0]; if (x0.pair + 1 >= x0.b.time[0]) continue;
    // (and one of them held over the beat in the middle: else they are eighth-note triplets)
    const mid = x0.b.t + (x0.pair + 1) * x0.beat;
    if (xs.every((x) => x.eQ <= x.tol) && xs.some((x) => x.eQ + 1 < x.e16 && x.n.on < mid && x.n.off > mid + x.tol)) {
      const g = { start: x0.b.t + x0.pair * x0.beat, span: 2 * x0.beat };
      groups.set(x0.m + ':' + x0.pair, g); groups.set(x0.m + ':' + (x0.pair + 1), g);
    }
  }
  for (const [k, xs] of byKey((x) => x.m + ':' + x.bi)) {
    if (groups.has(k)) continue; const x0 = xs[0], bStart = x0.b.t + x0.bi * x0.beat;
    // (sixteenth-note triplets, by half a beat: a half with a note off the sixteenths and on sixths of the beat)
    // (short notes only: a chord rolled by hand, its notes held on, is not a triplet)
    if (xs.some((x) => x.e16t + 1 < Math.min(x.e16, x.e8t) && x.n.off - x.n.on <= x.beat / 2 + x.tol)) {
      for (const h of [0, 1]) if (xs.some((x) => Math.min(1, Math.floor((x.inBeat + x.tol) / (x.beat / 2))) === h && x.e16 > x.tol)) groups.set(k + ':' + h, { start: bStart + (h * x0.beat) / 2, span: x0.beat / 2 });
    } else if (xs.some((x) => x.e8t + 1 < x.e16)) groups.set(k, { start: bStart, span: x0.beat });
  }
  const out = [];
  for (const x of info) {
    const { n, b, beat, tol } = x, k = x.m + ':' + x.bi;
    const grp = groups.get(k) || groups.get(k + ':' + Math.min(1, Math.floor((x.inBeat + tol) / (beat / 2)))) || null;
    const g = grp ? grp.span / 3 : beat / 4, at = grp ? grp.start : b.t;
    let on = at + Math.round((n.on - at) / g) * g;
    if (grp && on >= grp.start + grp.span) on = grp.start + grp.span - g;
    const len = Math.max(g, Math.round((n.off - on) / g) * g);
    // (a triplet holds only its group: it ends where its group does)
    const off = grp ? Math.min(on + len, grp.start + grp.span) : on + len;
    out.push({ ...n, on, off, m: x.m, bi: x.bi, trip: !!grp, grp });
  }
  // (and a note held into a group of triplets is let go where that group begins)
  const starts = [...new Set([...groups.values()])].map((g) => g.start).sort((a, b) => a - b);
  for (const x of out) if (!x.trip) { const cut = starts.find((t) => t > x.on && t < x.off); if (cut !== undefined) x.off = cut; }
  return out.filter((x) => x.off > x.on);
}
// A chord rolled by hand (three or more notes begun one after another, a moment apart, held and let go
// together) is one chord with an arpeggio sign, as it is written.
function arpeggios(bars, raw) {
  const ns = raw.map((n) => ({ ...n })).sort((a, b) => a.on - b.on || a.midi - b.midi);
  for (let i = 0; i < ns.length; i++) {
    const a = ns[i]; if (a.arp) continue;
    const beat = WHOLE / bars[barAt(bars, a.on)].time[1];
    if (a.off - a.on < beat * 0.75) continue;
    const chain = [a];
    for (let j = i + 1; j < ns.length; j++) {
      const c = ns[j], last = chain[chain.length - 1];
      if (c.on - last.on > beat / 6 || c.on - a.on > beat / 2) break;
      if (!c.arp && Math.abs(c.off - a.off) <= beat / 4 && c.midi > last.midi) chain.push(c);
    }
    if (chain.length >= 3 && chain[chain.length - 1].on - a.on >= beat / 16) for (const c of chain) { c.on = a.on; c.off = a.off; c.arp = true; }
  }
  return ns;
}
function placeNotes(score, bars, part, st, raw, drums) {
  if (!raw.length) return;
  const notes = quantize(bars, drums ? raw : arpeggios(bars, raw)).sort((a, b) => a.on - b.on || b.midi - a.midi);
  // chords, and lanes (voices) so that nothing in one voice overlaps
  const lanes = [[], [], [], []];
  for (const n of notes) {
    let done = false;
    for (const L of lanes) { const c = L.find((x) => x.on === n.on && x.off === n.off); if (c) { if (!c.midis.includes(n.midi)) c.midis.push(n.midi); if (n.arp) c.arp = true; done = true; break; } }
    if (done) continue;
    let li = lanes.findIndex((L) => !L.length || L[L.length - 1].off <= n.on);
    if (li < 0) { const L = lanes[0]; L[L.length - 1].off = Math.max(L[L.length - 1].on + 1, n.on); li = 0; }   // (played legato: the note before is let go)
    lanes[li].push({ on: n.on, off: n.off, midis: [n.midi], trip: n.trip, grp: n.grp, arp: !!n.arp });
  }
  lanes.forEach((L, li) => {
    if (!L.length) return;
    const view = li === 0 ? st : voiceView(st, li + 1, score);
    // (a group of triplets is first filled with triplet rests, so it always adds up)
    const done = new Set();
    for (const c of L) if (c.grp) {
      if (done.has(c.grp)) continue; done.add(c.grp);
      const m = barAt(bars, c.grp.start), b = bars[m], g = c.grp.span / 3, v = valueOf(g * 1.5);
      if (!v) continue;
      for (let k = 0; k < 3; k++) writeEvent(score, view, m, c.grp.start - b.t + k * g, { id: newId(), rest: true, keep: true, t: v.t, dots: v.dots, tup: { n: 3, m: 2, base: v.t } });
    }
    for (const c of L) writeChord(score, bars, view, c, drums);
    // (a bar that does not add up after that, from triplets mixed with other notes, is written again
    // on the plain grid of sixteenths)
    const sumOf = (m) => { const time = timeAt(score, m); return (view.bars[m] || []).reduce((a, e) => a + (e.full ? barTicks(time) : evTicksOf(e)), 0) === barTicks(time); };
    const badBars = new Set(); for (let m = 0; m < bars.length; m++) if (!sumOf(m)) badBars.add(m);
    for (const m of badBars) {
      const b = bars[m], time = timeAt(score, m), g = WHOLE / time[1] / 4, end = b.t + barTicks(time);
      view.bars[m] = restBar(time);
      for (const c of L) { if (c.on >= end || c.off <= b.t) continue; const on = Math.max(b.t, b.t + Math.round((c.on - b.t) / g) * g), off = Math.min(end, Math.max(on + g, b.t + Math.round((c.off - b.t) / g) * g)); if (off > on) writeChord(score, bars, view, { ...c, on, off, trip: false }, drums); }
    }
  });
}
function writeChord(score, bars, st, c, drums) {
  const notesOf = (m) => c.midis.slice().sort((a, b) => a - b).map((midi) => {
    if (drums) { const dm = DRUM[midi] || [36, 'x']; return { s: dm[0], a: 0, perc: midi, ...(dm[1] ? { head: dm[1] } : {}) }; }
    const sp = spell(midi, keyFifths(score, m)); return { s: sp.s, a: sp.a };
  });
  let t = c.on;
  while (t < c.off - 1) {
    const m = barAt(bars, t), b = bars[m], end = Math.min(c.off, b.t + barTicks(timeAt(score, m))), pos = t - b.t, len = end - t;
    if (len <= 0) break;
    const time = timeAt(score, m), beat = WHOLE / time[1];
    const more = end < c.off - 1;
    if (c.trip) {
      // a triplet note: one to three places of its group (what lasts longer is not tied on)
      const grp = c.grp || { start: b.t + Math.floor(pos / beat) * beat, span: beat }, gs = grp.start - b.t, g = grp.span / 3;
      const slot = Math.max(0, Math.min(2, Math.round((pos - gs) / g))), k = Math.max(1, Math.min(3 - slot, Math.round(len / g)));
      const v = valueOf(k * g * 1.5) || valueOf(g * 1.5);
      const ev = { id: newId(), t: v.t, dots: v.dots, tup: { n: 3, m: 2, base: v.t }, notes: notesOf(m) };
      writeEvent(score, st, m, gs + slot * g, ev);
      break;
    } else {
      const pieces = decompose(pos, len, time, false);
      let p = pos;
      pieces.forEach((pc, i) => { writeEvent(score, st, m, p, { id: newId(), t: pc.t, dots: pc.dots, notes: notesOf(m).map((n) => ({ ...n, tie: more || i < pieces.length - 1 })), ...(c.arp && t === c.on && !i && c.midis.length > 1 ? { art: ['arp'] } : {}) }); p += pc.ticks; });
    }
    t = end;
  }
}
function evTicksOf(e) { return Math.round((WHOLE / e.t) * (2 - Math.pow(0.5, e.dots || 0)) * (e.tup ? e.tup.m / e.tup.n : 1)); }
function keyFifths(score, m) { for (let i = m; i >= 0; i--) if (score.measures[i].key !== undefined && score.measures[i].key !== null) return score.measures[i].key; return 0; }
void allStaves;
