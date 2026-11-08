// One shared AudioContext and one shared microphone for the whole app.
let ctx = null;
let masterGain = null;
// what happened to the sound lately (shown in Settings › Sound, to tell what went wrong)
export const audioLog = [];
export function alog(what) { audioLog.push({ t: Date.now(), what, state: ctx ? ctx.state : '-', sr: ctx ? ctx.sampleRate : 0 }); if (audioLog.length > 40) audioLog.shift(); }
if (typeof window !== 'undefined') window.__audioLog = audioLog;
// while recording, the sound system is never replaced (the take would go silent): only woken
let holding = 0;
export function holdSound(on) { holding = Math.max(0, holding + (on ? 1 : -1)); }

// What kind of sound Stand makes, said to iOS. Without it, the web view's sound counts as
// "ambient": with the iPad or iPhone in silent mode the speaker stays quiet (Bluetooth headphones
// still play), until the microphone opens and the sound becomes play-and-record. So it is said in
// the app too: playback (the silent switch does not mute it), or play-and-record while the
// microphone is open, or when the sound is kept on the iPad's speaker (that choice exists only there).
function setSession(type) {
  try {
    if (!navigator.audioSession) return;
    if (type === 'playback' && window.standCaps && window.standCaps.native && window.__standSpeaker) type = 'play-and-record';
    if (navigator.audioSession.type !== type) navigator.audioSession.type = type;
  } catch { /* not supported */ }
}
// said again (the speaker choice changed): the kind of sound for what is going on now
export function applySession() { setSession(micStream ? 'play-and-record' : 'playback'); }

