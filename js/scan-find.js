// Finding the page in a photo, the way a document scanner does: the ink is taken away first (the
// music's lines and notes would otherwise look like edges), the straight edges left are found, every
// four of them that could make a sheet of paper are tried, and the one that looks most like a sheet —
// strong edges all round, paper inside, the right shape — is kept and fitted exactly to its edges.
// Works on a picture about 640 points across; the corners come back as fractions of the picture.

const S = 640;
const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);

function smallOf(src) {
  const k = Math.min(1, S / Math.max(src.width, src.height));
  const c = document.createElement('canvas'); c.width = Math.max(1, Math.round(src.width * k)); c.height = Math.max(1, Math.round(src.height * k));
  const g = c.getContext('2d', { willReadFrequently: true }); g.imageSmoothingQuality = 'high'; g.drawImage(src, 0, 0, c.width, c.height);
  return c;
}
// running max (or min) over 2r+1 along rows then columns (van Herk / Gil-Werman: three compares a
// pixel, whatever r is)
function runExt(a, w, h, r, isMax) {
  const n = 2 * r + 1, out = new Float32Array(a.length), tmp = new Float32Array(a.length);
  const maxLen = Math.max(w, h) + 2 * r + n;
  const pad = new Float32Array(maxLen), g = new Float32Array(maxLen), hh = new Float32Array(maxLen);
  const fill = isMax ? -Infinity : Infinity;
  const pass = (src, dst, len, count, stride, step) => {
    const Lp = len + 2 * r;
    for (let c = 0; c < count; c++) {
      const base = c * stride;
      for (let i = 0; i < Lp; i++) { const j = i - r; pad[i] = j >= 0 && j < len ? src[base + j * step] : fill; }
      if (isMax) {
        for (let i = 0; i < Lp; i++) g[i] = i % n === 0 ? pad[i] : (g[i - 1] > pad[i] ? g[i - 1] : pad[i]);
        for (let i = Lp - 1; i >= 0; i--) hh[i] = i % n === n - 1 || i === Lp - 1 ? pad[i] : (hh[i + 1] > pad[i] ? hh[i + 1] : pad[i]);
        for (let j = 0; j < len; j++) { const x = hh[j], y = g[j + n - 1]; dst[base + j * step] = x > y ? x : y; }
      } else {
        for (let i = 0; i < Lp; i++) g[i] = i % n === 0 ? pad[i] : (g[i - 1] < pad[i] ? g[i - 1] : pad[i]);
        for (let i = Lp - 1; i >= 0; i--) hh[i] = i % n === n - 1 || i === Lp - 1 ? pad[i] : (hh[i + 1] < pad[i] ? hh[i + 1] : pad[i]);
        for (let j = 0; j < len; j++) { const x = hh[j], y = g[j + n - 1]; dst[base + j * step] = x < y ? x : y; }
      }
    }
  };
  pass(a, tmp, w, h, w, 1);
  pass(tmp, out, h, w, 1, w);
  return out;
}
const close = (a, w, h, r) => runExt(runExt(a, w, h, r, true), w, h, r, false);
function gauss(a, w, h, s) {
  const r = Math.max(1, Math.ceil(s * 2.5)), k = new Float32Array(2 * r + 1); let sum = 0;
  for (let i = -r; i <= r; i++) { const v = Math.exp(-(i * i) / (2 * s * s)); k[i + r] = v; sum += v; }
  for (let i = 0; i < k.length; i++) k[i] /= sum;
  const t = new Float32Array(a.length), o = new Float32Array(a.length);
  for (let y = 0; y < h; y++) {
    const row = y * w;
    for (let x = 0; x < w; x++) {
      let v = 0;
      if (x >= r && x < w - r) { const b0 = row + x - r; for (let i = 0; i < k.length; i++) v += a[b0 + i] * k[i]; }
      else for (let i = -r; i <= r; i++) v += a[row + clamp(x + i, 0, w - 1)] * k[i + r];
      t[row + x] = v;
    }
  }
  for (let y = 0; y < h; y++) {
    const inner = y >= r && y < h - r;
    for (let x = 0; x < w; x++) {
      let v = 0;
      if (inner) { let p = (y - r) * w + x; for (let i = 0; i < k.length; i++, p += w) v += t[p] * k[i]; }
      else for (let i = -r; i <= r; i++) v += t[clamp(y + i, 0, h - 1) * w + x] * k[i + r];
      o[y * w + x] = v;
    }
  }
  return o;
}
function sobel(a, w, h) {
  const gx = new Float32Array(a.length), gy = new Float32Array(a.length);
  for (let y = 0; y < h; y++) {
    const ym = (y > 0 ? y - 1 : 0) * w, y0 = y * w, yp = (y < h - 1 ? y + 1 : h - 1) * w;
    for (let x = 0; x < w; x++) {
      const xm = x > 0 ? x - 1 : 0, xp = x < w - 1 ? x + 1 : w - 1;
      const tl = a[ym + xm], tc = a[ym + x], tr = a[ym + xp], ml = a[y0 + xm], mr = a[y0 + xp], bl = a[yp + xm], bc = a[yp + x], br = a[yp + xp];
      gx[y0 + x] = (tr + 2 * mr + br - tl - 2 * ml - bl) / 8;
      gy[y0 + x] = (bl + 2 * bc + br - tl - 2 * tc - tr) / 8;
    }
  }
  return [gx, gy];
}
function pct(a, p) {
  // (a percentile from a sample of the values)
  const step = Math.max(1, Math.floor(a.length / 40000)), s = [];
  for (let i = 0; i < a.length; i += step) s.push(a[i]);
  s.sort((x, y) => x - y); return s[Math.min(s.length - 1, Math.floor(s.length * p))];
}
// The page's real height over its width, from its corners as the camera saw them (Zhang and He,
// "whiteboard scanning": the camera's focal length is worked out from the corners themselves).
// q: TL TR BR BL in pixels of a picture w × h.
export function trueAspect(q, w, h) {
  const u0 = w / 2, v0 = h / 2;
  const P = q.map(([x, y]) => [x - u0, y - v0, 1]);
  const [m1, m2, m4, m3] = P;
  const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const side = (i) => Math.hypot(q[(i + 1) % 4][0] - q[i][0], q[(i + 1) % 4][1] - q[i][1]);
  const plain = (side(1) + side(3)) / (side(0) + side(2));
  const d2 = dot(cross(m2, m4), m3), d3 = dot(cross(m3, m4), m2);
  if (Math.abs(d2) < 1e-9 || Math.abs(d3) < 1e-9) return plain;
  const k2 = dot(cross(m1, m4), m3) / d2, k3 = dot(cross(m1, m4), m2) / d3;
  const n2 = [k2 * m2[0] - m1[0], k2 * m2[1] - m1[1], k2 * m2[2] - m1[2]], n3 = [k3 * m3[0] - m1[0], k3 * m3[1] - m1[1], k3 * m3[2] - m1[2]];
  const den = n2[2] * n3[2];
  if (Math.abs(den) < 1e-9) return plain;
  const f2 = -(n2[0] * n3[0] + n2[1] * n3[1]) / den, M = Math.max(w, h);
  if (!(f2 > (0.3 * M) ** 2 && f2 < (6 * M) ** 2)) return plain;
  const wr = Math.sqrt((n2[0] ** 2 + n2[1] ** 2) / f2 + n2[2] ** 2), hr = Math.sqrt((n3[0] ** 2 + n3[1] ** 2) / f2 + n3[2] ** 2);
  return hr / wr;
}
function order(q) {
  const cx = (q[0][0] + q[1][0] + q[2][0] + q[3][0]) / 4, cy = (q[0][1] + q[1][1] + q[2][1] + q[3][1]) / 4;
  const s = q.slice().sort((a, b) => Math.atan2(a[1] - cy, a[0] - cx) - Math.atan2(b[1] - cy, b[0] - cx));
  let k = 0; for (let i = 1; i < 4; i++) if (s[i][0] + s[i][1] < s[k][0] + s[k][1]) k = i;
  return [0, 1, 2, 3].map((i) => s[(k + i) % 4]);
}

