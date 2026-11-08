// The tempo printed in a score: a metronome mark (♩ = 108, M.M. 108, J = 108 as the iPad reads
// it) and the words (Allegretto, Andante con moto, Langsam, Modéré…). From the words of a page with
// where they are, the marks found, each with the tempo it asks for and its place on the page (0..1).

// typical tempos (beats a minute) for the words, the middle of each one's range
const WORDS = [
  ['prestissimo', 200], ['presto', 176], ['vivacissimo', 168], ['vivace', 152], ['allegrissimo', 160],
  ['allegro', 132], ['allegretto', 112], ['moderato', 108], ['andantino', 92], ['andante', 84],
  ['adagietto', 76], ['adagio', 70], ['larghetto', 63], ['lento', 56], ['largo', 50], ['grave', 40],
  // German, French, English
  ['sehr schnell', 184], ['schnell', 160], ['lebhaft', 138], ['bewegt', 112], ['mäßig', 96], ['massig', 96], ['gehend', 88],
  ['ruhig', 66], ['langsam', 58], ['sehr langsam', 46],
  ['très vite', 184], ['vite', 160], ['vif', 150], ['animé', 132], ['anime', 132], ['allant', 104], ['modéré', 100], ['modere', 100],
  ['lent', 56], ['très lent', 44],
  ['very fast', 180], ['fast', 152], ['quick', 144], ['lively', 138], ['brisk', 132], ['moderately', 104], ['moderate', 104], ['walking', 88],
  ['slowly', 60], ['slow', 60], ['very slow', 46],
];
// words that change the tempo of the word before or after them
const MODS = [
  [/\bmolto\s+allegro\b|\ballegro\s+(?:molto|assai)\b/, 152], [/\ballegro\s+(?:ma\s+non\s+troppo|non\s+troppo|moderato|giusto)\b/, 120],
  [/\ballegro\s+vivace\b/, 144], [/\ballegro\s+con\s+brio\b/, 144], [/\bandante\s+con\s+moto\b/, 92], [/\bandante\s+(?:sostenuto|maestoso)\b/, 76],
  [/\bpoco\s+adagio\b/, 76], [/\badagio\s+(?:molto|assai)\b|\bmolto\s+adagio\b/, 56], [/\badagio\s+(?:ma\s+)?non\s+troppo\b/, 76],
  [/\bpoco\s+allegro\b/, 120], [/\bpresto\s+(?:ma\s+)?non\s+troppo\b/, 160], [/\btempo\s+di\s+(?:minuetto|menuetto)\b/, 112],
  [/\btempo\s+di\s+valse\b|\bvalse\b|\bwaltz\b/, 168], [/\bmaestoso\b/, 84], [/\bsostenuto\b/, 72], [/\bcantabile\b/, 80],
];
const strip = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

