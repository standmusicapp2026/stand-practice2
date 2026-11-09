// Two parts on one screen: two players at one stand (a first and a second clarinet), each part
// with its own pages, shown one above the other at the same bars. Here: from the lines of music
// of every page and the words read on it, where each line is in the music (which piece or cue,
// which bars), the pieces of the two parts matched, and where the screen goes on a turn.
// (no screen here: main.js draws; this is the arithmetic, tested on its own)

// ---------- a part: its lines and their bars ----------
// pages: [{ lines: [{ y0, y1, x0, x1, top, bot, sp }], words: [{ s, x, y, w, h }] }] (parts of the page, 0…1)
// → [{ p, li, seg, label, first, last, known }] in playing order, and the pieces [{ label, from, to }]

// the name of a cue or piece as printed in film and show parts: 1M1, 1M2S, 2M14-15-16, 3M17-18
const CUE = /^([1-9]\d?)M(\d{1,3})([A-Z]{0,3})((?:[-–]\d{1,3}[A-Z]?)*)$/i;
export function cueOf(s, act = null) {
  // (the reader's usual slips: I or l for 1, O for 0, a dot or comma stuck on; the act's digit
  // left out of a big heading, "M1" for 1M1: the act it is in)
  let t = String(s || '').trim().replace(/[.,;:'"’)(]+$/, '').replace(/^[(]/, '');
  if (act && /^M[\dO]/.test(t)) t = act + t;
  t = t.replace(/^[Il|]/, '1').replace(/(?<=^\dM)[il|](?=\d)/, '').replace(/(?<=M\d*)[O]/g, '0');
  const m = t.match(CUE);
  return m ? (m[1] + 'M' + m[2] + m[3].toUpperCase() + m[4].replace(/–/g, '-')).toUpperCase() : null;
}

// (where a cue stands in the order: act, then number)
const cueRank = (c) => { const m = /^(\d+)M(\d+)/.exec(c || ''); return m ? +m[1] * 1000 + +m[2] : -1; };

// a bar number as printed: "37", or a span of bars resting "47-50" (or "47–50")
function numOf(s) {
  const t = String(s || '').trim().replace(/[.,]$/, '');
  let m = t.match(/^(\d{1,3})$/); if (m) return [+m[1], +m[1]];
  m = t.match(/^(\d{1,3})\s*[-–—~]\s*(\d{1,3})$/); if (m && +m[2] > +m[1]) return [+m[1], +m[2]];
  return null;
}

// the longest run of numbers that go up from left to right (a tuplet's 3, a fingering among them is left out)
function rising(c) {
  const n = c.length; if (!n) return [];
  const best = new Array(n).fill(1), prev = new Array(n).fill(-1);
  for (let i = 0; i < n; i++) for (let j = 0; j < i; j++) {
    // (each bar further on, and not too far: a line holds a few bars, or a few bars of rest)
    if (c[j].b < c[i].a && c[i].a - c[j].b <= 40 && best[j] + 1 > best[i]) { best[i] = best[j] + 1; prev[i] = j; }
  }
  let k = 0; for (let i = 1; i < n; i++) if (best[i] > best[k] || (best[i] === best[k] && c[i].a < c[k].a)) k = i;
  const out = []; for (; k >= 0; k = prev[k]) out.unshift(c[k]);
  return out;
}

// the numbers printed with one line: under the staff (each bar's own, or the line's first), or
// over it at the very start of the line
function lineNumbers(L, words) {
  const sp = L.sp || (L.bot - L.top) / 4 || 0.005, w = L.x1 - L.x0;
  const c = [];
  for (const q of words) {
    const v = numOf(q.s); if (!v) continue;
    const cy = q.y + q.h / 2, cx = q.x + q.w / 2;
    if (cx < L.x0 - w * 0.02 || cx > L.x1 + w * 0.02) continue;
    if (q.h > sp * 2.6) continue;   // (a big number is a count of bars over a rest, or a heading)
    const below = cy > L.bot + sp * 0.15 && cy < L.bot + sp * 4.2;
    const above = cy < L.top - sp * 0.3 && cy > L.top - sp * 4.5 && cx < L.x0 + w * 0.1;
    if (!below && !above) continue;
    c.push({ a: v[0], b: v[1], x: cx, above });
  }
  c.sort((p, q) => p.x - q.x);
  return rising(c);
}
// how many bars a line holds: its barlines (not the one it may open with), and the bars of rest a
// big number over a bar or a span under it ("1–6") counts; null when its barlines are not known
function barsIn(L, words, nums) {
  if (!Array.isArray(L.bars)) return null;
  const sp = L.sp || (L.bot - L.top) / 4 || 0.005;
  const inner = L.bars.filter((x) => x > L.x0 + sp * 3);
  let n = inner.length + (!inner.length || inner[inner.length - 1] < L.x1 - sp * 2.5 ? 1 : 0);
  // (rests of many bars: one bar on the line, many in the music)
  for (const q of nums) if (q.b > q.a) n += q.b - q.a;
  if (!nums.some((q) => q.b > q.a)) {
    for (const q of words) {
      const v = numOf(q.s); if (!v || v[0] !== v[1] || v[0] < 2 || v[0] > 99) continue;
      const cy = q.y + q.h / 2, cx = q.x + q.w / 2;
      if (cx < L.x0 || cx > L.x1 || q.h < sp * 2.2 || cy > L.top || cy < L.top - sp * 6) continue;
      n += v[0] - 1;
    }
  }
  return n;
}

export function partMap(pages) {
  const lines = [];
  let label = null;
  for (let p = 0; p < pages.length; p++) {
    const pg = pages[p] || {}, ls = (pg.lines || []).slice().sort((a, b) => a.y0 - b.y0), ws = pg.words || [];
    // the cue names on the page, top to bottom (the running head at the top, a new cue's heading
    // in the page)
    // (not the one a note at the end names: "0:15 until 1M2S")
    const until = ws.filter((q) => /^until$|^bis$|^jusqu/i.test(q.s));
    const act = label ? label.split('M')[0] : '1';
    const cues = ws.filter((q) => !until.some((u) => Math.abs(u.y - q.y) < 0.012 && q.x > u.x && q.x - u.x < 0.12))
      .map((q) => ({ c: cueOf(q.s, act), y: q.y + q.h / 2 })).filter((q) => q.c).sort((a, b) => a.y - b.y);
    ls.forEach((L, li) => {
      // (cues come in order: a name before the one being played is a name read wrong, 2M1 for 2M11)
      const over = cues.filter((q) => q.y < (L.top ?? L.y0) && !(label && cueRank(q.c) < cueRank(label)));
      // (one heading read twice, "M2" and "1M2S": the fullest reading)
      if (over.length) { const y = over[over.length - 1].y; label = over.filter((q) => y - q.y < 0.012).sort((a, b) => b.c.length - a.c.length)[0].c; }
      // (words standing clear between this line and the one before it — a heading, a piece's title —
      // and no new name read in them: a piece whose name the reader missed may start here)
      const sp = L.sp || 0.006, upper = li ? (ls[li - 1].bot ?? ls[li - 1].y1) + sp * 4.5 : 0.065, lower = (L.top ?? L.y0) - sp * 4.5;
      const heading = ws.filter((q) => { const cy = q.y + q.h / 2; return cy > upper && cy < lower && /\p{L}{2,}/u.test(q.s); }).length >= 2;
      const nums = lineNumbers(L, ws);
      lines.push({ p, li, label, heading, nums, count: barsIn(L, ws, nums), box: L, first: null, last: null, max: null, known: false });
    });
  }
  // (one cue read two ways, 1M2 and 1M2S, M17-18 put in the wrong act: the way most of its pages say it)
  const num = (c) => { const m = /M(\d+)/.exec(c || ''); return m ? +m[1] : null; };
  for (let i = 0; i < lines.length;) {
    let j = i; while (j < lines.length && lines[j].label === lines[i].label) j++;
    let k = j; while (k < lines.length && lines[k].label === (lines[j] || {}).label) k++;
    const a = lines[i].label, b = j < lines.length ? lines[j].label : null;
    const noAct = (c) => c.replace(/^\d+/, '');
    const aEnd = Math.max(0, ...lines.slice(i, j).flatMap((l) => l.nums.map((q) => q.b))), bStart = (lines.slice(j, k).find((l) => l.nums.length) || { nums: [{ a: 0 }] }).nums[0].a;
    if (a && b && num(a) === num(b) && (noAct(a) === noAct(b) || ((a.startsWith(b) || b.startsWith(a)) && bStart > aEnd))) {
      const keep = k - j >= j - i ? lines[j].label : lines[i].label;
      for (let q = i; q < k; q++) lines[q].label = keep;
      continue;   // (the two runs are one now: look again from its start)
    }
    i = j;
  }
  // the pieces: a new cue name, or the bars clearly starting again from the beginning
  const segs = [];
  let cur = null, high = 0;
  for (let i = 0; i < lines.length; i++) {
    const L = lines[i], prev = i ? lines[i - 1] : null, own = L.nums;
    // (a cue's name the reader missed: its first bars, 1 2 3…, after bars far on)
    const startsAt = own.length && (own[0].x - L.box.x0) / (L.box.x1 - L.box.x0) < (L.heading ? 0.45 : 0.3);
    const restart = prev && L.label === prev.label && high >= 8 && (
      (own.length >= 3 && own[0].a <= 3 && own[1].a - own[0].b <= 2 && own[2].a - own[1].b <= 2) ||
      (L.heading && startsAt && own[0].a <= 2));
    if (!cur || L.label !== cur.label || restart) { cur = { label: L.label, guess: !!restart, from: i, to: i, n: segs.length }; segs.push(cur); high = 0; }
    if (restart) L.label = null;
    cur.to = i; L.seg = cur.n;
    if (own.length >= 2) high = Math.max(high, own[own.length - 2].b);
  }
  // (a piece found by its bars starting again, whose name is read on a later page: the same piece)
  for (let k = segs.length - 2; k >= 0; k--) {
    const G = segs[k], N = segs[k + 1];
    if (!G.guess || N.guess || !N.label || N.label === G.label) continue;
    const g = lines.slice(G.from, G.to + 1).flatMap((l) => l.nums), n = lines.slice(N.from, N.to + 1).flatMap((l) => l.nums);
    if (g.length && n.length && n[0].a < g[g.length - 1].b) continue;
    G.to = N.to; G.label = N.label; G.guess = false; segs.splice(k + 1, 1);
  }
  segs.forEach((S, n) => { S.n = n; for (let i = S.from; i <= S.to; i++) { lines[i].seg = n; lines[i].label = S.label; } });
  for (const S of segs) {
    // in a piece the bar numbers go up from line to line: a number read wrong (a 7 for a 1, a
    // tuplet's 3 under the staff) is the one that does not
    const all = [];
    for (let i = S.from; i <= S.to; i++) lines[i].nums.forEach((q, j) => all.push({ ...q, i, j }));
    const keep = new Set(rising(all).map((q) => q.i + ':' + q.j));
    for (let i = S.from; i <= S.to; i++) lines[i].nums = lines[i].nums.filter((q, j) => keep.has(i + ':' + j));
    // each line's first bar: the number under its first bar, or the bar after the line before
    for (let i = S.from; i <= S.to; i++) {
      const L = lines[i], prev = i > S.from ? lines[i - 1] : null;
      if (!L.nums.length) {
        // (a line with no number read: after the line before, and before the next one read)
        let j = i + 1; while (j <= S.to && !lines[j].nums.length) j++;
        const nx = j <= S.to ? lines[j].nums[0].a : null;
        const st = prev ? prev.max + 1 : 1;
        L.first = nx != null ? Math.min(st, nx) : st; L.max = L.first + Math.max(1, L.count || 1) - 1;
        if (nx != null) L.max = Math.min(L.max, nx - 1);
        continue;
      }
      const n0 = L.nums[0], wl = L.box.x1 - L.box.x0, atStart = (n0.x - L.box.x0) / wl < 0.2;
      const after = prev ? prev.max + 1 : null;
      // (with its barlines known: the number less the bars before the one it stands under)
      const sp = L.box.sp || 0.006, inner = Array.isArray(L.box.bars) ? L.box.bars.filter((x) => x > L.box.x0 + sp * 3) : null;
      if (inner) L.first = n0.a - inner.filter((x) => x < n0.x).length;
      else L.first = atStart || after == null || after > n0.a ? n0.a : after;
      L.known = true;
      // (its last bar: the last number read on it, or as many bars on from its first as it holds)
      L.max = Math.max(L.first, L.nums[L.nums.length - 1].b, L.count ? L.first + L.count - 1 : 0);
    }
    for (let i = S.from; i <= S.to; i++) {
      const L = lines[i], N = i < S.to ? lines[i + 1] : null;
      L.last = N && N.first > L.first ? N.first - 1 : L.max;
    }
  }
  return { lines: lines.map(({ p, li, seg, label, first, last, known, box, nums }) => ({ p, li, seg, label, first, last, known, box, nums })), segs: segs.map(({ label, guess, from, to }) => ({ label: guess ? null : label, from, to })) };
}

// ---------- two parts: their pieces matched ----------
// The pieces in order, each part's piece for each (or none: a part that rests the whole piece).
// By name when the parts print one; by place in the order and the bars when not.
export function matchParts(A, B) {
  const a = A.segs, b = B.segs, na = a.length, nb = b.length;
  const bars = (P, s) => { const L = P.lines; return [L[s.from].first, L[s.to].last]; };
  const same = (i, j) => {
    const x = a[i], y = b[j];
    if (x.label && y.label) return x.label === y.label ? 0 : 9;
    // (no names: alike when their bars are alike)
    const [a0, a1] = bars(A, x), [b0, b1] = bars(B, y);
    return Math.abs(a0 - b0) <= 2 && Math.abs(a1 - b1) <= Math.max(4, a1 * 0.1) ? 0.5 : 3;
  };
  const SKIP = 2;
  const D = Array.from({ length: na + 1 }, () => new Float64Array(nb + 1));
  for (let i = 1; i <= na; i++) D[i][0] = i * SKIP;
  for (let j = 1; j <= nb; j++) D[0][j] = j * SKIP;
  for (let i = 1; i <= na; i++) for (let j = 1; j <= nb; j++) D[i][j] = Math.min(D[i - 1][j - 1] + same(i - 1, j - 1), D[i - 1][j] + SKIP, D[i][j - 1] + SKIP);
  const out = [];
  let i = na, j = nb;
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && D[i][j] === D[i - 1][j - 1] + same(i - 1, j - 1) && same(i - 1, j - 1) < SKIP) { out.unshift([i - 1, j - 1]); i--; j--; }
    else if (i > 0 && (j === 0 || D[i][j] === D[i - 1][j] + SKIP)) { out.unshift([i - 1, null]); i--; }
    else { out.unshift([null, j - 1]); j--; }
  }
  return out;   // [[segment of A or null, segment of B or null], …] in playing order
}

