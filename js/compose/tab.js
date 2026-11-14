// Tablature for fretted instruments: which string and fret each note is played on.
// A tuning lists the open strings from the bottom line of the tablature up (for a guitar the low E
// first), as MIDI numbers at sounding pitch. String numbers are counted the guitarist's way: 1 is the
// highest string (the top line).
import { midiOf, VOICES, hasVoice, voiceKey, timeAt, ticksOf, instOf } from './model.js';

export const MAX_FRET = 24;

// the tuning of a part's tablature (the file's own, or the instrument's), or null when it has none
export function tabTuning(part) {
  if (!part) return null;
  const t = part.tuning || instOf(part).tuning;
  return Array.isArray(t) && t.length >= 3 && t.length <= 10 ? t : null;
}
// the part shows a tablature under its notes
export function hasTab(part) { return !!(part && part.tab && tabTuning(part)); }

// The strings for the notes sounding together: every note on its own string, the hand in one place
// (four frets at most from the lowest to the highest finger), where it already is when it can be
// (prev: the fret under the first finger; the hand covers it and the three above), low on the neck. fixed: note → string number
// asked for (a string marked in the music or read from a file). Returns [{ i, fret }] by note, or
// null for a note that does not fit.
export function placeChord(midis, tuning, prev = null, fixed = []) {
  const n = midis.length, S = tuning.length;
  const order = midis.map((m, k) => k).sort((a, b) => midis[b] - midis[a]);
  let best = null, bestCost = Infinity;
  const cur = new Array(n).fill(null), used = new Array(S).fill(false);
  const cost = () => {
    const fr = cur.filter(Boolean).map((c) => c.fret), played = fr.filter((f) => f > 0);
    const lo = played.length ? Math.min(...played) : 0, hi = played.length ? Math.max(...played) : 0, span = hi - lo;
    let c = (span > 4 ? 12 * (span - 4) : 0) + span * 0.5 + played.reduce((a, f) => a + f * 0.08, 0);
    if (prev !== null && played.length) c += (Math.max(0, prev - lo) + Math.max(0, hi - (prev + 3))) * 0.8;
    // (a note left out of a chord costs more than any reach)
    c += cur.filter((x) => !x).length * 100;
    return c;
  };
  const go = (j) => {
    if (j === n) { const c = cost(); if (c < bestCost) { bestCost = c; best = cur.map((x) => x && { ...x }); } return; }
    const k = order[j], m = midis[k];
    const want = fixed[k] ? S - fixed[k] : null;
    let any = false;
    for (let i = S - 1; i >= 0; i--) {
      if (used[i] || (want !== null && want >= 0 && want < S && i !== want)) continue;
      const f = m - tuning[i]; if (f < 0 || f > MAX_FRET) continue;
      used[i] = true; cur[k] = { i, fret: f }; any = true; go(j + 1); used[i] = false; cur[k] = null;
    }
    // (a string asked for that cannot play the note: any string then)
    if (!any && want !== null) for (let i = S - 1; i >= 0; i--) {
      if (used[i]) continue; const f = m - tuning[i]; if (f < 0 || f > MAX_FRET) continue;
      used[i] = true; cur[k] = { i, fret: f }; any = true; go(j + 1); used[i] = false; cur[k] = null;
    }
    if (!any) { cur[k] = null; go(j + 1); }
  };
  go(0);
  return best || midis.map(() => null);
}

// where the hand is after a chord: still in place when the frets are under it, else moved just enough
export function handAfter(prev, frets) {
  const played = frets.filter((f) => f > 0); if (!played.length) return prev;
  const lo = Math.min(...played), hi = Math.max(...played);
  if (prev === null) return Math.max(1, Math.min(lo, hi - 3));
  return lo < prev ? lo : hi > prev + 3 ? Math.min(lo, hi - 3) : prev;
}
// Every note of a staff (all its voices), placed in turn through the piece: Map note → { i, fret,
// str (1 = highest string), tied (held over from the note before) }.
export function tabPlan(score, st, tuning) {
  const out = new Map(); if (!tuning) return out;
  const S = tuning.length;
  let prev = null; const held = new Map();   // pitch held by a tie → its place
  for (let m = 0; m < st.bars.length; m++) {
    const time = timeAt(score, m), at = new Map();
    for (const bar of [st.bars[m] || [], ...VOICES.filter((v) => hasVoice(st, v, m)).map((v) => st[voiceKey(v)][m])]) {
      let p = 0;
      for (const ev of bar) { if (ev.notes && ev.notes.length && !ev.rest && !ev.cue) { if (!at.has(p)) at.set(p, []); at.get(p).push(ev); } p += ticksOf(ev, time); }
    }
    for (const p of [...at.keys()].sort((a, b) => a - b)) {
      const notes = [], fixed = [], keep = [];
      for (const ev of at.get(p)) for (const n of ev.notes) {
        const md = midiOf(n.s, n.a);
        const h = held.get(md);
        if (h) { keep.push([n, h]); continue; }
        const strMark = ev.notes.length === 1 && ev.str ? { I: 1, II: 2, III: 3, IV: 4, V: 5, VI: 6 }[ev.str] : 0;
        notes.push([n, md]); fixed.push(n.ts >= 1 && n.ts <= S ? n.ts : strMark || 0);
      }
      held.clear();
      // (notes held over keep their strings; the new ones take the others)
      for (const [n, h] of keep) out.set(n, { ...h, tied: true });
      const taken = new Set(keep.map(([, h]) => h.i));
      const t2 = tuning.map((x, i) => (taken.has(i) ? -999 : x));
      const pl = placeChord(notes.map(([, md]) => md), t2, prev, fixed);
      const frets = [];
      notes.forEach(([n], k) => { const c = pl[k]; if (!c) return; out.set(n, { i: c.i, fret: c.fret, str: S - c.i }); frets.push(c.fret); });
      prev = handAfter(prev, frets);
      for (const ev of at.get(p)) for (const n of ev.notes) if (n.tie && out.get(n)) held.set(midiOf(n.s, n.a), { i: out.get(n).i, fret: out.get(n).fret, str: out.get(n).str });
    }
  }
  return out;
}
