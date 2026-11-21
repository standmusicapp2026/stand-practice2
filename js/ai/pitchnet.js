// On-device AI: a neural network that hears which notes sound, moment by moment.
//
// The network is Spotify's "Basic Pitch" (Apache 2.0): a small model (under 1 MB) trained on many
// instruments and voices, solo and together. For every 11.6 ms of a recording it says, for each of
// the 88 piano keys, how likely that note is sounding ("note") and how likely it is beginning
// ("onset"). It runs here, inside Stand, with TensorFlow.js — no internet, no account, nothing sent.
//
// Used by Studio (the score following a video), and by the live listener.

export const NET_SR = 22050;               // the network hears at 22 050 Hz
export const NET_HOP = 256;                // one frame every 256 samples (86.13 frames a second)
export const NET_FPS = NET_SR / NET_HOP;
export const NET_LO = 21, NET_KEYS = 88;   // A0 .. C8
const WIN = NET_SR * 2 - NET_HOP;          // the network takes two seconds at a time
const OVER = 30;                           // frames shared by neighbouring windows (half dropped each side)
const HALF = OVER / 2;
const STEP = WIN - OVER * NET_HOP;

let loading = null;
let state = null;   // { tf, model, backend }

function addScript(src) {
  return new Promise((res, rej) => {
    const s = document.createElement('script');
    s.src = src; s.async = true;
    s.onload = () => res(); s.onerror = () => rej(new Error('could not load ' + src));
    document.head.appendChild(s);
  });
}

// (for the tests outside the app: the network already loaded)
export function setNet(s) { state = s; }
// Loads TensorFlow.js and the network (once). Returns { tf, model, backend } or throws.
export function loadNet() {
  if (state) return Promise.resolve(state);
  if (loading) return loading;
  loading = (async () => {
    const base = new URL('vendor/', document.baseURI).href;
    if (!globalThis.tf) await addScript(base + 'tf/tf.min.js');
    const tf = globalThis.tf;
    let backend = null;
    // WebAssembly first (exact, steady, fast on every iPad); the graphics chip next; plain JavaScript last
    try {
      if (!tf.wasm) await addScript(base + 'tf/tf-backend-wasm.min.js');
      tf.wasm.setWasmPaths(base + 'tf/');
      if (await tf.setBackend('wasm')) backend = 'wasm';
    } catch (e) { console.warn('AI: wasm', e); }
    if (!backend) { try { if (await tf.setBackend('webgl')) backend = 'webgl'; } catch (e) { console.warn('AI: webgl', e); } }
    if (!backend) { await tf.setBackend('cpu'); backend = 'cpu'; }
    await tf.ready();
    const model = await tf.loadGraphModel(base + 'basicpitch/model.json');
    state = { tf, model, backend };
    return state;
  })();
  loading.catch(() => { loading = null; });
  return loading;
}

// A mono recording brought to 22 050 Hz (low-pass first, so nothing folds back).
export function resample(pcm, sr, a = 0, b = Infinity) {
  const i0 = Math.max(0, Math.floor(a * sr)), i1 = Math.min(pcm.length, Math.floor(Math.min(b, pcm.length / sr) * sr));
  const src = pcm.subarray(i0, i1);
  if (Math.abs(sr - NET_SR) < 1) return Float32Array.from(src);
  const ratio = sr / NET_SR, n = Math.floor(src.length / ratio), out = new Float32Array(n);
  const cut = Math.min(1, 1 / ratio) * 0.94, TAPS = 16;
  // (a windowed sinc evaluated at each output sample's place in the original)
  for (let i = 0; i < n; i++) {
    const c = i * ratio, k0 = Math.floor(c);
    let s = 0, wsum = 0;
    for (let k = k0 - TAPS + 1; k <= k0 + TAPS; k++) {
      if (k < 0 || k >= src.length) continue;
      const x = k - c, w = 0.5 + 0.5 * Math.cos((Math.PI * x) / (TAPS + 1));
      const v = x === 0 ? cut : Math.sin(Math.PI * cut * x) / (Math.PI * x);
      s += src[k] * v * w; wsum += v * w;
    }
    out[i] = wsum ? s / wsum : 0;
  }
  return out;
}