// ---------- where the screen is ----------
// A place: { k, bar } (k: the piece in the order of matchParts). Each part shows from the line that
// holds it.
export function makeDuo(A, B) {
  const M = matchParts(A, B), P = [A, B];
  // for each part: its pieces' place in the order, and each line's
  P.forEach((X, x) => {
    X.k = new Array(X.segs.length).fill(null);
    M.forEach((m, k) => { if (m[x] != null) X.k[m[x]] = k; });
    X.lines.forEach((L) => { L.k = X.k[L.seg]; });
  });
  const linked = P.every((X) => X.lines.some((L) => L.known));
  const before = (p, q) => p.k < q.k || (p.k === q.k && p.bar < q.bar);
  // the line of part x that holds a place (in a piece the part rests: its next line after it)
  function lineAt(x, at) {
    const L = P[x].lines; if (!L.length) return 0;
    let best = -1;
    for (let i = 0; i < L.length; i++) {
      const l = L[i];
      if (l.k < at.k || (l.k === at.k && l.first <= at.bar)) best = i;
      else break;
    }
    if (best < 0) return 0;
    const l = L[best];
    // (the place is past this line, and its piece goes on in another line further on: that one)
    if (l.k < at.k && best + 1 < L.length) return best + 1;
    return best;
  }
  const placeOf = (x, i) => { const l = P[x].lines[i]; return { k: l.k, bar: l.first }; };
  const endOf = (x, i) => { const l = P[x].lines[i]; return { k: l.k, bar: l.last }; };
  // after a place: the next bar, or the next piece's start
  function after(at) {
    for (let x = 0; x < 2; x++) {
      // (the last bar of a piece in a part that has it: on to the next piece)
    }
    const segLast = Math.max(...P.map((X) => { const ls = X.lines.filter((l) => l.k === at.k); return ls.length ? ls[ls.length - 1].last : -1; }));
    if (at.bar >= segLast) {
      // the first piece after it that either part has
      const nk = Math.min(...P.map((X) => { const l = X.lines.find((q) => q.k > at.k); return l ? l.k : Infinity; }));
      if (!isFinite(nk)) return null;
      const firsts = P.map((X) => { const l = X.lines.find((q) => q.k === nk); return l ? l.first : Infinity; });
      return { k: nk, bar: Math.min(...firsts) };
    }
    return { k: at.k, bar: at.bar + 1 };
  }
  return {
    M, parts: P, linked, before, lineAt, placeOf, endOf, after,
    start() { const p = P.map((X, x) => (X.lines.length ? placeOf(x, 0) : null)).filter(Boolean); return p.reduce((m, q) => (before(q, m) ? q : m), p[0] || { k: 0, bar: 1 }); },
    // the place after the screen: shown[x] = how many lines part x shows from its top line tops[x]
    next(tops, shown) {
      let end = null;
      for (let x = 0; x < 2; x++) {
        if (!P[x].lines.length || !shown[x]) continue;
        const e = endOf(x, Math.min(P[x].lines.length - 1, tops[x] + shown[x] - 1));
        if (!end || before(e, end)) end = e;
      }
      return end ? after(end) : null;
    },
  };
}

