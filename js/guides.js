// Smart guides, as in a design app (Canva, Keynote, Freeform): while something is moved or resized
// it is pulled into line with the page (its middle, edges and margins) and with the things around it
// (their edges and middles), and into equal spacing with its neighbours. Pink lines show what it
// lines up with; equal gaps show their size. Everything here works in page pixels (so a gap across
// is measured as a gap down), on plain boxes { x0, y0, x1, y1 }; nothing here touches the page.

// the page's own lines: its edges, its middle and the margins a layout keeps
function pageLines(W, H) {
  return {
    x: [{ at: 0, page: 1 }, { at: W / 2, page: 1, mid: 1 }, { at: W, page: 1 }, { at: W * 0.06, page: 1 }, { at: W * 0.94, page: 1 }],
    y: [{ at: 0, page: 1 }, { at: H / 2, page: 1, mid: 1 }, { at: H, page: 1 }, { at: H * 0.05, page: 1 }, { at: H * 0.95, page: 1 }],
  };
}
const lo = (b, ax) => (ax === 'x' ? b.x0 : b.y0), hi = (b, ax) => (ax === 'x' ? b.x1 : b.y1);
const plo = (b, ax) => (ax === 'x' ? b.y0 : b.x0), phi = (b, ax) => (ax === 'x' ? b.y1 : b.x1);
// do two boxes share a band across this axis (a row for x, a column for y)?
const sameBand = (a, b, ax) => Math.min(phi(a, ax), phi(b, ax)) - Math.max(plo(a, ax), plo(b, ax)) > 0;

// The ways the box could land on one axis: each a move d (pixels) that would put one of its edges
// (which: 0 low, 1 middle, 2 high; only those in `edges`) on a line, or make a gap equal.
function candidates(box, others, ax, W, H, edges) {
  const out = [], P = pageLines(W, H)[ax];
  const e = [lo(box, ax), (lo(box, ax) + hi(box, ax)) / 2, hi(box, ax)];
  const lines = [...P];
  for (const o of others) lines.push({ at: lo(o, ax), o }, { at: (lo(o, ax) + hi(o, ax)) / 2, o }, { at: hi(o, ax), o });
  for (const k of edges) for (const l of lines) out.push({ d: l.at - e[k], kind: 'line' });
  // equal spacing: only between neighbours in the same row (or column)
  if (edges.length === 3) {
    const band = others.filter((o) => sameBand(o, box, ax));
    const before = band.filter((o) => hi(o, ax) <= e[1]).sort((a, b) => hi(b, ax) - hi(a, ax));
    const after = band.filter((o) => lo(o, ax) >= e[1]).sort((a, b) => lo(a, ax) - lo(b, ax));
    const L = before[0], R = after[0], size = e[2] - e[0];
    // in the middle between its two neighbours
    if (L && R && lo(R, ax) - hi(L, ax) > size) out.push({ d: hi(L, ax) + (lo(R, ax) - hi(L, ax) - size) / 2 - e[0], kind: 'gap' });
    // the same gap as between the neighbour and the one beyond it
    const LL = L && band.filter((o) => o !== L && hi(o, ax) <= lo(L, ax) && sameBand(o, L, ax)).sort((a, b) => hi(b, ax) - hi(a, ax))[0];
    if (LL) out.push({ d: hi(L, ax) + (lo(L, ax) - hi(LL, ax)) - e[0], kind: 'gap' });
    const RR = R && band.filter((o) => o !== R && lo(o, ax) >= hi(R, ax) && sameBand(o, R, ax)).sort((a, b) => lo(a, ax) - lo(b, ax))[0];
    if (RR) out.push({ d: lo(R, ax) - (lo(RR, ax) - hi(R, ax)) - e[2], kind: 'gap' });
  }
  return out;
}

// The pull on one axis: the smallest move within reach (pixels), or 0.
export function snapMove(box, others, W, H, reach, edgesX = [0, 1, 2], edgesY = [0, 1, 2]) {
  const pick = (ax, edges) => {
    let best = null;
    for (const c of candidates(box, others, ax, W, H, edges)) if (Math.abs(c.d) <= reach && (!best || Math.abs(c.d) < Math.abs(best.d) - 1e-9)) best = c;
    return best ? best.d : 0;
  };
  return { dx: edgesX.length ? pick('x', edgesX) : 0, dy: edgesY.length ? pick('y', edgesY) : 0 };
}

