// Following two parts by listening: the notes of both parts, bar by bar, in one line of music (the
// first clarinet's notes and the second's where they come in each bar), followed the way the page
// follower follows one part (a probability for every note, moved along by what is heard). Says where
// the playing is: the piece, the bar, and how far into the bar.
import { readPage } from './follow-read.js';
import { readElsewhere, fit } from './follow.js';
import { getCtx, acquireMic, releaseMic } from './audio.js';
import { Listener, chromaOf } from './listen.js';

const MOVE = [0.14, 0.62, 0.15, 0.05, 0.02];   // stay, next, skip 1, 2, 3
const JUMP = 2e-4;
const like = (f) => 0.04 + 0.96 * f * f;
// the written key of the part against what sounds ("Clarinet 1 in B♭": written a tone above)
export function shiftOfName(name) {
  const m = /\bin\s*([A-G])\s*(♭|b|flat|♯|#)?(?![a-z])/i.exec(String(name || ''));
  if (!m) return 0;
  const pc = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 }[m[1].toUpperCase()] + (m[2] && /♭|b|flat/i.test(m[2]) ? -1 : m[2] ? 1 : 0);
  // (sounding = written + pc (from C); heard as written: heard − pc, the follower's shift is pc)
  return ((pc % 12) + 12) % 12;
}

