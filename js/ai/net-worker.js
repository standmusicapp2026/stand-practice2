// The AI's neural network in a thread of its own: the score, the drawing and the sound never wait for
// it. (A classic worker: TensorFlow.js comes as plain scripts.)
// In:  { id, op: 'load' }                       -> { id, ok, backend }
//      { id, op: 'run', x: Float32Array (22 050 Hz) } -> progress { id, p }, then { id, n, note, onset }
//      { id, op: 'win', x: Float32Array (two seconds) } -> { id, T, fr, on }
// Out on failure: { id, error }
/* global tf, importScripts */
const NET_SR = 22050, NET_HOP = 256, NET_FPS = NET_SR / NET_HOP, NET_KEYS = 88;
const WIN = NET_SR * 2 - NET_HOP, OVER = 30, HALF = OVER / 2, STEP = WIN - OVER * NET_HOP;
const base = new URL('../../vendor/', self.location.href).href;
let ready = null, model = null, backend = null;
function load() {
  if (ready) return ready;
  ready = (async () => {
    importScripts(base + 'tf/tf.min.js');
    try {
      importScripts(base + 'tf/tf-backend-wasm.min.js');
      tf.wasm.setWasmPaths(base + 'tf/');
      if (await tf.setBackend('wasm')) backend = 'wasm';
    } catch (e) { backend = null; }
    if (!backend) { try { if (await tf.setBackend('webgl')) backend = 'webgl'; } catch (e) { backend = null; } }
    if (!backend) { await tf.setBackend('cpu'); backend = 'cpu'; }
    await tf.ready();
    model = await tf.loadGraphModel(base + 'basicpitch/model.json');
    return backend;
  })();
  ready.catch(() => { ready = null; });
  return ready;
}
// (the same as runNet in pitchnet.js)
async function runNet(x, id) {
  const n = Math.floor((x.length * NET_FPS) / NET_SR);
  const nWin = Math.ceil((n * NET_HOP) / STEP) + 1;
  const P0 = Math.floor((OVER * NET_HOP) / 2);
  const padded = new Float32Array(nWin * STEP + WIN);
  padded.set(x, P0);
  const note = new Float32Array(n * NET_KEYS), onset = new Float32Array(n * NET_KEYS), filled = new Uint8Array(n);
  const BATCH = 4;
  let done = 0;
  for (let w = 0; w < nWin; w += BATCH) {
    const k = Math.min(BATCH, nWin - w);
    const buf = new Float32Array(k * WIN);
    for (let q = 0; q < k; q++) buf.set(padded.subarray((w + q) * STEP, (w + q) * STEP + WIN), q * WIN);
    const inp = tf.tensor3d(buf, [k, WIN, 1]);
    const outs = model.execute(inp, ['Identity_1', 'Identity_2']);
    const [fr, on] = await Promise.all([outs[0].data(), outs[1].data()]);
    const T = outs[0].shape[1];
    inp.dispose(); outs.forEach((o) => o.dispose());
    for (let q = 0; q < k; q++) {
      const s0 = (w + q) * STEP - P0;
      for (let f = HALF; f < T - HALF; f++) {
        const i = Math.round((s0 + f * NET_HOP) / NET_HOP);
        if (i < 0 || i >= n || filled[i]) continue;
        const src = (q * T + f) * NET_KEYS;
        note.set(fr.subarray(src, src + NET_KEYS), i * NET_KEYS);
        onset.set(on.subarray(src, src + NET_KEYS), i * NET_KEYS);
        filled[i] = 1;
      }
    }
    done += k;
    self.postMessage({ id, p: Math.min(1, done / nWin) });
  }
  for (let i = 1; i < n; i++) if (!filled[i]) { note.copyWithin(i * NET_KEYS, (i - 1) * NET_KEYS, i * NET_KEYS); onset.copyWithin(i * NET_KEYS, (i - 1) * NET_KEYS, i * NET_KEYS); }
  return { n, note, onset };
}
self.onmessage = async (e) => {
  const { id, op, x } = e.data || {};
  try {
    const b = await load();
    if (op === 'load') { self.postMessage({ id, ok: true, backend: b }); return; }
    if (op === 'run') {
      const r = await runNet(x, id);
      self.postMessage({ id, n: r.n, note: r.note, onset: r.onset }, [r.note.buffer, r.onset.buffer]);
      return;
    }
    if (op === 'win') {
      const inp = tf.tensor3d(x, [1, WIN, 1]);
      const outs = model.execute(inp, ['Identity_1', 'Identity_2']);
      const [fr0, on0] = await Promise.all([outs[0].data(), outs[1].data()]);
      const T = outs[0].shape[1];
      const fr = Float32Array.from(fr0), on = Float32Array.from(on0);
      inp.dispose(); outs.forEach((o) => o.dispose());
      self.postMessage({ id, T, fr, on }, [fr.buffer, on.buffer]);
      return;
    }
    self.postMessage({ id, error: 'unknown op' });
  } catch (err) {
    self.postMessage({ id, error: String((err && err.message) || err) });
  }
};