// When the sound goes somewhere else (Bluetooth headphones connected or gone), or the microphone
// was used and let go, iOS can leave the sound system running with its clock ticking and nothing
// reaching the ears. That cannot be seen from here, so the sound system is then marked stale, and
// the next drone, metronome or scale started with a tap gets a new one (freshSound), as long as
// nothing else is playing in the old one.
let stale = false;
// (when the sound system was interrupted, by a call, Siri, an alarm; and when iOS said it ended)
let intrAt = 0, endedAt = 0, intrHealed = false;
export function getCtx() {
  if (!ctx) {
    const AC = window.AudioContext || window.webkitAudioContext;
    ctx = new AC({ latencyHint: 'interactive' });
    alog('new sound system');
    // (a sound system this slow: Bluetooth headphones in their call mode, the sound poor)
    if (ctx.sampleRate <= 24000 && typeof window !== 'undefined') setTimeout(() => window.dispatchEvent(new Event('stand-audio-callmode')), 0);
    masterGain = ctx.createGain();
    masterGain.gain.value = 1;
    // Gentle safety limiter so stacked sounds never clip harshly.
    const comp = ctx.createDynamicsCompressor();
    comp.threshold.value = -3; comp.knee.value = 6; comp.ratio.value = 12; comp.attack.value = 0.002; comp.release.value = 0.1;
    masterGain.connect(comp).connect(ctx.destination);
    // Play through the speaker even when the iPad's silent switch is on (play-and-record while the
    // microphone is open: a new sound system then must not take it away)
    setSession(micStream ? 'play-and-record' : 'playback');
    const c0 = ctx;
    c0.addEventListener('statechange', () => {
      if (c0 !== ctx) return;
      alog('now ' + c0.state + (c0.__ours ? ' (by Stand)' : ''));
      // (replaced once for an interruption; again only after sound has come back in between)
      if (c0.state === 'interrupted') { if (!intrAt) intrAt = performance.now(); } else if (c0.state === 'running') { intrAt = 0; intrHealed = false; }
      // Pause and play away from Stand (the lock screen, Control Center, the headphones' button):
      // iOS pauses the sound system itself, or starts it again. Not woken up then (as after an
      // interruption): told to what plays, which stops — or starts again where it was.
      if (c0.state === 'running') { c0.__ran = true; c0.__ours = false; }
      if (pausedOutside(c0)) return;
      playedOutside(c0);
      if (wantSound && c0.state !== 'running' && !remotePaused) c0.resume().catch(() => {});
    });
  }
  // (asked for: it will sound now, so it does not rest; see "battery" below)
  lastSound = performance.now(); if (restingCtx === ctx) restingCtx = null;
  // (not when it was paused from the lock screen: then what plays stops instead)
  if (ctx.state === 'running') { ctx.__ran = true; ctx.__ours = false; }
  if (ctx.state !== 'running' && !pausedOutside(ctx) && !remotePaused) ctx.resume().catch(() => {});
  return ctx;
}
export function freshSound() {
  // (spoilt by the microphone opening: replaced even while it listens; it is connected again)
  if (!ctx || !stale || (wantSound && !staleByMic) || (micUsers > 0 && !staleByMic) || holding || ctx.state === 'closed') return;
  alog('fresh (was stale)');
  stale = false; staleByMic = false;
  const old = ctx; ctx = null;
  try { old.close(); } catch {}
  lastReplace = performance.now();
  const n = getCtx();
  if (micStream) { try { micSource = n.createMediaStreamSource(micStream); } catch { micStream = null; micSource = null; } }
  window.dispatchEvent(new Event('stand-audio-new'));
}
// The microphone opening (or closing) moves the sound to another way out on iOS, and the sound
// system playing then can go quiet, or come out of the iPhone's earpiece instead of its speaker.
// So, once for each opening and closing (never because of a new sound system itself, which keeps
// the microphone open): what plays gets a new sound system; else the next sound started does.
let staleByMic = false;
function afterMicChange(what) {
  window.dispatchEvent(new Event('stand-mic-changed'));   // (the way out is said again: speaker or Bluetooth)
  if (!ctx) return;
  stale = true; staleByMic = true;
  if (!wantSound || holding) return;
  setTimeout(() => {
    if (!staleByMic || holding || !ctx) return;
    alog('renewed after the microphone ' + what);
    freshSound();
  }, 700);
}
export function markStale() { if (ctx) stale = true; }
// The camera's own microphone (video recording through the web view) changes how iOS sends the
// sound out just as the microphone does: said here too, so the sound that plays afterwards (a
// video played back, the metronome) is never left silent. While the camera records, the sound
// system is kept, never replaced (recording: holdSound).
let camMic = false;
export function cameraMic(on) {
  if (on === camMic) return;
  camMic = on; micChangedAt = performance.now();
  alog('camera microphone ' + (on ? 'open' : 'closed'));
  setSession(on || micStream ? 'play-and-record' : 'playback');
  afterMicChange(on ? 'opened' : 'closed');
}
// The metronome, the drone and scales ask for sound to keep coming: an interruption (a call, a
// lock, the mic starting) is then undone at once. Each asks for itself, so one stopping never
// leaves another without its watch.
const wanting = new Set();
// (pause/play from outside Stand: its own pauses and wakes are told apart from those of iOS)
let ourSuspendAt = -1e9, ourResumeAt = -1e9, remotePaused = false;
const remoteFns = [];
function remote(what) { for (const f of remoteFns) { try { f(what); } catch (e) { console.warn(e); } } }
export function onRemote(f) { remoteFns.push(f); }
export function setRemotePaused(b) { remotePaused = !!b; }
// Paused from outside Stand (iOS, from the lock screen)? Asked before anything wakes the sound: then
// it is not woken, and what plays is told to stop (once). Also: started again from outside?
export function pausedOutside(c = ctx) {
  // (only a sound system that was playing and that Stand did not pause itself)
  if (!c || c.state !== 'suspended' || !c.__ran || c.__ours || remotePaused || !wantSound) return false;
  alog('paused from outside Stand'); c.__outside = true; remotePaused = true; remote('pause'); return true;
}
export function playedOutside(c = ctx) {
  if (!c || !c.__outside || c.state !== 'running') return false;
  c.__outside = false;
  if (!remotePaused) return false;
  alog('played from outside Stand'); remote('play'); return true;
}
// (every pause and wake asked for by Stand itself goes through these)
if (typeof window !== 'undefined' && window.AudioContext) {
  const AP = window.AudioContext.prototype, sus0 = AP.suspend, res0 = AP.resume;
  if (sus0) AP.suspend = function (...a) { ourSuspendAt = performance.now(); this.__ours = true; return sus0.apply(this, a); };
  // (paused from outside: nothing wakes it by itself — a touch, coming back, a check — until play is
  // pressed or something is started in Stand)
  if (res0) AP.resume = function (...a) {
    if (remotePaused && this.__outside) { alog('not woken (paused from outside Stand)'); return Promise.resolve(); }
    // (a pause of Stand's own not yet taken effect is undone; one that has stays Stand's until it plays)
    ourResumeAt = performance.now(); this.__outside = false; if (this.state === 'running') this.__ours = false; return res0.apply(this, a); };
  window.__standOutside = { pause: (c) => sus0.call(c), play: (c) => res0.call(c) };   // (tests: as iOS does)
}
let wantSound = false;
export function wantAudio(on, who = 'metro') {
  // (something asked to sound: whatever was paused from the lock screen is over)
  if (on && who !== 'nowplaying') remotePaused = false;
  if (on) wanting.add(who); else wanting.delete(who);
  wantSound = wanting.size > 0;
  if (on) { getCtx(); watch(); }
}
// While sound is wanted (or the microphone is open), once a second: is the sound system awake and
// is its clock moving? If not, wake it, or rebuild it (healAudio). Nothing runs when idle.
let watchT = 0, lastClock = -1, stuckFor = 0;
function watch() {
  if (watchT) return;
  watchT = setInterval(() => {
    if (!wantSound && micUsers === 0) { clearInterval(watchT); watchT = 0; lastClock = -1; stuckFor = 0; return; }
    if (document.hidden || !ctx) return;
    if (remotePaused || pausedOutside()) return;
    // (interrupted: a call or Siri has the sound, and it comes back by itself when they end; but
    // the microphone opening or closing also leaves it "interrupted", and that never ends by itself.
    // So: replaced once that interruption has lasted a few seconds, and only once for it, never
    // again and again)
    if (ctx.state !== 'running') {
      ctx.resume().catch(() => {});
      if (ctx.state === 'interrupted' && !intrAt) intrAt = performance.now();
      if (ctx.state === 'closed' || (ctx.state === 'interrupted' && intrStuck())) healAudio('watch');
      return;
    }
    const t = ctx.currentTime;
    stuckFor = t === lastClock ? stuckFor + 1 : 0;
    lastClock = t;
    if (stuckFor >= 2) { stuckFor = 0; healAudio('stuck'); }
  }, 1000);
}

