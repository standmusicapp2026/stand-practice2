// What Stand is playing, shown by iOS away from Stand (the lock screen, Control Center, the
// headphones' button), like a music app: "Metronome · 96 bpm" or "Drone · A" with Stand's icon,
// and a play/pause that stops what plays and starts it again where it was.
// (iOS already shows Stand's sound there, as WebKit's own "Now Playing" entry, but with nothing in
// it: this gives it a name and a picture, and its buttons (the Media Session of the page).)
import { wantAudio } from './audio.js';

const ART = [180, 192, 512].map((s) => ({ src: new URL(`icons/icon-${s}.png`, location.href).href, sizes: `${s}x${s}`, type: 'image/png' }));
// (after a pause from the lock screen the sound system is kept awake a while, so the play button
// stays there to start again; then it rests as usual)
const HOLD_MS = 10 * 60 * 1000;

export function initNowPlaying({ describe, pause, resume }) {
  const ms = typeof navigator !== 'undefined' && navigator.mediaSession;
  if (!ms || typeof MediaMetadata === 'undefined') return { update() {} };
  let paused = null, holdT = 0, last = '';
  const hold = (on) => {
    clearTimeout(holdT); holdT = 0;
    wantAudio(on, 'nowplaying');
    if (on) holdT = setTimeout(() => { wantAudio(false, 'nowplaying'); paused = null; update(); }, HOLD_MS);
  };
  function update() {
    let d = null; try { d = describe(); } catch {}
    // (something plays again, started in Stand: the pause from the lock screen is over)
    if (d && paused) { paused = null; hold(false); }
    const what = d || (paused && paused.label ? { title: paused.label, paused: true } : null);
    const key = what ? what.title + '|' + (what.paused ? 0 : 1) : '';
    if (key === last) return;
    last = key;
    try {
      if (!what) { ms.metadata = null; ms.playbackState = 'none'; return; }
      ms.metadata = new MediaMetadata({ title: what.title, artist: 'Stand', album: what.album || '', artwork: ART });
      ms.playbackState = what.paused ? 'paused' : 'playing';
    } catch {}
  }
  const act = (name, fn) => { try { ms.setActionHandler(name, fn); } catch {} };
  act('pause', () => { const p = pause(); if (p) { paused = p; hold(true); } update(); });
  act('stop', () => { const p = pause(); if (p) { paused = p; hold(true); } update(); });
  act('play', () => { const p = paused; paused = null; hold(false); if (p) resume(p); update(); });
  // (no skipping: there is nothing to skip to)
  for (const a of ['previoustrack', 'nexttrack', 'seekbackward', 'seekforward', 'seekto']) act(a, null);
  // back in Stand: the pause from the lock screen is over (the buttons on the screen are used again)
  document.addEventListener('visibilitychange', () => { if (!document.hidden && paused) { paused = null; hold(false); update(); } });
  setInterval(update, 1000);
  return { update, playing: () => !!paused };
}
