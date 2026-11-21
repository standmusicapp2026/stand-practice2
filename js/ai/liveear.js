// The AI's ear for turning pages by listening: the neural network (ai/pitchnet.js) on the last two
// seconds of the microphone, several times a second, so that every note or chord the live listener
// hears is also told by the network — which notes really sound, a piano behind a cello or a singer
// told apart from the overtones of either. All on this device; nothing is recorded or kept.
import { netWindow, resample, NET_SR, NET_FPS, NET_KEYS, NET_LO } from './pitchnet.js';

const WIN = NET_SR * 2 - 256;     // the samples the network takes at a time (two seconds)
const KEEP = 4;                   // seconds of what was heard kept
const EDGE = 8;                   // frames at the very end of a window are less sure: the next run tells them better

export class LiveEar {
  constructor() { this.on = false; this.frames = []; this.waiters = []; this.busy = false; }
  async attach(ctx, src) {
    // (the network made ready first: if it cannot run here, the ear stays off)
    await netWindow(new Float32Array(WIN));
    this.ctx = ctx; this.sr = ctx.sampleRate;
    this.raw = new Float32Array(Math.ceil(this.sr * 2.3)); this.filled = 0; this.tEnd = 0;
    // (the sound taken as it comes, through a node that plays nothing)
    this.sp = ctx.createScriptProcessor(2048, 1, 1);
    this.mute = ctx.createGain(); this.mute.gain.value = 0;
    src.connect(this.sp); this.sp.connect(this.mute); this.mute.connect(ctx.destination);
    this.src = src;
    this.sp.onaudioprocess = (e) => {
      const x = e.inputBuffer.getChannelData(0), n = x.length, r = this.raw;
      r.copyWithin(0, n); r.set(x, r.length - n);
      this.filled = Math.min(r.length, this.filled + n);
      this.tEnd = performance.now();
    };
    this.on = true;
    this.timer = setInterval(() => this.run(), 140);
  }
  detach() {
    if (!this.on) return;
    this.on = false; clearInterval(this.timer);
    try { this.src.disconnect(this.sp); } catch {}
    try { this.sp.disconnect(); this.mute.disconnect(); } catch {}
    this.sp.onaudioprocess = null;
    for (const w of this.waiters) w.res(null);
    this.waiters = [];
  }
  async run() {
    if (!this.on || this.busy || this.filled < this.sr * 0.5) return;
    this.busy = true;
    try {
      const end = this.tEnd;
      const x = resample(this.raw, this.sr);
      const pad = new Float32Array(WIN); pad.set(x.subarray(Math.max(0, x.length - WIN)), Math.max(0, WIN - x.length));
      const { T, fr, on } = await netWindow(pad);
      if (!this.on) return;
      // frame f stands for the moment (end - two seconds) + f frames
      const t0 = end - (WIN / NET_SR) * 1000, dt = 1000 / NET_FPS;
      // (the frames this run tells better than the last one: from where that one's sure part ended)
      const keepFrom = this.sureTo ?? -Infinity;
      this.frames = this.frames.filter((f) => f.t < keepFrom && f.t > end - KEEP * 1000);
      for (let f = 0; f < T; f++) {
        const t = t0 + f * dt; if (t < keepFrom || t < end - KEEP * 1000) continue;
        const v = new Float32Array(NET_KEYS);
        for (let k = 0; k < NET_KEYS; k++) v[k] = Math.max(fr[f * NET_KEYS + k], on[f * NET_KEYS + k]);
        this.frames.push({ t, v });
      }
      this.sureTo = t0 + (T - EDGE) * dt;
      this.heardTo = t0 + T * dt;
      // the notes waiting for this moment
      this.waiters = this.waiters.filter((w) => { if (this.heardTo >= w.t1) { w.res(this._chroma(w.t0, w.t1)); return false; } return true; });
    } catch (err) { console.warn('AI ear', err); }
    finally { this.busy = false; }
  }
  _chroma(t0, t1) {
    const c = new Float32Array(12); let any = false;
    for (const f of this.frames) {
      if (f.t < t0 || f.t > t1) continue; any = true;
      for (let k = 0; k < NET_KEYS; k++) { const pc = (k + NET_LO) % 12; if (f.v[k] > c[pc]) c[pc] = f.v[k]; }
    }
    if (!any) return null;
    // (squared: a note the network is sure of stands out from one it only half hears)
    for (let i = 0; i < 12; i++) c[i] *= c[i];
    return c;
  }
  // What sounds just after an attack heard at time t (performance.now()): the 12 pitch classes, as
  // sure as the network is of each. Waits (at most `wait` ms) for the network to have heard it.
  chromaAfter(t, wait = 450) {
    if (!this.on) return Promise.resolve(null);
    const t0 = t - 20, t1 = t + 130;
    if (this.heardTo >= t1) return Promise.resolve(this._chroma(t0, t1));
    return new Promise((res) => {
      const w = { t0, t1, res };
      this.waiters.push(w);
      setTimeout(() => { const i = this.waiters.indexOf(w); if (i >= 0) { this.waiters.splice(i, 1); res(this._chroma(t0, t1)); } }, wait);
    });
  }
}
