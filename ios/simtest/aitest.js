// Stand AI's own self-test, run inside the real app (iOS Simulator, WKWebView) when it is started with
// -standSelfTest: the neural network loads in its thread, hears the notes of a recording, and listens
// live. Each step writes "SELFTEST ok|FAIL <step> <detail>" to the events log.
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const say = (t) => { try { window.webkit.messageHandlers.standDiag.postMessage({ op: 'log', text: String(t).slice(0, 290) }); } catch {} };
const R = { ok: 0, fail: 0 };
async function step(name, fn, ms = 120000) {
  const t0 = Date.now();
  try {
    const r = await Promise.race([fn(), sleep(ms).then(() => { throw new Error('took more than ' + ms / 1000 + ' s'); })]);
    if (r === false) throw new Error('check failed');
    R.ok++; say(`SELFTEST ok ${name} ${Date.now() - t0}ms ${typeof r === 'string' ? r : ''}`);
  } catch (e) { R.fail++; say(`SELFTEST FAIL ${name} ${(e && e.message) || e}`); }
}
(async () => {
  await sleep(4000);
  const P = await import('./ai/pitchnet.js');
  await step('AI: the network in its thread', async () => { const r = await P.netWindow(new Float32Array(P.NET_SR * 2 - 256)); return r && r.T > 100 ? `T ${r.T}` : false; });
  await step('AI: hears the notes of a recording', async () => {
    const sr = 48000, n = sr * 8, pcm = new Float32Array(n);
    for (let i = 0; i < n; i++) { const t = i / sr; pcm[i] = t < 4 ? 0.3 * Math.sin(2 * Math.PI * 220 * t) + 0.1 * Math.sin(2 * Math.PI * 440 * t) : 0.2 * Math.sin(2 * Math.PI * 554.37 * t) + 0.2 * Math.sin(2 * Math.PI * 659.26 * t); }
    const t0 = performance.now();
    const h = await P.hearNotes(pcm, sr, 0, 8, () => {});
    const top = (i) => { let b = 0; for (let k = 1; k < 88; k++) if (h.note[i * 88 + k] > h.note[i * 88 + b]) b = k; return b + 21; };
    const a = top(Math.round(P.NET_FPS * 2)), c = top(Math.round(P.NET_FPS * 6));
    const ok = a === 57 && (c === 73 || c === 76);
    if (!ok) throw new Error(`heard ${a}, ${c}`);
    return `A3 then C#5/E5 heard, ${Math.round(performance.now() - t0)} ms for 8 s`;
  });
  await step('AI: the live ear', async () => {
    const { LiveEar } = await import('./ai/liveear.js');
    const ctx = new AudioContext(); try { await ctx.resume(); } catch {}
    const osc = ctx.createOscillator(); osc.frequency.value = 196; const g = ctx.createGain(); g.gain.value = 0.3; osc.connect(g); osc.start();
    const ear = new LiveEar(); await ear.attach(ctx, g);
    await sleep(3000);
    const c = await ear.chromaAfter(performance.now() - 300);
    ear.detach(); osc.stop();
    if (!c) throw new Error(`nothing heard yet (sound ${ctx.state}; a slow simulator)`);
    let b = 0; for (let i = 1; i < 12; i++) if (c[i] > c[b]) b = i;
    if (b !== 7) throw new Error('heard pitch class ' + b);
    return `G heard (${c[7].toFixed(2)})`;
  });
  say(`SELFTEST DONE ok ${R.ok} fail ${R.fail}`);
})();