export class DuoFollower {
  // parts: [{ render(p, canvas, w, h), lineOf(p, yn) → line index or -1, unitAt(lineIndex, xn) → { k, bar, frac } or null, store }]
  // window(): [{ x, pages: [p…] }] the pages around the place to read; onPlace({ k, bar, frac, conf })
  // order(k, bar) → where a bar is in the whole music, counted in bars (pieces one after another)
  constructor({ parts, window, onPlace, onState, shift, order }) {
    Object.assign(this, { parts, windowFn: window, onPlace, onState, shift0: shift || 0, order });
    this.cache = new Map(); this.on = false; this.seq = []; this.p = null; this.heard = 0; this.alt = null; this.key = '';
    // how fast the music goes (bars a second), learnt from the playing
    this.v = 0.5; this.vSure = 0; this.track = [];
  }
  async start(at) {
    if (this.on) return;
    this.on = true; this.at = at || null;
    const tok = this._tok = (this._tok || 0) + 1;
    try { this.src = await acquireMic(); } catch { if (tok === this._tok) { this.on = false; this.onState && this.onState('No microphone'); } return; }
    if (!this.on || tok !== this._tok) { releaseMic(); return; }
    // (listening at once: the notes, read beforehand while the long line was on screen, are there)
    this.refresh();
    this.listener = new Listener((o) => this._heard({ ...o, onset: true }));
    this.listener.attach(this.src.context || getCtx(), this.src);
    // (and the sound as it goes, every tenth of a second: a fast passage has more notes than can be
    // heard one by one)
    this.tLast = performance.now();
    this.frameT = setInterval(() => this._frame(), 100);
    this.onState && this.onState('Listening');
  }
  stop() {
    if (!this.on) return;
    this.on = false; this._tok = (this._tok || 0) + 1; clearInterval(this.frameT);
    if (this.listener) { this.listener.detach(); this.listener = null; releaseMic(); }
  }
  // the notes of one page of a part (read once, in a thread of its own, and kept)
  notesOf(x, p) {
    const key = x + ':' + p;
    if (this.cache.has(key)) return this.cache.get(key);
    const P = this.parts[x];
    const job = (async () => {
      const kept = P.store ? await P.store.get(p).catch(() => null) : null;
      if (kept && Array.isArray(kept.seq) && kept.v === 2) return kept;
      const c = document.createElement('canvas');
      await P.render(p, c, 1600, 2263);
      let r = null;
      try { r = await readElsewhere(c); } catch { r = null; }
      if (!r) r = await readPage(c);
      c.width = c.height = 0;
      if (P.store && r && r.seq && r.seq.length) P.store.put(p, r).catch(() => {});
      return r;
    })().catch(() => ({ seq: [] }));
    this.cache.set(key, job);
    return job;
  }
  // the music to follow: both parts' notes of the pages around the place, in the order they are
  // played (by bar, then by how far into the bar), each with its place in bars
  async refresh() {
    const win = this.windowFn();
    const evs = [];
    for (const w of win) {
      for (const p of w.pages) {
        const r = await this.notesOf(w.x, p);
        if (!this.on) return;
        for (const e of r.seq || []) {
          const li = this.parts[w.x].lineOf(p, e.yn); if (li < 0) continue;
          const u = this.parts[w.x].unitAt(li, e.xn); if (!u) continue;
          evs.push({ k: u.k, bar: u.bar, frac: u.frac, m: this.order(u.k, u.bar) + u.frac, pcs: e.pcs.slice(), tpl: Float32Array.from(e.tpl), x: w.x });
        }
      }
    }
    evs.sort((a, b) => a.m - b.m);
    const seq = [];
    for (const e of evs) {
      const q = seq[seq.length - 1];
      if (q && Math.abs(q.m - e.m) < 0.03 && q.x !== e.x) { for (const c of e.pcs) if (!q.pcs.includes(c)) q.pcs.push(c); for (let i = 0; i < 12; i++) q.tpl[i] = Math.max(q.tpl[i], e.tpl[i]); continue; }
      seq.push({ ...e });
    }
    // (what sounds around each note: the notes of both parts within an eighth of a bar)
    for (let j = 0; j < seq.length; j++) {
      const t = new Float32Array(12);
      for (let i = j; i >= 0 && seq[j].m - seq[i].m < 0.125; i--) for (let c = 0; c < 12; c++) t[c] += seq[i].tpl[c];
      for (let i = j + 1; i < seq.length && seq[i].m - seq[j].m < 0.125; i++) for (let c = 0; c < 12; c++) t[c] += seq[i].tpl[c];
      seq[j].wtpl = t;
    }
    const key = seq.length ? `${seq[0].m}-${seq[seq.length - 1].m}:${seq.length}` : '';
    if (key === this.key) return;
    const was = this.mNow !== undefined ? this.mNow : this.at ? this.order(this.at.k, this.at.bar) + (this.at.frac || 0) : null;
    // The music as places a sixteenth of a bar apart (not note by note: a rest, a held note, a bar the
    // reader saw few notes in, all take their time), each with what sounds there: the notes starting
    // in it, and the ones before still sounding.
    const H = 1 / 16, cells = [];
    if (seq.length) {
      const m0 = Math.floor(seq[0].m), m1 = Math.ceil(seq[seq.length - 1].m + 0.5);
      let j = 0; let held = null;
      for (let m = m0; m < m1; m += H) {
        const t = new Float32Array(12), pcs = [];
        while (j < seq.length && seq[j].m < m - H / 2) { held = seq[j]; j++; }
        let q = j;
        for (; q < seq.length && seq[q].m < m + H / 2; q++) { for (let c = 0; c < 12; c++) t[c] += seq[q].tpl[c]; for (const c of seq[q].pcs) if (!pcs.includes(c)) pcs.push(c); held = seq[q]; }
        const starts = q > j;
        if (held && !starts) for (let c = 0; c < 12; c++) t[c] += held.tpl[c] * 0.6;
        cells.push({ m, tpl: t, pcs: pcs.length ? pcs : held ? held.pcs : [], starts, ev: starts ? seq[j] : held });
      }
    }
    this.seq = seq; this.cells = cells; this.key = key;
    this.p = new Float64Array(cells.length);
    if (!cells.length) return;
    for (let i = 0; i < cells.length; i++) { const d = was === null ? 0 : cells[i].m - was; this.p[i] = Math.exp(-0.5 * (d / 0.4) ** 2) + 1e-5; }
    this._norm(this.p);
    if (this.alt) for (const st of this.alt.values()) st.p = Float64Array.from(this.p);
  }
  _norm(p) { let s = 0; for (const v of p) s += v; for (let j = 0; j < p.length; j++) p[j] /= s || 1; }
  // the music moves on with the time gone by, at about the speed it has been going
  _move(prev, dt) {
    const n = prev.length, out = new Float64Array(n), H = 1 / 16;
    const go = (this.v * dt) / H, sd = Math.max(0.6, (0.05 + (this.vSure > 0.5 ? 0.15 : 0.35) * this.v * dt) / H);
    const r = Math.ceil(sd * 3), ker = [];
    for (let d = Math.floor(go) - r; d <= Math.ceil(go) + r; d++) ker.push([d, Math.exp(-0.5 * ((d - go) / sd) ** 2) * (d < 0 ? 0.3 : 1)]);
    const ks = ker.reduce((a, q) => a + q[1], 0);
    for (let j = 0; j < n; j++) {
      const pj = prev[j]; if (pj < 1e-9) continue;
      for (const [d, w] of ker) { const q = Math.max(0, Math.min(n - 1, j + d)); out[q] += (pj * w) / ks; }
    }
    return out;
  }
  _update(obs, frame) {
    const now = performance.now(), dt = Math.max(0, Math.min(1.5, (now - (this.tLast || now)) / 1000)); this.tLast = now;
    const n = this.cells.length;
    const lk = (cell, sh) => {
      if (frame) { const f = fit({ chroma: obs.chroma, mono: false }, { tpl: cell.tpl }, sh); return Math.pow(0.15 + 0.85 * f, 0.4); }
      // (a note heard starting: likely where a note of the music starts)
      return like(fit(obs, { pcs: cell.pcs, tpl: cell.tpl }, sh)) * (cell.starts ? 1 : 0.35);
    };
    const step = (prev, sh) => {
      const out = this._move(prev, dt); let s = 0;
      // (a jump — starting again, a repeat — is believed only from notes heard one by one, never from
      // the sound as it goes: music that repeats itself must not pull the place away)
      const jp = frame ? 1e-7 : JUMP;
      for (let j = 0; j < n; j++) { out[j] = (out[j] * (1 - jp) + jp / n) * lk(this.cells[j], sh); s += out[j]; }
      for (let j = 0; j < n; j++) out[j] /= s || 1;
      return { p: out, ev: s };
    };
    if (!this.alt && this.shift === undefined) this.alt = new Map([[this.shift0, { p: this.p, s: 0 }], ...(this.shift0 ? [[0, { p: Float64Array.from(this.p), s: 0 }]] : [])]);
    if (this.alt) {
      for (const [sh, st] of this.alt) { const r = step(st.p, sh); st.p = r.p; st.s = st.s * 0.97 + Math.log(r.ev + 1e-12) + (sh === this.shift0 ? 0.05 : 0); }
      const arr = [...this.alt.entries()].sort((a, b) => b[1].s - a[1].s);
      this.p = arr[0][1].p;
      if (this.heard > 30 && (arr.length < 2 || arr[0][1].s - arr[1][1].s > 3)) { this.shift = arr[0][0]; this.alt = null; }
    } else this.p = step(this.p, this.shift ?? this.shift0).p;
  }
  _frame() {
    if (!this.on || !this.listener || !this.cells || !this.cells.length) return;
    const L = this.listener; if (!L.mag || !L.ctx) return;
    let ms = 0; for (let i = 0; i < L.td.length; i++) ms += L.td[i] * L.td[i];
    if (Math.sqrt(ms / L.td.length) < 0.003) { this.tLast = performance.now(); return; }   // (silence: nothing moves)
    const chroma = chromaOf(L.mag, L.ctx.sampleRate, L.an.fftSize);
    this.heard++;
    this._update({ chroma }, true);
    this._report();
  }
  _heard(obs) {
    if (!this.on || !this.cells || !this.cells.length || !this.p) return;
    this.heard++;
    this._update(obs, false);
    this._report();
  }
  _report() {
    const p = this.p, cells = this.cells;
    let best = 0; for (let j = 1; j < p.length; j++) if (p[j] > p[best]) best = j;
    // (the place: the mean around the most likely one, so the screen glides instead of jumping)
    let s = 0, m = 0;
    for (let j = Math.max(0, best - 10); j <= Math.min(p.length - 1, best + 10); j++) { s += p[j]; m += p[j] * cells[j].m; }
    m /= s || 1; const conf = s;
    this.best = best; this.mNow = m;
    // the speed, from where the playing has been these last seconds
    const t = performance.now() / 1000;
    if (conf > 0.5) { this.track.push([t, m]); while (this.track.length && t - this.track[0][0] > 6) this.track.shift(); }
    if (this.track.length > 8 && t - this.track[0][0] > 2.5) {
      const tr = this.track, nT = tr.length, mt = tr.reduce((a, q) => a + q[0], 0) / nT, mm = tr.reduce((a, q) => a + q[1], 0) / nT;
      let num = 0, den = 0; for (const [a, b] of tr) { num += (a - mt) * (b - mm); den += (a - mt) ** 2; }
      const v = den ? num / den : this.v;
      if (v > 0.08 && v < 3) { this.v = this.v * 0.7 + v * 0.3; this.vSure = Math.min(1, this.vSure + 0.1); }
    }
    const e = cells[best].ev || this.seq[0];
    if (this.heard >= 4) this.onPlace && this.onPlace({ k: e.k, bar: e.bar, frac: e.frac, m, conf });
    if (best > cells.length * 0.6 && !this._refreshing) { this._refreshing = true; this.refresh().finally(() => { this._refreshing = false; }); }
  }
}
