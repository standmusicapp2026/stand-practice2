// The drone's ear on real playing: a recording (or cello samples), heard every 40 ms, the drone sounding into the "microphone" too.
// Returns the key changes it made.
window.__keyReal = async function ({ url, start = 0, secs = 60, key = [7, 0], drone = true, droneLevel = 0.2, sens, notes = null, reverb = 0.25, noise = 0.002 } = {}) {
  const KF = await import('/js/keyfollow.js');
  if (sens !== undefined) globalThis.__earSens = sens; else delete globalThis.__earSens;
  const sr = 44100;
  const oc = new OfflineAudioContext(1, Math.ceil(sr * (secs + 1)), sr);
  const bus = oc.createGain(); bus.connect(oc.destination);
  { const b = oc.createBuffer(1, sr * 2, sr), d = b.getChannelData(0); for (let i = 0; i < d.length; i++) d[i] = (Math.random() * 2 - 1) * noise; const h = oc.createBufferSource(); h.buffer = b; h.loop = true; h.connect(bus); h.start(0); }
  // a room: a short decaying noise as the reverb
  const room = oc.createConvolver(); { const n = Math.round(sr * 1.2), b = oc.createBuffer(1, n, sr), d = b.getChannelData(0); for (let i = 0; i < n; i++) d[i] = (Math.random() * 2 - 1) * Math.exp(-i / (sr * 0.25)); room.buffer = b; }
  const wet = oc.createGain(); wet.gain.value = reverb; room.connect(wet).connect(bus);
  const dry = oc.createGain(); dry.gain.value = 1; dry.connect(bus); dry.connect(room);
  if (url) {
    const ab = await (await fetch(url)).arrayBuffer(); const buf = await oc.decodeAudioData(ab);
    const s = oc.createBufferSource(); s.buffer = buf; s.connect(dry); s.start(0, start, secs);
  }
  if (notes) {
    // cello samples (one every 3 semitones), shifted to the note
    const cache = {};
    const get = async (m) => { const base = Math.max(33, Math.min(81, Math.round((m - 33) / 3) * 3 + 33)); if (!cache[base]) cache[base] = await oc.decodeAudioData(await (await fetch('/vendor/sounds/cello/' + base + '.mp3')).arrayBuffer()); return [cache[base], base]; };
    for (const [m, t, d, lv] of notes) {
      const [b, base] = await get(m);
      const s = oc.createBufferSource(); s.buffer = b; s.playbackRate.value = Math.pow(2, (m - base) / 12);
      const g = oc.createGain(); g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(lv || 0.7, t + 0.03); g.gain.setValueAtTime(lv || 0.7, t + d * 0.9); g.gain.linearRampToValueAtTime(0, t + d);
      s.connect(g).connect(dry); s.start(t); s.stop(t + d + 0.05);
    }
  }
  let dv = [];
  const droneOn = (k, t) => { if (!drone) return; for (const x of dv) { try { x.g.gain.setValueAtTime(x.g.gain.value, t); x.g.gain.linearRampToValueAtTime(0, t + 0.1); x.o.stop(t + 0.12); } catch {} } dv = [];
    const base = 130.81 * Math.pow(2, k.pc / 12) * (k.pc > 6 ? 0.5 : 1);
    for (const [r, lv] of [[1, droneLevel], [1.5, droneLevel * 0.7]]) { const o = oc.createOscillator(); o.type = 'triangle'; o.frequency.value = base * r; const g = oc.createGain(); g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(lv, t + 0.1); o.connect(g).connect(bus); o.start(t); dv.push({ o, g }); } };
  const an = oc.createAnalyser(); an.fftSize = 4096; an.smoothingTimeConstant = 0; bus.connect(an);
  const events = []; let now = 0;
  let cur = { pc: key[0], minor: !!key[1] };
  const kf = new KF.KeyFollower((k) => { events.push([+now.toFixed(1), k.pc + (k.minor ? 'm' : ''), globalThis.__kdbg ? JSON.stringify({ dbg: kf.dbg, r: kf.r.map((x) => +x.toFixed(2)), w: Array.from(kf.w || []).map((x) => +x.toFixed(2)) }) : '']); cur = { ...k }; droneOn(k, now + 0.02); }, () => {});
  kf.clock = () => now * 1000;
  kf.set(cur.pc, cur.minor); droneOn(cur, 0);
  kf.on = true; kf.src = bus; kf.an = an; kf.buf = new Float32Array(2048); kf.fd = new Float32Array(an.frequencyBinCount); kf.mag = new Float32Array(an.frequencyBinCount); kf._init();
  const heard = [];
  const snaps = []; for (let s = 0.04; s < secs - 0.05; s += 0.04) { const at = s; oc.suspend(at).then(() => { now = at; const on0 = kf.onsets; kf._tick(sr); if (globalThis.__noteLog && kf.onsets !== on0 && kf.recent && kf.recent.length) heard.push([+at.toFixed(2), kf.recent[kf.recent.length - 1]]); if (globalThis.__snap && Math.round(at * 25) % 50 === 0) snaps.push([Math.round(at), globalThis.__snapDbg ? JSON.stringify(kf.dbg) + ' top ' + (kf.post ? Array.from(kf.post).map((v, i) => [v, i]).sort((a, b) => b[0] - a[0]).slice(0, 3).map(([v, i]) => (['C','C#','D','Eb','E','F','F#','G','Ab','A','Bb','B'][i % 12]) + (i >= 12 ? 'm' : '') + ':' + v.toFixed(2)).join(' ') : '') : kf.h.map((x) => +x.toFixed(1)).join(' ')]); oc.resume(); }); }
  await oc.startRendering();
  return { events, snaps, heard };
};
