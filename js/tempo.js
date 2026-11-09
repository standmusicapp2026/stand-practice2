// The tempo printed in a score: a metronome mark (♩ = 108, M.M. 108, J = 108 as the iPad reads
// it) and the words (Allegretto, Andante con moto, Langsam, Modéré…). From the words of a page with
// where they are, the marks found, each with the tempo it asks for and its place on the page (0..1).
// Tempo changes are marks too: a new movement, "Più mosso", "Meno mosso", "a tempo", "Tempo I"…
// (those say how the tempo changes; the tempo they make is worked out from the marks before them).

// typical tempos (beats a minute) for the words: the middle of the range each one is usually played in
const WORDS = [
  ['prestissimo', 208], ['presto', 184], ['vivacissimo', 172], ['allegrissimo', 168], ['vivace', 160], ['vivo', 160],
  ['allegro', 132], ['allegretto', 112], ['moderato', 112], ['andantino', 92], ['andante', 88],
  ['adagietto', 74], ['adagio', 70], ['larghetto', 63], ['lento', 52], ['largo', 50], ['grave', 40], ['larghissimo', 30],
  // German, French, English
  ['sehr schnell', 184], ['schnell', 160], ['lebhaft', 138], ['bewegt', 112], ['mäßig', 96], ['massig', 96], ['gehend', 88],
  ['ruhig', 66], ['langsam', 58], ['sehr langsam', 46],
  ['très vite', 184], ['vite', 160], ['vif', 150], ['animé', 132], ['anime', 132], ['allant', 104], ['modéré', 100], ['modere', 100],
  ['lent', 56], ['très lent', 44],
  ['very fast', 180], ['fast', 152], ['quick', 144], ['lively', 138], ['brisk', 132], ['moderately', 104], ['moderate', 104], ['walking', 88],
  ['slowly', 60], ['slow', 60], ['very slow', 46],
];
// the dances of suites and sonatas, named at the head of a movement: their usual tempo (and beat)
const DANCES = [
  ['allemande', 66], ['allemanda', 66], ['courante', 88], ['corrente', 132], ['sarabande', 54], ['sarabanda', 54],
  ['menuet', 120], ['menuetto', 120], ['minuetto', 120], ['minuet', 120], ['bourrée', 120], ['bourree', 120], ['gavotte', 120], ['gavotta', 120],
  ['gigue', 100, 1.5], ['giga', 100, 1.5], ['siciliano', 50, 1.5], ['siciliana', 50, 1.5], ['sicilienne', 50, 1.5], ['loure', 50, 1.5],
  ['polonaise', 88], ['polacca', 88], ['passepied', 152], ['rigaudon', 120], ['chaconne', 66], ['ciaccona', 66], ['passacaglia', 66],
  ['mazurka', 138], ['tarantella', 132, 1.5], ['habanera', 72], ['tango', 66],
];
// words that change the tempo of the word before or after them
const MODS = [
  [/\bmolto\s+allegro\b|\ballegro\s+(?:molto|assai)\b/, 152], [/\ballegro\s+(?:ma\s+non\s+troppo|non\s+troppo|moderato|giusto)\b/, 120],
  [/\ballegro\s+vivace\b/, 150], [/\ballegro\s+con\s+brio\b/, 144], [/\bandante\s+con\s+moto\b/, 96], [/\bandante\s+(?:sostenuto|maestoso)\b/, 76],
  [/\bandante\s+moderato\b/, 100], [/\bandante\s+(?:ma\s+)?non\s+troppo\b/, 80], [/\ballegretto\s+(?:ma\s+)?non\s+troppo\b/, 104],
  [/\bpoco\s+adagio\b/, 76], [/\badagio\s+(?:molto|assai)\b|\bmolto\s+adagio\b/, 56], [/\badagio\s+(?:ma\s+)?non\s+troppo\b/, 76],
  [/\bpoco\s+allegro\b/, 120], [/\bpresto\s+(?:ma\s+)?non\s+troppo\b/, 160], [/\btempo\s+di\s+(?:minuetto|menuetto)\b/, 120],
  [/\btempo\s+di\s+valse\b|\bvalse\b|\bwaltz\b/, 168], [/\bmaestoso\b/, 84], [/\bsostenuto\b/, 72], [/\bcantabile\b/, 80],
];
// the changes: faster or slower than before (by how much), back to the tempo before, the same again
const REL = [
  [/^(?:un\s+)?poco\s+(?:piu|più)\s+(?:mosso|animato|vivo|allegro|presto|moto)\b/, 'k', 1.08],
  [/^(?:piu|più)\s+(?:mosso|animato|vivo|allegro|presto|moto|vivace)\b|^stretto\b|^(?:plus\s+(?:vite|anime))\b|^(?:schneller|bewegter|etwas\s+bewegter|lebhafter)\b|^animato\b|^faster\b/, 'k', 1.15],
  [/^(?:un\s+)?poco\s+meno\s+(?:mosso|allegro|vivo)\b|^(?:un\s+)?poco\s+(?:piu|più)\s+lento\b/, 'k', 0.92],
  [/^meno\s+(?:mosso|allegro|vivo|presto)\b|^(?:piu|più)\s+(?:lento|tranquillo|calmo|adagio|largo)\b|^(?:plus\s+lent|moins\s+vite|retenu)\b|^(?:langsamer|ruhiger|etwas\s+langsamer)\b|^slower\b/, 'k', 0.85],
  [/^doppio\s+movimento\b|^doppio\s+(?:piu|più)\s+mosso\b/, 'k', 2],
  [/^doppio\s+(?:piu|più)\s+lento\b/, 'k', 0.5],
  [/^(?:tempo\s+(?:i|1|primo|1o|1°)|primo\s+tempo|tempo\s+(?:come\s+prima|del\s+principio)|come\s+prima|1er\s+mouvement|premier\s+mouvement|mouvement\s+du\s+debut|erstes\s+zeitma(?:ss|ß)|wie\s+(?:zu\s+anfang|vorher)|as\s+at\s+first)\b/, 'first'],
  [/^(?:a\s+tempo|in\s+tempo|au\s+mouvement|im\s+zeitma(?:ss|ß)|l['’]?\s*istesso\s+tempo|lo\s+stesso\s+tempo|stesso\s+tempo|tempo\s+giusto)\b/, 'same'],
];
const strip = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
// the note a metronome mark counts, in quarter notes: ♩ 1, ♩. 1.5, 𝅗𝅥 2, ♪ 0.5 (the music fonts'
// own signs, the Unicode ones, and the letters text fonts and the iPad's reader turn them into)
const NOTE = { '♩': 1, '♪': 0.5, '𝅗𝅥': 2, '𝅘𝅥': 1, '𝅘𝅥𝅮': 0.5, '\uECA3': 2, '\uECA5': 1, '\uECA7': 0.5, '\uE1D3': 2, '\uE1D5': 1, '\uE1D7': 0.5, '\uE1D9': 0.25 };
const NOTE_DOT = /[.·]/;
function unitOf(before) {
  const b = before.replace(/\s+$/, '');
  if (!b) return null;
  const m = b.match(/([♩♪]|𝅗𝅥|𝅘𝅥𝅮|𝅘𝅥|(?:^|[\s(])[qhejdJ])\s?([.·])?\(?$/u);
  if (!m) return null;
  const c = m[1].replace(/[\s(]/g, '');
  let u = NOTE[c];
  if (u == null) u = { q: 1, J: 1, j: 1, h: 2, d: 2, e: 0.5 }[c];
  if (u == null) return null;
  return m[2] && NOTE_DOT.test(m[2]) ? u * 1.5 : u;
}

// One line of words: the tempo it marks, or null. A change ("Più mosso") has no number of its own:
// { rel: 'k' (k: how much faster), 'first' (Tempo I) or 'same' (a tempo) }.
export function parseTempo(text) {
  if (!text) return null;
  const raw = String(text).replace(/\s+/g, ' ').trim();
  if (raw.length > 80) return null;
  const t = strip(raw).replace(/[“”"«»]/g, '');
  // (an instruction to go back, or the end: not a tempo)
  if (/\b(?:da\s+capo|d\.\s*c\.|dal\s+segno|d\.\s*s\.|fine|attacca|segue|volti)\b/.test(t) && !/=/.test(t)) return null;
  // a number given with "=": ♩ = 108, J=108, q = 108, M.M. ♩ = c. 108, (= 60)
  let bpm = null, exact = false, unit = null;
  const m = t.match(/(?:=|＝)\s*(?:c(?:a|irca)?\.?\s*)?(\d{2,3})(?:\s*[-–]\s*(\d{2,3}))?(?!\d)/) || t.match(/\bm\.?\s*m\.?\s*(?:[^\d\s]{1,2}\s*)?(?:=\s*)?(\d{2,3})(?:\s*[-–]\s*(\d{2,3}))?(?!\d)/);
  if (m) {
    let v = +m[1]; if (m[2]) v = Math.round((v + +m[2]) / 2);
    if (v >= 30 && v <= 300) {
      bpm = v; exact = true;
      // (the note before "=", in the line as printed)
      const at = raw.search(/=|＝/);
      if (at > 0) unit = unitOf(raw.slice(Math.max(0, at - 5), at));
    }
  }
  // the words: at the start of the line (a tempo opens it), or alone before the number
  let word = null, wbpm = null, rel = null, k = null, dunit = null;
  // (a movement's number before it: "II. Adagio", "2. Andante"; a bar's number: "25 Più mosso")
  const numbered = /^[\s(\[]*(?:(?:[ivx]+|\d+)\.\s*|\d{1,3}\s+(?=\p{L}))?/iu;
  const lead = t.replace(numbered, '');
  for (const [re, kind, f] of REL) { const r = lead.match(re); if (r) { rel = kind; k = f || null; word = r[0]; break; } }
  if (!rel) for (const [re, v] of MODS) { const i = lead.search(re); if (i >= 0 && i <= 2) { wbpm = v; word = lead.slice(i).match(re)[0]; break; } }
  if (!word && !rel) for (const [w, v] of WORDS.slice().sort((a, b) => b[0].length - a[0].length)) {
    const re = new RegExp('^' + w.replace(/\s/g, '\\s+') + '(?![\\p{L}])', 'u');
    if (re.test(lead)) { word = w; wbpm = v; break; }
  }
  // (a dance named at the head of a movement: "Sarabande", "Menuet II", "Gigue")
  if (!word && !rel) for (const [w, v, u] of DANCES) {
    const re = new RegExp('^' + w + '(?:\\s+(?:[ivx]+|\\d))?\\.?$', 'u');
    if (re.test(lead)) { word = w; wbpm = v; dunit = u || null; break; }
  }
  // (a long sentence that only happens to start with "Lent" is no tempo: a mark is a few words)
  if (word && !exact) {
    const words = lead.split(/\s+/).filter(Boolean);
    if (words.length > 6) { word = null; rel = null; }
    // (what to do, not how fast: "rit.", "rall.", "accel." are no tempo of their own)
    if (/^(rit|rall|accel|string|allarg|smorz|calando|morendo)/.test(lead)) { word = null; rel = null; }
  }
  if (!exact && !word && !rel) return null;
  // the label as printed (its words), the tempo as a number
  let printed = word ? (raw.replace(numbered, '').match(/^[^=(\d♩♪-]*[\p{L}.]/u) || [''])[0].trim() : '';
  if (unit && printed) printed = printed.replace(/\s+[qhejdJ]\s*\.?$/, '');
  const out = { bpm: exact ? bpm : rel ? null : wbpm, exact, word: word ? (printed || word) : '', text: raw };
  if (unit) out.unit = unit; else if (!exact && dunit) out.unit = dunit;
  if (!exact && wbpm && DANCES.some(([w]) => w === word)) out.dance = true;
  // (a change with its own number is just a tempo: "Più mosso ♩ = 132")
  if (rel && !exact) { out.rel = rel; if (k) out.k = k; }
  return out;
}

// (a word that can begin a mark in the middle of a line: after a bar's number, a dynamic, "cresc.")
const STARTS = /^(?:(?:un\s+)?poco\s+)?(?:piu|più|meno|tempo|a\s+tempo|doppio|stretto|animato|l['’]?istesso|lo\s+stesso|come\s+prima|allegr|andant|adagi|lento|largo|larghetto|moderato|presto|vivace|vivo|prestissimo|grave)/i;

// The words of a page, each with its box (0..1 of the page), into the tempo marks: the words of a
// line read together, "Allegretto" and "(♩ = 108)" side by side are one mark.
export function findMarks(items) {
  // (words only: the music font's signs (clefs, time signatures, notes) are left out — no letters or
  // figures, a character of the font's own, or much taller than the words of the page — except the
  // notes of a metronome mark, kept as ♩ ♪ 𝅗𝅥 and the dot)
  const keepNote = (s) => s.replace(/[]/g, '𝅗𝅥').replace(/[]/g, '♩').replace(/[]/g, '♪').replace(/[]/g, '.');
  let L = (items || []).filter((it) => it && it.s && String(it.s).trim() && it.w > 0 && it.h > 0)
    .map((it) => ({ s: keepNote(String(it.s)), x: it.x, y: it.y, w: it.w, h: it.h }))
    .filter((it) => !/[-]/.test(it.s) && /[\p{L}\d=♩♪𝅗𝅥]/u.test(it.s));
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
  const box = (ps) => { const x0 = Math.min(...ps.map((p) => p.x)), x1 = Math.max(...ps.map((p) => p.x + p.w)), y0 = Math.min(...ps.map((p) => p.y)), y1 = Math.max(...ps.map((p) => p.y + p.h)); return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 }; };
  for (const ln of lines) {
    ln.parts.sort((a, b) => a.x - b.x);
    let t = parseTempo(ln.parts.map((p) => p.s).join(' ')), ps = ln.parts;
    // not at its start: a mark later in the line ("25  Più mosso", "p  a tempo", "cresc.  Allegro")
    if (!t) for (let i = 1; i < ln.parts.length && !t; i++) {
      const first = ln.parts[i].s.trim();
      if (!STARTS.test(strip(first)) || !/^\p{Lu}|^a\s|^a$/u.test(first)) continue;
      const tt = parseTempo(ln.parts.slice(i).map((p) => p.s).join(' '));
      if (tt) { t = tt; ps = ln.parts.slice(i); }
    }
    if (!t || (!t.bpm && !t.rel)) continue;
    const b = ps === ln.parts ? ln : box(ps);
    const m = { x: +b.x.toFixed(4), y: +b.y.toFixed(4), w: +b.w.toFixed(4), h: +b.h.toFixed(4), bpm: t.bpm, exact: t.exact, word: t.word, text: t.text };
    if (t.unit) m.unit = t.unit;
    if (t.rel) { m.rel = t.rel; if (t.k) m.k = t.k; }
    if (t.dance) m.dance = true;
    out.push(m);
  }
  // (a dance's name with the tempo printed next to it, "Siciliano. Largo.": the tempo is the mark)
  return out.filter((m) => !m.dance || !out.some((o) => o !== m && !o.dance && Math.abs(o.y - m.y) < 0.06 && Math.abs(o.x - m.x) < 0.2));
}

// The tempo each mark makes, in reading order (pages one after another, each page top to bottom):
// a change goes from the tempo before it ("Più mosso" a little faster, "a tempo" the same again,
// "Tempo I" back to the tempo before the last change). `start` is the tempo when nothing came before.
export function resolveMarks(seq, start = null) {
  const abs = []; let cur = start, lastAbs = false;
  return seq.map((m) => {
    let v;
    if (!m.rel) v = m.bpm;
    else if (m.rel === 'same') v = cur;
    // (Tempo I: the tempo the section began in — the last printed tempo, or the one before it when
    // that last one is itself the change)
    else if (m.rel === 'first') v = lastAbs ? (abs.length >= 2 ? abs[abs.length - 2] : abs[0]) : abs.length ? abs[abs.length - 1] : cur;
    else v = cur != null ? Math.round(cur * (m.k || 1)) : null;
    if (!m.rel && v != null) abs.push(v);
    lastAbs = !m.rel;
    if (v != null) cur = v;
    return v;
  });
}

// The metronome's beat for a mark: the mark counts one note (♩ = 1, ♩. = 1.5, 𝅗𝅥 = 2, in quarters),
// the metronome another (its time signature's lower number). Returns { bpm, meter? } — a meter
// only when the metronome's cannot count it (♩. = 60 with the metronome in 4/4: 6/8 at 180).
export function metroFor(bpm, unit, meter) {
  if (!unit || !bpm) return { bpm };
  const mm = String(meter || '4/4').match(/^(\d+)\/(\d+)/), beats = mm ? +mm[1] : 4, lower = mm ? +mm[2] : 4;
  const per = 4 / lower;                           // the metronome's beat, in quarters
  const compound = (lower === 8 || lower === 16) && beats % 3 === 0;
  if (unit === 1.5 || unit === 0.75 || unit === 3) {
    // a dotted note: counted in threes. In a compound meter, its smaller notes; else 6/8 (or 6/4 for 𝅗𝅥.)
    if (compound) { const v = Math.round(bpm * unit / per); if (v <= 280) return { bpm: v }; }
    const lw = unit === 3 ? 4 : unit === 0.75 ? 16 : 8, v = Math.round(bpm * unit / (4 / lw));
    if (v >= 20 && v <= 280) return { bpm: v, meter: (compound && lower === lw ? beats : 6) + '/' + lw };
    return { bpm, meter: (compound ? beats / 3 : 2) + '/' + (unit === 3 ? 2 : unit === 0.75 ? 8 : 4), sub: 3 };
  }
  const v = Math.round(bpm * unit / per);
  if (v >= 20 && v <= 280) return { bpm: v };
  // (too fast or slow to count that way: the meter counted in the mark's own note)
  const lw = unit === 2 ? 2 : unit === 0.5 ? 8 : unit === 0.25 ? 16 : 4;
  const nb = Math.max(1, Math.round(beats * per / unit));
  return { bpm, meter: nb + '/' + lw };
}