// ---------- the barlines of a line ----------
// Where its barlines are (as parts of the page's width): straight strokes from the staff's top line to
// its bottom line, no further, standing alone (a stem goes on past the staff to its head or beam; a
// letter, a clef, a time signature is wider and has ink beside it).
// img: { data (RGBA), width, height } of the page drawn; L: a line (0…1)
export function barsOf(img, L) {
  const W = img.width, H = img.height, d = img.data;
  if (L.top == null || L.bot == null) return null;
  const sp = (L.bot - L.top) * H / 4; if (!(sp > 3)) return null;
  const dark = (x, y) => { if (x < 0 || y < 0 || x >= W || y >= H) return false; const i = (y * W + x) * 4; return d[i] * 0.3 + d[i + 1] * 0.59 + d[i + 2] * 0.11 < 150; };
  // (ym: in a space of the staff, between its second and third lines, never on a line)
  const x0 = Math.round(L.x0 * W), x1 = Math.round(L.x1 * W), yT = L.top * H, yB = L.bot * H, ym = Math.round(yT + sp * 1.5);
  const out = [];
  for (let x = x0; x <= x1; x++) {
    // the dark run up and down from the staff's middle (a pixel of white in it allowed)
    if (!dark(x, ym) && !dark(x, ym + 1) && !dark(x, ym - 1)) continue;
    let a = ym, z = ym;
    for (let gap = 0; a > 0 && gap <= 1; a--) gap = dark(x, a - 1) ? 0 : gap + 1;
    for (let gap = 0; z < H - 1 && gap <= 1; z++) gap = dark(x, z + 1) ? 0 : gap + 1;
    const len = z - a;
    if (len < sp * 3.55 || len > sp * 4.5) continue;
    // (its ends on the top and bottom lines: the staff may lean a little across the page)
    if (Math.abs(a - yT) > sp * 1.2 || Math.abs(z - yB) > sp * 1.2) continue;
    // thin, and nothing beside it in the staff's spaces (a note's head, a digit, a clef)
    let e = x; while (e + 1 <= x1 && dark(e + 1, ym) && e - x < sp) e++;
    if (e - x + 1 > sp * 0.6) { x = e; continue; }
    const side = (xx) => { let n = 0, t = 0; for (let y = Math.round(a + sp * 0.5); y <= z - sp * 0.5; y++) { t++; if (dark(xx, y)) n++; } return t ? n / t : 1; };
    const besideL = side(Math.round(x - sp * 0.3)), besideR = side(Math.round(e + sp * 0.3));
    if (Math.max(besideL, besideR) > 0.42) { x = e; continue; }
    // (a stem with its head at an end, on a line: ink wide at that end, beside the stroke)
    const capped = [a, z].some((y) => { let n = 0; for (let dy = -Math.round(sp * 0.35); dy <= sp * 0.35; dy++) for (const xx of [x - Math.round(sp * 0.6), e + Math.round(sp * 0.6)]) if (dark(xx, y + dy)) n++; return n > sp * 0.5; });
    if (capped) { x = e; continue; }
    out.push((x + e) / 2 / W);
    x = e + Math.round(sp * 0.4);
  }
  // (a double barline is one)
  const merged = [];
  for (const b of out) { if (merged.length && (b - merged[merged.length - 1]) * W < sp * 1.2) merged[merged.length - 1] = b; else merged.push(b); }
  return merged.map((b) => +b.toFixed(4));
}

