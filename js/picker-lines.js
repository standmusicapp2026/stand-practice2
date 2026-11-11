// The lines of music of a page, from what the reader found: where each line is, its bars (the
// places it can be cut), as parts of the page (0..1). Used by Capture (picker.js and its thread).
export function linesOf(A) {
  const lines = [];
  const W = A.w, H = A.h;
  for (const sys of A.systems || []) {
    const sts = sys.map((i) => A.staves[i]);
    const s0 = sts[0], sp = s0.sp;
    const top = Math.min(...sts.map((q) => q.top)), bot = Math.max(...sts.map((q) => q.bottom));
    const x0 = Math.max(0, Math.min(...sts.map((q) => q.x0)) - sp * 0.6), x1 = Math.min(W, Math.max(...sts.map((q) => q.x1)) + sp * 0.6);
    const heads = s0.heads || [];
    const firstHead = heads.length ? Math.min(...heads.map((q) => q.x)) : s0.x0 + sp * 5;
    const headEnd = Math.max(s0.x0 + sp * 2.5, firstHead - sp * 1.0);
    const bars = (s0.bars || []).map((b) => b.x).filter((x) => x > headEnd + sp && x < s0.x1 - sp * 1.2).sort((a, b) => a - b);
    // (each staff of the line, top to bottom: a piano's two, a quartet's four; one can be kept alone)
    const staves = sts.map((q) => [q.top, q.bottom]).sort((p, q) => p[0] - q[0]);
    lines.push({ y0: top - sp * 4.2, y1: bot + sp * 4.2, top, bot, x0, x1, headEnd, cuts: [headEnd, ...bars, s0.x1], W, H, sp, staves });
  }
  // neighbouring lines share the white space between them
  for (let i = 0; i < lines.length; i++) {
    if (i > 0) lines[i].y0 = Math.max(lines[i].y0, (lines[i - 1].bot + lines[i].top) / 2);
    if (i < lines.length - 1) lines[i].y1 = Math.min(lines[i].y1, (lines[i].bot + lines[i + 1].top) / 2);
  }
  for (let i = 0; i < lines.length; i++) {
    const L = lines[i];
    lines[i] = { y0: Math.max(0, L.y0) / H, y1: Math.min(H, L.y1) / H, x0: L.x0 / W, x1: L.x1 / W, cuts: L.cuts.map((x) => x / W), top: L.top / H, bot: L.bot / H, sp: L.sp / H, staves: L.staves.map(([t, b]) => [t / H, b / H]) };
  }
  return lines;
}

// only real lines of music: as wide as the others (a first line may be set in a little), staves of
// the size of the page's own
export function cleanLines(lines) {
  let ok = (lines || []).filter((L) => L && L.x1 > L.x0 && L.y1 > L.y0).sort((a, b) => a.y0 - b.y0);
  if (!ok.length) return [];
  // the staves played together (a violin over its piano, a quartet): one line, even where no bar
  // line joins them. Staves closer to each other than the lines of music are to each other belong
  // together.
  if (ok.length >= 2 && ok.every((L) => L.top !== undefined && L.sp)) {
    // (a staff this close to the next one, much closer than the lines of music are to each other,
    // and closer than about one and a half staves: they are played together)
    const gaps = ok.slice(1).map((L, i) => L.top - ok[i].bot), gmax = Math.max(...gaps);
    const out = [{ ...ok[0] }];
    gaps.forEach((g, i) => {
      const L = ok[i + 1], cur = out[out.length - 1], staff = Math.min(4 * cur.sp, 4 * L.sp);
      if (g < gmax * 0.4 && g < staff * 1.6) Object.assign(cur, { x0: Math.min(cur.x0, L.x0), x1: Math.max(cur.x1, L.x1), y1: L.y1, bot: L.bot, sp: Math.max(cur.sp, L.sp) });
      else out.push({ ...L });
    });
    ok = out;
  }
  const wmax = Math.max(...ok.map((L) => L.x1 - L.x0));
  const sps = ok.map((L) => L.sp || 0).filter((x) => x > 0).sort((a, b) => a - b), sp = sps.length ? sps[sps.length >> 1] : 0;
  const kept = ok.filter((L) => (L.x1 - L.x0) >= wmax * 0.45 && (!sp || !L.sp || (L.sp > sp * 0.65 && L.sp < sp * 1.5)));
  return kept.map((L, i) => {
    const s = L.sp || 0.01;
    // (tight around the staves: what is above and below them, not the next line's notes; above the
    // first line of a page (a title, a composer) and below the last (a footnote), tighter still)
    const up = i === 0 ? 3.0 : 4.2, down = i === kept.length - 1 ? 2.8 : 3.6;
    const y0 = L.top !== undefined ? Math.max(L.y0, L.top - s * up) : L.y0, y1 = L.bot !== undefined ? Math.min(L.y1, L.bot + s * down) : L.y1;
    return { x0: Math.max(0, L.x0 - 0.008), x1: Math.min(1, L.x1 + 0.008), y0: Math.max(0, y0), y1: Math.min(1, y1), ...(L.top !== undefined ? { top: L.top, bot: L.bot, sp: s } : {}) };
  });
}

