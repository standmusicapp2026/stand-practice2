// How much the listening holds the page's thread: the time of each listening step, and how late a
// timer (like a wink arriving from the iPad) runs while it listens
window.__followLoad = async function ({ pdf, first, last, audio, secs = 40 }) {
  const S = await import('/js/score.js'); const F = await import('/js/follow.js'); const L = await import('/js/listen.js');
  const data = await (await fetch(pdf)).arrayBuffer();
  const doc = await S.openDocument({ kind: 'pdf', data, id: 'real:' + pdf });
  let page = first;
  const { getCtx } = await import('/js/audio.js'); const ctx = getCtx(); await ctx.resume();
  const f = new F.PageFollower({ render: async (i, c, w) => { await doc.render(i, c, w, Math.round(w * doc.sizes[i][1] / doc.sizes[i][0])); }, pages: () => last + 1, turn: () => { page++; f.setPages(page, page); }, onState: () => {}, when: () => 0.5, fixedShift: () => 0 });
  f.setPages(first, first); await f.prepare(); f.on = true;
  const steps = [];
  const orig = L.Listener.prototype.tick;
  L.Listener.prototype.tick = function () { const t = performance.now(); const r = orig.apply(this, arguments); steps.push(performance.now() - t); return r; };
  const buf = await new Promise(async (res, rej) => ctx.decodeAudioData(await (await fetch(audio)).arrayBuffer(), res, rej));
  const bus = ctx.createGain();
  const listener = new L.Listener((o) => f._heard(o)); listener.attach(ctx, bus);
  const src = ctx.createBufferSource(); src.buffer = buf; src.connect(bus); src.start(ctx.currentTime + 0.2);
  const lates = []; let stop = false;
  (async () => { while (!stop) { const want = performance.now() + 50; await new Promise((r) => setTimeout(r, 50)); lates.push(performance.now() - want); } })();
  await new Promise((r) => setTimeout(r, secs * 1000));
  stop = true; listener.detach(); try { src.stop(); } catch {} doc.destroy(); L.Listener.prototype.tick = orig;
  const q = (a, p) => { const s = a.slice().sort((x, y) => x - y); return +s[Math.floor(p * (s.length - 1))].toFixed(1); };
  return { steps: steps.length, stepMed: q(steps, 0.5), stepP95: q(steps, 0.95), stepMax: q(steps, 1), lateMed: q(lates, 0.5), lateP95: q(lates, 0.95), lateMax: q(lates, 1), turns: page - first };
};
