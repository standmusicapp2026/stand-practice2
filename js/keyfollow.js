// Hearing which key you are playing in, so a drone can follow a change of key — and only that.
// Note by note, as a musician hears it: each note makes the keys whose scale has it more likely
// (allowing that a note is now and then misheard), and where the music comes to rest — a long
// note, the end of a phrase, a note reached from its leading note — says which note is home (G
// major and E minor have the same notes; only that tells them apart). The 24 keys are weighed
// all the time, a change to a near key (a fifth away, relative, parallel) a little more readily;
// the drone moves when another key is clearly the likely one for a few seconds. A new note is
// counted only where a note begins (an attack), and only notes the instrument can play. A
// chromatic run, a shifting exercise or tuning the strings never moves it; a scale of another key,
// played after a pause, moves it as soon as it reaches the octave.
// After a pause (a new piece, a scale) it judges the new music on its own notes and moves within a
// few seconds; while you play on without stopping it waits for the music to settle in the new key.
// (Measured live on Bach suite openings and scales, the drone moving itself: the new key reached in
// about 4-10 s instead of 12 or more — the earlier ear mostly never moved within a piece — and long
// passages in one key, chromatic runs, open strings and tuning never move it.)

import { getCtx, acquireMic, releaseMic } from './audio.js';
import { chromaOf } from './listen.js';

// the key shapes: how much each note of the scale is played in real music (Albrecht & Shanahan,
// from a large set of pieces; they tell keys apart better than the older listening tests)
const MAJOR = [0.238, 0.006, 0.111, 0.006, 0.137, 0.094, 0.016, 0.214, 0.009, 0.080, 0.008, 0.081];
const MINOR = [0.220, 0.006, 0.104, 0.123, 0.019, 0.103, 0.012, 0.214, 0.062, 0.022, 0.061, 0.052];
const corr = (a, b) => {
  const ma = a.reduce((s, x) => s + x, 0) / 12, mb = b.reduce((s, x) => s + x, 0) / 12;
  let n = 0, da = 0, db = 0; for (let i = 0; i < 12; i++) { n += (a[i] - ma) * (b[i] - mb); da += (a[i] - ma) ** 2; db += (b[i] - mb) ** 2; }
  return da && db ? n / Math.sqrt(da * db) : 0;
};
const rot = (p, k) => Array.from({ length: 12 }, (_, i) => p[(i - k + 12) % 12]);
export const keyScore = (h, pc, minor) => corr(h, rot(minor ? MINOR : MAJOR, pc));
// the best key for a pitch-class weighting: { pc, minor, score, margin }
export function keyOf(h) {
  const all = [];
  for (let k = 0; k < 12; k++) all.push({ pc: k, minor: false, score: keyScore(h, k, false) }, { pc: k, minor: true, score: keyScore(h, k, true) });
  all.sort((a, b) => b.score - a.score);
  return { ...all[0], margin: all[0].score - all[1].score };
}
// relative major and minor share their notes; telling them apart needs more proof
const relative = (a, b) => a.minor !== b.minor && ((a.minor ? a.pc + 3 : b.pc + 3) % 12) === (a.minor ? b.pc : a.pc);