// Runs the network over audio at 22 050 Hz. Returns { n, note, onset } (n frames x 88 keys, row by
// row, values 0..1). Works with any TensorFlow.js (also used by the tests outside the app).
export async function runNet(tf, model, x, onProgress, stop) {
  const n = Math.floor((x.length * NET_FPS) / NET_SR);
  // (each window gives the frames of its middle; the first window starts half an overlap early)
  const nWin = Math.ceil((n * NET_HOP) / STEP) + 1;
  const P0 = Math.floor((OVER * NET_HOP) / 2);
  const padded = new Float32Array(nWin * STEP + WIN);
  padded.set(x, P0);
  const starts = []; for (let w = 0; w < nWin; w++) starts.push(w * STEP);
  const note = new Float32Array(n * NET_KEYS), onset = new Float32Array(n * NET_KEYS), filled = new Uint8Array(n);
  let at = 0;
  const BATCH = 4;
  for (let w = 0; w < starts.length && at < n; w += BATCH) {
    const k = Math.min(BATCH, starts.length - w);
    const buf = new Float32Array(k * WIN);
    for (let q = 0; q < k; q++) buf.set(padded.subarray(starts[w + q], starts[w + q] + WIN), q * WIN);
    const inp = tf.tensor3d(buf, [k, WIN, 1]);
    const outs = model.execute(inp, ['Identity_1', 'Identity_2']);
    const [fr, on] = await Promise.all([outs[0].data(), outs[1].data()]);
    const T = outs[0].shape[1];
    inp.dispose(); outs.forEach((o) => o.dispose());
    // (each frame put at its own moment: a window is 171.3 frames long, not a whole number, so frames
    // taken one after another would drift — half a second over a few minutes)
    for (let q = 0; q < k; q++) {
      const s0 = starts[w + q] - P0;
      for (let f = HALF; f < T - HALF; f++) {
        const i = Math.round((s0 + f * NET_HOP) / NET_HOP);
        if (i < 0 || i >= n || filled[i]) continue;
        const src = (q * T + f) * NET_KEYS;
        note.set(fr.subarray(src, src + NET_KEYS), i * NET_KEYS);
        onset.set(on.subarray(src, src + NET_KEYS), i * NET_KEYS);
        filled[i] = 1; if (i + 1 > at) at = i + 1;
      }
    }
    onProgress && onProgress(Math.min(1, at / n));
    await new Promise((r) => setTimeout(r, 0));
    if (stop && stop()) return null;
  }
  // (a frame no window gave: the one before it)
  for (let i = 1; i < n; i++) if (!filled[i]) { note.copyWithin(i * NET_KEYS, (i - 1) * NET_KEYS, i * NET_KEYS); onset.copyWithin(i * NET_KEYS, (i - 1) * NET_KEYS, i * NET_KEYS); }
  return { n, note, onset };
}

// The notes heard in a recording (from a to b seconds), with the frames' loudness.
// Returns { t0, fps, n, note, onset, rms } or null if the network cannot run here.
const cache = new WeakMap();
export async function hearNotes(pcm, sr, a, b, onProgress, stop) {
  const key = `${sr}|${a.toFixed(3)}|${b.toFixed(3)}`;
  const c = cache.get(pcm); if (c && c.key === key) return c.res;
  const { tf, model } = await loadNet();
  const x = resample(pcm, sr, a, b);
  const r = await runNet(tf, model, x, onProgress, stop);
  if (!r) return null;
  const rms = new Float32Array(r.n);
  for (let i = 0; i < r.n; i++) {
    const s0 = Math.max(0, i * NET_HOP - NET_HOP), s1 = Math.min(x.length, i * NET_HOP + 2 * NET_HOP);
    let m = 0; for (let j = s0; j < s1; j++) m += x[j] * x[j];
    rms[i] = Math.sqrt(m / Math.max(1, s1 - s0));
  }
  const res = { t0: Math.max(0, a), fps: NET_FPS, n: r.n, note: r.note, onset: r.onset, rms };
  cache.set(pcm, { key, res });
  return res;
}

export function netAvailable() {
  try { return typeof WebAssembly === 'object' || !!document.createElement('canvas').getContext('webgl2'); } catch { return false; }
}
