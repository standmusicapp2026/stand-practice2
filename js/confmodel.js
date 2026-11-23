// How sure Studio is of each bar it followed: the chance the bar is wrong (more than a quarter of a bar
// off), by a model learned from recordings followed and checked by hand (confmodel-data.js, written by
// omreval/tools/confexport.py). The bars sure by it are shown plain; only the others are to check.
import { SURE, DOUBT, BASE, TREES } from './confmodel-data.js';
export { SURE, DOUBT };

// what the model looks at for each bar (the same, in the same order, as omreval/tools/conffit.py):
// how well its notes fit, how much the other likely ways of following agree on it, how far it is from
// bars with notes, how its length compares with its neighbours' and the piece's, where it is.
export function barFeatures({ conf, conf2, bconf, ev, nn, T, n, staffsN, risk }) {
  const nb = nn.length, d = [];
  for (let k = 0; k < nb; k++) d.push(T[k + 1] - T[k]);
  const md = d.slice().sort((a, b) => a - b)[nb >> 1] || 1;
  const out = [];
  for (let k = 0; k < nb; k++) {
    const e = ev[k];
    let run = 0, j = k;
    while (j >= 0 && !nn[j]) { run++; j--; }
    j = k + 1;
    while (j < nb && !nn[j]) { run++; j++; }
    let dl = 99, dr = 99;
    for (j = k; j >= 0; j--) if (nn[j]) { dl = k - j; break; }
    for (j = k; j < nb; j++) if (nn[j]) { dr = j - k; break; }
    const nbh = [k - 1, k + 1].filter((q) => q >= 0 && q < nb).map((q) => d[q]);
    const jump = nbh.length ? Math.abs(Math.log(Math.max(0.05, d[k]) / Math.max(0.05, nbh.reduce((a, b) => a + b, 0) / nbh.length))) : 0;
    let cs = Infinity;
    for (let q = Math.max(0, k - 2); q < Math.min(nb, k + 3); q++) cs = Math.min(cs, conf2[q]);
    out.push([conf[k], conf2[k], cs, bconf[k] != null ? bconf[k] : 0.5,
      e ? e[0] : -1, e ? e[1] : -1, e ? e[2] : 0, nn[k], Math.min(run, 20), Math.min(dl, 20), Math.min(dr, 20),
      jump, Math.abs(Math.log(Math.max(0.05, d[k]) / md)), d[k], k / nb, Math.min(k, 10), Math.min(nb - 1 - k, 10),
      n, staffsN || 1, risk ? 1 : 0]);
    // (the neighbours: their evidence and how sure they are; how evenly the pace runs here)
    const E = (q) => (q >= 0 && q < nb && ev[q] ? ev[q][0] : -1);
    let em = 9;
    for (let q = k - 2; q < k + 3; q++) if (q >= 0 && q < nb && ev[q]) em = Math.min(em, ev[q][0]);
    const w = [];
    for (let q = Math.max(0, k - 3); q < Math.min(nb, k + 4); q++) w.push(Math.log(Math.max(0.05, d[q])));
    const wm = w.reduce((a, b) => a + b, 0) / w.length, wsd = Math.sqrt(w.reduce((a, b) => a + (b - wm) ** 2, 0) / w.length);
    let empty = 0;
    for (let q = Math.max(0, k - 4); q < Math.min(nb, k + 5); q++) if (!nn[q]) empty++;
    out[k].push(E(k - 1), E(k + 1), em, k ? conf[k - 1] : 1, k + 1 < nb ? conf[k + 1] : 1, wsd, empty);
  }
  return out;
}
// the chance one bar is wrong, from its features
export function wrongChance(x) {
  let s = BASE;
  for (const t of TREES) {
    let i = 0;
    while (!t[i][5]) i = x[t[i][0]] <= t[i][1] ? t[i][2] : t[i][3];
    s += t[i][4];
  }
  return 1 / (1 + Math.exp(-s));
}