export function master() { getCtx(); return masterGain; }

// Sound must really be running before a metronome or a tuner starts. iOS can leave the sound
// system suspended (the first tap of the day) or "interrupted" (after a call, Siri, or when the
// microphone opens). Wake it; if it will not wake, make a new one (the old one is dead).
export async function ensureRunning(timeout = 500, { force = false } = {}) {
  const c = getCtx();
  if (c.state === 'running') return c;
  try { await Promise.race([c.resume(), new Promise((r) => setTimeout(r, timeout))]); } catch {}
  if (c.state === 'running') return c;
  // only a broken sound system is replaced, and not over and over: a merely suspended one just
  // waits for the next touch (iOS allows only a few sound systems; making more breaks sound until
  // Stand is closed)
  if (holding || !mayReplace(c, false, force)) return c;
  alog('replaced: would not wake');
  try { c.close(); } catch {}
  ctx = null;
  const n = getCtx();
  // anyone using the microphone hears it again through the new sound system
  if (micStream) { try { micSource = n.createMediaStreamSource(micStream); } catch {} }
  try { await Promise.race([n.resume(), new Promise((r) => setTimeout(r, timeout))]); } catch {}
  window.dispatchEvent(new Event('stand-audio-new'));
  return n;
}
// After Stand was in the background, after a call, or when iOS restarted its audio, the sound
// system can look alive and play nothing, and the microphone can be dead. Check both, and rebuild
// what is broken; everyone using sound (metronome, drone, tuner…) hears 'stand-audio-new' or
// 'stand-mic-lost' and carries on by itself. No need to close Stand any more.
let healing = null, lastReplace = -1e9;
// an interruption that will not end by itself: lasted a few seconds, or iOS said it ended, or it
// came with the microphone opening or closing; and not replaced for already
function intrStuck() {
  if (intrHealed || !intrAt) return false;
  const now = performance.now();
  return now - intrAt > 4000 || (endedAt > intrAt && now - endedAt > 1500) || (now - micChangedAt < 6000 && now - intrAt > 900);
}
function mayReplace(c, clockStuck = false, force = false) {
  // (force: started with a tap, and the sound system will not wake: a new one is made at once)
  if (performance.now() - lastReplace < (force ? 1500 : 5000)) return false;
  // (interrupted: a tap asking for sound replaces it; on its own, only once per interruption)
  if (c.state === 'interrupted' && !intrAt) intrAt = performance.now();
  const deadIntr = c.state === 'interrupted' && (force || intrStuck());
  if (deadIntr) intrHealed = true;
  const broken = deadIntr || c.state === 'closed' || (c.state === 'running' && clockStuck) || (force && c.state === 'suspended');
  if (!broken) return false;
  lastReplace = performance.now();
  return true;
}
const clockMoves = async (c, ms = 260) => { const t0 = c.currentTime; await new Promise((r) => setTimeout(r, ms)); return c.currentTime > t0; };
export function healAudio(reason = '') {
  if (healing) return healing;
  healing = (async () => {
    if (micStream && micStream.getAudioTracks().some((t) => t.readyState !== 'live')) {
      micStream = null; micSource = null;
      window.dispatchEvent(new Event('stand-mic-lost'));
    }
    if (!ctx) return;
    const inUse = wantSound || micUsers > 0;
    // (never more than one new sound system every few seconds, whatever asks: a storm of them
    // left iOS with no sound at all; and never while recording)
    if (reason === 'reset' && (holding || performance.now() - lastReplace < 2500)) { reason = 'check'; }
    if (reason !== 'reset') {
      try { await Promise.race([ctx.resume(), new Promise((r) => setTimeout(r, 600))]); } catch {}
      const moving = ctx.state === 'running' && await clockMoves(ctx);
      if (moving) return;
      if (!inUse) return;          // nothing is playing: it wakes on the next touch
      if (!mayReplace(ctx, ctx.state === 'running')) return;   // suspended: the next touch wakes it
    } else lastReplace = performance.now();
    if (holding) { alog('kept (recording)'); return; }
    alog('replaced: ' + reason);
    // dead: a new sound system, and the microphone connected to it
    try { ctx.close(); } catch {}
    ctx = null;
    const n = getCtx();
    if (micStream) { try { micSource = n.createMediaStreamSource(micStream); } catch { micStream = null; micSource = null; } }
    try { await Promise.race([n.resume(), new Promise((r) => setTimeout(r, 600))]); } catch {}
    window.dispatchEvent(new Event('stand-audio-new'));
    if (!micSource && micUsers > 0) window.dispatchEvent(new Event('stand-mic-lost'));
    intrAt = 0;
  })().finally(() => { healing = null; });
  return healing;
}
// the sound went somewhere else (told by the app around Stand, or seen as a device change)
// The microphone opening or closing changes the route itself: that is not a new device, and the
// sound system that is playing is only checked then, never replaced (replacing it each time made
// a chain: a new sound system, the tuner listening again, the route changing again…).
let routeT = 0, micChangedAt = -1e9;
export function routeChanged(reason = 'route') {
  clearTimeout(routeT);
  routeT = setTimeout(() => {
    if (!ctx) return;
    const ours = performance.now() - micChangedAt < 3000;
    alog('route: ' + reason + (ours ? ' (the microphone)' : ''));
    if (ours) { healAudio('check'); return; }
    if (wantSound || micUsers > 0) { stale = false; healAudio('reset'); }
    else stale = true;
  }, 450);
}
// Settings › Sound: a new sound system now, by hand
export function resetSound() {
  alog('reset by hand');
  lastReplace = -1e9; stale = false;
  if (!ctx) { getCtx(); return Promise.resolve(); }
  if (!wantSound && micUsers === 0 && !holding) { try { ctx.close(); } catch {} ctx = null; getCtx(); window.dispatchEvent(new Event('stand-audio-new')); return Promise.resolve(); }
  return healAudio('reset');
}
if (typeof window !== 'undefined') {
  window.standAudioWake = (reason) => {
    const r = String(reason || '').toLowerCase();
    if (/\b(ended|end|interruption ?ended)\b/.test(r) || /interruptionended|ended$/.test(r)) endedAt = performance.now();
    // an interruption that has ended, a reset of the sound services or a new route: replace it
    if (/route|reset|servic|\bended\b|\bend\b|change|device|bluetooth|headphone|new/.test(r)) routeChanged(r);
    else healAudio(reason);
  };
  try { navigator.mediaDevices && navigator.mediaDevices.addEventListener && navigator.mediaDevices.addEventListener('devicechange', () => { if (performance.now() - micAskedAt > 4000) routeChanged('device'); }); } catch {}
  document.addEventListener('visibilitychange', () => { if (!document.hidden) setTimeout(() => healAudio('visible'), 400); });
  window.addEventListener('pageshow', () => setTimeout(() => healAudio('visible'), 400));
}
// The first touch anywhere wakes the sound (iOS only allows it inside a touch), and so does
// coming back to the app.
if (typeof document !== 'undefined') {
  const wake = () => { if (ctx && ctx.state !== 'running') ctx.resume().catch(() => {}); };
  document.addEventListener('pointerdown', wake, true);
  document.addEventListener('touchend', wake, true);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) wake(); });
}