// ---------- one long line of each part, one over the other ----------
// The bars of a line, each with where it is across the page (0…1): from its barlines and its numbers
// (a bar of rest with a span under it, "47–50", is those bars). Barlines the reader missed or saw
// twice: the line shared out evenly between its bars.
export function lineUnits(L, { trim = false } = {}) {
  const box = L.box || {}, sp = box.sp || 0.006, n = Math.max(1, L.last - L.first + 1);
  // (a line that goes on from the one before: from after its clef)
  const x0 = trim && box.clef && box.clef > box.x0 ? box.clef : box.x0, x1 = box.x1;
  const inner = Array.isArray(box.bars) ? box.bars.filter((x) => x > x0 + sp * 3 && x < x1 - sp * 0.8) : [];
  // (the line's last barline is its end; the line's box goes a little past it)
  const ends = inner.length && x1 - inner[inner.length - 1] < sp * 3 ? inner : [...inner, x1];
  const cuts = [x0, ...ends];
  const spans = (L.nums || []).filter((q) => q.b > q.a);
  const units = [];
  for (let i = 0; i < cuts.length - 1; i++) {
    const a = cuts[i], z = cuts[i + 1]; if (z - a < sp * 1.5) continue;
    const r = spans.find((q) => q.x > a && q.x < z);
    units.push({ x0: a, x1: z, w: r ? r.b - r.a + 1 : 1 });
  }
  const tot = units.reduce((s, u) => s + u.w, 0);
  if (!units.length || tot !== n) {
    // (shared out evenly: a bar's place is a guess, the line's is not)
    return Array.from({ length: n }, (_, i) => ({ a: L.first + i, b: L.first + i, x0: x0 + ((x1 - x0) * i) / n, x1: x0 + ((x1 - x0) * (i + 1)) / n }));
  }
  let bar = L.first;
  return units.map((u) => { const o = { a: bar, b: bar + u.w - 1, x0: u.x0, x1: u.x1 }; bar += u.w; return o; });
}

