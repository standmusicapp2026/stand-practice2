// Hearing which key you are playing in, so a drone can follow a change of key — and only that.
// Note by note, as a musician hears it: each note makes the keys whose scale has it more likely
// (allowing that a note is now and then misheard), and where the music comes to rest — a long
// note, the end of a phrase, a note reached from its leading note — says which note is home (G
// major and E minor have the same notes; only that tells them apart). The 24 keys are weighed
// all the time, a change to a near key (a fifth away, relative, parallel) a little more readily;
// the drone moves when another key is clearly the likely one for a few seconds. A new note is
// counted only where a note begins (an attack), and only notes the instrument can play. A
// chromatic run, a shifting exercise, tuning the strings or a scale never moves it.
// (Measured on cello melodies with changes of key: on the right key 83% of the time instead of
// 75%, a change followed in about 15 s instead of 23, and no wrong move instead of 8.)

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
const LOGP = (() => { const out = []; for (const [prof, sc] of [[MAJOR, [0, 2, 4, 5, 7, 9, 11]], [MINOR, [0, 2, 3, 5, 7, 8, 9, 10, 11]]]) for (let k = 0; k < 12; k++) { const r = rot(prof, k), sum = r.reduce((a, v) => a + v, 0); out.push(r.map((v, i) => Math.log((globalThis.__kfMix ?? 0.2) * v / sum + (1 - (globalThis.__kfMix ?? 0.2)) * (sc.includes((i - k + 12) % 12) ? 1 / sc.length : 0) + 0.004))); } return out; })();
const NOTE_CAP = 0.55;     // seconds a single note can count for
const V2 = () => (globalThis.__kfV ?? 2) === 2;
// A note heard is now and then the wrong note (an attack, an overtone: about one in ten, and more
// in a room or a scratchy attack): each note
// counts as "this note, or a mistake", so one wrong note says little, the same note again and again a lot.
let LOGE = null, LOGE_EPS = -1;
const logE = () => {
  const eps = globalThis.__kfEps ?? 0.35;
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
  set(pc, minor) { this.fastBg = this._now() + 2500; this.key = { pc, minor }; this.cand = null; this.onsets = 0; this._resetPost(); this.pa = null; if (this.w) this.w.fill(0); }
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
    return res;
  }
  // the note heard in what is new: the pitch whose overtones together are strongest
  _pitch(res, sr) {
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
    const chroma = pt && pt.clarity > 6 ? null : () => chromaOf(res, sr, this.an.fftSize);
    if (globalThis.__kfRec) globalThis.__kfRec.push([now, dt, e, pt && pt.clarity > 6 ? pt.midi : -1, chroma ? chroma() : null]);
    this._step(now, dt, e, pt && pt.clarity > 6 ? pt.midi : -1, chroma);
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
    if (e > Math.max(eMin * (globalThis.__kfRise ?? 1.4), this.eFloor * 6)) this.onsetAt = now;
    eh.push(e); if (eh.length > 3) eh.shift();
    if (e < this.eFloor * 3 + 1e-5) { this.prevPc = -1; this.pcRun = 0; this.quietAt = now; if (V2()) this._noteOff(now, true); return; }
    let heard = false;
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
        if (this.pcRun === RUN) { this.lastNotePc = pc; this.onsets++; this.noteW = 0; (this.recent || (this.recent = [])).push(midi); if (this.recent.length > 24) this.recent.shift(); }
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
    this.notesSince = (this.notesSince || 0) + 1;
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
    if (c > 0) this._evidence((k) => Math.log(REST[k][n.pc]) * c * (globalThis.__kfRestW ?? 1.4));
  }
  _evidence(f) {
    const p = this.post; if (!p) return;
    // (a key may change at any note: a little of each key's likelihood flows to its near keys first)
    const s = globalThis.__kfStay ?? 0.97, q = new Float64Array(24);
    for (let a = 0; a < 24; a++) { const pa = p[a]; if (!pa) continue; q[a] += pa * s; const row = NEAR[a]; for (let b = 0; b < 24; b++) q[b] += pa * (1 - s) * row[b]; }
    let mx = -Infinity; const l = new Float64Array(24);
    for (let k = 0; k < 24; k++) { l[k] = f(k); if (l[k] > mx) mx = l[k]; }
    let sum = 0; for (let k = 0; k < 24; k++) { q[k] *= Math.exp(l[k] - mx); sum += q[k]; }
    for (let k = 0; k < 24; k++) p[k] = Math.max(1e-6, q[k] / sum);
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
      this.dbg.guard = [spread, chromatic, settled];
    }
    if (!want || !calmOk) { if (this.cand && now - this.cand.lastOk > 700) this.cand = null; return; }
    if (!this.cand || this.cand.pc !== best.pc || this.cand.minor !== best.minor) { this.cand = { ...best, since: now, lastOk: now }; return; }
    this.cand.lastOk = now;
    if (now - this.cand.since >= lerp(globalThis.__kfHold ?? 1200, 400, S)) {
      this.key = best; this.cand = null; this.movedAt = now; this.notesSince = 0; this.fastBg = now + 2500;
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