// Each line's top and bottom edges, in pixels of a page drawn W x H, moved onto clean paper: a word
// or a note that the edge would cut through (a tempo above, a high note of the next line below) is
// either taken in whole or left out whole. g: the page's 2d context.
export function cleanEdges(g, W, H, lines) {
  // (ink: anything clearly darker than the paper, the grey staff lines of some editions too)
  const inkRow = (y, x0, w) => { if (y < 0 || y >= H) return false; const d = g.getImageData(x0, y, w, 1).data; for (let q = 0; q < d.length; q += 4) if (d[q] + d[q + 1] + d[q + 2] < 480) return true; return false; };
  const edges = lines.map((L) => ({ sx: Math.max(0, Math.round(L.x0 * W)), sw: Math.max(1, Math.min(W, Math.round(L.x1 * W)) - Math.max(0, Math.round(L.x0 * W))), a: Math.round(L.y0 * H), b: Math.min(H - 1, Math.round(L.y1 * H)) }));
  // (an edge moved inwards never comes into the staff itself: a line is never cut through)
  const staffTop = (k) => { const L = lines[k]; return L.top !== undefined ? Math.round((L.top - (L.sp || 0) * 1.2) * H) : H; };
  const staffBot = (k) => { const L = lines[k]; return L.bot !== undefined ? Math.round((L.bot + (L.sp || 0) * 1.2) * H) : 0; };
  edges.forEach((E, k) => {
    const reach = Math.round(H * 0.035);
    const upLimit = k > 0 ? edges[k - 1].b : 0, downLimit = k < edges.length - 1 ? edges[k + 1].a : H - 1;
    if (inkRow(E.a, E.sx, E.sw)) {
      let y = E.a; while (y > Math.max(upLimit, E.a - reach) && inkRow(y, E.sx, E.sw)) y--;
      if (!inkRow(y, E.sx, E.sw)) E.a = y; else { y = E.a; const stop = Math.min(E.a + Math.round((E.b - E.a) * 0.3), staffTop(k)); while (y < stop && inkRow(y, E.sx, E.sw)) y++; if (!inkRow(y, E.sx, E.sw)) E.a = y; }
    }
    if (inkRow(E.b, E.sx, E.sw)) {
      let y = E.b; while (y < Math.min(downLimit, E.b + reach) && inkRow(y, E.sx, E.sw)) y++;
      if (!inkRow(y, E.sx, E.sw)) E.b = y; else { y = E.b; const stop = Math.max(E.b - Math.round((E.b - E.a) * 0.3), staffBot(k)); while (y > stop && inkRow(y, E.sx, E.sw)) y--; if (!inkRow(y, E.sx, E.sw)) E.b = y; }
    }
  });
  return edges;
}

