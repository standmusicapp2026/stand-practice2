// The drone's ear, tested with real sound: melodies in a key that change key, played by a bowed
// voice (with the drone itself sounding into the "microphone" too, as on an iPad's speaker)
window.__keyEar = async function ({ seed = 1, drone = true, secs = 24, sens, noise = 0.003, plan = [[7, 0], [2, 0], [11, 1], [7, 0]] } = {}) {
  const KF = await import('/js/keyfollow.js'), SY = await import('/js/synth.js'), A = await import('/js/audio.js');
  const ctx = A.getCtx(); await ctx.resume();
  if (sens !== undefined) globalThis.__earSens = sens;
  const rnd = ((s) => () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; })(seed);
  const bus = ctx.createGain(); bus.gain.value = 1;
  const hiss = ctx.createBufferSource(); { const b = ctx.createBuffer(1, ctx.sampleRate * 2, ctx.sampleRate); const d = b.getChannelData(0); for (let i = 0; i < d.length; i++) d[i] = (Math.random() * 2 - 1) * noise; hiss.buffer = b; hiss.loop = true; hiss.connect(bus); hiss.start(); }
  const events = []; let dKey = { pc: plan[0][0], minor: !!plan[0][1] }, dv = null;
  const droneOn = (k) => { if (!drone) return; const t = ctx.currentTime; if (dv) dv.forEach((v) => v.stop(t, 0.1)); const f = 440 * Math.pow(2, ((k.pc + 3) % 12 - 9 + 12 * -1) / 12 + 0); const base = 130.81 * Math.pow(2, k.pc / 12); dv = [SY.holdNote(bus, base, 'organ', 0.5, t + 0.02, 0.1), SY.holdNote(bus, base * 1.5, 'organ', 0.35, t + 0.02, 0.1)]; void f; };
  const t0 = performance.now();
  const kf = new KF.KeyFollower((k) => { events.push({ t: (performance.now() - t0) / 1000, pc: k.pc, minor: k.minor }); dKey = { ...k }; droneOn(k); }, () => {});
  kf.set(dKey.pc, dKey.minor); droneOn(dKey);
  kf.on = true; kf._wire(bus);
  // the music: per section, a melody of the key (tonic triad more often, mostly steps), eighths and quarters
  const MAJ = [0, 2, 4, 5, 7, 9, 11], MIN = [0, 2, 3, 5, 7, 8, 10, 11];
  let t = ctx.currentTime + 0.3; const beat = 60 / 100;
  const bounds = [];
  plan.forEach(([pc, minor], si) => {
    const sc = minor ? MIN : MAJ; bounds.push({ at: si * secs, pc, minor: !!minor });
    let deg = 0; const end = t + secs;
    while (t < end) {
      const r = rnd(); deg += r < 0.35 ? 1 : r < 0.7 ? -1 : r < 0.8 ? 2 : r < 0.9 ? -2 : 0;
      if (rnd() < 0.15) deg = [0, 2, 4][Math.floor(rnd() * 3)] * (minor ? 1 : 1);
      deg = Math.max(-5, Math.min(9, deg));
      const oct = Math.floor(deg / sc.length), idx = ((deg % sc.length) + sc.length) % sc.length;
      let semis = sc[idx] + 12 * oct;
      if (minor && sc[idx] === 11 && rnd() < 0.5) semis -= 1;
      const midi = 55 + pc + semis - (pc > 6 ? 12 : 0);
      const d = (rnd() < 0.55 ? 0.5 : 1) * beat;
      SY.playNote(bus, 440 * Math.pow(2, (midi - 69) / 12), t, d * 0.92, 'bow', 0.8);
      t += d;
    }
  });
  const total = plan.length * secs;
  await new Promise((r) => setTimeout(r, (total + 1) * 1000));
  clearInterval(kf.timer); kf.on = false; try { bus.disconnect(); hiss.stop(); } catch {} if (dv) dv.forEach((v) => v.stop(ctx.currentTime, 0.05));
  // judge: each change found (delay), wrong moves
  const res = [];
  for (let i = 1; i < bounds.length; i++) {
    const b = bounds[i], end = i + 1 < bounds.length ? bounds[i + 1].at : total;
    const hit = events.find((e) => e.t >= b.at && e.t < end && e.pc === b.pc && e.minor === b.minor);
    res.push(hit ? +(hit.t - b.at).toFixed(1) : null);
  }
  const wrong = events.filter((e) => { const b = [...bounds].reverse().find((q) => q.at <= e.t); return !(b && b.pc === e.pc && b.minor === e.minor); }).map((e) => [+e.t.toFixed(1), e.pc + (e.minor ? 'm' : '')]);
  return { seed, drone, delays: res, wrong, events: events.map((e) => [+e.t.toFixed(1), e.pc + (e.minor ? 'm' : '')]) };
};
