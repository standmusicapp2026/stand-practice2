// Write by playing: the microphone hears one note at a time and each note played is written at the
// selection with the note value chosen, then the selection moves on (as a MIDI keyboard does).
// A note is written once it is clear (a few readings at the same pitch); the same note played again
// is written again after a little silence or a new attack; a slide to another pitch is a new note.
import { getCtx, acquireMic, releaseMic } from '../audio.js';
import { detectPitch, PitchTracker } from '../tuner.js';

export class ListenWrite {
  constructor(onNote, opts = {}) {
    this.onNote = onNote; this.ref = opts.ref || 440; this.on = false;
    this.tracker = new PitchTracker();
  }
  async start() {
    if (this.on) return true;
    const src = await acquireMic();
    const c = getCtx();
    this.an = c.createAnalyser(); this.an.fftSize = 2048; src.connect(this.an);
    this.buf = new Float32Array(this.an.fftSize); this.sr = c.sampleRate;
    this.on = true; this.cur = null; this.cand = null; this.quietAt = 0; this.lv = [];
    this.timer = setInterval(() => this._tick(), 25);
    return true;
  }
  stop() {
    if (!this.on) return;
    this.on = false; clearInterval(this.timer);
    try { this.an.disconnect(); } catch {}
    releaseMic();
  }
  _tick() {
    const now = performance.now();
    this.an.getFloatTimeDomainData(this.buf);
    let ms = 0; for (let i = 0; i < this.buf.length; i++) ms += this.buf[i] * this.buf[i];
    const rms = Math.sqrt(ms / this.buf.length);
    // (a new attack on the same note: the level jumps up after a dip)
    this.lv.push(rms); if (this.lv.length > 8) this.lv.shift();
    const low = Math.min(...this.lv.slice(0, -1));
    // (not in the note's own attack, just after it was written: the sound is still rising there)
    const attack = this.lv.length >= 4 && now - (this.wroteAt || 0) > 250 && rms > 0.01 && rms > low * (globalThis.__lwAttack ?? 3);
    const r = detectPitch(this.buf, this.sr, 0.003);
    const res = this.tracker.feed(r, rms, now);
    if (!res || res.held) {
      // (a real gap: the sound falls well below the note's own level, not only a moment of noise)
      const quiet = rms < Math.max(0.002, (this.peak || 0) * 0.2);
      if (!quiet) { this.quietAt = 0; return; }
      if (this.cur !== null && !this.quietAt) this.quietAt = now;
      // (silence long enough: the next note is a new one, even at the same pitch)
      if (this.quietAt && now - this.quietAt > 110) { this.cur = null; this.cand = null; }
      return;
    }
    this.quietAt = 0; this.peak = Math.max(this.peak || 0, rms);
    const midi = Math.round(69 + 12 * Math.log2(res.f / this.ref));
    if (globalThis.__lwLog) globalThis.__lwLog.push([Math.round(now), midi, +rms.toFixed(4), +(this.peak || 0).toFixed(4), this.cur, attack ? 1 : 0]);
    if (midi < 21 || midi > 108) return;
    // (a note to write is clearly heard, not a faint sound in the room)
    if (rms < (globalThis.__lwMin ?? 0.008)) return;
    if (this.cur === midi && !attack) { this.cand = null; return; }
    // (the same reading twice in a row before it is written: never a passing sound)
    if (this.cand && this.cand.midi === midi) this.cand.n++; else this.cand = { midi, n: 1 };
    // (a change of note without a gap: only while the sound is still strong — a fading low note is
    // often heard at its octave or twelfth — and a harmonic of the note needs longer)
    let need = this.cur === null ? 2 : 3;
    if (this.cur !== null && !attack) {
      if (rms < (this.peak || 0) * 0.35) return;
      const d = midi - this.cur; if (d === 12 || d === 19 || d === 24 || d === 28 || d === 31) need = 7;
    }
    if (this.cand.n >= need || (attack && this.cur === midi && this.cand.n >= 1)) {
      this.cur = midi; this.cand = null; this.lv = [rms]; this.peak = rms; this.wroteAt = now;
      try { this.onNote(midi); } catch (e) { console.warn(e); }
    }
  }
}
