// Turning pages by listening, with a real recording and a real score: the pages of the PDF read as
// the app reads them, the recording played into the listener in real time.
window.__readPages = async function ({ pdf, pages, w = 1600, h = 2263 }) {
  const S = await import('/js/score.js'); const R = await import('/js/follow-read.js');
  const data = await (await fetch(pdf)).arrayBuffer();
  const doc = await S.openDocument({ kind: 'pdf', data, id: 'real:' + pdf });
  const out = [];
  for (const i of pages) { const c = document.createElement('canvas'); const [pw, ph] = doc.sizes[i]; await doc.render(i, c, w, Math.round(w * ph / pw)); const r = await R.readPage(c); out.push({ i, seq: r.seq.map((e) => ({ pcs: e.pcs, bar: e.bar, sys: e.sys })), at: r.at, bars: r.bars, solo: r.solo ? r.solo.map((e) => ({ pcs: e.pcs, bar: e.bar, sys: e.sys })) : null, soloAt: r.soloAt }); c.width = c.height = 0; }
  doc.destroy();
  return out;
};
window.__followReal = async function ({ pdf, first, last, audio, when = 0.5, gain = 1, noise = 0.002, from = 0, shift = 0 }) {
  const S = await import('/js/score.js'); const F = await import('/js/follow.js'); const L = await import('/js/listen.js');
  const data = await (await fetch(pdf)).arrayBuffer();
  const doc = await S.openDocument({ kind: 'pdf', data, id: 'real:' + pdf });
  let page = first; const turns = []; const trace = [];
  const { getCtx } = await import('/js/audio.js'); const ctx = getCtx(); await ctx.resume();
  let t0 = 0;
  const f = new F.PageFollower({
    render: async (i, c, w, h) => { await doc.render(i, c, w, Math.round(w * doc.sizes[i][1] / doc.sizes[i][0])); },
    pages: () => last + 1,
    turn: () => { turns.push([+(ctx.currentTime - t0).toFixed(2), (window.__followDbg || []).slice(-14)]); page++; f.setPages(page, page); },
    onState: (txt) => { trace.push([+(ctx.currentTime - t0).toFixed(1), txt]); },
    when: () => when,
    fixedShift: () => shift,
  });
  f.setPages(first, first); await f.prepare(); f.on = true; window.__followDbg = [];
  const buf = await new Promise(async (res, rej) => ctx.decodeAudioData(await (await fetch(audio)).arrayBuffer(), res, rej));
  const bus = ctx.createGain(); bus.gain.value = gain;
  const hiss = ctx.createBufferSource(); { const b = ctx.createBuffer(1, ctx.sampleRate * 2, ctx.sampleRate); const d = b.getChannelData(0); for (let i = 0; i < d.length; i++) d[i] = (Math.random() * 2 - 1) * noise; hiss.buffer = b; hiss.loop = true; hiss.connect(bus); hiss.start(); }
  const listener = new L.Listener((o) => f._heard(o)); listener.attach(ctx, bus);
  const src = ctx.createBufferSource(); src.buffer = buf; src.connect(bus);
  t0 = ctx.currentTime + 0.3 - from; src.start(ctx.currentTime + 0.3, from);
  while (ctx.currentTime - t0 < buf.duration + 0.5 && page <= last) await new Promise((r) => setTimeout(r, 200));
  listener.detach(); hiss.stop(); try { src.stop(); } catch {} bus.disconnect(); doc.destroy();
  return { turns, trace: trace.filter((x, i, a) => i === 0 || x[1] !== a[i - 1][1]) };
};
