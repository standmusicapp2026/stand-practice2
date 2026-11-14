// A standard MIDI file (.mid) read into a score, as Sibelius, Dorico and MuseScore do: each track (or
// each channel of a single-track file) becomes an instrument, named from the track or its sound; the
// notes are put on the nearest sixteenth (or eighth-note triplet, where a beat is played in threes),
// chords are gathered, notes that overlap go to a second voice, a piano is split at middle C into
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

// Each beat is read on a grid of sixteenths, or of eighth-note triplets when its notes fall on those.
function quantize(bars, notes) {
  const out = [];
  for (const n of notes) {
    const m = barAt(bars, n.on), b = bars[m], beat = WHOLE / b.time[1];
    const rel = n.on - b.t, bi = Math.floor(rel / beat), inBeat = rel - bi * beat;
    const g16 = beat / 4, g3 = beat / 3;
    const e16 = Math.abs(inBeat - Math.round(inBeat / g16) * g16), e3 = Math.abs(inBeat - Math.round(inBeat / g3) * g3);
    out.push({ ...n, m, bi, trip: e3 + 1 < e16 && b.time[1] <= 4 && !(b.time[1] === 8 && b.time[0] % 3 === 0) });
  }
  // (a beat with one note on a triplet place is written in triplets as a whole)
  const tripBeat = new Set(out.filter((x) => x.trip).map((x) => x.m + ':' + x.bi));
  for (const x of out) {
    const b = bars[x.m], beat = WHOLE / b.time[1], tr = tripBeat.has(x.m + ':' + x.bi), g = tr ? beat / 3 : beat / 4;
    x.on = b.t + Math.round((x.on - b.t) / g) * g;
    const len = Math.max(g, Math.round((x.off - x.on) / g) * g);
    x.off = x.on + len; x.trip = tr;
    // (a beat in triplets holds only its triplets: a triplet ends with its beat)
    if (tr) { const bEnd = b.t + (Math.floor((x.on - b.t) / beat) + 1) * beat; x.off = Math.min(x.off, bEnd); }
  }
  // (and a note held into a beat of triplets is let go where that beat begins)
  const starts = [...tripBeat].map((k) => { const [m, bi] = k.split(':').map(Number); const b = bars[m]; return b.t + bi * (WHOLE / b.time[1]); }).sort((a, b) => a - b);
  for (const x of out) if (!x.trip) { const cut = starts.find((t) => t > x.on && t < x.off); if (cut !== undefined) x.off = cut; }
  return out.filter((x) => x.off > x.on);
}
function placeNotes(score, bars, part, st, raw, drums) {
  if (!raw.length) return;
  const notes = quantize(bars, raw).sort((a, b) => a.on - b.on || b.midi - a.midi);
  // chords, and lanes (voices) so that nothing in one voice overlaps
  const lanes = [[], [], [], []];
  for (const n of notes) {
    let done = false;
    for (const L of lanes) { const c = L.find((x) => x.on === n.on && x.off === n.off); if (c) { if (!c.midis.includes(n.midi)) c.midis.push(n.midi); done = true; break; } }
    if (done) continue;
    let li = lanes.findIndex((L) => !L.length || L[L.length - 1].off <= n.on);
    if (li < 0) { const L = lanes[0]; L[L.length - 1].off = Math.max(L[L.length - 1].on + 1, n.on); li = 0; }   // (played legato: the note before is let go)
    lanes[li].push({ on: n.on, off: n.off, midis: [n.midi], trip: n.trip });
  }
  lanes.forEach((L, li) => {
    if (!L.length) return;
    const view = li === 0 ? st : voiceView(st, li + 1, score);
    // (a beat in triplets is first filled with triplet rests, so it always adds up)
    const done = new Set();
    for (const c of L) if (c.trip) {
      const m = barAt(bars, c.on), b = bars[m], time = timeAt(score, m), beat = WHOLE / time[1], bi = Math.floor((c.on - b.t) / beat);
      if (done.has(m + ':' + bi)) continue; done.add(m + ':' + bi);
      for (let k = 0; k < 3; k++) writeEvent(score, view, m, bi * beat + (k * beat) / 3, { id: newId(), rest: true, keep: true, t: time[1] * 2, dots: 0, tup: { n: 3, m: 2, base: time[1] * 2 } });
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
      // a triplet note: one or two triplet places, within its beat (what lasts longer is not tied on)
      const g = beat / 3, slot = Math.round((pos % beat) / g), k = Math.max(1, Math.min(3 - slot, Math.round(len / g)));
      const v = valueOf(k * g * 1.5) || valueOf(beat / 2);
      const ev = { id: newId(), t: v.t, dots: v.dots, tup: { n: 3, m: 2, base: v.t }, notes: notesOf(m) };
      writeEvent(score, st, m, Math.floor(pos / beat) * beat + slot * g, ev);
      break;
    } else {
      const pieces = decompose(pos, len, time, false);
      let p = pos;
      pieces.forEach((pc, i) => { writeEvent(score, st, m, p, { id: newId(), t: pc.t, dots: pc.dots, notes: notesOf(m).map((n) => ({ ...n, tie: more || i < pieces.length - 1 })) }); p += pc.ticks; });
    }
    t = end;
  }
}
function evTicksOf(e) { return Math.round((WHOLE / e.t) * (2 - Math.pow(0.5, e.dots || 0)) * (e.tup ? e.tup.m / e.tup.n : 1)); }
function keyFifths(score, m) { for (let i = m; i >= 0; i--) if (score.measures[i].key !== undefined && score.measures[i].key !== null) return score.measures[i].key; return 0; }
void allStaves;