// ---------- battery: the sound system rests when nothing has sounded for a while ----------
// A sound system left running keeps the iPad's and iPhone's sound hardware working all the time,
// even silent (after the tuner or the metronome was used once, for the whole session). So, when
// nothing plays or listens for 30 s it is paused; anything that makes a sound wakes it at once
// (getCtx, a sound started, a video or recording played through it, a touch).
// Never paused while: the metronome, drone or scales want sound, the microphone is open, a
// recording holds it, a sound started has not ended (a sound never stopped keeps it awake), or a
// video or recording connected to it is playing.
const IDLE_MS = 30000;
const playing = new WeakMap();      // sound system -> sounds started and not ended
const mediaEls = new Set();         // videos and recordings played through it
let lastSound = typeof performance !== 'undefined' ? performance.now() : 0, restingCtx = null;
function rouse() {
  lastSound = performance.now();
  // (a sound started in Stand after a pause from outside: that pause is over)
  if (remotePaused) { remotePaused = false; alog('started again in Stand'); }
  if (restingCtx && restingCtx === ctx) { restingCtx = null; alog('awake again'); }
  if (ctx && ctx.state === 'suspended') ctx.resume().catch(() => {});
}
function soundBusy() {
  if (wantSound || micUsers > 0 || holding || micPending) return true;
  if (ctx && (playing.get(ctx) || 0) > 0) return true;
  for (const m of mediaEls) { if (!m.isConnected && m.paused) { mediaEls.delete(m); continue; } if (!m.paused && !m.ended) return true; }
  return false;
}
if (typeof window !== 'undefined' && window.AudioScheduledSourceNode && window.AudioContext) {
  const P = window.AudioScheduledSourceNode.prototype, start0 = P.start;
  P.start = function (...a) {
    const c = this.context;
    // (only the live sound system: sounds made offline, for a file, are not counted)
    if (c && c === ctx) {
      playing.set(c, (playing.get(c) || 0) + 1);
      let done = false;
      this.addEventListener('ended', () => { if (done) return; done = true; playing.set(c, Math.max(0, (playing.get(c) || 0) - 1)); lastSound = performance.now(); });
      rouse();
    }
    return start0.apply(this, a);
  };
  const AC = window.AudioContext.prototype, mes0 = AC.createMediaElementSource;
  if (mes0) AC.createMediaElementSource = function (m) {
    const n = mes0.call(this, m);
    try { if (!mediaEls.has(m)) { mediaEls.add(m); m.addEventListener('play', rouse); m.addEventListener('playing', rouse); } } catch {}
    return n;
  };
  setInterval(() => {
    if (!ctx || ctx.state !== 'running') return;
    if (soundBusy()) { lastSound = performance.now(); return; }
    // (away from Stand, nothing playing: it rests at once, see below)
    if (document.hidden) { restAway(); return; }
    if (performance.now() - lastSound < IDLE_MS) return;
    restingCtx = ctx; alog('resting (nothing played for 30 s)');
    ctx.suspend().catch(() => {});
  }, 5000);
  document.addEventListener('pointerdown', () => { if (restingCtx) rouse(); }, true);
  // Stand left (home screen, another app, the screen locked) with nothing playing or listening:
  // the sound system rests at once and the app lets go of the iPad's sound, so iOS stops showing
  // Stand as playing. A metronome, drone or recording that is going keeps going; when it stops
  // while Stand is away, the next check (5 s) lets go then. Coming back wakes it as before.
  document.addEventListener('visibilitychange', () => { if (document.hidden) setTimeout(restAway, 1200); });
}
function restAway() {
  if (!document.hidden || !ctx || ctx.state !== 'running' || soundBusy()) return;
  const c = ctx; restingCtx = c; alog('resting (Stand in the background, nothing playing)');
  window.__standRested = (window.__standRested || 0) + 1;
  c.suspend().then(() => {
    if (!document.hidden || ctx !== c || c.state !== 'suspended') return;
    try { const h = window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.standAudio; if (h) h.postMessage({ rest: true }); } catch {}
  }, () => {});
}