// The columns of the two long lines: as few bars as both parts end a bar together after (a bar of
// rest of many bars in one part takes as many bars of the other). Each part's pieces of line in it.
// sizeOf(x, line) → how wide one unit of page width is on screen for that line (its staff the size
// of the other part's)
export function columns(D, sizeOf) {
  const out = [];
  D.M.forEach((m, k) => {
    // each part's bars of this piece, in order
    const U = [0, 1].map((x) => {
      const P = D.parts[x]; if (m[x] == null) return [];
      const u = [];
      let firstLine = true;
      P.lines.forEach((L, i) => { if (L.k !== k) return; for (const q of lineUnits(L, { trim: !firstLine })) u.push({ ...q, line: i, px: (q.x1 - q.x0) * sizeOf(x, L) }); firstLine = false; });
      return u;
    });
    let ia = 0, ib = 0;
    while (ia < U[0].length || ib < U[1].length) {
      const ca = [], cb = [];
      if (ia >= U[0].length) { cb.push(U[1][ib++]); }
      else if (ib >= U[1].length) { ca.push(U[0][ia++]); }
      else {
        ca.push(U[0][ia++]); cb.push(U[1][ib++]);
        // (until both end the same bar)
        for (let guard = 0; guard < 200; guard++) {
          const ea = ca[ca.length - 1].b, eb = cb[cb.length - 1].b;
          if (ea === eb) break;
          if (ea < eb) { if (ia >= U[0].length) break; ca.push(U[0][ia++]); }
          else { if (ib >= U[1].length) break; cb.push(U[1][ib++]); }
        }
      }
      const wa = ca.reduce((s, u) => s + u.px, 0), wb = cb.reduce((s, u) => s + u.px, 0);
      const a = Math.min(...[...ca, ...cb].map((u) => u.a)), b = Math.max(...[...ca, ...cb].map((u) => u.b));
      out.push({ k, a, b, w: Math.max(wa, wb), units: [ca, cb], first: out.length === 0 || out[out.length - 1].k !== k });
    }
  });
  return out;
}

