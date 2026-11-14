// Guitar chord diagrams for chord symbols (standard tuning E A D G B E).
// The usual open shapes for C, D and G; every other chord from the two movable barre shapes (root on
// the 6th string, the "E" shape, or on the 5th, the "A" shape), whichever sits lower on the neck.
// A shape: frets for strings 6 to 1, -1 = not played.

const X = -1;
// open chords that are not a barre shape moved (the A and E families are the barre shapes at fret 0)
const OPEN = {
  C: [X, 3, 2, 0, 1, 0], C7: [X, 3, 2, 3, 1, 0], Cmaj7: [X, 3, 2, 0, 0, 0],
  D: [X, X, 0, 2, 3, 2], Dm: [X, X, 0, 2, 3, 1], D7: [X, X, 0, 2, 1, 2], Dm7: [X, X, 0, 2, 1, 1], Dmaj7: [X, X, 0, 2, 2, 2], Dsus4: [X, X, 0, 2, 3, 3], Dsus2: [X, X, 0, 2, 3, 0],
  G: [3, 2, 0, 0, 0, 3], G7: [3, 2, 0, 0, 0, 1],
};
// the barre shapes at fret 0 (E and A themselves): moved up by the root's fret
const E_FORM = { '': [0, 2, 2, 1, 0, 0], m: [0, 2, 2, 0, 0, 0], 7: [0, 2, 0, 1, 0, 0], m7: [0, 2, 0, 0, 0, 0], maj7: [0, 2, 1, 1, 0, 0], sus4: [0, 2, 2, 2, 0, 0] };
const A_FORM = { '': [X, 0, 2, 2, 2, 0], m: [X, 0, 2, 2, 1, 0], 7: [X, 0, 2, 0, 2, 0], m7: [X, 0, 2, 0, 1, 0], maj7: [X, 0, 2, 1, 2, 0], sus4: [X, 0, 2, 2, 3, 0], sus2: [X, 0, 2, 2, 0, 0],
  m7b5: [X, 0, 1, 0, 1, X], dim7: [X, 0, 1, 2, 1, 2], dim: [X, 0, 1, 2, 1, X], 6: [X, 0, 2, 2, 2, 2], m6: [X, 0, 2, 2, 1, 2] };
const PC = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
// the many ways a quality is written
function quality(q) {
  q = q.replace(/\s+/g, '');
  const map = [[/^(maj7|M7|Δ7?|ma7)$/, 'maj7'], [/^(m7b5|m7♭5|ø7?|-7b5)$/, 'm7b5'], [/^(dim7|°7|o7)$/, 'dim7'], [/^(dim|°|o)$/, 'dim'],
    [/^(m7|min7|-7)$/, 'm7'], [/^(m6|min6|-6)$/, 'm6'], [/^(m|min|-)$/, 'm'], [/^(7)$/, '7'], [/^(6)$/, '6'], [/^(sus4?|4)$/, 'sus4'], [/^(sus2|2)$/, 'sus2'], [/^(maj|M)?$/, '']];
  for (const [re, v] of map) if (re.test(q)) return v;
  return null;
}
// The shape for a chord symbol: { frets: [6 strings], base: the first fret shown } or null.
export function chordShape(sym) {
  const m = /^([A-G])([#♯b♭]?)([^/]*)(?:\/.*)?$/.exec(String(sym || '').trim());
  if (!m) return null;
  const q = quality(m[3]); if (q === null) return null;
  const name = m[1] + (m[2] === '♯' ? '#' : m[2] === '♭' ? 'b' : m[2]);
  if (OPEN[name + q]) return norm(OPEN[name + q]);
  const pc = (PC[m[1]] + (/[#♯]/.test(m[2]) ? 1 : /[b♭]/.test(m[2]) ? -1 : 0) + 12) % 12;
  const opts = [];
  if (E_FORM[q]) opts.push(E_FORM[q].map((f) => (f < 0 ? f : f + ((pc - 4 + 12) % 12))));
  if (A_FORM[q]) opts.push(A_FORM[q].map((f) => (f < 0 ? f : f + ((pc - 9 + 12) % 12))));
  if (!opts.length) return null;
  // (the shape lower on the neck)
  opts.sort((a, b) => Math.max(...a) - Math.max(...b));
  return norm(opts[0]);
}
function norm(frets) {
  const played = frets.filter((f) => f > 0);
  const hi = played.length ? Math.max(...played) : 0, lo = played.length ? Math.min(...played) : 0;
  const base = hi <= 4 ? 1 : lo;
  // a barre: the lowest fret across several strings, when the shape is moved up the neck
  let barre = null;
  if (base > 1 || frets.every((f) => f !== 0)) {
    const at = frets.map((f, i) => (f === lo ? i : -1)).filter((i) => i >= 0);
    if (at.length >= 2 && lo > 0) barre = { fret: lo, from: at[0], to: at[at.length - 1] };
  }
  return { frets: frets.slice(), base, barre };
}