export function findPage(src, { dbg = null } = {}) {
  const T0 = performance.now(), tm = {};
  const c = smallOf(src), w = c.width, h = c.height, N = w * h;
  const d = c.getContext('2d', { willReadFrequently: true }).getImageData(0, 0, w, h).data;
  const L = new Float32Array(N), c1 = new Float32Array(N), c2 = new Float32Array(N);
  for (let j = 0, i = 0; j < N; j++, i += 4) { const R = d[i], G = d[i + 1], B = d[i + 2]; L[j] = 0.299 * R + 0.587 * G + 0.114 * B; c1[j] = R - G; c2[j] = (R + G) / 2 - B; }
  const r = Math.max(3, Math.round(S / 110));
  // the ink taken away: dark marks narrower than r vanish into the paper
  const Ls = gauss(close(L, w, h, r), w, h, 1.2), C1 = gauss(close(c1, w, h, r), w, h, 1.2), C2 = gauss(close(c2, w, h, r), w, h, 1.2);
  tm.prep = performance.now() - T0;
  const [gx, gy] = sobel(Ls, w, h), [ax, ay] = sobel(C1, w, h), [bx, by] = sobel(C2, w, h);
  const mag = new Float32Array(N), ang = new Float32Array(N);
  for (let j = 0; j < N; j++) { const hx = ax[j] + bx[j], hy = ay[j] + by[j]; mag[j] = Math.hypot(gx[j], gy[j]) + 1.5 * Math.hypot(hx, hy); ang[j] = Math.atan2(gy[j] + 1e-9, gx[j] + 1e-9); }
  // Hough: each strong edge pixel votes for the lines through it near its own direction
  const NT = 180, NR = Math.ceil(Math.hypot(w, h)) + 1, RW = 2 * NR;
  const acc = new Float32Array(NT * RW);
  const E = pct(mag, 0.99), thr = Math.max(pct(mag, 0.88), 0.12 * E, 1.2), CT = Math.min(9, Math.max(4, 0.9 * E));
  const vx = [], vy = [], vm = [], va = [];
  const cosT = new Float32Array(NT), sinT = new Float32Array(NT);
  for (let t = 0; t < NT; t++) { cosT[t] = Math.cos((t * Math.PI) / NT); sinT[t] = Math.sin((t * Math.PI) / NT); }
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const j = y * w + x; if (mag[j] <= thr) continue;
    const m = Math.min(mag[j], 60); let th = ang[j] % Math.PI; if (th < 0) th += Math.PI;
    vx.push(x); vy.push(y); vm.push(m); va.push(ang[j]);
    const t0 = Math.round((th / Math.PI) * NT);
    for (let dd = -2; dd <= 2; dd++) { const t = (((t0 + dd) % NT) + NT) % NT; const rho = Math.round(x * cosT[t] + y * sinT[t]) + NR; acc[t * RW + rho] += m; }
  }
  // (smoothed a little: a line's votes spread over a degree and a point or two)
  const A = new Float32Array(acc.length);
  for (let t = 0; t < NT; t++) for (let q = 1; q < RW - 1; q++) {
    let v = 0, wt = 0;
    for (let dt = -1; dt <= 1; dt++) { const tt = (t + dt + NT) % NT; for (let dq = -1; dq <= 1; dq++) { const k = (dt ? 1 : 2) * (dq ? 1 : 2); v += acc[tt * RW + q + dq] * k; wt += k; } }
    A[t * RW + q] = v / wt;
  }
  tm.hough = performance.now() - T0;
  const peaks = [];
  for (let n = 0; n < 26; n++) {
    let bi = 0, bv = 0; for (let i = 0; i < A.length; i++) if (A[i] > bv) { bv = A[i]; bi = i; }
    if (bv <= 0) break;
    const t = Math.floor(bi / RW), q = bi % RW;
    peaks.push([(t * Math.PI) / NT, q - NR, bv]);
    for (let dt = -5; dt <= 5; dt++) { const tt = (t + dt + NT) % NT; for (let dq = -8; dq <= 8; dq++) { const qq = q + dq; if (qq >= 0 && qq < RW) A[tt * RW + qq] = 0; } }
  }
  tm.peaks = performance.now() - T0;
  // each line made exact from the edge points along it (the votes are coarse: a degree, a point)
  const lines = [];
  for (const [t, rho, sv] of peaks) {
    const ct = Math.cos(t), st = Math.sin(t);
    let px = [], py = [], pw = [];
    for (let i = 0; i < vx.length; i++) {
      if (Math.abs(vx[i] * ct + vy[i] * st - rho) >= 3.5) continue;
      let da = ((va[i] - t) % Math.PI + Math.PI * 1.5) % Math.PI - Math.PI / 2;
      if (Math.abs(da) >= (12 * Math.PI) / 180) continue;
      px.push(vx[i]); py.push(vy[i]); pw.push(vm[i]);
    }
    if (px.length < 15) { lines.push({ t, r: rho, s: sv }); continue; }
    let nx = ct, ny = st, mx = 0, my = 0;
    for (let pass = 0; pass < 2; pass++) {
      let W = 0; mx = 0; my = 0; for (let i = 0; i < px.length; i++) { W += pw[i]; mx += px[i] * pw[i]; my += py[i] * pw[i]; } mx /= W; my /= W;
      let sxx = 0, sxy = 0, syy = 0; for (let i = 0; i < px.length; i++) { const dx = px[i] - mx, dy = py[i] - my; sxx += dx * dx * pw[i]; sxy += dx * dy * pw[i]; syy += dy * dy * pw[i]; }
      // the normal: the eigenvector of the smaller eigenvalue
      const tr = sxx + syy, det = sxx * syy - sxy * sxy, l2 = tr / 2 - Math.sqrt(Math.max(0, (tr * tr) / 4 - det));
      let ex = sxy, ey = l2 - sxx; if (Math.hypot(ex, ey) < 1e-9) { ex = l2 - syy; ey = sxy; } if (Math.hypot(ex, ey) < 1e-9) { ex = nx; ey = ny; }
      const nn = Math.hypot(ex, ey); nx = ex / nn; ny = ey / nn;
      const res = px.map((x, i) => Math.abs((x - mx) * nx + (py[i] - my) * ny));
      const sr = res.slice().sort((a, b) => a - b), cut = Math.max(1, sr[Math.floor(sr.length * 0.85)] * 1.3);
      const keep = res.map((v) => v < cut);
      px = px.filter((_, i) => keep[i]); py = py.filter((_, i) => keep[i]); pw = pw.filter((_, i) => keep[i]);
      if (px.length < 15) break;
    }
    let tt = Math.atan2(ny, nx), rr = mx * nx + my * ny;
    if (tt < 0) { tt += Math.PI; rr = -rr; }
    if (tt >= Math.PI) { tt -= Math.PI; rr = -rr; }
    lines.push({ t: tt, r: rr, s: sv });
  }
  tm.exact = performance.now() - T0;
  // the picture's own edges, for a page that runs off it
  const all = [...lines, { t: 0, r: 0, f: true }, { t: Math.PI / 2, r: 0, f: true }, { t: 0, r: w - 1, f: true }, { t: Math.PI / 2, r: h - 1, f: true }];
  const meet = (a, b) => {
    const a1 = Math.cos(a.t), b1 = Math.sin(a.t), a2 = Math.cos(b.t), b2 = Math.sin(b.t), det = a1 * b2 - a2 * b1;
    if (Math.abs(det) < 1e-6) return null;
    return [(a.r * b2 - b.r * b1) / det, (a1 * b.r - a2 * a.r) / det];
  };
  const angd = (a, b) => { const x = Math.abs(a - b) % Math.PI; return Math.min(x, Math.PI - x); };
  const at = (arr, x, y) => arr[clamp(Math.round(y), 0, h - 1) * w + clamp(Math.round(x), 0, w - 1)];
  const OFF = [2, 3, 5], NS = 28;
  // how clearly a side is an edge: the ink-free picture differs on its two sides (light or colour)
  const sideScore = (P, Q, cx, cy, isf) => {
    if (isf) return [0.45, 0];
    const len = Math.hypot(Q[0] - P[0], Q[1] - P[1]) + 1e-9;
    let nx = -(Q[1] - P[1]) / len, ny = (Q[0] - P[0]) / len;
    if (((P[0] + Q[0]) / 2 - cx) * nx + ((P[1] + Q[1]) / 2 - cy) * ny < 0) { nx = -nx; ny = -ny; }
    let sup = 0, sum = 0, br = 0;
    for (let k = 0; k < NS; k++) {
      const u = 0.06 + (0.88 * k) / (NS - 1), x = P[0] + (Q[0] - P[0]) * u, y = P[1] + (Q[1] - P[1]) * u;
      let li = 0, lo = 0, ai = 0, ao = 0, bi = 0, bo = 0;
      for (const e of OFF) {
        li += at(Ls, x - nx * e, y - ny * e); lo += at(Ls, x + nx * e, y + ny * e);
        ai += at(C1, x - nx * e, y - ny * e); ao += at(C1, x + nx * e, y + ny * e);
        bi += at(C2, x - nx * e, y - ny * e); bo += at(C2, x + nx * e, y + ny * e);
      }
      const cc = (Math.abs(li - lo) + 1.5 * (Math.abs(ai - ao) + Math.abs(bi - bo))) / 3;
      if (cc > CT) sup++;
      sum += Math.min(cc, 40); br += (li - lo) / 3;
    }
    return [(sup / NS) * Math.min(1, sum / NS / (CT * 2.8)), br / NS];
  };
  // (a side is the piece of one line between two others: many outlines share it, so it is scored once,
  // with its normal turned one fixed way; which way is "out" is settled for each outline)
  const memo = new Map();
  const sideOf = (li, e1, e2, P, Q, cx, cy, isf) => {
    if (isf) return [0.45, 0];
    const key = li * 4096 + Math.min(e1, e2) * 64 + Math.max(e1, e2);
    let m = memo.get(key);
    const [A0, B0] = e1 < e2 ? [P, Q] : [Q, P];
    if (!m) { m = sideScore(A0, B0, -1e7, -1e7, false); memo.set(key, m); }
    // (sideScore above took "inside" as away from a far point; flip the light difference if the page is the other side)
    const len = Math.hypot(B0[0] - A0[0], B0[1] - A0[1]) + 1e-9;
    let nx = -(B0[1] - A0[1]) / len, ny = (B0[0] - A0[0]) / len;
    const toFar = ((A0[0] + B0[0]) / 2 + 1e7) * nx + ((A0[1] + B0[1]) / 2 + 1e7) * ny >= 0;
    if (!toFar) { nx = -nx; ny = -ny; }
    const toC = ((A0[0] + B0[0]) / 2 - cx) * nx + ((A0[1] + B0[1]) / 2 - cy) * ny >= 0;
    return toC ? m : [m[0], -m[1]];
  };
  // (where every two lines cross, worked out once)
  const NL = all.length, MT = new Array(NL * NL).fill(null);
  for (let i = 0; i < NL; i++) for (let j = 0; j < NL; j++) if (i !== j) MT[i * NL + j] = meet(all[i], all[j]);
  const pairs = [];
  for (let i = 0; i < all.length; i++) for (let j = i + 1; j < all.length; j++) if (angd(all[i].t, all[j].t) <= (32 * Math.PI) / 180) pairs.push([i, j]);
  const cand = [];
  const ten = (n) => Array.from({ length: n }, (_, i) => 0.04 + (0.92 * i) / (n - 1));
  const UV = ten(9);
  for (let p1 = 0; p1 < pairs.length; p1++) {
    const [i, j] = pairs[p1];
    for (let p2 = p1 + 1; p2 < pairs.length; p2++) {
      const [k, l] = pairs[p2];
      if (k === i || k === j || l === i || l === j) continue;
      if (angd(all[i].t, all[k].t) < (50 * Math.PI) / 180) continue;
      const q = [MT[i * NL + k], MT[i * NL + l], MT[j * NL + l], MT[j * NL + k]];
      if (q.some((p) => !p)) continue;
      if (q.some(([x, y]) => x < -0.02 * w || x > 1.02 * w || y < -0.02 * h || y > 1.02 * h)) continue;
      let area = 0; for (let s = 0; s < 4; s++) area += q[s][0] * q[(s + 1) % 4][1] - q[(s + 1) % 4][0] * q[s][1]; area = Math.abs(area) / 2;
      if (area < 0.1 * N || area > 0.995 * N) continue;
      let ok = true, sgn = 0;
      for (let s = 0; s < 4; s++) {
        const ux = q[(s + 3) % 4][0] - q[s][0], uy = q[(s + 3) % 4][1] - q[s][1], wx = q[(s + 1) % 4][0] - q[s][0], wy = q[(s + 1) % 4][1] - q[s][1];
        const cs = Math.abs(ux * wx + uy * wy) / (Math.hypot(ux, uy) * Math.hypot(wx, wy) + 1e-9), z = Math.sign(ux * wy - uy * wx);
        if (cs > 0.6 || (sgn && z !== sgn)) { ok = false; break; } sgn = z;
      }
      if (!ok) continue;
      const sd = [0, 1, 2, 3].map((s) => Math.hypot(q[(s + 1) % 4][0] - q[s][0], q[(s + 1) % 4][1] - q[s][1]));
      if (Math.min(sd[0], sd[2]) / Math.max(sd[0], sd[2]) < 0.6 || Math.min(sd[1], sd[3]) / Math.max(sd[1], sd[3]) < 0.6) continue;
      let asp = (sd[1] + sd[3]) / (sd[0] + sd[2]); asp = Math.max(asp, 1 / asp); if (asp > 2.1) continue;
      const cx = (q[0][0] + q[1][0] + q[2][0] + q[3][0]) / 4, cy = (q[0][1] + q[1][1] + q[2][1] + q[3][1]) / 4;
      const l4 = [i, l, j, k], ends = [[k, l], [i, j], [l, k], [j, i]];
      let fr = 0; const sc = [], brs = [];
      for (let s = 0; s < 4; s++) { const isf = !!all[l4[s]].f; fr += isf; const [v, bb] = sideOf(l4[s], ends[s][0], ends[s][1], q[s], q[(s + 1) % 4], cx, cy, isf); sc.push(v); brs.push(bb); }
      if (fr > 2) continue;
      // (too weak an outline to be the page: not looked at further)
      const part = Math.pow(sc.reduce((m, v) => m * Math.max(v, 1e-3), 1), 0.25) * Math.pow(area / N, 0.2);
      if (part < 0.14) continue;
      // inside: paper all over (after the ink is taken away, much the same light and colour); a quad
      // reaching past the page takes in some of the table
      const iv = [], i1 = [], i2 = [];
      for (const vv of UV) for (const uu of UV) {
        const x = q[0][0] * (1 - uu) * (1 - vv) + q[1][0] * uu * (1 - vv) + q[2][0] * uu * vv + q[3][0] * (1 - uu) * vv;
        const y = q[0][1] * (1 - uu) * (1 - vv) + q[1][1] * uu * (1 - vv) + q[2][1] * uu * vv + q[3][1] * (1 - uu) * vv;
        iv.push(at(Ls, x, y)); i1.push(at(C1, x, y)); i2.push(at(C2, x, y));
      }
      const med = (arr) => { const s2 = arr.slice().sort((x, y) => x - y); return s2[s2.length >> 1]; };
      const ref = med(iv), r1 = med(i1), r2 = med(i2);
      let un = 0; for (let n = 0; n < iv.length; n++) if (Math.abs(iv[n] - ref) < Math.max(14, ref * 0.12) && Math.abs(i1[n] - r1) + Math.abs(i2[n] - r2) < 18) un++;
      const uni = un / iv.length;
      let score = Math.pow(sc.reduce((m, v) => m * Math.max(v, 1e-3), 1), 0.25) * Math.pow(area / N, 0.2) * uni * uni;
      // (an edge where the inside is darker than outside counts less: the page is the light thing)
      score *= 1 - 0.25 * (brs.filter((x) => x < -3).length / 4);
      // (a picture held upright and a page lying across it: most likely two pages side by side)
      const wide = sd[0] + sd[2] > (sd[1] + sd[3]) * 1.08;
      if ((h > w) === wide && fr === 0) score *= 0.8;
      // (a sheet of music paper is about 1.3 to 1.65 times as tall as it is wide)
      if (fr === 0) {
        let ta = trueAspect(order(q), w, h); ta = Math.max(ta, 1 / ta);
        if (ta < 1.22) score *= Math.max(0.4, Math.exp(-(((1.22 - ta) / 0.12) ** 2)));
        else if (ta > 1.75) score *= Math.max(0.4, Math.exp(-(((ta - 1.75) / 0.15) ** 2)));
      }
      cand.push({ score, q, ids: [i, j, k, l] });
    }
  }
  tm.quads = performance.now() - T0; tm.n = cand.length; tm.pairs = pairs.length;
  cand.sort((x, y) => y.score - x.score);
  // the best few looked at again: a clear straight edge right across the inside — a second sheet's
  // edge, the fold of a book — means two pages, and the page is one of them
  let best = null;
  for (const cd of cand.slice(0, 30)) {
    const { q } = cd; let pen = 1;
    for (let li = 0; li < all.length && pen === 1; li++) {
      const Ln = all[li]; if (Ln.f || cd.ids.includes(li)) continue;
      const nt = [Math.cos(Ln.t), Math.sin(Ln.t)];
      for (const [s1, s2] of [[0, 2], [1, 3]]) {
        const cross = (Aq, Bq) => { const dx = Bq[0] - Aq[0], dy = Bq[1] - Aq[1], den = nt[0] * dx + nt[1] * dy; if (Math.abs(den) < 1e-6) return null; const t = (Ln.r - nt[0] * Aq[0] - nt[1] * Aq[1]) / den; return t > 0.2 && t < 0.8 ? [Aq[0] + dx * t, Aq[1] + dy * t] : null; };
        const P1 = cross(q[s1], q[(s1 + 1) % 4]), P2 = cross(q[s2], q[(s2 + 1) % 4]);
        if (!P1 || !P2) continue;
        const [v] = sideScore(P1, P2, (P1[0] + P2[0]) / 2 + 1e3, (P1[1] + P2[1]) / 2 + 1e3, false);
        if (v > 0.35) { pen = 0.45; break; }
      }
    }
    const s = cd.score * pen;
    if (!best || s > best.score) best = { score: s, q };
  }
  tm.split = performance.now() - T0; globalThis.__fpT = tm;
  if (dbg) { dbg.lines = lines.length; dbg.cand = cand.length; dbg.score = best && best.score; }
  if (!best || best.score < 0.18) return null;
  let q = order(best.q);
  const Lr = gauss(Ls, w, h, 0.8);
  q = refine(q, Lr, w, h); q = refine(q, Lr, w, h);
  return q.map(([x, y]) => [clamp(x / w, 0, 1), clamp(y / h, 0, 1)]);
}
// each side moved onto the strongest step of the ink-free picture beside it, then fitted again
function refine(q, Ls, w, h) {
  const samp = (x, y) => {
    x = clamp(x, 0, w - 1.001); y = clamp(y, 0, h - 1.001); const x0 = Math.floor(x), y0 = Math.floor(y), fx = x - x0, fy = y - y0, i = y0 * w + x0;
    return Ls[i] * (1 - fx) * (1 - fy) + Ls[i + 1] * fx * (1 - fy) + Ls[i + w] * (1 - fx) * fy + Ls[i + w + 1] * fx * fy;
  };
  const cx = (q[0][0] + q[1][0] + q[2][0] + q[3][0]) / 4, cy = (q[0][1] + q[1][1] + q[2][1] + q[3][1]) / 4;
  const lines = [];
  for (let s = 0; s < 4; s++) {
    const P = q[s], Q = q[(s + 1) % 4], len = Math.hypot(Q[0] - P[0], Q[1] - P[1]);
    const dx = (Q[0] - P[0]) / len, dy = (Q[1] - P[1]) / len; let nx = -dy, ny = dx;
    if (((P[0] + Q[0]) / 2 - cx) * nx + ((P[1] + Q[1]) / 2 - cy) * ny < 0) { nx = -nx; ny = -ny; }
    const onFrame = (P[0] < 1 && Q[0] < 1) || (P[0] > w - 2 && Q[0] > w - 2) || (P[1] < 1 && Q[1] < 1) || (P[1] > h - 2 && Q[1] > h - 2);
    let pts = [];
    if (!onFrame) for (let k = 0; k < 40; k++) {
      const u = 0.08 + (0.84 * k) / 39, x = P[0] + (Q[0] - P[0]) * u, y = P[1] + (Q[1] - P[1]) * u;
      let bg = 0, bo = 0;
      for (let o = -10; o <= 10.001; o += 0.25) {
        const X = x + nx * o, Y = y + ny * o;
        const g = Math.abs((samp(X + nx * 0.5, Y + ny * 0.5) - samp(X - nx * 0.5, Y - ny * 0.5)));
        if (g > bg) { bg = g; bo = o; }
      }
      if (bg > 2) pts.push([x + nx * bo, y + ny * bo]);
    }
    if (pts.length < 8) { lines.push([P, [dx, dy]]); continue; }
    let c = [0, 0], dd = [dx, dy];
    for (let pass = 0; pass < 3; pass++) {
      c = [pts.reduce((a, p) => a + p[0], 0) / pts.length, pts.reduce((a, p) => a + p[1], 0) / pts.length];
      let sxx = 0, sxy = 0, syy = 0; for (const [x, y] of pts) { sxx += (x - c[0]) ** 2; sxy += (x - c[0]) * (y - c[1]); syy += (y - c[1]) ** 2; }
      const th = 0.5 * Math.atan2(2 * sxy, sxx - syy); dd = [Math.cos(th), Math.sin(th)];
      const nn = [-dd[1], dd[0]], res = pts.map(([x, y]) => Math.abs((x - c[0]) * nn[0] + (y - c[1]) * nn[1]));
      const sr = res.slice().sort((a, b) => a - b), cut = Math.max(0.6, sr[Math.floor(sr.length * 0.8)] * 1.5);
      const kept = pts.filter((_, i) => res[i] <= cut); if (kept.length < 8) break; pts = kept;
    }
    lines.push([c, dd]);
  }
  const meetPD = ([p, d], [r, e]) => { const det = d[0] * -e[1] - -e[0] * d[1]; if (Math.abs(det) < 1e-6) return null; const bx = r[0] - p[0], by = r[1] - p[1]; const t = (bx * -e[1] - -e[0] * by) / det; return [p[0] + d[0] * t, p[1] + d[1] * t]; };
  const out = [0, 1, 2, 3].map((s) => meetPD(lines[(s + 3) % 4], lines[s]));
  if (out.some((o) => !o) || out.some((o, i) => Math.hypot(o[0] - q[i][0], o[1] - q[i][1]) > 16)) return q;
  return out;
}

// The paper under the ink: light taken where it is brightest nearby (the ink taken away), then
// smoothed — what the page would look like with nothing printed on it. r: about half a notehead.
export function paperOf(L, w, h, r) {
  const P = close(L, w, h, r);
  // (a second, wider pass for big dark shapes — beams, a title — then smooth, the light changing slowly)
  const P2 = runExt(P, w, h, r * 2, true);
  const out = new Float32Array(P.length);
  for (let i = 0; i < P.length; i++) out[i] = Math.max(P[i], P2[i] * 0.9);
  return gauss(out, w, h, r * 0.8);
}
export const runMin = (a, w, h, r) => runExt(a, w, h, r, false);
export const gaussOf = (a, w, h, s) => gauss(a, w, h, s);