// One line of words: the tempo it marks, or null.
export function parseTempo(text) {
  if (!text) return null;
  const raw = String(text).replace(/\s+/g, ' ').trim();
  if (raw.length > 80) return null;
  const t = strip(raw).replace(/[“”"«»]/g, '');
  // a number given with "=": ♩ = 108, J=108, q = 108, M.M. ♩ = c. 108, (= 60)
  let bpm = null, exact = false;
  const m = t.match(/(?:=|＝)\s*(?:c(?:a|irca)?\.?\s*)?(\d{2,3})(?:\s*[-–]\s*(\d{2,3}))?(?!\d)/) || t.match(/\bm\.?\s*m\.?\s*(?:[^\d\s]{1,2}\s*)?(?:=\s*)?(\d{2,3})(?:\s*[-–]\s*(\d{2,3}))?(?!\d)/);
  if (m) {
    let v = +m[1]; if (m[2]) v = Math.round((v + +m[2]) / 2);
    if (v >= 30 && v <= 300) { bpm = v; exact = true; }
  }
  // the words: at the start of the line (a tempo opens it), or alone before the number
  let word = null, wbpm = null;
  // (a movement's number before it: "II. Adagio", "2. Andante")
  const numbered = /^[\s(\[]*(?:(?:[ivx]+|\d+)\.\s*)?/i;
  const lead = t.replace(numbered, '');
  for (const [re, v] of MODS) { const k = lead.search(re); if (k >= 0 && k <= 2) { wbpm = v; word = lead.slice(k).match(re)[0]; break; } }
  if (!word) for (const [w, v] of WORDS.slice().sort((a, b) => b[0].length - a[0].length)) {
    const re = new RegExp('^' + w.replace(/\s/g, '\\s+') + '(?![\\p{L}])', 'u');
    if (re.test(lead)) { word = w; wbpm = v; break; }
  }
  // (a long sentence that only happens to start with "Lent" is no tempo: a mark is a few words)
  if (word && !exact) {
    const words = lead.split(/\s+/).filter(Boolean);
    if (words.length > 6) word = null;
    // (a word that tells what to do, not how fast: "a tempo", "Tempo I", "rit." are not starts)
    if (/^(a tempo|tempo i|tempo primo|rit|rall|accel)/.test(lead)) word = null;
  }
  if (!exact && !word) return null;
  // the label as printed (its words), the tempo as a number
  const printed = word ? (raw.replace(numbered, '').match(/^[^=(\d♩]*[\p{L}.]/u) || [''])[0].trim() : '';
  return { bpm: exact ? bpm : wbpm, exact, word: word ? (printed || word) : '', text: raw };
}

// The words of a page, each with its box (0..1 of the page), into the tempo marks: the words of a
// line read together, "Allegretto" and "(♩ = 108)" side by side are one mark.
export function findMarks(items) {
  // (words only: the music font's signs (clefs, time signatures, notes) are left out — no letters or
  // figures, a character of the font's own, or much taller than the words of the page)
  let L = (items || []).filter((it) => it && it.s && String(it.s).trim() && it.w > 0 && it.h > 0 && !/[\uE000-\uF8FF]/.test(it.s) && /[\p{L}\d=♩]/u.test(it.s)).map((it) => ({ s: String(it.s), x: it.x, y: it.y, w: it.w, h: it.h }));
  const hs = L.filter((it) => /\p{L}{2}/u.test(it.s)).map((it) => it.h).sort((a, b) => a - b);
  if (hs.length) { const mh = hs[hs.length >> 1]; L = L.filter((it) => it.h <= Math.max(mh * 2.4, hs[hs.length - 1] * 1.05) || /\p{L}{2}/u.test(it.s)); }
  L.sort((a, b) => a.y + a.h / 2 - (b.y + b.h / 2) || a.x - b.x);
  // words on one line (their middles at the same height) and near each other, joined
  const lines = [];
  for (const it of L) {
    const cy = it.y + it.h / 2;
    const ln = lines.find((l) => Math.abs(l.cy - cy) < Math.max(l.h, it.h) * 0.6 && it.x - (l.x + l.w) < 0.08 && it.x + it.w > l.x - 0.08);
    if (ln) { ln.parts.push(it); const x0 = Math.min(ln.x, it.x), x1 = Math.max(ln.x + ln.w, it.x + it.w), y0 = Math.min(ln.y, it.y), y1 = Math.max(ln.y + ln.h, it.y + it.h); Object.assign(ln, { x: x0, w: x1 - x0, y: y0, h: y1 - y0 }); }
    else lines.push({ cy, x: it.x, y: it.y, w: it.w, h: it.h, parts: [it] });
  }
  const out = [];
  for (const ln of lines) {
    ln.parts.sort((a, b) => a.x - b.x);
    const text = ln.parts.map((p) => p.s).join(' ');
    const t = parseTempo(text);
    if (!t || !t.bpm) continue;
    out.push({ x: +ln.x.toFixed(4), y: +ln.y.toFixed(4), w: +ln.w.toFixed(4), h: +ln.h.toFixed(4), bpm: t.bpm, exact: t.exact, word: t.word, text: t.text });
  }
  return out;
}