// What reaches into a line from beyond its edge (the stems of the next line's high notes, the tail of
// the line above) is taken away: at each edge, ink that goes on past it is wiped back to the paper.
// crop: the line's own 2d context (sw x sh), drawn from the page at (sx, sy); page: the page's context.
export function eraseCrossings(crop, sw, sh, page, sx, sy, H) {
  const dark = (d, i) => d[i] + d[i + 1] + d[i + 2] < 600;
  const img = crop.getImageData(0, 0, sw, sh), d = img.data;
  const out = (y) => (y >= 0 && y < H ? page.getImageData(sx, y, sw, 1).data : null);
  const below = out(sy + sh), above = out(sy - 1);
  let changed = false;
  for (const [edge, beyond, dir] of [[sh - 1, below, -1], [0, above, 1]]) {
    if (!beyond) continue;
    for (let x = 0; x < sw; x++) {
      if (!dark(beyond, x * 4) || !dark(d, (edge * sw + x) * 4)) continue;
      // (the run of ink from the edge inwards, at most a fifth of the line's height)
      // (only the thin part, a stem's end: where it meets something wider, a note head or a beam of
      // this line, it stops, and that is kept)
      const wide = (yy) => { let a = x, b = x; while (a > 0 && x - a < 8 && dark(d, (yy * sw + a - 1) * 4)) a--; while (b < sw - 1 && b - x < 8 && dark(d, (yy * sw + b + 1) * 4)) b++; return b - a + 1 > Math.max(6, sw * 0.004); };
      let y = edge, n = 0; const lim = Math.round(sh * 0.2);
      while (y >= 0 && y < sh && n < lim && dark(d, (y * sw + x) * 4) && !wide(y)) { y += dir; n++; }
      // (a long run, or one that ends in a note head or a beam inside: this line's own, kept; only a
      // thin end that stops on the paper inside belongs to the line beyond)
      if (n >= lim || n === 0 || (y >= 0 && y < sh && dark(d, (y * sw + x) * 4))) continue;
      for (let k = 0, yy = edge; k < n; k++, yy += dir) { for (const xx of [x - 2, x - 1, x, x + 1, x + 2]) { if (xx < 0 || xx >= sw || yy < 0 || yy >= sh) continue; const i = (yy * sw + xx) * 4; d[i] = d[i + 1] = d[i + 2] = 255; } }
      changed = true;
    }
  }
  if (changed) crop.putImageData(img, 0, 0);
}

