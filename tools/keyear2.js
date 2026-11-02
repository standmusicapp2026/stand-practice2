// The drone's ear tested fast: the sound made offline (an OfflineAudioContext), heard every 40 ms
// of its own time; melodies in keys that change, and the drone sounding into the "microphone" too.
window.__keyEar2 = async function ({ seed = 1, drone = true, secs = 24, sens, noise = 0.003, plan = [[7, 0], [2, 0], [11, 1], [7, 0]], tempo = 100, droneLevel = 0.25, style = 'melody' } = {}) {
  const KF = await import('/js/keyfollow.js');
  if (sens !== undefined) globalThis.__earSens = sens; else delete globalThis.__earSens;
  const sr = 44100, total = plan.length * secs + 1;
  const oc = new OfflineAudioContext(1, Math.ceil(sr * total), sr);
  const rnd = ((s) => () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; })(seed);
  const bus = oc.createGain(); bus.connect(oc.destination);
  { const b = oc.createBuffer(1, sr * 2, sr), d = b.getChannelData(0); for (let i = 0; i < d.length; i++) d[i] = (Math.random() * 2 - 1) * noise; const h = oc.createBufferSource(); h.buffer = b; h.loop = true; h.connect(bus); h.start(0); }
  // a bowed note: sawtooth, softened, a little vibrato
  const note = (midi, t, d, lv = 0.25) => {
    const o = oc.createOscillator(); o.type = 'sawtooth'; o.frequency.value = 440 * Math.pow(2, (midi - 69) / 12);
    const v = oc.createOscillator(); v.frequency.value = 5.5; const vg = oc.createGain(); vg.gain.value = o.frequency.value * 0.006; v.connect(vg).connect(o.frequency);
    const lp = oc.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 2400;
    const g = oc.createGain(); g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(lv, t + 0.04); g.gain.setValueAtTime(lv, t + d * 0.85); g.gain.linearRampToValueAtTime(0, t + d * 0.95);
    o.connect(lp).connect(g).connect(bus); o.start(t); o.stop(t + d); v.start(t); v.stop(t + d);
  };
  let dv = [];
  const droneOn = (k, t) => { if (!drone) return; for (const x of dv) { try { x.g.gain.setValueAtTime(x.g.gain.value, t); x.g.gain.linearRampToValueAtTime(0, t + 0.1); x.o.stop(t + 0.12); } catch {} } dv = [];
    const base = 130.81 * Math.pow(2, k.pc / 12) * (k.pc > 6 ? 0.5 : 1);
    for (const [r, lv] of [[1, droneLevel], [1.5, droneLevel * 0.7]]) { const o = oc.createOscillator(); o.type = 'triangle'; o.frequency.value = base * r; const g = oc.createGain(); g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(lv, t + 0.1); o.connect(g).connect(bus); o.start(t); dv.push({ o, g }); } };
  // the music
  const MAJ = [0, 2, 4, 5, 7, 9, 11], MIN = [0, 2, 3, 5, 7, 8, 10, 11];
  const sched = []; let t = 0.3; const beat = 60 / tempo; const bounds = [];
  plan.forEach(([pc, minor], si) => {
    const sc = minor ? MIN : MAJ; bounds.push({ at: si * secs, pc, minor: !!minor });
    let deg = 0; const end = si * secs + secs + 0.3;
    while (t < end - 0.05) {
      const r = rnd(); deg += r < 0.35 ? 1 : r < 0.7 ? -1 : r < 0.8 ? 2 : r < 0.9 ? -2 : 0;
      if (rnd() < 0.15) deg = [0, 2, 4][Math.floor(rnd() * 3)] + (minor ? 0 : 0);
      deg = Math.max(-5, Math.min(9, deg));
      const L = sc.length, oct = Math.floor(deg / L), idx = ((deg % L) + L) % L;
      let semis = sc[idx] + 12 * oct;
      if (minor && sc[idx] === 11 && rnd() < 0.5) semis -= 1;   // raised or natural 7th
      const midi = 48 + pc + (pc < 5 ? 12 : 0) + semis;
      const d = (rnd() < 0.55 ? 0.5 : 1) * beat;
      note(midi, t, d * 0.95); sched.push([t, d * 0.95, midi]);
      t += d;
    }
  });
  // the ear, hearing the offline sound every 40 ms of its time
  const an = oc.createAnalyser(); an.fftSize = 4096; an.smoothingTimeConstant = 0; bus.connect(an);
  const events = []; let now = 0; const trace = [];
  let cur = { pc: plan[0][0], minor: !!plan[0][1] };
  const kf = new KF.KeyFollower((k) => { events.push({ t: now, pc: k.pc, minor: k.minor }); cur = { ...k }; droneOn(k, now + 0.02); }, () => {});
  kf.clock = () => now * 1000; const det = []; if (globalThis.__det) { const P = kf._pitch.bind(kf); kf._pitch = (r, s2) => { const x = P(r, s2); det.push([now, x && x.midi, x && +x.clarity.toFixed(1)]); return x; }; }
  kf.set(cur.pc, cur.minor); droneOn(cur, 0);
  kf.on = true; kf.src = bus; kf.an = an; kf.buf = new Float32Array(2048); kf.fd = new Float32Array(an.frequencyBinCount); kf.mag = new Float32Array(an.frequencyBinCount); kf._init();
  for (let s = 0.04; s < total - 0.05; s += 0.04) { const at = s; oc.suspend(at).then(() => { now = at; kf._tick(sr); if (globalThis.__trace && Math.round(at * 25) % 50 === 0) trace.push([+at.toFixed(0), kf.dbg && kf.dbg.best, kf.dbg && kf.dbg.prob, kf.h.map(x=>+x.toFixed(1)).join(' ')]); oc.resume(); }); }
  await oc.startRendering();
  const res = [];
  for (let i = 1; i < bounds.length; i++) {
    const b = bounds[i], end = i + 1 < bounds.length ? bounds[i + 1].at : total;
    const hit = events.find((e) => e.t >= b.at && e.t < end && e.pc === b.pc && e.minor === b.minor);
    res.push(hit ? +(hit.t - b.at).toFixed(1) : null);
  }
  const wrong = events.filter((e) => { const b = [...bounds].reverse().find((q) => q.at <= e.t); return !(b && b.pc === e.pc && b.minor === e.minor); }).map((e) => [+e.t.toFixed(1), e.pc + (e.minor ? 'm' : '')]);
  return { seed, drone, delays: res, wrong, pcs: globalThis.__pcs ? [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23].map((q) => sched.filter((x) => x[0] >= q * 4 && x[0] < q * 4 + 4).map((x) => x[2] % 12).join(",")) : undefined, trace: globalThis.__trace ? trace : undefined, conf: globalThis.__det ? (() => { let ok = 0, oct = 0, bad = 0, none = 0, low = 0; const m = {}; for (const [tt, mi, cl] of det) { const n = sched.find((q) => tt - 0.06 >= q[0] && tt < q[0] + q[1]); if (!n) continue; if (mi == null) { none++; continue; } if (cl <= 6) { low++; continue; } if (mi === n[2]) ok++; else if ((mi - n[2]) % 12 === 0) oct++; else { bad++; const k = ((mi - n[2]) % 12 + 12) % 12; m[k] = (m[k] || 0) + 1; } } return { ok, oct, bad, none, low, m }; })() : undefined };
};