// Where a line's clef ends (as part of the page's width), for lines put end to end: the clef is
// printed again at every line, the long line needs it only at its start. The first stroke of ink
// from the left that rises above the staff and is about a clef wide; null if not clear.
export function clefEnd(img, L) {
  const W = img.width, H = img.height, d = img.data;
  if (L.top == null || L.bot == null) return null;
  const sp = ((L.bot - L.top) * H) / 4; if (!(sp > 3)) return null;
  const dark = (x, y) => { if (x < 0 || y < 0 || x >= W || y >= H) return false; const i = (y * W + x) * 4; return d[i] * 0.3 + d[i + 1] * 0.59 + d[i + 2] * 0.11 < 150; };
  const yT = L.top * H;
  // (rows in the staff's spaces and just outside it: never on a staff line)
  const rows = [-1.1, -0.6, 0.5, 1.5, 2.5, 3.5, 4.6].map((k) => Math.round(yT + k * sp));
  const ink = (x) => rows.some((y) => dark(x, y) || dark(x, y + 1));
  const x0 = Math.round(L.x0 * W), lim = Math.round(x0 + sp * 7);
  let a = x0; while (a < lim && !ink(a)) a++;
  if (a >= lim) return null;
  let z = a, gap = 0;
  for (let x = a; x < lim; x++) { if (ink(x)) { z = x; gap = 0; } else if (++gap > sp * 0.3) break; }
  const w = (z - a) / sp;
  // (a clef: one to four staff spaces wide, its ink above the staff)
  if (w < 1 || w > 4 || ![a, Math.round((a + z) / 2), z].some((x) => dark(x, rows[0]) || dark(x, rows[1]))) return null;
  return +((z + sp * 0.35) / W).toFixed(4);
}