// Call from a user gesture; iOS needs a sound to start inside a tap.
export function unlock() {
  const c = getCtx();
  const b = c.createBuffer(1, 1, c.sampleRate);
  const s = c.createBufferSource(); s.buffer = b; s.connect(c.destination); s.start();
}

let micStream = null, micSource = null, micUsers = 0, micPending = null, micAskedAt = -1e9;

export async function acquireMic() {
  const c = getCtx();
  micUsers++; watch();
  // a microphone that iOS stopped while Stand was away is opened afresh
  if (micStream && micStream.getAudioTracks().some((t) => t.readyState !== 'live')) { micStream = null; micSource = null; }
  if (micSource && micSource.context !== c) { try { micSource = c.createMediaStreamSource(micStream); } catch { micStream = null; micSource = null; } }
  if (micSource) return micSource;
  if (!micPending) {
    setSession('play-and-record'); micAskedAt = performance.now(); micChangedAt = micAskedAt; alog('microphone opening');
    micPending = navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false, channelCount: 1 },
    }).then((stream) => preferBuiltIn(stream)).then((stream) => {
      micStream = stream;
      micSource = c.createMediaStreamSource(stream);
      afterMicChange('opened');
      // iOS can take the microphone away (a call, Siri, another app): forget it, so the next one
      // to ask opens it afresh, and tell everyone listening
      for (const t of stream.getAudioTracks()) t.addEventListener('ended', () => {
        if (micStream !== stream) return;
        micStream = null; micSource = null;
        window.dispatchEvent(new Event('stand-mic-lost'));
      });
      return micSource;
    }).catch((e) => { micUsers = 0; setSession('playback'); throw e; })
      .finally(() => { micPending = null; });
  }
  return micPending;
}