// What to draw for a box where it is now: every line it sits on (to within tol pixels), drawn from
// it to what it lines up with (the page's lines across the whole page), and the equal gaps around it.
export function guidesFor(box, others, W, H, tol = 0.75) {
  const lines = [], gaps = [];
  for (const ax of ['x', 'y']) {
    const P = pageLines(W, H)[ax];
    const e = [lo(box, ax), (lo(box, ax) + hi(box, ax)) / 2, hi(box, ax)];
    const seen = new Map();
    const add = (at, a, b, page, mid) => {
      const k = Math.round(at * 2) / 2, g = seen.get(k);
      if (g) { g.a = Math.min(g.a, a); g.b = Math.max(g.b, b); g.page = g.page || page; g.mid = g.mid || mid; return; }
      const n = { ax, at, a, b, page, mid }; seen.set(k, n); lines.push(n);
    };
    for (const v of e) {
      for (const l of P) if (Math.abs(l.at - v) <= tol) add(l.at, 0, ax === 'x' ? H : W, 1, l.mid);
      for (const o of others) for (const at of [lo(o, ax), (lo(o, ax) + hi(o, ax)) / 2, hi(o, ax)]) {
        if (Math.abs(at - v) <= tol) add(at, Math.min(plo(o, ax), plo(box, ax)), Math.max(phi(o, ax), phi(box, ax)), 0, 0);
      }
    }
    // equal gaps: the gap on each side, and the same gap between the neighbours beyond
    const band = others.filter((o) => sameBand(o, box, ax));
    const L = band.filter((o) => hi(o, ax) <= e[0] + tol).sort((a, b) => hi(b, ax) - hi(a, ax))[0];
    const R = band.filter((o) => lo(o, ax) >= e[2] - tol).sort((a, b) => lo(a, ax) - lo(b, ax))[0];
    const gL = L ? e[0] - hi(L, ax) : null, gR = R ? lo(R, ax) - e[2] : null;
    const mid = (a, b) => (Math.max(plo(a, ax), plo(b, ax)) + Math.min(phi(a, ax), phi(b, ax))) / 2;
    const push = (a, b, across) => gaps.push({ ax, a, b, at: across, len: b - a });
    let shown = false;
    if (L && R && gL > 1 && Math.abs(gL - gR) <= tol * 2) { push(hi(L, ax), e[0], mid(L, box)); push(e[2], lo(R, ax), mid(R, box)); shown = true; }
    const LL = L && band.filter((o) => o !== L && hi(o, ax) <= lo(L, ax) + tol && sameBand(o, L, ax)).sort((a, b) => hi(b, ax) - hi(a, ax))[0];
    if (LL && gL > 1 && Math.abs(lo(L, ax) - hi(LL, ax) - gL) <= tol * 2) { push(hi(LL, ax), lo(L, ax), mid(LL, L)); if (!shown) push(hi(L, ax), e[0], mid(L, box)); shown = true; }
    const RR = R && band.filter((o) => o !== R && lo(o, ax) >= hi(R, ax) - tol && sameBand(o, R, ax)).sort((a, b) => lo(a, ax) - lo(b, ax))[0];
    if (RR && gR > 1 && Math.abs(lo(RR, ax) - hi(R, ax) - gR) <= tol * 2) { push(hi(R, ax), lo(RR, ax), mid(R, RR)); if (!shown || !gaps.some((g) => g.ax === ax && Math.abs(g.a - e[2]) < 0.5)) push(e[2], lo(R, ax), mid(R, box)); }
  }
  return { lines, gaps };
}

// Equal spacing for several things at once (Distribute): the moves (dx or dy, pixels) that leave the
// same gap between each one and the next, the first and last staying where they are.
export function distribute(boxes, ax) {
  const order = boxes.map((b, i) => ({ b, i })).sort((p, q) => lo(p.b, ax) + hi(p.b, ax) - lo(q.b, ax) - hi(q.b, ax));
  const n = order.length, moves = boxes.map(() => 0);
  if (n < 3) return moves;
  const start = lo(order[0].b, ax), end = Math.max(...order.map((p) => hi(p.b, ax)));
  const total = order.reduce((s, p) => s + hi(p.b, ax) - lo(p.b, ax), 0), gap = (end - start - total) / (n - 1);
  let at = start;
  for (const p of order) { moves[p.i] = at - lo(p.b, ax); at += hi(p.b, ax) - lo(p.b, ax) + gap; }
  return moves;
}