// the notes of a key: major scale; minor with both the natural and the raised 6th and 7th
const SCALE_MAJOR = [0, 2, 4, 5, 7, 9, 11], SCALE_MINOR = [0, 2, 3, 5, 7, 8, 9, 10, 11];
export function scaleFit(h, pc, minor) {
  let tot = 0, inK = 0; const sc = minor ? SCALE_MINOR : SCALE_MAJOR;
  for (let i = 0; i < 12; i++) { tot += h[i]; if (sc.includes((i - pc + 12) % 12)) inK += h[i]; }
  return tot ? inK / tot : 1;
}
// the share of what you play that is NOT on the notes the old key has and the new one has not
function scaleFitOf(h, oldK, newK) {
  const so = oldK.minor ? SCALE_MINOR : SCALE_MAJOR, sn = newK.minor ? SCALE_MINOR : SCALE_MAJOR;
  let tot = 0, only = 0;
  for (let i = 0; i < 12; i++) { tot += h[i]; if (so.includes((i - oldK.pc + 12) % 12) && !sn.includes((i - newK.pc + 12) % 12)) only += h[i]; }
  return tot ? 1 - only / tot : 1;
}
// the likelihood of each note in each of the 24 keys (0–11 major, 12–23 minor), as logarithms
// (half the key's shape, half its scale: a note outside the scale says much more than the shape alone)
// (each note of the scale by how often it is used: in minor the raised 7th, the leading note, is
// nearly always there, the flat 7th and the raised 6th less — so minor keys are not spread over nine
// equal notes, which made every note a major key shares count a little against them)
const SCW = [[1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1], [1, 0, 1, 1, 0, 1, 0, 1, 1, G0('__kfM6', 0.45), G0('__kfB7', 0.55), G0('__kfL7', 0.9)]];
function G0(k, d) { return globalThis[k] ?? ({ __kfMix: 0.2 })[k] ?? d; }
const LOGP = (() => { const out = []; const mix = globalThis.__kfMix ?? 0.2; for (const [prof, sw] of [[MAJOR, SCW[0]], [MINOR, SCW[1]]]) for (let k = 0; k < 12; k++) { const r = rot(prof, k), sum = r.reduce((a, v) => a + v, 0), ws = sw.reduce((a, v) => a + v, 0); out.push(r.map((v, i) => Math.log(mix * v / sum + (1 - mix) * sw[(i - k + 12) % 12] / ws + 0.004))); } return out; })();
const NOTE_CAP = 0.55;     // seconds a single note can count for
const V3 = () => (globalThis.__kfV ?? 3) === 3;
const V2 = () => (globalThis.__kfV ?? 3) >= 2;
// (the settings found best on real music — Bach suites, scales — and confirmed on pieces not used to find them)
const KF_DEFAULTS = {"__kfH": 8.816, "__kfOwn": 0.8, "__kfM": 0.8, "__kfHalf": 5, "__kfHalfW": 5, "__kfNear": 1.68, "__kfFit": 0.482, "__kfEps": 0.41, "__kfRestW": 0.8, "__kfChroma": 0, "__kfH3": 0.247, "__kfFreshH": 0.17, "__kfNew": 1.398, "__kfGone": 0.4, "__kfGoneN": 12, "__kfSettle": 1258, "__kfMinNotes": 5, "__kfStartW": 1.2, "__kfMix": 0.2, "__kfTriad": 1, "__kfQuiet": 0.3, "__kfLowRun": 6, "__kfGap": 800, "__kfD": 2.709, "__kfRiv": 1.513, "__kfFreshMs": 19000, "__kfLvQ": 0.35, "__kfCL": 2.571};
// how many fifths apart two keys are (a minor key counted as its relative major)
const fifthsApart = (a, b) => { const m = (k) => ((k.pc + (k.minor ? 3 : 0)) * 7) % 12; const d = ((m(a) - m(b)) % 12 + 12) % 12; return Math.min(d, 12 - d); };
const G = (k, d) => globalThis[k] ?? KF_DEFAULTS[k] ?? d;
// A note heard is now and then the wrong note (an attack, an overtone: about one in ten, and more
// in a room or a scratchy attack): each note
// counts as "this note, or a mistake", so one wrong note says little, the same note again and again a lot.
let LOGE = null, LOGE_EPS = -1;
const logE = () => {
  const eps = G('__kfEps', 0.35);
  if (LOGE && LOGE_EPS === eps) return LOGE;
  LOGE_EPS = eps; LOGE = LOGP.map((row) => { const pr = row.map(Math.exp), sum = pr.reduce((a, v) => a + v, 0); return pr.map((v) => Math.log((1 - eps) * v / sum + eps / 12)); });
  return LOGE;
};
// Where the music comes to rest says which note is home: a long note, the end of a phrase (a rest
// after it), a note reached from a half step below (the leading note) — most often the tonic, then
// the fifth, then the third. How much such a note says for each of the 24 keys (as a factor).
const REST = (() => { const out = []; for (const minor of [false, true]) for (let k = 0; k < 12; k++) { const sc = minor ? SCALE_MINOR : SCALE_MAJOR; out.push(Array.from({ length: 12 }, (_, i) => { const d = (i - k + 12) % 12; return d === 0 ? 3.2 : d === 7 ? 1.5 : d === (minor ? 3 : 4) ? 1.15 : sc.includes(d) ? 0.75 : 0.45; })); } return out; })();
// how likely a change of key is, from each key to each (per note): mostly to near keys (a fifth
// away, the relative and the parallel key), rarely far
const NEAR = (() => { const m = []; for (let a = 0; a < 24; a++) { const row = []; let sum = 0; for (let b = 0; b < 24; b++) { if (a === b) { row.push(0); continue; } const pa = a % 12, pb = b % 12, ma = a >= 12, mb = b >= 12; const dpc = Math.min((pb - pa + 12) % 12, (pa - pb + 12) % 12); const rel = ma !== mb && ((ma ? pa + 3 : pb + 3) % 12) === (ma ? pb : pa); const near = (ma === mb && (dpc === 5 || dpc === 7)) || rel || (pa === pb && ma !== mb); const v = near ? 4 : 1; row.push(v); sum += v; } m.push(row.map((v) => v / sum)); } return m; })();
const lerp = (a, b, t) => a + (b - a) * t;
export class KeyFollower {
  constructor(onKey, onHear) { this.onKey = onKey; this.onHear = onHear; this.on = false; this.memory = 9; this.sens = 0.5; }
  async start() {
    if (this.on) return;
    this.on = true; this.gen = (this.gen || 0) + 1; const gen = this.gen;
    try { this.src = await acquireMic(); } catch { this.on = false; this.onHear && this.onHear(null, 'No microphone'); return; }
    if (!this.on || gen !== this.gen) { releaseMic(); return; }   // stopped while the microphone was opening
    this._wire(this.src);
    this.mic = true;
  }
  // listening to a sound (the microphone; a test feeds its own)
  _wire(src) {
    const ctx = src.context || getCtx();
    this.src = src;
    this.an = ctx.createAnalyser(); this.an.fftSize = 4096; this.an.smoothingTimeConstant = 0; this.src.connect(this.an);
    this.buf = new Float32Array(2048); this.fd = new Float32Array(this.an.frequencyBinCount); this.mag = new Float32Array(this.an.frequencyBinCount);
    this._init();
    this.timer = setInterval(() => this._tick(ctx.sampleRate), 40);
  }
  _init() {
    this.h = new Array(12).fill(0); this.r = new Array(12).fill(0); this.last = this._now(); this.cand = null; this.key = this.key || null;
    this.noise = 0.0006; this.prevPc = -1; this.pcRun = 0; this.noteW = 0; this.zero = 0; this.onsets = 0;
    this.bg = null; this.res = null; this.eFloor = 0;
    this.ev = new Array(12).fill(0); if (!this.post) this._resetPost();
    if (!this.range && globalThis.__kfRange) this.range = globalThis.__kfRange;   // (tests)
  }
  _now() { return this.clock ? this.clock() : performance.now(); }
  // (the slider's middle hears a change of key sooner than before — tested: no false changes at
  // that — and its ends still go from careful to very quick)
  _sens() { const g = globalThis.__earSens; return Math.max(0, Math.min(1, g !== undefined ? g : 0.35 + 0.6 * this.sens)); }
  stop() {
    if (!this.on) return;
    this.on = false; clearInterval(this.timer);
    if (this.mic) { try { this.src.disconnect(this.an); } catch {} releaseMic(); this.mic = false; }
  }
  // the microphone was taken away (a call, another app): open it again
  // (the microphone held meanwhile, so it is never closed and opened again for this)
  async restart() { let held = false; try { await acquireMic(); held = true; } catch {} this.stop(); await this.start(); if (held) releaseMic(); }
  // tell it the key the drone is in now (you chose it, or it just moved): it starts counting afresh
  // (counting starts afresh, as after a move of its own: the notes before the key you chose never
  // move the drone away from it a moment later)
  set(pc, minor) {
    const now = this._now();
    this.fastBg = now + 2500; this.flFrom = now; this.key = { pc, minor }; this.home = { pc, minor }; this.cand = null; this.onsets = 0; this._resetPost(); this.pa = null; if (this.w) this.w.fill(0);
    this.notesSince = 0; this.movedAt = now; this.recent = []; this.recentAt = []; this.cur = null; this.durs = [];
    if (this.r) this.r.fill(0);
    if (this.C) this.C.fill(0);
  }
  // how likely each of the 24 keys is now, given what was heard (the key it is in counts most at first)
  _resetPost() {
    const p = new Float64Array(24).fill(0.1 / 23);
    if (this.key) p[this.key.pc + (this.key.minor ? 12 : 0)] = 0.9; else p.fill(1 / 24);
    this.post = p;
  }
  // every note heard moves the likelihoods of the keys (a note of the key's scale, above all its
  // tonic, fifth and leading note, makes that key more likely); a key may change at any moment, a
  // little more readily to a near key (a fifth away, or the relative or parallel key)
  _update(dt, now) {
    const S = this._sens(), ev = this.ev, w = this.w || (this.w = new Float64Array(12));
    // what was played in the last few seconds (each note by how long it sounded, up to a cap)
    const fadeW = Math.pow(0.5, dt / lerp(8, 3.5, S));
    for (let i = 0; i < 12; i++) w[i] = w[i] * fadeW + ev[i];
    ev.fill(0);
    let tot = 0; for (let i = 0; i < 12; i++) tot += w[i];
    // how well each of the 24 keys explains those notes
    const ll = new Float64Array(24); let b = 0;
    for (let k = 0; k < 24; k++) { const L = LOGP[k]; let l = 0; for (let i = 0; i < 12; i++) l += w[i] * L[i]; ll[k] = l; if (l > ll[b]) b = k; }
    const best = { pc: b % 12, minor: b >= 12 };
    let second = -Infinity; for (let k = 0; k < 24; k++) if (k !== b && ll[k] > second) second = ll[k];
    this.onHear && this.onHear(tot > 1 && ll[b] - second > 0.5 ? { pc: best.pc, minor: best.minor, score: Math.min(1, (ll[b] - second) / 3) } : null);
    const cur = this.key;
    const ci = cur ? cur.pc + (cur.minor ? 12 : 0) : -1;
    if (!cur) return;
    const r = this.r;
    // the same on the last couple of seconds alone (what you play now)
    const llR = new Float64Array(24);
    for (let k = 0; k < 24; k++) { const L = LOGP[k]; let l = 0; for (let i = 0; i < 12; i++) l += r[i] * L[i]; llR[k] = l; }
    let bo = -1, ro = -1; for (let k = 0; k < 24; k++) if (k !== ci) { if (bo < 0 || ll[k] > ll[bo]) bo = k; if (ro < 0 || llR[k] > llR[ro]) ro = k; }
    const keyAt = (k) => ({ pc: k % 12, minor: k >= 12 });
    // notes only the new key has, and notes only the old one has, in what you play now
    const sides = (nk) => {
      const sn = nk.minor ? SCALE_MINOR : SCALE_MAJOR, so = cur.minor ? SCALE_MINOR : SCALE_MAJOR; let nw = 0, od = 0;
      for (let i = 0; i < 12; i++) { const inN = sn.includes((i - nk.pc + 12) % 12), inO = so.includes((i - cur.pc + 12) % 12); if (inN && !inO) nw += r[i]; else if (inO && !inN) od += r[i]; }
      return [nw, od];
    };
    const enough = tot >= lerp(3, 1.6, S) && this.onsets >= Math.round(lerp(8, 4, S));
    // 1. the old key clearly left: notes only the new key has, again and again, and the old key's
    //    own notes gone (C♯ heard and C no more, from G to D), the new key fitting what you play now
    const kr = keyAt(ro), nearR = relative(cur, kr) || cur.pc === kr.pc, [nwR, odR] = sides(kr);
    //    (to the relative minor, its leading note is that: A♯ in B minor, after D major)
    const toRelMinor = relative(cur, kr) && kr.minor && !cur.minor;
    const clean = enough && (!nearR || toRelMinor) && nwR >= lerp(1.0, 0.45, S) * (toRelMinor ? 1.3 : 1) && odR <= nwR * 0.45 && llR[ro] - llR[ci] >= lerp(1.2, 0.4, S);
    // 2. the shape of the last few seconds says another key, clearly (relative and parallel keys,
    //    with the same notes or the same tonic, need more), with one of its own notes heard
    const kb = keyAt(bo), nearB = relative(cur, kb) || cur.pc === kb.pc, [nwB] = sides(kb);
    const shape = enough && bo === b && ll[bo] - ll[ci] >= lerp(3.2, 1.3, S) * (nearB ? 1.6 : 1) && (nearB || nwB >= lerp(0.5, 0.2, S));
    // 3. from a major key to its relative minor: the minor's leading note again and again (A♯, from D
    //    major to B minor), and the music leaning on the minor's tonic more than on the major's
    let relM = false; const rm = cur.minor ? -1 : ((cur.pc + 9) % 12) + 12;
    if (rm >= 0 && enough) {
      const lead = r[(cur.pc + 8) % 12], sixth = r[(cur.pc + 7) % 12] * 0.5;
      relM = lead + sixth >= lerp(1.3, 0.6, S) && llR[rm] - llR[ci] >= lerp(0.8, 0.2, S) && r[(cur.pc + 9) % 12] >= r[cur.pc] * 0.8;
    }
    const pick = clean ? ro : shape ? bo : relM ? rm : -1;
    this.dbg = { best: best.pc + (best.minor ? 'm' : ''), prob: [kr.pc + (kr.minor ? 'm' : ''), +nwR.toFixed(2), +odR.toFixed(2), +(llR[ro] - llR[ci]).toFixed(2), clean, shape, this.onsets, +tot.toFixed(1)] };
    // Never on what is not a key at all: a chromatic scale, a shifting exercise, half steps up and
    // down (nearly every note of the twelve), nor on a key that does not hold what you play now and
    // over the last few seconds; and not again so soon after a move (one key at a time, settled).
    let calmOk = true;
    if (pick >= 0) {
      const nk0 = keyAt(pick);
      let totR = 0; for (let i = 0; i < 12; i++) totR += r[i];
      let spread = 0; for (let i = 0; i < 12; i++) if (r[i] >= 0.05 * totR) spread++;
      const fitR = scaleFit(r, nk0.pc, nk0.minor), fitW = scaleFit(w, nk0.pc, nk0.minor);
      const steady = spread <= (globalThis.__kfSpread ?? 9) && fitR >= lerp(0.93, 0.86, S) && fitW >= lerp(0.88, 0.8, S);
      const settled = now - (this.movedAt ?? -1e12) >= lerp(12000, 6000, S);
      // half steps one after another (a shifting exercise, a chromatic run): no key in it
      const rc = this.recent || []; let semi = 0, steps = 0;
      for (let i = 1; i < rc.length; i++) { const d = Math.abs(rc[i] - rc[i - 1]); if (d === 0) continue; steps++; if (d === 1) semi++; }
      const chromatic = steps >= 8 && semi / steps > (globalThis.__kfSemi ?? 0.4);
      // and the longer memory (the last half minute) agrees: a key only touched for a moment (a
      // passing tonicization: A minor for a bar in G major) never moves the drone
      // (judged on the shape of the music, its tonic and fifth above all: a few chromatic notes, as
      // every piece has, never count against the key it is in)
      const h = this.h; const llH = keyScore(h, nk0.pc, nk0.minor), llC = keyScore(h, cur.pc, cur.minor);
      const longOk = llH - llC >= (globalThis.__kfLong ?? lerp(0.03, -0.02, S));
      calmOk = steady && settled && !chromatic && longOk;
      this.dbg.guard = [spread, +fitR.toFixed(2), +fitW.toFixed(2), settled, +(semi / Math.max(1, steps)).toFixed(2), +(llH - llC).toFixed(2)];
    }
    if (pick < 0 || !calmOk) { if (this.cand && now - this.cand.lastOk > 900) this.cand = null; return; }
    const nk = keyAt(pick), near = relative(cur, nk) || cur.pc === nk.pc;
    if (!this.cand || this.cand.pc !== nk.pc || this.cand.minor !== nk.minor) { this.cand = { pc: nk.pc, minor: nk.minor, since: now, lastOk: now }; return; }
    this.cand.lastOk = now;
    if (now - this.cand.since >= lerp(1800, 500, S) * (near ? 1.5 : 1)) {
      this.key = nk; this.cand = null; this.onsets = 0; this.movedAt = now;
      this.onKey && this.onKey(this.key);
    }
  }
  // what sounds now that was not sounding a moment ago: the steady sound (the drone itself, heard
  // by the microphone, a fridge, a hum) is taken out, the notes played stay
  _fresh(sr) {
    const an = this.an, n = an.frequencyBinCount;
    an.getFloatFrequencyData(this.fd);
    const mag = this.mag; for (let k = 0; k < n; k++) mag[k] = this.fd[k] > -160 ? Math.pow(10, this.fd[k] / 20) : 0;
    if (!this.bg) { this.bg = Float32Array.from(mag); this.res = new Float32Array(n); }
    const bg = this.bg, res = this.res;
    // (the drone has just moved: its new sound is learnt as the steady sound quickly, so the notes you
    // play are heard at once and not hidden behind it)
    const up = this._now() < (this.fastBg ?? -1) ? 1.3 : 1.025;
    // the steady level follows a sound down at once and up slowly (a note fades into it only after
    // a couple of seconds held: a held note still counts, as long as it sounds new)
    for (let k = 0; k < n; k++) {
      const m = mag[k], b = bg[k];
      res[k] = m > b * 1.6 ? m - b * 1.3 : 0;
      bg[k] = m < b ? b * 0.75 + m * 0.25 : Math.min(m, b * up + 1e-7);
    }
    // (the level above the drone's own steady sound: what is played, held notes too; the drone's
    // sound is learnt as the lowest each frequency has been over a moment after it starts or moves,
    // and afterwards rises only very slowly — so a pause is heard as one, a long note never is)
    const now = this._now(), fl = this.fl || (this.fl = new Float32Array(n)), mv = this.flFrom ?? -1;
    if (now < mv + 150) { this.flLearn = 0; }
    else if (now < mv + 1650) { if (!this.flLearn) { fl.set(mag); this.flLearn = 1; } else for (let k = 0; k < n; k++) if (mag[k] < fl[k]) fl[k] = mag[k]; }
    else for (let k = 0; k < n; k++) fl[k] = mag[k] < fl[k] ? fl[k] * 0.9 + mag[k] * 0.1 : fl[k] * 1.0015 + 1e-9;
    const k0 = Math.max(2, Math.floor(45 / (this.an.context ? this.an.context.sampleRate / this.an.fftSize : 10.77))), k1 = Math.min(n, Math.ceil(5000 / (this.an.context ? this.an.context.sampleRate / this.an.fftSize : 10.77)));
    let lv = 0; for (let k = k0; k < k1; k++) { const d = mag[k] - 2 * fl[k]; if (d > 0) lv += d; }
    this.lv = now < mv + 1650 ? -1 : lv;
    return res;
  }
  // the note heard in what is new: the pitch whose overtones together are strongest
  // The note, precisely: the peaks of the new sound, each found to a fraction of a bin (so a low C
  // and C♯, 4 Hz apart, are never confused), and the pitch whose harmonics explain them best (each
  // peak's strength compressed, so the many weak overtones of a low note count too, and its 3rd
  // harmonic is never taken for the note: that read a fifth too high).
  _pitch(res, sr) { return G('__kfP', 2) === 2 ? this._pitch2(res, sr) : this._pitch1(res, sr); }
  _pitch2(res, sr) {
    const N = this.an.fftSize, binHz = sr / N, n = res.length;
    const [lo, hi] = this.range || [36, 96];
    const kLo = Math.max(2, Math.floor(45 / binHz)), kHi = Math.min(n - 2, Math.ceil(5000 / binHz));
    let mx = 0; for (let k = kLo; k <= kHi; k++) if (res[k] > mx) mx = res[k];
    if (mx <= 0) return null;
    const thr = mx * G('__kfPk', 0.03), pk = [];
    for (let k = kLo; k <= kHi; k++) {
      const b = res[k]; if (b <= thr || b < res[k - 1] || b < res[k + 1]) continue;
      const a = Math.log(res[k - 1] + 1e-12), c = Math.log(res[k + 1] + 1e-12), bb = Math.log(b);
      const den = a - 2 * bb + c, off = den < 0 ? Math.max(-0.5, Math.min(0.5, 0.5 * (a - c) / den)) : 0;
      pk.push([(k + off) * binHz, Math.sqrt(b / mx)]);
    }
    if (!pk.length) return null;
    pk.sort((x, y) => y[1] - x[1]); if (pk.length > 16) pk.length = 16;
    if (globalThis.__kfRec) this.lastPk = pk.map((q) => [+q[0].toFixed(2), +q[1].toFixed(3)]);
    let tot = 0; for (const q of pk) tot += q[1];
    const fLo = 440 * Math.pow(2, (lo - 69.5) / 12), fHi = 440 * Math.pow(2, (hi - 68.5) / 12);
    const score = (f0) => {
      const got = new Float64Array(13); let s = 0;
      for (const [f, a] of pk) { const h = Math.round(f / f0); if (h < 1 || h > 12) continue; const dev = Math.abs(1200 * Math.log2(f / (h * f0))); if (dev > 40) continue; const v = a * (1 - dev / 40) / Math.pow(h, G('__kfHw', 0.35)); if (v > got[h]) { s += v - got[h]; got[h] = v; } }
      // (a pitch with no peak at its own place, nor at its octave, is not the note)
      if (!got[1] && !got[2]) s *= 0.5;
      return s;
    };
    let best = 0, bestF = 0, second = 0;
    for (let i = 0; i < Math.min(6, pk.length); i++) for (let h = 1; h <= 8; h++) {
      const f0 = pk[i][0] / h; if (f0 < fLo || f0 > fHi) continue;
      // (refined: the harmonics' own average place)
      const s0 = score(f0);
      if (s0 > best * 1.0001) { if (Math.abs(1200 * Math.log2(f0 / (bestF || 1))) > 60) second = best; best = s0; bestF = f0; } else if (s0 > second && Math.abs(1200 * Math.log2(f0 / bestF)) > 60) second = s0;
    }
    if (!bestF) return null;
    const midi = Math.round(69 + 12 * Math.log2(bestF / 440));
    // clarity: how much of the new sound this note explains (above half reads as above 6, as before)
    return { midi, clarity: 12 * best / tot, sum: best, f: bestF };
  }
  _pitch1(res, sr) {
    const N = this.an.fftSize, binHz = sr / N;
    let best = -1, bestS = 0, second = 0, tot = 0;
    const [lo, hi] = this.range || [36, 96];
    for (let m = lo; m <= hi; m++) {
      const f = 440 * Math.pow(2, (m - 69) / 12); let sc = 0;
      for (let k = 1; k <= 6; k++) {
        const b = Math.round((f * k) / binHz); if (b >= res.length - 1) break;
        sc += Math.max(res[b], res[b - 1] * 0.7, res[b + 1] * 0.7) / Math.sqrt(k);
      }
      // (the octave below a note gets its even overtones: it must have its own fundamental)
      const b1 = Math.round(f / binHz); if (Math.max(res[b1], res[b1 - 1], res[b1 + 1]) < sc * 0.08) sc *= 0.3;
      tot += sc;
      if (sc > bestS) { second = bestS; bestS = sc; best = m; } else if (sc > second) second = sc;
    }
    return best >= 0 && tot > 0 ? { midi: best, clarity: bestS / (tot / (hi - lo + 1)), sum: bestS } : null;
  }
  _tick(sr) {
    const now = this._now(), dt = Math.min(0.2, (now - this.last) / 1000); this.last = now;
    this.an.getFloatTimeDomainData(this.buf);
    let ms = 0; for (let i = 0; i < this.buf.length; i++) ms += this.buf[i] * this.buf[i];
    const rms = Math.sqrt(ms / this.buf.length);
    // a microphone that went silent for good (taken by another app) is opened again
    if (rms === 0) { this._fade(dt); if (++this.zero > 60) { this.zero = 0; this.restart(); } return; } else this.zero = 0;
    const res = this._fresh(sr);
    let e = 0; for (let k = 4; k < res.length; k++) e += res[k];
    const pt = this._pitch(res, sr);
    // (chords and double stops: the pitch classes that sound, when no single note is clear)
    const CLT = G('__kfP', 2) === 2 ? G('__kfCL', 3.5) : 6;
    const chroma = pt && pt.clarity > CLT ? null : () => chromaOf(res, sr, this.an.fftSize);
    if (globalThis.__kfRec) globalThis.__kfRec.push([now, dt, e, pt && pt.clarity > CLT ? pt.midi : -1, chromaOf(res, sr, this.an.fftSize).map((v) => +v.toFixed(3)), pt ? pt.midi : -1, pt ? +pt.clarity.toFixed(2) : 0, ...((q) => q ? [q.midi, +q.clarity.toFixed(2)] : [-1, 0])(this._pitch1(res, sr)), +rms.toExponential(3), +(this.lv ?? -1).toExponential(3), this.lastPk || []]); this.lastPk = null;
    this._step(now, dt, e, pt && pt.clarity > CLT ? pt.midi : -1, chroma);
  }
  // two memories: the last half minute or so, and the last few seconds (what you play now)
  _fade(dt) {
    const S = this._sens();
    const fade = Math.pow(0.5, dt / this.memory), fadeR = Math.pow(0.5, dt / lerp(4, 2.2, S));
    for (let i = 0; i < 12; i++) { this.h[i] *= fade; this.r[i] *= fadeR; }
  }
  // what was heard in one moment (the new sound's level, the note if one is clear, else what sounds)
  _step(now, dt, e, midi, chroma) {
    this._fade(dt);
    // the room's quiet: a low level of the new sound, followed down quickly and up slowly
    this.eFloor = e < this.eFloor || !this.eFloor ? Math.max(1e-6, e * 0.5 + this.eFloor * 0.5) : this.eFloor * 1.002;
    // a note begins where the new sound rises (an attack, a bow change): only there is a new note
    // counted; a different pitch read later, while a note sounds on and fades, is not a note
    const eh = this.eHist || (this.eHist = []); const eMin = eh.length ? Math.min(...eh) : 0;
    if (e > Math.max(eMin * (globalThis.__kfRise ?? 1.4), this.eFloor * G('__kfOnF', 6))) this.onsetAt = now;
    eh.push(e); if (eh.length > 3) eh.shift();
    // a pause: the new sound well below how loud you have been playing (the last few seconds), for a
    // moment (a dip between two notes is not one). (The room's quiet alone was not enough: it starts
    // from the silence before the first note and took minutes to reach the room's own noise, so no
    // pause, nor the end of a phrase, was ever heard.)
    this.ePeak = Math.max(e, (this.ePeak || 0) * Math.pow(0.5, dt / G('__kfPeakHalf', 4)));
    let low = e < Math.max(this.eFloor * 3 + 1e-5, this.ePeak * G('__kfQuiet', 0.12));
    // (better: the level above the drone's own sound, against how loud you have been playing lately —
    // a held note stays above it, the drone and the room never do)
    const lv = this.__tickLv !== undefined ? this.__tickLv : this.lv;
    if (G('__kfLvPause', 1) && lv !== undefined && lv < 0) low = false;
    else if (G('__kfLvPause', 1) && lv !== undefined) {
      const hs = this.lvHist || (this.lvHist = []);
      const srt = [...hs].sort((a, b) => a - b), P = srt.length >= 10 ? srt[Math.floor(srt.length * 0.4)] : 0;
      low = P > 0 && lv < G('__kfLvQ', 0.3) * P;
      if (!low) { hs.push(lv); if (hs.length > 75) hs.shift(); }
    }
    this.lowRun = low ? (this.lowRun || 0) + 1 : 0;
    // (only the pause and the end of a phrase: the notes themselves are counted as before)
    if (V3() && this.lowRun === (G('__kfLvPause', 1) && (this.__tickLv ?? this.lv) !== undefined ? G('__kfLvN', 8) : G('__kfLowRun', 10))) { if (!(this.silentFrom >= 0)) this.silentFrom = now - 40 * (this.lowRun - 1); this._noteOff(now, true); }
    if (V3() && !low && this.silentFrom >= 0) { if (now - this.silentFrom >= G('__kfGap', 1000)) this._afresh(now); this.silentFrom = -1; }
    if (e < this.eFloor * 3 + 1e-5) { this.prevPc = -1; this.pcRun = 0; this.quietAt = now; if (V2()) this._noteOff(now, true); return; }
    let heard = false;
    // (every moment, the share of each of the 12 notes in what sounds new, a little: fast passages
    // and double stops count too, where no single note is clear)
    const cw = G('__kfChroma', 0);
    if (cw > 0 && V3()) {
      const c = this.__tickChroma || (typeof chroma === 'function' ? chroma() : chroma);
      if (c) {
        const a = G('__kfH3', 0.35), b2 = G('__kfH5', 0.2), d = new Float64Array(12); let sm = 0;
        for (let i = 0; i < 12; i++) { d[i] = Math.max(0, c[i] - a * c[(i + 5) % 12] - b2 * c[(i + 8) % 12]); sm += d[i]; }
        if (sm > 0) { const L = logE(); this._evidence((k) => { let v = 0; for (let i = 0; i < 12; i++) v += d[i] * L[k][i]; return cw * dt * v / sm; }); }
      }
    }
    if (midi >= 0) {
      const pc = ((midi % 12) + 12) % 12;
      // the same note twice in a row (80 ms) is a note, not a scrape
      if (pc === this.prevPc) {
        this.pcRun++;
        // (no attack just before, and not just out of silence: the same note sounding on, misread)
        const fresh = !(globalThis.__kfOnset ?? 1) || now - (this.onsetAt ?? -1e9) < 220 || now - (this.quietAt ?? -1e9) < 220;
        const RUN = globalThis.__kfRun ?? 1;
        if (this.pcRun === RUN && !fresh && this.lastNotePc !== undefined) { this.pcRun = 0; this.prevPc = -1; return; }
        if (this.pcRun < RUN) return;
        if (this.pcRun === RUN && V2()) this._noteOn(pc, now - 40 * (RUN + 1));
        if (this.pcRun === RUN) { this.lastNotePc = pc; this.onsets++; this.noteW = 0; (this.recent || (this.recent = [])).push(midi); if (this.recent.length > 24) this.recent.shift(); const ra = this.recentAt || (this.recentAt = []); ra.push(now); if (ra.length > 24) ra.shift(); }
        // each note counts once: a little for being played, then for as long as it sounds, up to a cap
        const add = (this.pcRun === RUN ? 0.15 : 0) + (this.noteW < NOTE_CAP ? Math.min(dt, NOTE_CAP - this.noteW) : 0);
        this.noteW += dt;
        const w = add * (midi < 57 ? 1.15 : 1); this.h[pc] += w; this.r[pc] += w; this.ev[pc] += w;
        heard = true;
      } else { this.prevPc = pc; this.pcRun = 0; }
    } else {
      this.prevPc = -1; this.pcRun = 0;
      // chords and double stops (no single pitch): every pitch class that sounds, by its share
      const c = typeof chroma === 'function' ? chroma() : chroma;
      const sum = c ? c.reduce((a, v) => a + v, 0) : 0;
      if (sum > 0) { for (let i = 0; i < 12; i++) { const w = (dt * 0.35 * c[i]) / sum; this.h[i] += w; this.r[i] += w; this.ev[i] += w; } heard = true; }
    }
    if (!heard) return;
    if (G('__kfD', 3) === 4 && V3()) { this._decide4(now); return; }
    if (V3()) {
      const k0 = this.key; this._decide3(now);
      // (and, while you play on without a pause, the steadier way of the earlier ear: the likely key over
      // the last few seconds — it follows a piece that moves to a near key, where only one note changes)
      // (not just after a pause: there the new piece is judged as above, on its own notes)
      if (G('__kfHyb', 1) && this.key === k0 && !(G('__kfHybF', 1) && now - (this.freshAt ?? -1e12) < G('__kfHybMs', 14000)) && !this._tuned(now)) this._decide2(now);
      return;
    }
    if (V2()) { this._decide2(now); return; }
    this._update(dt, now);
  }
  // ---- the ear, note by note (a filter over the 24 keys) ----
  _noteOn(pc, at) {
    this._noteOff(at, false);
    const prev = this.cur;
    this.cur = { pc, at, from: prev ? prev.pc : -1, fromAt: prev ? prev.at : -1e9 };
    // each note: the keys whose scale has it gain, the others lose (a little for being played)
    const L = logE(); this._evidence((k) => L[k][pc] * 0.6);
    // (a triad outlined, root – third – fifth one after another, up or down: an arpeggio of that
    // chord, most often the tonic's — G B D says G major, E G B says E minor)
    const tw = G('__kfTriad', 1);
    if (V3() && tw > 0) {
      const h = this.tri || (this.tri = []); h.push(pc); if (h.length > 3) h.shift();
      if (h.length === 3 && new Set(h).size === 3) {
        const st = [...h].sort((a, b) => a - b);
        for (const r of st) { const d1 = (st.find((x) => (x - r + 12) % 12 === 4) ?? -1), d1m = (st.find((x) => (x - r + 12) % 12 === 3) ?? -1), d5 = st.find((x) => (x - r + 12) % 12 === 7) ?? -1;
          if (d5 < 0) continue;
          const minor = d1 < 0 && d1m >= 0; if (d1 < 0 && d1m < 0) continue;
          const kk = r + (minor ? 12 : 0); this._evidence((k) => (k === kk ? Math.log(3) : 0) * tw); break; }
      }
    }
    // (the first note after a pause: the start of a scale, a piece, a phrase — very often the tonic)
    if (V3() && this.freshAt !== undefined && !this.startDone && this.freshAt >= 0) { this.startDone = true; this.firstAfter = pc; this._evidence((k) => Math.log(REST[k][pc]) * G('__kfStartW', 1.2)); }
    this.notesSince = (this.notesSince || 0) + 1; this.notesSeen = (this.notesSeen || 0) + 1;
    if (this.afterFresh && this.afterFresh.length < 30) this.afterFresh.push(pc);
    // (the notes of the last several seconds, one count each, for "a note only the new key has")
    const nw = this.nwin || (this.nwin = new Float64Array(12)), f = Math.pow(0.5, Math.max(0, at - (this.nwAt ?? at)) / 1000 / G('__kfNwHalf', 6)); this.nwAt = at;
    for (let i = 0; i < 12; i++) nw[i] *= f; nw[pc] += 1;
  }
  _noteOff(at, rest) {
    const n = this.cur; if (!n) return;
    this.cur = null;
    this.lastEnd = { pc: n.pc, at };
    const dur = Math.min(2.5, Math.max(0.05, (at - n.at) / 1000));
    const durs = this.durs || (this.durs = []); durs.push(dur); if (durs.length > 12) durs.shift();
    const med = [...durs].sort((a, b) => a - b)[Math.floor(durs.length / 2)];
    // a note that sounded on counts for its length (short notes less, up to a cap)
    const lw = Math.min(1, dur / 0.6) * 0.8;
    const L = logE(); this._evidence((k) => L[k][n.pc] * lw);
    // where the music comes to rest
    const long = durs.length >= 3 && dur >= Math.max(0.5, med * 1.6);
    const lead = n.from === (n.pc + 11) % 12 && at - n.fromAt < 3000;
    const c = (long ? 1 : 0) + (rest && dur >= 0.25 ? 0.8 : 0) + (lead && (long || rest) ? 0.6 : 0);
    if (c > 0) this._evidence((k) => Math.log(REST[k][n.pc]) * c * G('__kfRestW', 1.4));
  }
  _evidence(f) {
    if (V3()) this._proof(f);
    const p = this.post; if (!p) return;
    // (a key may change at any note: a little of each key's likelihood flows to its near keys first)
    const s = globalThis.__kfStay ?? 0.97, q = new Float64Array(24);
    for (let a = 0; a < 24; a++) { const pa = p[a]; if (!pa) continue; q[a] += pa * s; const row = NEAR[a]; for (let b = 0; b < 24; b++) q[b] += pa * (1 - s) * row[b]; }
    let mx = -Infinity; const l = new Float64Array(24);
    for (let k = 0; k < 24; k++) { l[k] = f(k); if (l[k] > mx) mx = l[k]; }
    let sum = 0; for (let k = 0; k < 24; k++) { q[k] *= Math.exp(l[k] - mx); sum += q[k]; }
    for (let k = 0; k < 24; k++) p[k] = Math.max(1e-6, q[k] / sum);
  }
  // ---- the proof for each other key against the key the drone is in (a change detector) ----
  // Each note adds, for every other key, how much better that key explains it than the drone's key
  // (a note both keys have adds about nothing; a note only the other key has adds a lot; a note only
  // the drone's key has takes it away); the proof never goes below nothing and fades with time
  // (a few passing notes long ago are forgotten).
  _proof(f) {
    const cur = this.key; if (!cur) return;
    const ci = cur.pc + (cur.minor ? 12 : 0), now = this._now();
    const C = this.C || (this.C = new Float64Array(24));
    const fade = Math.pow(0.5, Math.max(0, now - (this.Cat ?? now)) / 1000 / G('__kfHalf', 8)); this.Cat = now;
    const lc = f(ci);
    // and, apart from the drone's key, how well each key explains the last few seconds (to choose among them)
    const W = this.W || (this.W = new Float64Array(24)), fw = Math.pow(0.5, Math.max(0, now - (this.Wat ?? now)) / 1000 / G('__kfHalfW', 5)); this.Wat = now;
    for (let k = 0; k < 24; k++) { const fk = f(k); W[k] = W[k] * fw + fk; if (k === ci) { C[k] = 0; continue; } C[k] = Math.max(0, C[k] * fade + fk - lc); }
  }
  // Tuning: open strings, a fifth apart, again and again — no key in that. (A note misheard now and
  // then, A taken for B♭, does not hide it: four notes make nearly all of it.)
  _tuning() {
    const rc = this.recent || []; let fifths = 0, moves = 0; const cnt = {};
    const from = Math.max(1, rc.length - 12);
    for (let i = from; i < rc.length; i++) { const d = ((rc[i] - rc[i - 1]) % 12 + 12) % 12; cnt[rc[i] % 12] = (cnt[rc[i] % 12] || 0) + 1; if (d === 0) continue; moves++; if (d === 5 || d === 7) fifths++; }
    const n = rc.length - from; if (n < 5) return false;
    const top4 = Object.values(cnt).sort((a, b) => b - a).slice(0, 4).reduce((a, b) => a + b, 0);
    return moves >= 4 && fifths / moves >= 0.5 && top4 / n >= 0.8;
  }
  // (and a little after it: a long open string, a note misheard now and then, does not end the tuning)
  // (slow open strings, a string a little out of tune or heard a half step off: the slide of a half step
  // is the same string, and the moves between strings are fifths)
  _tuningSlow() {
    const rc = this.recent || [], ra = this.recentAt || []; if (rc.length < 6 || ra.length !== rc.length) return false;
    const from = Math.max(1, rc.length - 12); let base = rc[from - 1], moves = 0, fifths = 0; const cnt = {};
    const H = G('__kfTuneH', 1);
    for (let i = from; i < rc.length; i++) {
      // (a blip, another note heard within half a second, is not a string played; nor is the string's
      // own twelfth, its strongest harmonic, heard above it)
      if (H && i < rc.length - 1 && ra[i + 1] - ra[i] < 500) continue;
      const up = rc[i] - base, d = (up % 12 + 12) % 12; if (d === 0 || d === 1 || d === 11) continue;
      if (H && (Math.abs(up - 19) <= 1 || Math.abs(up - 31) <= 1)) continue;
      base = rc[i]; moves++; cnt[base % 12] = (cnt[base % 12] || 0) + 1; if ((d >= 5 && d <= 7) || (H && Math.abs(up) >= 6 && Math.abs(up) <= 8)) fifths++;
    }
    if (moves < 4) return false;
    const top4 = Object.values(cnt).sort((a, b) => b - a).slice(0, 4).reduce((a, b) => a + b, 0);
    return fifths / moves >= 0.5 && top4 / moves >= 0.8 && (ra[ra.length - 1] - ra[from - 1]) / moves >= G('__kfTuneSlow', 1000);
  }
  _tuned(now) { if (this._tuning() || this._tuningSlow()) this.tunedAt = now; return now - (this.tunedAt ?? -1e12) < G('__kfTuneMs', 6000); }
  _decide3(now) {
    const S = this._sens(), cur = this.key;
    // what the ear believes now (shown under the drone)
    const p = this.post; let b = 0; for (let k = 1; k < 24; k++) if (p[k] > p[b]) b = k;
    this.onHear && this.onHear(p[b] > 0.5 ? { pc: b % 12, minor: b >= 12, score: p[b] } : null);
    if (!cur || !this.C) return;
    const C = this.C, ci = cur.pc + (cur.minor ? 12 : 0);
    // 1. has the drone's key been left? (some key has proof enough against it)
    // 2. then which key: the one that explains the last few seconds best, clearly, and has proof too
    // a scale says its key: a stepwise run from a note to the same note an octave away
    const sk = G('__kfScale', 1) ? this._scaleKey() : null;
    if (sk && !(sk.pc === cur.pc && sk.minor === cur.minor) && now - (this.movedAt ?? -1e12) >= 1200) {
      this.why = 'scale'; this.pa = null; this.cand = null; this.key = sk; this.movedAt = now; this.notesSince = 0; this.fastBg = now + 2500; this.flFrom = now; this.C.fill(0); this.scaleDone = this.notesSeen;
      this.onKey && this.onKey(this.key); return;
    }
    const W = this.W;
    let k1 = -1, k2 = -1; for (let k = 0; k < 24; k++) { if (k === ci || C[k] <= 0) continue; if (k1 < 0 || W[k] > W[k1]) { k2 = k1; k1 = k; } else if (k2 < 0 || W[k] > W[k2]) k2 = k; }
    if (k1 < 0) return;
    let cm = 0; for (let k = 0; k < 24; k++) if (C[k] > cm) cm = C[k];
    const nk = { pc: k1 % 12, minor: k1 >= 12 };
    const near = relative(cur, nk) || cur.pc === nk.pc;
    const fresh = now - (this.freshAt ?? -1e12) < G('__kfFreshMs', 8000);
    // (a key two or more fifths away, while a key plays on without a pause, wants more proof: music
    // passes through such keys for a bar or two without going there)
    const far = !near && fifthsApart(cur, nk) >= 2 && !fresh;
    const H = lerp(G('__kfH', 4.5) * 1.5, G('__kfH', 4.5) * 0.7, S) * (near ? G('__kfNear', 1.4) : 1) * (fresh ? G('__kfFreshH', 0.7) : 1) * (far ? G('__kfFar', 1) : 1);
    const wm = k2 < 0 ? 99 : W[k1] - W[k2];
    this.dbg = { k: k1, C: +C[k1].toFixed(2), C2: +cm.toFixed(2), H: +H.toFixed(2), wm: +wm.toFixed(2) };
    if (cm < H || C[k1] < H * G('__kfOwn', 0.6) || wm < G('__kfM', 0.8)) return;
    // never on what is not a key at all (a chromatic run, a shifting exercise, half steps), never on a
    // key that does not hold what you play now, and not again the moment after a move
    const r = this.r; let totR = 0; for (let i = 0; i < 12; i++) totR += r[i];
    let spread = 0; for (let i = 0; i < 12; i++) if (r[i] >= 0.05 * totR) spread++;
    const rc = this.recent || []; let semi = 0, steps = 0;
    for (let i = 1; i < rc.length; i++) { const d = Math.abs(rc[i] - rc[i - 1]); if (d === 0) continue; steps++; if (d === 1) semi++; }
    const chromatic = steps >= 8 && semi / steps > G('__kfSemi', 0.4);
    const fit = scaleFit(r, nk.pc, nk.minor);
    const settled = now - (this.movedAt ?? -1e12) >= G('__kfSettle', 2500);
    this.dbg.guard = [spread, chromatic, +fit.toFixed(2), settled];
    // tuning: open strings, a fifth apart, again and again (no key in that)
    if (this._tuning()) { this.dbg.tuning = true; return; }
    if (chromatic || spread > G('__kfSpread', 9) || fit < G('__kfFit', 0.8) || !settled || (this.notesSince || 0) < G('__kfMinNotes', 3)) return;
    // as a musician hears it: a key changes only with a note the new key has and the old one has not
    // (C♯ from G to D, D♯ to E minor, F♯ from D minor to D major); from a minor key to its relative
    // major (A minor to C) there is none: there the minor's leading note (G♯) must have gone
    if (!this._newNote(cur, nk)) { this.dbg.nn = false; return; }
    // and not while a neighbour of that key (its dominant or subdominant, its relative or parallel
    // key) explains what you play almost as well: only once the note that tells them apart has been
    // heard (E♯, not E, for F♯ major against B major; the leading note for a minor key against its
    // relative major) — the way a musician tells them apart
    const riv = this._rival(k1, W);
    if (riv >= 0) { this.dbg.rival = riv; return; }
    this.why = 'proof'; this.pa = null; this.cand = null; this.key = nk; this.movedAt = now; this.notesSince = 0; this.fastBg = now + 2500; this.flFrom = now; this.C.fill(0);
    // (the filter shown under the drone starts from the new key too)
    const q = this.post; for (let k = 0; k < 24; k++) q[k] = Math.max(q[k], 0); q[k1] = Math.max(q[k1], 0.6); let sm = 0; for (let k = 0; k < 24; k++) sm += q[k]; for (let k = 0; k < 24; k++) q[k] /= sm;
    this.onKey && this.onKey(this.key);
  }
  // ---- the key now: which key explains the last few seconds best (the ends of phrases weighing
  // most), against the drone's key; it moves when another key is clearly better, stays the better
  // one for a few notes, and has a note the drone's key has not ----
  _decide4(now) {
    const S = this._sens(), cur = this.key;
    const p = this.post; let b = 0; for (let k = 1; k < 24; k++) if (p[k] > p[b]) b = k;
    this.onHear && this.onHear(p[b] > 0.5 ? { pc: b % 12, minor: b >= 12, score: p[b] } : null);
    const W = this.W; if (!cur || !W) return;
    const ci = cur.pc + (cur.minor ? 12 : 0);
    // (only on a new note: the decision is a musician's, note by note)
    const n = this.notesSeen || 0; if (n === this.lastDecN) return; this.lastDecN = n;
    let k1 = -1, k2 = -1; for (let k = 0; k < 24; k++) { if (k1 < 0 || W[k] > W[k1]) { k2 = k1; k1 = k; } else if (k2 < 0 || W[k] > W[k2]) k2 = k; }
    if (k1 === ci) { this.win = null; return; }
    const nk = { pc: k1 % 12, minor: k1 >= 12 }, near = relative(cur, nk) || cur.pc === nk.pc;
    const fresh = now - (this.freshAt ?? -1e12) < G('__kfFreshMs', 8000);
    const T = lerp(1.4, 0.7, S) * G('__kfT', 3) * (near ? G('__kfNear', 1.4) : 1) * (fresh ? G('__kfFreshH', 0.7) : 1);
    const gap = W[k1] - W[ci], marg = W[k1] - W[k2];
    this.dbg = { k: k1, C: +gap.toFixed(2), C2: +marg.toFixed(2), H: +T.toFixed(2) };
    if (gap < T || marg < G('__kfM', 0.8)) { this.win = null; return; }
    if (!this.win || this.win.k !== k1) { this.win = { k: k1, n: 0 }; }
    this.win.n++;
    if (this.win.n < G('__kfStable', 2)) return;
    const r = this.r; let totR = 0; for (let i = 0; i < 12; i++) totR += r[i];
    let spread = 0; for (let i = 0; i < 12; i++) if (r[i] >= 0.05 * totR) spread++;
    const rc = this.recent || []; let semi = 0, steps = 0;
    for (let i = 1; i < rc.length; i++) { const d = Math.abs(rc[i] - rc[i - 1]); if (d === 0) continue; steps++; if (d === 1) semi++; }
    const chromatic = steps >= 8 && semi / steps > G('__kfSemi', 0.4);
    const settled = now - (this.movedAt ?? -1e12) >= G('__kfSettle', 2500);
    this.dbg.guard = [spread, chromatic, settled];
    if (chromatic || spread > G('__kfSpread', 9) || !settled || (this.notesSince || 0) < G('__kfMinNotes', 3)) return;
    if (G('__kfNN', 1) && !this._newNote(cur, nk)) { this.dbg.nn = false; return; }
    this.key = nk; this.movedAt = now; this.notesSince = 0; this.fastBg = now + 2500; this.flFrom = now; this.win = null;
    if (this.C) this.C.fill(0);
    this.onKey && this.onKey(this.key);
  }
  _scaleKey() {
    const now0 = (o) => o._now();
    // a scale from a pause: from its first note (or the second or third, when the first was not
    // heard) step by step to the same note an octave away; steps by note name, so an octave heard
    // wrongly does not break it, a wrong note away and straight back is left out, and a note not
    // heard at all leaves a third, still a step
    const seq0 = this.afterFresh || []; if (seq0.length < 6 || this.scaleFor === this.freshAt) return null;
    if (now0(this) - (this.freshAt ?? -1e12) > 15000) return null;
    const seq = []; for (let k = 0; k < seq0.length; k++) { const p = seq0[k]; if (seq.length && seq[seq.length - 1] === p) continue; seq.push(p); }
    const iv = (a, b) => ((b - a) % 12 + 12) % 12;
    const f = []; for (let k = 0; k < seq.length; k++) { const a = f[f.length - 1], b = seq[k], c = seq[k + 1]; if (a !== undefined && c !== undefined) { const d1 = iv(a, b), d2 = iv(a, c); const step = (d) => (d >= 1 && d <= 4) || (d >= 8 && d <= 11); if (!step(d1) && step(d2) && G('__kfScaleTol', 1)) continue; } f.push(b); }
    // (from its first note, or from that note again an octave on — a low first octave is often
    // half heard, the second clearly)
    for (let s0 = 0; s0 < f.length; s0++) {
      if (s0 > G("__kfScaleS0", 0) && !(G('__kfScale2', 1) && f[s0] === f[0])) continue;
      let dir = 0, tot = 0; const seg = [f[s0]];
      for (let k = s0 + 1; k < f.length; k++) {
        const d = iv(f[k - 1], f[k]); const up = d >= 1 && d <= 4, dn = d >= 8 && d <= 11;
        if (!up && !dn) break; const sd = up ? 1 : -1; if (dir && sd !== dir) break; dir = sd;
        tot += up ? d : 12 - d; seg.push(f[k]);
        if (tot === 12 && f[k] === f[s0] && seg.length >= G('__kfScaleN', 6)) {
          const t = f[s0], pcs = new Set(seg), rel = (x) => pcs.has((t + x) % 12);
          if (pcs.size < 6) break;
          // (only a real major or minor scale on that note: every note of it in that scale, the second a
          // whole step up, the fifth there — G to G in C major (no F♯) or B to B in G (C, a half step up)
          // is a mode of another key, not a scale of its own; a minor scale needs its sixth or leading note)
          const inSet = (set) => [...pcs].every((x) => set.includes((x - t + 12) % 12));
          if (G('__kfScaleStrict', 1)) {
            if (inSet([0, 2, 4, 5, 7, 9, 11]) && rel(2) && rel(4) && rel(7) && pcs.size >= G('__kfScaleN', 6)) { this.scaleFor = this.freshAt; return { pc: t, minor: false }; }
            if (inSet([0, 2, 3, 5, 7, 8, 9, 10, 11]) && rel(2) && rel(3) && rel(5) && rel(7) && (rel(8) || rel(11)) && !(rel(9) && rel(10) && !rel(11))) { this.scaleFor = this.freshAt; return { pc: t, minor: true }; }
            break;
          }
          if (rel(4) && !rel(3) && rel(7)) { this.scaleFor = this.freshAt; return { pc: t, minor: false }; }
          if (rel(3) && !rel(4) && rel(7)) { this.scaleFor = this.freshAt; return { pc: t, minor: true }; }
          break;
        }
        if (tot > 12) break;
      }
    }
    return null;
  }
  _afresh(now) {
    this.freshAt = now; this.startDone = false; this.firstAfter = -1; this.afterFresh = [];
    for (const a of [this.C, this.W, this.nwin]) if (a) a.fill(0);
  }
  _rival(k1, W) {
    const M2 = G('__kfRiv', 0); if (!M2) return -1;
    const nk = { pc: k1 % 12, minor: k1 >= 12 }, nw = this.nwin; if (!nw) return -1;
    const core = (k) => k.minor ? [0, 2, 3, 5, 7, 8, 11] : [0, 2, 4, 5, 7, 9, 11];
    let tot = 0; for (let i = 0; i < 12; i++) tot += nw[i];
    for (let k = 0; k < 24; k++) {
      if (k === k1 || W[k1] - W[k] >= M2) continue;
      const rk = { pc: k % 12, minor: k >= 12 };
      const d = (rk.pc - nk.pc + 12) % 12;
      const nb = (rk.minor === nk.minor && (d === 5 || d === 7)) || relative(rk, nk) || (rk.pc === nk.pc && rk.minor !== nk.minor);
      if (!nb) continue;
      const cn = core(nk), cr = core(rk); let only = 0, gone = 0;
      for (let i = 0; i < 12; i++) { const inN = cn.includes((i - nk.pc + 12) % 12), inR = cr.includes((i - rk.pc + 12) % 12); if (inN && !inR) only += nw[i]; else if (inR && !inN) gone += nw[i]; }
      // (a major key against its relative minor has no note of its own: the minor's leading note must be absent)
      const ok = only > 0 ? (only >= G('__kfRivN', 1) && only > gone) : (gone <= 0.3 && tot >= G('__kfRivT', 8));
      if (!ok) return k;
    }
    return -1;
  }
  _newNote(cur, nk) {
    const nw = this.nwin; if (!nw) return false;
    const core = (k) => k.minor ? [0, 2, 3, 5, 7, 8, 11] : [0, 2, 4, 5, 7, 9, 11];
    const so = core(cur), sn = core(nk); let fresh = 0, gone = 0, tot = 0;
    for (let i = 0; i < 12; i++) { tot += nw[i]; const inN = sn.includes((i - nk.pc + 12) % 12), inO = so.includes((i - cur.pc + 12) % 12); if (inN && !inO) fresh += nw[i]; else if (inO && !inN) gone += nw[i]; }
    if (fresh >= G('__kfNew', 1.2) && gone <= fresh) return true;
    // (or the old key's own note has gone, over many notes: G no more, from D to A)
    if (tot >= G('__kfGoneN', 9) && gone <= G('__kfGone', 0.3) && !(nk.minor && relative(cur, nk))) return true;
    // (minor to its relative major: no leading note of the minor any more)
    if (cur.minor && !nk.minor && relative(cur, nk)) return nw[(cur.pc + 11) % 12] <= G('__kfLeadGone', 0.15) * Math.max(1, tot / 6);
    return false;
  }
  _decide2(now) {
    const S = this._sens(), cur = this.key;
    // (what the ear believes over the last couple of seconds, not at one note: one note never moves it)
    const dt = Math.min(0.3, Math.max(0, (now - (this.paAt ?? now)) / 1000)); this.paAt = now;
    const pa = this.pa || (this.pa = Float64Array.from(this.post)), a = 1 - Math.exp(-dt / (globalThis.__kfAvg ?? 3));
    for (let k = 0; k < 24; k++) pa[k] += (this.post[k] - pa[k]) * a;
    const p = pa;
    let b = 0; for (let k = 1; k < 24; k++) if (p[k] > p[b]) b = k;
    const best = { pc: b % 12, minor: b >= 12 };
    this.onHear && this.onHear(p[b] > 0.5 ? { pc: best.pc, minor: best.minor, score: p[b] } : null);
    if (!cur) return;
    const ci = cur.pc + (cur.minor ? 12 : 0);
    this.dbg = { best: best.pc + (best.minor ? 'm' : ''), p: +p[b].toFixed(2), pc: +p[ci].toFixed(2), notes: this.notesSince };
    const want = b !== ci && p[b] >= lerp(globalThis.__kfOn ?? 0.7, (globalThis.__kfOn ?? 0.7) - 0.2, S) && p[ci] <= (globalThis.__kfOff ?? 0.15);
    let calmOk = false;
    if (want) {
      // never on what is not a key at all (a chromatic run, a shifting exercise, half steps), and not
      // again so soon after a move
      const r = this.r; let totR = 0; for (let i = 0; i < 12; i++) totR += r[i];
      let spread = 0; for (let i = 0; i < 12; i++) if (r[i] >= 0.05 * totR) spread++;
      const rc = this.recent || []; let semi = 0, steps = 0;
      for (let i = 1; i < rc.length; i++) { const d = Math.abs(rc[i] - rc[i - 1]); if (d === 0) continue; steps++; if (d === 1) semi++; }
      const chromatic = steps >= 8 && semi / steps > (globalThis.__kfSemi ?? 0.4);
      const settled = now - (this.movedAt ?? -1e12) >= lerp(6000, 3000, S);
      calmOk = spread <= (globalThis.__kfSpread ?? 9) && !chromatic && settled && (this.notesSince || 0) >= 4;
      // (a key far from the drone's, without a pause: only when its own notes are really there, not a
      // low note or two heard a half step off — a G heard as F♯, an A as B♭, while you tune)
      if (calmOk && fifthsApart(cur, best) >= 2) {
        const cOf = (k) => k.minor ? [0, 2, 3, 5, 7, 8, 11] : [0, 2, 4, 5, 7, 9, 11];
        const cn = cOf(best), co = cOf(cur); let own = 0;
        for (let i = 0; i < 12; i++) if (cn.includes((i - best.pc + 12) % 12) && !co.includes((i - cur.pc + 12) % 12)) own += r[i];
        // (and its keynote is heard; and not away from the piece's own key while that is still likely:
        // from D back to G, not on to C)
        const hm = this.home, hi = hm ? hm.pc + (hm.minor ? 12 : 0) : -1;
        const homeNear = hm && hi !== b && fifthsApart(hm, cur) <= 1 && p[hi] >= G('__kfHomeP', 0.1);
        if (own < G('__kfFar2', 0.3) * totR || r[best.pc] < G('__kfFarT', 0.1) * totR || homeNear) { calmOk = false; this.dbg.far = [+(own / Math.max(1e-9, totR)).toFixed(2), +(r[best.pc] / Math.max(1e-9, totR)).toFixed(2), !!homeNear]; }
      }
      this.dbg.guard = [spread, chromatic, settled];
    }
    if (!want || !calmOk) { if (this.cand && now - this.cand.lastOk > 700) this.cand = null; return; }
    if (!this.cand || this.cand.pc !== best.pc || this.cand.minor !== best.minor) { this.cand = { ...best, since: now, lastOk: now }; return; }
    this.cand.lastOk = now;
    if (now - this.cand.since >= lerp(globalThis.__kfHold ?? 1200, 400, S)) {
      this.key = best; this.cand = null; this.movedAt = now; this.notesSince = 0; this.fastBg = now + 2500; this.flFrom = now; this.why = 'filter'; if (this.C) this.C.fill(0);
      // (the new key is now the likely one; the filter goes on from where it is)
      this.onKey && this.onKey(this.key);
    }
  }
  _decide(now) {
    const S = this._sens();
    const h = this.h, r = this.r, total = h.reduce((s, x) => s + x, 0), totalR = r.reduce((s, x) => s + x, 0);
    let distinct = 0; for (const x of h) if (x >= 0.05 * total) distinct++;
    let distinctR = 0; for (const x of r) if (x >= 0.05 * totalR) distinctR++;
    // too little to say anything yet: a few notes, or a held note, or a fragment
    if (total < lerp(2.4, 1.2, S) || distinct < 4) { this.cand = null; this.onHear && this.onHear(null); return; }
    const k = keyOf(h);
    this.onHear && this.onHear(k.score >= 0.5 ? k : null);
    // what you play now: the key it points to, if it is clear
    const kr = totalR >= lerp(1.6, 0.9, S) && distinctR >= (S > 0.6 ? 4 : 5) ? keyOf(r) : null;
    const minScore = lerp(0.62, 0.45, S);
    this.dbg = { kr: kr && kr.pc + (kr.minor ? 'm' : ''), score: kr && +kr.score.toFixed(2), totalR: +totalR.toFixed(1), distinctR };
    if (!kr || !this.key || kr.score < minScore || (kr.pc === this.key.pc && kr.minor === this.key.minor)) { if (this.cand && now - this.cand.lastOk > 1200) this.cand = null; return; }
    const cur = this.key;
    const rel = relative(cur, kr), sameTonic = cur.pc === kr.pc;
    const gainR = kr.score - keyScore(r, cur.pc, cur.minor), gainH = keyScore(h, kr.pc, kr.minor) - keyScore(h, cur.pc, cur.minor);
    const fitNew = scaleFit(r, kr.pc, kr.minor), fitOld = scaleFit(r, cur.pc, cur.minor);
    // the old key is broken when its scale clearly does not hold what you play: many notes outside
    // it, or some notes outside it while the notes only the old key has (C♯ for D against G) are gone
    const onlyOld = 1 - scaleFitOf(r, cur, kr);
    const clean = 1 - fitOld >= 0.03 && onlyOld <= 0.03;   // the new key's note is there, the old key's note is gone
    const broken = 1 - fitOld >= 0.06 || clean;
    // the new key holds nearly every note you play now; the old key's scale is clearly broken by
    // them — or, between relative or parallel keys (same notes or same tonic), the shape of the
    // music says so very clearly; and the longer memory does not say otherwise
    const ok = this.onsets >= Math.round(lerp(10, 5, S)) && fitNew >= lerp(0.9, 0.8, S) && gainH > lerp(-0.04, -0.12, S) && (
      (rel || sameTonic) ? gainR >= lerp(0.24, 0.1, S) : (broken && gainR >= (clean ? 0.5 : 1) * lerp(0.12, 0.03, S)));
    this.dbg = { kr: kr.pc + (kr.minor ? 'm' : ''), score: +kr.score.toFixed(2), gainR: +gainR.toFixed(2), gainH: +gainH.toFixed(2), fitNew: +fitNew.toFixed(2), fitOld: +fitOld.toFixed(2), onlyOld: +onlyOld.toFixed(3), ok };
    // a moment that does not quite fit (a passing note) does not start the waiting again;
    // more than a second without it does
    if (!ok) { if (this.cand && now - this.cand.lastOk > 1200) this.cand = null; return; }
    const hold = rel || sameTonic ? lerp(5000, 2000, S) : lerp(3200, 1100, S);
    if (!this.cand || this.cand.pc !== kr.pc || this.cand.minor !== kr.minor) { this.cand = { pc: kr.pc, minor: kr.minor, since: now, lastOk: now }; return; }
    this.cand.lastOk = now;
    if (now - this.cand.since >= hold) {
      this.set(kr.pc, kr.minor);
      this.onKey && this.onKey(this.key);
    }
  }
}