// With Bluetooth headphones on, the sound goes to them, and the microphone should stay the iPad's
// (or iPhone's) own: it hears the instrument, and the headphones keep their full sound. If iOS
// opened another microphone, the built-in one is asked for instead.
const BUILT_IN = /iphone|ipad|built[- ]?in|integr|intern|eingebaut/i;
async function preferBuiltIn(stream) {
  try {
    const tr = stream.getAudioTracks()[0];
    if (!tr || BUILT_IN.test(tr.label || '')) return stream;
    const devs = await navigator.mediaDevices.enumerateDevices();
    const own = devs.find((d) => d.kind === 'audioinput' && BUILT_IN.test(d.label || ''));
    if (!own || (tr.getSettings && tr.getSettings().deviceId === own.deviceId)) return stream;
    const s2 = await navigator.mediaDevices.getUserMedia({ audio: { deviceId: { exact: own.deviceId }, echoCancellation: false, noiseSuppression: false, autoGainControl: false, channelCount: 1 } });
    stream.getTracks().forEach((t) => t.stop());
    return s2;
  } catch { return stream; }
}
export function releaseMic() {
  micUsers = Math.max(0, micUsers - 1);
  if (micUsers === 0 && micStream) {
    micChangedAt = performance.now(); alog('microphone closed');
    micStream.getTracks().forEach((t) => t.stop());
    try { micSource.disconnect(); } catch {}
    micStream = null; micSource = null;
    setSession('playback');
    // the iPhone changes how sound goes out while the microphone is open: start afresh
    afterMicChange('closed');
  }
}

export function micErrorText(e) {
  if (!navigator.mediaDevices) return 'This browser cannot use the microphone. Open Stand in Safari.';
  if (e && (e.name === 'NotAllowedError' || e.name === 'SecurityError')) return (window.standCaps && window.standCaps.native) ? 'Microphone access is off. Allow it in the iPad’s Settings › Stand › Microphone, then try again.' : 'Microphone access is off. Allow it in Settings › Safari › Microphone, then try again.';
  if (e && e.name === 'NotFoundError') return 'No microphone was found.';
  return 'The microphone could not start. Try again.';
}
// (something sounds or listens now: the screen is kept on for it)
export const soundActive = () => soundBusy();
// (tests: the sound system's state, without waking it)
export const _soundState = () => (ctx ? ctx.state : '-');
export const _soundClock = () => (ctx ? ctx.currentTime : -1);