// Each chosen line of a page with only its own ink, every mark whole. A cut straight across the page
// between two lines cut through what reached over it — a slur over a high note, a tempo mark, the
// stems of the next line's low notes — and half a mark was then thrown away with what it touched (a
// note went with its slur). Instead each piece of ink on the page goes, whole, to one line: what
// touches a line's staves is that line's; the rest (words, numbers, dynamics, hairpins, slurs between
// the lines) goes, nearest first, to the line whose ink it lies closest to, so a word goes with its
// neighbours and a tempo mark over a line with that line's other marks. What lies far from every
// line (a title, a page number, a footnote) goes with none. A piece reaching over two lines' staves
// (a stem of one touching a ledger line of the next) is shared out, each point to the nearer line.
// g: the page's 2d context, W x H; lines: all the page's lines (as linesOf gives them); want: the
// indices of the lines wanted. Returns, for each wanted line, { y0, y1, canvas } — the rows of the page
// it covers and a W x (y1 - y0) picture of them with only that line's ink, on white.
export function ownInk(g, W, H, lines, want) {
  const P = lines.map((L) => ({ top: L.top * H, bot: L.bot * H, sp: Math.max(2, L.sp * H), x0: L.x0 * W, x1: L.x1 * W, staves: (L.staves && L.staves.length ? L.staves : [[L.top, L.bot]]).map(([t, b]) => [t * H, b * H]) }));
  const lo = Math.max(0, Math.min(...want) - 1), hi = Math.min(P.length - 1, Math.max(...want) + 1);
  const spm = Math.max(...P.map((q) => q.sp));
  const yA = Math.max(0, Math.floor(P[lo].top - spm * 9)), yB = Math.min(H, Math.ceil(P[hi].bot + spm * 9));
  const bh = yB - yA;
  const img = g.getImageData(0, yA, W, bh), d = img.data;
  // (on a grid of half the size: four times less to go through; marks a point apart are one anyway)
  const hw = (W + 1) >> 1, hh = (bh + 1) >> 1, N = hw * hh;
  const ink = new Uint8Array(N);
  for (let y = 0; y < bh; y++) for (let x = 0; x < W; x++) { const i = (y * W + x) * 4; if (d[i] * 299 + d[i + 1] * 587 + d[i + 2] * 114 < 205000) ink[(y >> 1) * hw + (x >> 1)] = 1; }
  const lab = new Int32Array(N).fill(-1);
  let par = new Int32Array(1 << 14), nl = 0;
  const find = (a) => { while (par[a] !== a) { par[a] = par[par[a]]; a = par[a]; } return a; };
  for (let y = 0; y < hh; y++) for (let x = 0; x < hw; x++) {
    const i = y * hw + x; if (!ink[i]) continue;
    let l = -1;
    const nb = [x > 0 ? lab[i - 1] : -1, y > 0 && x > 0 ? lab[i - hw - 1] : -1, y > 0 ? lab[i - hw] : -1, y > 0 && x < hw - 1 ? lab[i - hw + 1] : -1];
    for (const q of nb) if (q >= 0) { if (l < 0) l = find(q); else { const a = find(l), b = find(q); if (a !== b) { if (a < b) par[b] = a; else par[a] = b; l = Math.min(a, b); } } }
    if (l < 0) { if (nl >= par.length) { const p2 = new Int32Array(par.length * 2); p2.set(par); par = p2; } par[nl] = nl; l = nl++; }
    lab[i] = l;
  }
  // the pieces: their boxes (in page points)
  const C = new Map();
  for (let i = 0; i < N; i++) {
    if (lab[i] < 0) continue;
    const r = find(lab[i]); lab[i] = r;
    const x = (i % hw) * 2, y = ((i / hw) | 0) * 2 + yA;
    let c = C.get(r); if (!c) C.set(r, (c = { x0: x, y0: y, x1: x + 1, y1: y + 1, n: 0, own: -1 }));
    if (x < c.x0) c.x0 = x; if (x + 1 > c.x1) c.x1 = x + 1; if (y < c.y0) c.y0 = y; if (y + 1 > c.y1) c.y1 = y + 1; c.n++;
  }
  // (on its staves: the lines whose staves the piece reaches into, across their width)
  const onStaff = (c) => {
    const hits = [];
    P.forEach((q, k) => { if (c.x1 < q.x0 - q.sp || c.x0 > q.x1 + q.sp) return; for (const [t, b] of q.staves) if (c.y1 >= t - q.sp * 0.25 && c.y0 <= b + q.sp * 0.25) { hits.push(k); return; } });
    return hits;
  };
  const gapOnes = [];
  for (const c of C.values()) {
    const h = onStaff(c);
    if (h.length === 1) c.own = h[0];
    else if (h.length > 1) c.own = -2;   // (shared out point by point)
    else gapOnes.push(c);
  }
  // where each line's ink reaches, column by column (on the half grid): its lowest and highest point
  const low = P.map(() => new Float32Array(hw).fill(-1e9)), high = P.map(() => new Float32Array(hw).fill(1e9));
  const nearestLine = (y) => { let best = 0, bd = Infinity; P.forEach((q, k) => { for (const [t, b] of q.staves) { const dd = y < t ? t - y : y > b ? y - b : 0; if (dd < bd) { bd = dd; best = k; } } }); return best; };
  const rowLine = new Int16Array(hh); for (let y = 0; y < hh; y++) rowLine[y] = nearestLine(y * 2 + yA);
  const ownerAt = (i) => { const r = lab[i]; if (r < 0) return -1; const c = C.get(r); if (c.own !== -2) return c.own; return rowLine[(i / hw) | 0]; };
  for (let i = 0; i < N; i++) {
    const k = ownerAt(i); if (k < 0) continue;
    const x = i % hw, y = ((i / hw) | 0) * 2 + yA;
    if (y > low[k][x]) low[k][x] = y; if (y < high[k][x]) high[k][x] = y;
  }
  // the pieces off the staves, nearest first: each to the line whose ink it is closest to (above it or
  // below it, beside it within a space and a half), and that line's ink then reaches that far
  const dist = (c, k) => {
    const q = P[k], r = q.sp * 1.5, a = Math.max(0, Math.floor((c.x0 - r) / 2)), b = Math.min(hw - 1, Math.ceil((c.x1 + r) / 2));
    let best = Infinity;
    for (let x = a; x <= b; x++) {
      const lo2 = low[k][x], hi2 = high[k][x]; if (lo2 < -1e8) continue;
      // (vertically from the box to that line's ink in this column: 0 when side by side)
      const dv = c.y0 > lo2 ? c.y0 - lo2 : c.y1 < hi2 ? hi2 - c.y1 : 0;
      // (and sideways, so a word's next letter counts as near, a mark far to the side as far)
      const xx = x * 2, dh = xx < c.x0 ? c.x0 - xx : xx > c.x1 ? xx - c.x1 : 0;
      const dd = Math.hypot(dv, dh); if (dd < best) best = dd;
    }
    return best / q.sp;
  };
  // (only the line just above a piece and the one just below it can have it)
  const around = (c) => { const m = (c.y0 + c.y1) / 2; let up = -1, dn = -1; P.forEach((q, k) => { if (q.bot <= m && (up < 0 || q.bot > P[up].bot)) up = k; if (q.top >= m && (dn < 0 || q.top < P[dn].top)) dn = k; }); return [up, dn].filter((k) => k >= 0); };
  const left = gapOnes.map((c) => ({ c, ks: around(c), d: null }));
  for (const e of left) e.d = e.ks.map((k) => dist(e.c, k));
  for (;;) {
    let be = null, bj = -1, bd = Infinity;
    for (const e of left) { if (e.c.own >= 0) continue; e.d.forEach((dd, j) => { if (dd < bd) { bd = dd; be = e; bj = j; } }); }
    // (nothing left within three spaces of any line: a title, a page number, a footnote)
    if (!be || bd > 3) break;
    const bc = be.c, bk = be.ks[bj]; bc.own = bk;
    for (let x = Math.max(0, bc.x0 >> 1); x <= Math.min(hw - 1, bc.x1 >> 1); x++) { if (bc.y1 > low[bk][x]) low[bk][x] = bc.y1; if (bc.y0 < high[bk][x]) high[bk][x] = bc.y0; }
    // (the pieces beside it are now nearer that line)
    const r = P[bk].sp * 1.6;
    for (const e of left) if (e.c.own < 0 && e.c.x1 >= bc.x0 - r && e.c.x0 <= bc.x1 + r) e.ks.forEach((k, j) => { if (k === bk) e.d[j] = dist(e.c, k); });
  }
  // each wanted line: the rows its ink covers, and its ink alone
  const out = new Map();
  for (const k of want) {
    const q = P[k];
    let y0 = q.top, y1 = q.bot;
    for (let x = Math.max(0, Math.floor(q.x0 / 2)); x <= Math.min(hw - 1, Math.ceil(q.x1 / 2)); x++) { if (high[k][x] < y0) y0 = high[k][x]; if (low[k][x] > y1) y1 = low[k][x]; }
    y0 = Math.max(yA, Math.floor(Math.max(y0, q.top - q.sp * 9) - q.sp * 0.6)); y1 = Math.min(yB, Math.ceil(Math.min(y1 + 2, q.bot + q.sp * 9) + q.sp * 0.6));
    // (a point is kept when it, or a point next to it, is this line's: the soft edge of each mark too)
    // (1: this line's ink; 2: ink of another line, or of none; 0: paper — and the faint grey of a thin
    // line drawn small, never taken for ink, stays as it is)
    const mine = new Uint8Array(N);
    for (let i = 0; i < N; i++) { if (lab[i] < 0) continue; mine[i] = ownerAt(i) === k ? 1 : 2; }
    const c = document.createElement('canvas'); c.width = W; c.height = y1 - y0;
    const cg = c.getContext('2d'); const o = cg.createImageData(W, y1 - y0), od = o.data;
    for (let y = y0; y < y1; y++) {
      const hy = (y - yA) >> 1;
      for (let x = 0; x < W; x++) {
        const hx = x >> 1, j = ((y - y0) * W + x) * 4, s = ((y - yA) * W + x) * 4;
        // (a point is taken away only near another's ink and away from this line's own)
        let me = false, them = false;
        for (let dy = -1; dy <= 1 && !me; dy++) { const yy = hy + dy; if (yy < 0 || yy >= hh) continue; for (let dx = -1; dx <= 1; dx++) { const xx = hx + dx; if (xx < 0 || xx >= hw) continue; const v = mine[yy * hw + xx]; if (v === 1) { me = true; break; } if (v === 2) them = true; } }
        const keep = me || !them;
        if (keep) { od[j] = d[s]; od[j + 1] = d[s + 1]; od[j + 2] = d[s + 2]; } else od[j] = od[j + 1] = od[j + 2] = 255;
        od[j + 3] = 255;
      }
    }
    cg.putImageData(o, 0, 0);
    out.set(k, { y0, y1, canvas: c });
  }
  return out;
}
