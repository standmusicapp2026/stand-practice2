// Studio: put the score on a recording, the way musicians share playing on Instagram.
// Draw around the music in a score; Stand finds the bars, lays them out as one line and moves
// along with your playing: it listens to the recording, reads the notes on the page and lines
// them up. Three looks (white paper, warm paper, or just the lines and notes with the video
// showing through), any size and place on the picture, images, trimming, vertical or square
// formats, and an export that is saved in Recordings and ready to share.
import { db, uid } from './db.js';
import { getCtx, wantAudio } from './audio.js';
import { detectPitch } from './tuner.js';
import { analyse, staffEvents } from './omr.js';
import { makeImpulse, ROOMS, computePeaks, peakOf, encodeWav } from './recorder.js';
import { videoThumb } from './video.js';
import { CLEFS, keyAlter, midiOf } from './compose/model.js';
import { onsetsOf, template, cosine, chromaOf, fftMag } from './listen.js';
import { Grader, LOOKS, lookParams, isNeutral, autoLook } from './grade.js';
const grader = new Grader();

const $ = (s) => document.querySelector(s);
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; };
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const fmt = (s) => { s = Math.max(0, s); const m = Math.floor(s / 60), r = s - m * 60; return m + ':' + r.toFixed(1).padStart(4, '0'); };
const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

let D = {};
const ST = { take: null, P: null, media: null, url: null, pcm: null, sr: 48000, raf: 0, sel: null, strips: new Map(), images: new Map(), dur: 1, tapping: null, busy: null };
const FORMATS = { '9:16': [1080, 1920, 'Reels'], '4:5': [1080, 1350, 'Post'], '1:1': [1080, 1080, 'Square'], '16:9': [1920, 1080, 'Wide'], orig: [0, 0, 'Original'] };

export function initStudio(deps) {
  D = deps;
  wire();
}

// =====================================================================
// Opening and saving
// =====================================================================
export async function openStudio(takeId) {
  const take = await db.get('takes', takeId);
  if (!take) { D.toast('That recording could not be opened.'); return; }
  ST.take = take;
  const saved = await db.get('files', 'studio:' + takeId);
  ST.P = saved ? saved.data : { takeId, format: take.kind === 'video' ? '9:16' : '1:1', fit: 'fill', pan: { x: 0.5, y: 0.5 }, bg: '#14171f', overlays: [], trim: null, sound: { room: D.room ? D.room() : 'studio', wet: D.wet ? D.wet() : 0.18, level: true } };
  ST.strips.clear(); ST.images.clear();
  // media element: the video itself, or the recording as a sound file
  if (ST.url) URL.revokeObjectURL(ST.url);
  const af = await db.get('files', 'audio:' + takeId);
  ST.pcm = af ? af.data : null; ST.sr = take.sr || 48000;
  if (take.kind === 'video') {
    const vf = await db.get('files', 'video:' + takeId);
    if (!vf) { D.toast('That video could not be opened.'); return; }
    ST.url = URL.createObjectURL(vf.data);
    const v = document.createElement('video'); v.playsInline = true; v.preload = 'auto'; v.src = ST.url; v.muted = false;
    ST.media = v;
  } else {
    if (!ST.pcm) { D.toast('That recording could not be opened.'); return; }
    ST.url = URL.createObjectURL(encodeWav([ST.pcm], ST.sr));
    const a = document.createElement('audio'); a.preload = 'auto'; a.src = ST.url;
    ST.media = a;
  }
  await new Promise((res) => { ST.media.onloadedmetadata = res; ST.media.onerror = res; setTimeout(res, 4000); });
  ST.dur = isFinite(ST.media.duration) && ST.media.duration > 0 ? ST.media.duration : (take.dur || 1);
  if (!ST.P.trim) ST.P.trim = { a: 0, b: ST.dur };
  ST.P.trim.b = Math.min(ST.P.trim.b, ST.dur);
  for (const o of ST.P.overlays) await prepareOverlay(o);
  $('#studio').hidden = false; document.body.classList.add('in-studio');
  $('#stTitle').textContent = take.name || 'Studio';
  ST.sel = ST.P.overlays.find((o) => o.kind === 'score') ? { id: ST.P.overlays.find((o) => o.kind === 'score').id } : null;
  ST.media.currentTime = ST.P.trim.a;
  // (a picture of the first frame to show, and to draw the looks with)
  if (ST.media.readyState < 2) await new Promise((res) => { const done = () => { ST.media.removeEventListener('loadeddata', done); ST.media.removeEventListener('seeked', done); res(); }; ST.media.addEventListener('loadeddata', done); ST.media.addEventListener('seeked', done); setTimeout(done, 2500); });
  ST.tv = null; sizeCanvas(); renderSide(); renderTimeline(); drawWave(); frame();
  makeStrip();
  ST.media.addEventListener('seeked', () => frame());
  ST.media.addEventListener('ended', () => { ST.playing = false; syncPlay(); lsStop(); });
  // the sound heard as it will be in the video (room, level): played alongside the picture
  ST.pk = ST.pcm ? peakOf(ST.pcm) : 1; LS.buf = null;
  ST.media.addEventListener('playing', () => lsStart());
  ST.media.addEventListener('pause', () => lsStop());
  ST.media.addEventListener('seeked', () => { if (!ST.media.paused) lsStart(); });
}
// ---------- the sound while you watch, with the Sound settings ----------
// The recording's own sound is played by the sound system (with the room and the level chosen),
// in step with the picture, which plays silent; before, the picture's own sound played and the
// settings were only heard in the finished video.
const LS = { ctx: null, src: null, buf: null, irs: new Map() };
function lsGraph() {
  const ctx = getCtx();
  if (LS.ctx !== ctx) {
    LS.ctx = ctx; LS.buf = null; LS.irs.clear();
    LS.level = ctx.createGain(); LS.dry = ctx.createGain(); LS.conv = ctx.createConvolver(); LS.wet = ctx.createGain();
    LS.level.connect(LS.dry).connect(ctx.destination);
    LS.level.connect(LS.conv).connect(LS.wet).connect(ctx.destination);
  }
  lsApply();
  return ctx;
}
function lsApply() {
  if (!LS.ctx || !ST.P) return;
  const t = LS.ctx.currentTime, S = ST.P.sound || {};
  LS.level.gain.setTargetAtTime(S.level !== false && ST.pk > 0.001 ? Math.min(8, 0.89 / ST.pk) : 1, t, 0.03);
  const room = ROOMS[S.room];
  if (room) {
    if (!LS.irs.has(S.room)) LS.irs.set(S.room, makeImpulse(LS.ctx, room));
    if (LS.conv.buffer !== LS.irs.get(S.room)) LS.conv.buffer = LS.irs.get(S.room);
  }
  LS.wet.gain.setTargetAtTime(room ? (S.wet ?? 0.18) * 0.9 : 0, t, 0.03);
}
function lsStop() {
  if (LS.src) { const s = LS.src; LS.src = null; try { s.onended = null; s.stop(); } catch {} }
  wantAudio(false, 'studio');
}
function lsStart() {
  lsStop();
  const m = ST.media;
  if (!m || m.paused || ST.exporting || !ST.pcm) return;
  // (very long recordings: their own sound, as before; the copy for the sound system would be too big)
  if (ST.pcm.length > ST.sr * 60 * 15) { m.muted = false; return; }
  const ctx = lsGraph();
  if (!LS.buf || LS.buf.sampleRate !== ST.sr || LS.bufFor !== ST.pcm) { LS.buf = ctx.createBuffer(1, Math.max(1, ST.pcm.length), ST.sr); LS.buf.copyToChannel(ST.pcm, 0); LS.bufFor = ST.pcm; }
  m.muted = true;
  const src = ctx.createBufferSource(); src.buffer = LS.buf; src.playbackRate.value = m.playbackRate || 1; src.connect(LS.level);
  const at = Math.max(0, Math.min(LS.buf.duration - 0.01, m.currentTime));
  const when = ctx.currentTime + 0.01; src.start(when, at);
  LS.src = src; LS.c0 = when; LS.m0 = at;
  wantAudio(true, 'studio');
}
// (called every frame while playing: the sound kept with the picture)
function lsKeep() {
  if (!LS.src || !ST.media || ST.media.paused || LS.ctx !== getCtx()) { if (LS.src && LS.ctx !== getCtx()) lsStart(); return; }
  const heard = LS.m0 + (LS.ctx.currentTime - LS.c0) * (ST.media.playbackRate || 1);
  if (Math.abs(heard - ST.media.currentTime) > 0.12 && !ST.media.seeking) lsStart();
}
async function save() {
  if (!ST.P) return;
  await db.put('files', { id: 'studio:' + ST.take.id, data: ST.P });
}
let saveT; function saveSoon() { clearTimeout(saveT); saveT = setTimeout(save, 600); }
function close() {
  pause(); lsStop(); save();
  $('#studio').hidden = true; document.body.classList.remove('in-studio');
  if (ST.media) { ST.media.removeAttribute('src'); ST.media.load(); }
  if (ST.url) URL.revokeObjectURL(ST.url); ST.url = null;
  for (const s of ST.strips.values()) { s.canvas.width = 0; if (s.mask) s.mask.width = 0; }
  ST.strips.clear();
}

// =====================================================================
// The score: from the drawn region to a line of bars
// =====================================================================
// (second: another part on a line of its own under the first — a duet, two clarinets — each line
// following its own player)
async function addScore(opt = {}) {
  const second = opt === true || !!(opt && opt.second);
  pause();
  // (drawn bigger than for the page: the music is shown large on the video, and must stay sharp)
  const hi = /iPhone|iPod/.test(navigator.userAgent) ? 2600 : 3400;
  const region = await D.pickRegion(null, null, { title: second ? 'Choose the same bars in the other part' : 'Choose the lines you play in this video', long: hi });
  if (!region) return;
  busy('Reading the score…', 'Finding the staves and the bars.', 0.2);
  try {
    const A = await analyse(region.canvas);
    if (!A.staves.length) { busy(null); D.toast('No staves found there. Draw a little wider than the music, around whole lines.', 5000); return; }
    const blob = await new Promise((res) => region.canvas.toBlob(res, 'image/png'));
    const o = {
      id: uid(), kind: 'score', title: region.source && region.source.title || 'Score', src: { scoreId: region.source && region.source.scoreId, page: region.page, box: region.box },
      img: blob, look: 'paper', ink: '#ffffff', mode: 'scroll', band: true, perView: { '9:16': 2, '4:5': 2, '1:1': 3 }[ST.P.format] || 4, size: ST.P.format === '9:16' || ST.P.format === '4:5' ? 0.96 : 0.9, pos: { x: 0.5, y: ST.P.format === '16:9' ? 0.8 : 0.78 }, opacity: 1, highlight: true,
      layout: stripLayout(A, region.canvas.width, region.canvas.height), times: null, synced: 'even',
    };
    if (!o.layout.bars.length) { busy(null); D.toast('No bars found there.', 4000); return; }
    o.times = evenTimes(o.layout.bars.length);
    putScore(o, second);
    await prepareOverlay(o);
    ST.sel = { id: o.id };
    busy(null);
    stackLines();
    saveSoon(); renderSide(); renderTimeline(); frame();
    // line it up with the playing straight away
    if (ST.pcm) { if (second && scoreLines().length === 2) syncBoth(); else autoSync(o); }
    else D.toast(`${o.layout.bars.length} bars. Use Sync › Tap along to line them up with the video.`, 4500);
  } catch (err) { console.error(err); busy(null); D.toast('That part of the score could not be read.'); }
}
// The score's lines on the video: one, or two (a part on each). A second line looks like the first
// (the same paper, size and way of moving: one system of two staves) and sits right under it.
const scoreLines = () => ST.P.overlays.filter((x) => x.kind === 'score');
const SHARED = ['look', 'ink', 'shade', 'mode', 'band', 'perView', 'size', 'opacity', 'highlight'];
function putScore(o, second) {
  const first = scoreLines()[0];
  if (second && first) {
    for (const k of SHARED) if (first[k] !== undefined) o[k] = first[k];
    o.line = 2; first.line = 1;
    // (never more than two: a second line replaces the second line)
    ST.P.overlays = ST.P.overlays.filter((x) => x.kind !== 'score' || x === first);
    ST.P.overlays.splice(ST.P.overlays.indexOf(first) + 1, 0, o);
  } else {
    ST.P.overlays = ST.P.overlays.filter((x) => x.kind !== 'score');   // a new score: on its own
    ST.P.overlays.unshift(o);
  }
}
// the second line right under the first (moved up together when there is no room below)
function stackLines() {
  const [a, b] = scoreLines(); if (!a || !b) return;
  frame();
  const A = a._box, B = b._box; if (!A || !B || !A.H) return;
  const ha = A.h / A.H, hb = B.h / B.H, gap = 0.004;
  let ya = a.pos.y;
  if (ya + ha / 2 + gap + hb > 1) ya = 1 - hb - gap - ha / 2;
  if (ya - ha / 2 < 0) ya = ha / 2;
  a.pos = { x: a.pos.x, y: ya }; b.pos = { x: a.pos.x, y: ya + ha / 2 + gap + hb / 2 };
  frame();
}
// Two lines with the same bars (two parts of one piece): drawn on one grid, each bar as wide as the
// wider of the two, so bar 10 of one part stands right over bar 10 of the other, and the page moves
// for both together. (Not when the bars differ in number: then each line goes its own way.)
function jointOf(o) {
  const ls = scoreLines(); if (ls.length !== 2 || !ls.includes(o)) return null;
  const [a, b] = ls, n = a.layout.bars.length;
  if (n !== b.layout.bars.length || a.mode !== 'scroll' || b.mode !== 'scroll' || !a.times || !b.times) return null;
  const hOf = (L) => { const hs = L.segs.map((s) => s.h).sort((p, q) => p - q); return hs[hs.length >> 1] || L.height; };
  const rb = hOf(a.layout) / hOf(b.layout);           // the second line's pixels in the first one's
  const key = `${a.id}|${b.id}|${n}|${a.layout.width}|${b.layout.width}`;
  let J = ST._joint;
  if (!J || J.key !== key) {
    const cw = a.layout.bars.map((q, k) => Math.max(q.x1 - q.x0, (b.layout.bars[k].x1 - b.layout.bars[k].x0) * rb));
    const cx = []; let s = 0; for (const w2 of cw) { cx.push(s); s += w2; }
    J = ST._joint = { key, cw, cx, width: s };
  }
  J.r = (x) => (x === b ? rb : 1);
  // a place in a line (its own pixels, in bar k) on the shared grid
  J.toCommon = (x, pos, k) => { const q = x.layout.bars[k]; return J.cx[k] + clamp((pos - q.x0) / Math.max(1, q.x1 - q.x0), 0, 1) * J.cw[k]; };
  // where both are at time t, by the first line's bars (evenly through each bar: the page glides)
  const at = (t) => { const { b: k, f } = barAt(a, t); return k < 0 ? 0 : k >= n ? J.width : J.cx[k] + f * J.cw[k]; };
  J.viewAt = (t) => { const T = a.times, ts = [], xs = []; for (let k = 0; k <= n; k++) { ts.push(T[k]); xs.push(k < n ? J.cx[k] : J.width); } return glide(ts, xs, t); };
  void at;
  return J;
}
// a change to how a line looks: both lines, so the two read as one system
function sharedChange(o, fn) { const ls = scoreLines(); for (const x of ls.length > 1 && ls.includes(o) ? ls : [o]) fn(x); }
// Bars in reading order: each system cut at its barlines; later systems without their clef.
function stripLayout(A, W, H) {
  const sp = A.sp;
  const segs = [], bars = [], notes = [], events = [];
  let sx = 0;
  // every note of a staff as sounding pitch classes, with the clef and key as they change along the
  // line and the accidentals carried through the bar (as the score follower reads them)
  const pcsOf = (st, k, n) => {
    const clef0 = CLEFS[st.clef] ? st.clef : k > 0 && n === 2 ? 'bass' : 'treble';
    const bars = staffEvents(st); let key = st.key || 0; const out = [];
    bars.forEach((b, bi) => {
      if (bars.meta && bars.meta[bi] && bars.meta[bi].key !== undefined) key = bars.meta[bi].key;
      for (const it of b) {
        if (it.rest) continue;
        const bottom = (CLEFS[it.clef] || CLEFS[clef0]).bottom;
        out.push({ x: it.x, pcs: it.ps.map((q) => { const s2 = bottom + q; const a = it.acc && it.acc[q] !== undefined ? it.acc[q] : keyAlter(key, s2); return ((midiOf(s2, a) % 12) + 12) % 12; }) });
      }
    });
    return out;
  };
  A.systems.forEach((sys, si) => {
    const sts = sys.map((i) => A.staves[i]);
    const evAll = sts.map((st, k) => pcsOf(st, k, sts.length));
    const top = clamp(Math.min(...sts.map((s) => s.top)) - sp * 3.6, 0, H), bot = clamp(Math.max(...sts.map((s) => s.bottom)) + sp * 3.6, 0, H);
    const s0 = sts[0];
    const firstHead = s0.heads.length ? Math.min(...s0.heads.map((h) => h.x)) : s0.x0 + sp * 4;
    let x0 = si === 0 ? Math.max(0, s0.x0 - sp * 0.5) : Math.max(s0.x0, firstHead - sp * 1.6);
    const x1 = Math.min(W, s0.x1 + sp * 0.4);
    const lines = s0.bars.map((b) => b.x).filter((x) => x > x0 + sp * 1.2 && x < x1 - sp * 1.2).sort((a, b) => a - b);
    // a barline right at the start belongs to the previous line
    const cuts = [x0, ...lines, x1];
    const seg = { x: x0, y: top, w: x1 - x0, h: bot - top, sx, staff: s0.top - top, sX0: Math.max(0, s0.x0 - x0), sX1: Math.min(x1 - x0, s0.x1 - x0), sys: si };
    segs.push(seg);
    for (let k = 0; k < cuts.length - 1; k++) {
      const a = cuts[k], b = cuts[k + 1];
      if (b - a < sp * 1.5) continue;
      const bi = bars.length;
      bars.push({ x0: sx + (a - x0), x1: sx + (b - x0), seg: segs.length - 1 });
      // the notes of this bar (top staff), for following the playing
      const inBar = s0.heads.filter((h) => h.x >= a && h.x < b).sort((p, q) => p.x - q.x);
      const groups = [];
      for (const h of inBar) { const g = groups[groups.length - 1]; if (g && Math.abs(g.x - h.x) < sp * 0.5) g.ps.push({ p: h.p, acc: h.acc }); else groups.push({ x: h.x, ps: [{ p: h.p, acc: h.acc }] }); }
      for (const g of groups) notes.push({ bar: bi, x: sx + (g.x - x0), ps: g.ps });
      // every staff of the line together, as sounding pitch classes (for chords and the piano)
      const here = [];
      evAll.forEach((evs) => {
        for (const e of evs) if (e.x >= a && e.x < b) {
          const g = here.find((q) => Math.abs(q.x - e.x) < sp * 0.7);
          if (g) { for (const pc of e.pcs) if (!g.pcs.includes(pc)) g.pcs.push(pc); } else here.push({ x: e.x, pcs: [...e.pcs] });
        }
      });
      here.sort((p2, q) => p2.x - q.x);
      for (const g of here) events.push({ bar: bi, x: sx + (g.x - x0), pcs: g.pcs });
    }
    sx += x1 - x0 + sp * 1.2;
  });
  // every line of music sits at the same height in the strip
  const above = Math.max(...segs.map((s) => s.staff)), below = Math.max(...segs.map((s) => s.h - s.staff));
  for (const s of segs) s.dy = above - s.staff;
  // (each staff's lines along it, and the line of music it belongs to: for laying each line straight
  // and keeping with it the slurs and marks that belong to it, wherever they reach)
  const sysOf = new Map(); A.systems.forEach((sys, si) => sys.forEach((i) => sysOf.set(i, si)));
  const staffs = A.staves.every((st) => st.edge) ? A.staves.map((st, i) => ({ sys: sysOf.has(i) ? sysOf.get(i) : -1, sp: st.sp, top: st.top, bottom: st.bottom, edge: st.edge })) : null;
  return { segs, bars, notes, events, width: sx - sp * 1.2, height: above + below, sp, clef: A.staves[0].clef, key: A.staves[0].key, staffs, v: staffs ? 2 : 1 };
}
function evenTimes(n) {
  const a = ST.P.trim.a + 0.4, b = ST.P.trim.b - 0.2;
  return Array.from({ length: n + 1 }, (_, i) => a + ((b - a) * i) / n);
}
// The picture of the bars as one long line, plus a see-through version (just the ink).
async function prepareOverlay(o) {
  if (o.kind === 'image') {
    const bmp = await createImageBitmap(o.img).catch(() => null);
    if (bmp) ST.images.set(o.id, bmp);
    return;
  }
  const bmp = await createImageBitmap(o.img);
  const L = o.layout;
  if (L.staffs && L.segs.every((q) => q.sys !== undefined)) {
    try { const st = straightStrip(L, bmp); bmp.close && bmp.close(); ST.strips.set(o.id, st); return; }
    catch (e) { console.warn('straight strip', e); }
  }
  const c = document.createElement('canvas'); c.width = Math.ceil(L.width); c.height = Math.ceil(L.height);
  const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height);
  for (const s of L.segs) g.drawImage(bmp, s.x, s.y, s.w, s.h, s.sx, s.dy ?? (c.height - s.h) / 2, s.w, s.h);
  bmp.close && bmp.close();
  // join the lines: the staff runs on through the gaps, so it reads as one endless line
  if (L.sp && L.segs.length > 1) {
    const s0 = L.segs[0], top = (s0.dy ?? 0) + s0.staff;
    g.fillStyle = '#1a1a1a';
    const th = Math.max(1, L.sp * 0.1);
    for (let i = 0; i + 1 < L.segs.length; i++) {
      const A = L.segs[i], B = L.segs[i + 1];
      const xa = A.sx + (A.sX1 ?? A.w) - 1, xb = B.sx + (B.sX0 ?? 0) + 1;
      if (A.sX1 !== undefined) g.fillStyle = '#fff', g.fillRect(xa + 2, (A.dy ?? 0), B.sx + (B.sX0 ?? 0) - xa - 2, c.height), g.fillStyle = '#1a1a1a';
      for (let k = 0; k < 5; k++) g.fillRect(xa, Math.round(top + k * L.sp - th / 2), xb - xa, th);
    }
  }
  // the ink alone: dark becomes opaque, paper becomes clear
  const m = document.createElement('canvas'); m.width = c.width; m.height = c.height;
  const id = g.getImageData(0, 0, c.width, c.height); const d = id.data;
  for (let i = 0; i < d.length; i += 4) { const v = (d[i] * 299 + d[i + 1] * 587 + d[i + 2] * 114) / 1000; const a = clamp((235 - v) * 1.6, 0, 255); d[i] = d[i + 1] = d[i + 2] = 255; d[i + 3] = a; }
  m.getContext('2d').putImageData(id, 0, 0);
  ST.strips.set(o.id, { canvas: c, mask: m, tinted: new Map() });
}
// The long line, laid straight and whole. Every mark on the picture (a note, a slur, a dynamic, a
// fingering) is a piece of ink: each piece goes with the line of music it belongs to (the staff it
// touches, else the nearest one), so a slur reaching up over the line above is kept whole and the
// notes of the line above never come along. Each line is then laid straight (a scan a little turned
// or curved: its staff made level along its whole length), and the lines are joined at the same
// height, their staff lines running on from one to the next.
function straightStrip(L, bmp) {
  const W = bmp.width, H = bmp.height;
  const src = document.createElement('canvas'); src.width = W; src.height = H;
  const sg = src.getContext('2d', { willReadFrequently: true }); sg.fillStyle = '#fff'; sg.fillRect(0, 0, W, H); sg.drawImage(bmp, 0, 0);
  const px = sg.getImageData(0, 0, W, H).data; src.width = src.height = 0;
  const N = W * H, lum = new Uint8Array(N);
  for (let i = 0, j = 0; i < N; i++, j += 4) lum[i] = (px[j] * 299 + px[j + 1] * 587 + px[j + 2] * 114) / 1000;
  // (ink: anything clearly darker than the paper, the thin grey staff lines of a page drawn small too)
  const INK = 215, SOFT = 248;
  // the pieces of ink (8 neighbours), by two passes and a union-find
  const lab = new Int32Array(N).fill(-1);
  let par = new Int32Array(1 << 16), nl = 0;
  const find = (a) => { while (par[a] !== a) { par[a] = par[par[a]]; a = par[a]; } return a; };
  const unite = (a, b) => { a = find(a); b = find(b); if (a !== b) { if (a < b) par[b] = a; else par[a] = b; } };
  for (let y = 0; y < H; y++) {
    const r = y * W;
    for (let x = 0; x < W; x++) {
      const i = r + x; if (lum[i] >= INK) continue;
      let l = -1;
      const nb = [x > 0 ? lab[i - 1] : -1, y > 0 && x > 0 ? lab[i - W - 1] : -1, y > 0 ? lab[i - W] : -1, y > 0 && x < W - 1 ? lab[i - W + 1] : -1];
      for (const q of nb) if (q >= 0) { if (l < 0) l = q; else unite(l, q); }
      if (l < 0) { if (nl >= par.length) { const p2 = new Int32Array(par.length * 2); p2.set(par); par = p2; } par[nl] = nl; l = nl++; }
      lab[i] = l;
    }
  }
  const box = new Map();   // root -> [x0, y0, x1, y1, n]
  for (let i = 0; i < N; i++) {
    if (lab[i] < 0) continue;
    const r = find(lab[i]); lab[i] = r;
    const x = i % W, y = (i / W) | 0; let b = box.get(r);
    if (!b) box.set(r, (b = [x, y, x, y, 0]));
    if (x < b[0]) b[0] = x; if (x > b[2]) b[2] = x; if (y < b[1]) b[1] = y; if (y > b[3]) b[3] = y; b[4]++;
  }
  // where a staff's top and bottom lines are at x (along its edge, a sample every few points)
  const edgeAt = (st, x) => {
    const e = st.edge; if (x <= e[0][0]) return [e[0][1], e[0][2]];
    for (let k = 1; k < e.length; k++) if (x <= e[k][0]) { const f = (x - e[k - 1][0]) / Math.max(1e-3, e[k][0] - e[k - 1][0]); return [e[k - 1][1] + f * (e[k][1] - e[k - 1][1]), e[k - 1][2] + f * (e[k][2] - e[k - 1][2])]; }
    const z = e[e.length - 1]; return [z[1], z[2]];
  };
  const staffs = L.staffs.filter((st) => st.sys >= 0);
  const owner = new Map();
  for (const [r, b] of box) {
    if (b[4] < 3) continue;   // (specks)
    const cx = (b[0] + b[2]) / 2;
    let best = -1, bo = 0, gap = Infinity, near = -1;
    for (const st of staffs) {
      const [yT, yB] = edgeAt(st, cx), m = st.sp * 0.3;
      const ov = Math.min(b[3], yB + m) - Math.max(b[1], yT - m);
      if (ov > bo) { bo = ov; best = st.sys; }
      const g = b[3] < yT ? yT - b[3] : b[1] > yB ? b[1] - yB : 0;
      if (g < gap) { gap = g; near = st.sys; }
    }
    owner.set(r, best >= 0 ? best : near);
  }
  const ownerAt = (i) => (lab[i] >= 0 ? (owner.has(lab[i]) ? owner.get(lab[i]) : -2) : -1);
  // each line of music, laid straight
  const outs = L.segs.map((s) => {
    const first = staffs.find((st) => st.sys === s.sys) || staffs[0];
    const x0 = Math.max(0, Math.round(s.x)), w = Math.max(1, Math.min(W - x0, Math.round(s.w)));
    const mid = x0 + w / 2, [mT, mB] = edgeAt(first, mid), yc0 = (mT + mB) / 2;
    const d = new Int16Array(w); let dmin = 0, dmax = 0;
    for (let x = 0; x < w; x++) { const [yT, yB] = edgeAt(first, x0 + x); d[x] = Math.round(yc0 - (yT + yB) / 2); if (d[x] < dmin) dmin = d[x]; if (d[x] > dmax) dmax = d[x]; }
    // the rows its ink reaches
    let top = Infinity, bot = -Infinity;
    for (const [r, b] of box) if (owner.get(r) === s.sys && b[2] >= x0 && b[0] < x0 + w) { if (b[1] < top) top = b[1]; if (b[3] > bot) bot = b[3]; }
    if (!isFinite(top)) { top = Math.max(0, Math.round(mT - s.staff)); bot = Math.min(H - 1, Math.round(top + s.h)); }
    top = Math.max(0, top - 2); bot = Math.min(H - 1, bot + 2);
    const oTop = top + dmin, h = bot - top + 1 + (dmax - dmin);
    const c = document.createElement('canvas'); c.width = w; c.height = h;
    const g = c.getContext('2d'); const out = g.createImageData(w, h); const od = out.data; od.fill(255);
    for (let x = 0; x < w; x++) {
      const X = x0 + x, dx = d[x];
      for (let y = top; y <= bot; y++) {
        const i = y * W + X, v = lum[i]; if (v >= SOFT) continue;
        let mine = ownerAt(i) === s.sys;
        // (the soft edge of a mark goes with the mark)
        if (!mine && lab[i] < 0) for (let dy = -1; dy <= 1 && !mine; dy++) for (let ddx = -1; ddx <= 1; ddx++) { const yy = y + dy, xx = X + ddx; if (yy < 0 || yy >= H || xx < 0 || xx >= W) continue; if (ownerAt(yy * W + xx) === s.sys) { mine = true; break; } }
        if (!mine) continue;
        const o = ((y + dx - oTop) * w + x) * 4; od[o] = od[o + 1] = od[o + 2] = v;
      }
    }
    g.putImageData(out, 0, 0);
    const lines = (xx) => { const [yT, yB] = edgeAt(first, x0 + xx), dd = d[Math.max(0, Math.min(w - 1, xx))]; return [yT + dd - oTop, yB + dd - oTop]; };
    return { c, staffTop: mT - oTop, h, lines };
  });
  // the lines side by side, their staves at the same height
  const above = Math.max(...outs.map((q) => q.staffTop)), below = Math.max(...outs.map((q, k) => q.h - q.staffTop));
  const CH0 = Math.ceil(above + below), CW0 = Math.ceil(L.width);
  // (a very long line is kept a little smaller: iOS will not keep a picture bigger than this, it would
  // come out blank; drawn back at its size, it is the same)
  const LIMIT = /iPhone|iPod/.test(navigator.userAgent) ? 8e6 : 14e6;
  const K = Math.min(1, Math.sqrt(LIMIT / (CW0 * CH0)), 32000 / CW0);
  const CW = Math.ceil(CW0 * K), CH = Math.ceil(CH0 * K);
  const c = document.createElement('canvas'); c.width = CW; c.height = CH;
  const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, CW, CH);
  g.imageSmoothingQuality = 'high';
  g.scale(K, K);
  L.segs.forEach((s, k) => { const q = outs[k]; s.dy = above - q.staffTop; s.h = q.h; s.staff = q.staffTop; g.drawImage(q.c, s.sx, s.dy); });
  L.height = CH0;
  // and the staff running on from one line to the next (each of its five lines, where it ends to
  // where the next one begins)
  if (L.sp && L.segs.length > 1) {
    // (as dark and as thick as the staff lines of the page itself)
    const look = (() => {
      const q = outs[0], w = q.c.width, x = Math.max(0, Math.round((L.segs[0].sX1 ?? w) - L.sp * 2));
      const d = q.c.getContext('2d').getImageData(x, 0, 1, q.c.height).data; const [yT, yB] = q.lines(x);
      const vals = [], th = [];
      for (let k = 0; k < 5; k++) {
        const y = Math.round(yT + (k * (yB - yT)) / 4); let mn = 255, n = 0;
        for (let dy = -3; dy <= 3; dy++) { const yy = y + dy; if (yy < 0 || yy >= q.c.height) continue; const v = d[yy * 4]; if (v < 235) n++; if (v < mn) mn = v; }
        vals.push(mn); th.push(n);
      }
      vals.sort((p, r) => p - r); th.sort((p, r) => p - r);
      return { v: vals[2] < 235 ? vals[2] : 40, t: Math.max(1, Math.min(L.sp * 0.2, th[2] || L.sp * 0.1)) };
    })();
    g.strokeStyle = `rgb(${look.v},${look.v},${look.v})`; g.lineWidth = look.t; g.lineCap = 'butt';
    for (let i = 0; i + 1 < L.segs.length; i++) {
      const A = L.segs[i], B = L.segs[i + 1], qa = outs[i], qb = outs[i + 1];
      const ea = Math.round(A.sX1 ?? A.w) - 1, eb = Math.round(B.sX0 ?? 0);
      const xa = A.sx + ea, xb = B.sx + eb;
      g.fillStyle = '#fff'; g.fillRect(xa + 1, 0, Math.max(0, xb - xa - 1), CH0);
      const [aT, aB] = qa.lines(ea), [bT, bB] = qb.lines(eb);
      for (let k = 0; k < 5; k++) {
        const ya = A.dy + aT + (k * (aB - aT)) / 4, yb = B.dy + bT + (k * (bB - bT)) / 4;
        g.beginPath(); g.moveTo(xa, ya); g.lineTo(xb + 1, yb); g.stroke();
      }
    }
  }
  g.setTransform(1, 0, 0, 1, 0, 0);
  for (const q of outs) q.c.width = q.c.height = 0;
  // the ink alone: dark becomes opaque, paper becomes clear
  const m = document.createElement('canvas'); m.width = CW; m.height = CH;
  const id = g.getImageData(0, 0, CW, CH); const d2 = id.data;
  for (let i = 0; i < d2.length; i += 4) { const v = (d2[i] * 299 + d2[i + 1] * 587 + d2[i + 2] * 114) / 1000; const a = clamp((235 - v) * 1.6, 0, 255); d2[i] = d2[i + 1] = d2[i + 2] = 255; d2[i + 3] = a; }
  m.getContext('2d').putImageData(id, 0, 0);
  return { canvas: c, mask: m, tinted: new Map(), k: K };
}
function tintedMask(st, color) {
  if (st.tinted.has(color)) return st.tinted.get(color);
  const t = document.createElement('canvas'); t.width = st.mask.width; t.height = st.mask.height;
  const g = t.getContext('2d'); g.drawImage(st.mask, 0, 0); g.globalCompositeOperation = 'source-in'; g.fillStyle = color; g.fillRect(0, 0, t.width, t.height);
  st.tinted.set(color, t); return t;
}

// =====================================================================
// Following the playing: listen, read, line up
// =====================================================================
async function pitchTrack(pcm, sr, a, b, onProgress) {
  const N = 2048, hop = Math.round(sr * 0.01);
  const i0 = Math.max(0, Math.floor(a * sr)), i1 = Math.min(pcm.length - N, Math.floor(b * sr));
  const frames = [];
  let k = 0;
  for (let i = i0; i < i1; i += hop) {
    const buf = pcm.subarray(i, i + N);
    let ms = 0; for (let j = 0; j < N; j += 4) ms += buf[j] * buf[j];
    const rms = Math.sqrt(ms / (N / 4));
    const r = rms > 0.004 ? detectPitch(buf, sr) : null;
    frames.push({ t: (i + N / 2) / sr, midi: r && r.clarity > 0.82 ? 69 + 12 * Math.log2(r.freq / 440) : NaN, rms });
    if (++k % 200 === 0) { onProgress && onProgress((i - i0) / (i1 - i0)); await new Promise((r2) => setTimeout(r2, 0)); }
  }
  return frames;
}
function notesFrom(frames) {
  const n = frames.length;
  const med = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const w = []; for (let j = i - 2; j <= i + 2; j++) if (j >= 0 && j < n && !isNaN(frames[j].midi)) w.push(frames[j].midi);
    med[i] = w.length >= 3 ? w.sort((x, y) => x - y)[w.length >> 1] : NaN;
  }
  const notes = [];
  let cur = null, off = 0;
  const gate = Math.max(0.006, frames.reduce((m, f) => Math.max(m, f.rms), 0) * 0.04);
  for (let i = 0; i < n; i++) {
    const m = med[i], f = frames[i];
    // a new attack: the sound jumps up after a dip
    const prevMin = Math.min(...frames.slice(Math.max(0, i - 6), i).map((q) => q.rms), Infinity);
    const attack = f.rms > gate && f.rms > prevMin * 2.1 && (!cur || f.t - cur.t > 0.09);
    if (isNaN(m) || f.rms < gate) { if (cur && ++off > 4) { notes.push(cur); cur = null; } continue; }
    off = 0;
    if (!cur) { cur = { t: f.t, ps: [m] }; continue; }
    const cm = cur.ps.slice().sort((x, y) => x - y)[cur.ps.length >> 1];
    if (Math.abs(m - cm) > 0.6) {
      // only a real change if it lasts
      let stay = 0; for (let j = i; j < Math.min(n, i + 4); j++) if (!isNaN(med[j]) && Math.abs(med[j] - cm) > 0.6) stay++;
      if (stay >= 3) { notes.push(cur); cur = { t: f.t, ps: [m] }; continue; }
    } else if (attack) { notes.push(cur); cur = { t: f.t, ps: [m] }; continue; }
    cur.ps.push(m);
  }
  if (cur) notes.push(cur);
  return notes.filter((q) => q.ps.length >= 4).map((q) => ({ t: q.t, midi: q.ps.slice().sort((x, y) => x - y)[q.ps.length >> 1] }));
}
// Dynamic time warping between the notes on the page and the notes heard.
function align(scoreN, played) {
  const n = scoreN.length, m = played.length;
  const INF = 1e9, D = new Float64Array((n + 1) * (m + 1)).fill(INF), B = new Uint8Array((n + 1) * (m + 1));
  D[0] = 0;
  for (let i = 1; i <= n; i++) { D[i * (m + 1)] = i * 1.2; B[i * (m + 1)] = 2; }
  for (let j = 1; j <= m; j++) { D[j] = j * 0.9; B[j] = 3; }
  const cost = (i, j) => { let c = 99; const pm = played[j].midi; for (const sm of scoreN[i].midis) { const d = Math.abs(pm - sm); c = Math.min(c, d, Math.abs(d - 12) + 0.6, Math.abs(d - 24) + 1.2); } return Math.min(4, c); };
  for (let i = 1; i <= n; i++) for (let j = 1; j <= m; j++) {
    const c = cost(i - 1, j - 1);
    const a = D[(i - 1) * (m + 1) + j - 1] + c, b = D[(i - 1) * (m + 1) + j] + 1.2, d = D[i * (m + 1) + j - 1] + 0.9;
    const k = i * (m + 1) + j;
    if (a <= b && a <= d) { D[k] = a; B[k] = 1; } else if (b <= d) { D[k] = b; B[k] = 2; } else { D[k] = d; B[k] = 3; }
  }
  // best end: the score may end before the recording does
  let best = INF, bj = m; for (let j = 1; j <= m; j++) { const v = D[n * (m + 1) + j] + (m - j) * 0.05; if (v < best) { best = v; bj = j; } }
  const match = new Array(n).fill(-1);
  let i = n, j = bj, good = 0;
  while (i > 0 && j > 0) {
    const b = B[i * (m + 1) + j];
    if (b === 1) { const c = cost(i - 1, j - 1); if (c < 1.1) { match[i - 1] = j - 1; good++; } i--; j--; } else if (b === 2) i--; else j--;
  }
  return { match, cost: best / Math.max(1, n), good: good / Math.max(1, n) };
}
// Chords heard against chords on the page: dynamic time warping on how well each fits,
// trying the music in other keys too (for instruments that sound in another key).
function alignChords(evs, ons) {
  const n = evs.length, m = ons.length;
  if (m < 3) return null;
  let best = null;
  for (const sh of [0, 10, 2, 9, 3, 7, 5]) {
    const tp = evs.map((e) => template(e.pcs.map((p) => (p + sh) % 12)));
    const fit = (i, j) => Math.max(0, Math.min(1, (cosine(ons[j].chroma, tp[i]) - 0.3) / 0.55));
    const W = m + 1, Dm = new Float64Array((n + 1) * W).fill(1e9), B = new Uint8Array((n + 1) * W);
    Dm[0] = 0;
    for (let j = 1; j <= m; j++) { Dm[j] = j * 0.15; B[j] = 3; }
    for (let i = 1; i <= n; i++) { Dm[i * W] = i * 0.9; B[i * W] = 2; }
    for (let i = 1; i <= n; i++) for (let j = 1; j <= m; j++) {
      const c = 1 - fit(i - 1, j - 1);
      const a = Dm[(i - 1) * W + j - 1] + c, b = Dm[(i - 1) * W + j] + 0.9, d = Dm[i * W + j - 1] + 0.3;   // extra attacks (echoes, ornaments) are common
      const k = i * W + j;
      if (a <= b && a <= d) { Dm[k] = a; B[k] = 1; } else if (b <= d) { Dm[k] = b; B[k] = 2; } else { Dm[k] = d; B[k] = 3; }
    }
    let bc = 1e9, bj = m; for (let j = 1; j <= m; j++) { const v = Dm[n * W + j] + (m - j) * 0.15; if (v < bc) { bc = v; bj = j; } }
    const match = new Array(n).fill(-1); let i = n, j = bj, good = 0;
    while (i > 0 && j > 0) { const b = B[i * W + j]; if (b === 1) { if (fit(i - 1, j - 1) > 0.5) { match[i - 1] = j - 1; good++; } i--; j--; } else if (b === 2) i--; else j--; }
    const r = { good: good / n, cost: bc / n, shift: sh, match };
    if (!best || r.good - (sh ? 0.08 : 0) > best.good - (best.shift ? 0.08 : 0)) best = r;
  }
  best.evs = evs.map((e, i) => ({ bar: e.bar, x: e.x, src: e.src, t: best.match[i] >= 0 ? ons[best.match[i]].t : null }));
  best.how = 'chords';
  return best;
}
// The harmony heard, every tenth of a second: with a piano or an orchestra behind the soloist, the
// loudest pitch is often not the soloist's, and attacks blur; what still holds is which notes sound.
async function chromaFrames(pcm, sr, a, b, onProgress) {
  const N = 4096, hop = Math.round(sr * 0.1);
  const win = new Float32Array(N); for (let i = 0; i < N; i++) win[i] = 0.5 - 0.5 * Math.cos((2 * Math.PI * i) / N);
  const i0 = Math.max(0, Math.floor(a * sr)), i1 = Math.min(pcm.length - N, Math.floor(Math.min(b, pcm.length / sr) * sr));
  const out = []; let k = 0;
  for (let i = i0; i < i1; i += hop) {
    const re = new Float64Array(N), im = new Float64Array(N);
    let ms = 0; for (let j = 0; j < N; j++) { const v = pcm[i + j]; re[j] = v * win[j]; ms += v * v; }
    out.push({ t: (i + N / 2) / sr, c: chromaOf(fftMag(re, im), sr, N), rms: Math.sqrt(ms / N) });
    if (++k % 100 === 0) { onProgress && onProgress((i - i0) / Math.max(1, i1 - i0)); await new Promise((r) => setTimeout(r, 0)); }
  }
  // a little smoothing over time (a note rings on; the bow and the hammers add noise)
  return out.map((f, j) => { const c = new Float32Array(12); for (let q = Math.max(0, j - 1); q <= Math.min(out.length - 1, j + 1); q++) for (let x = 0; x < 12; x++) c[x] += out[q].c[x]; return { t: f.t, c, rms: f.rms }; });
}
// The notes on the page against the harmony heard, frame by frame (dynamic time warping over the
// whole passage): each note of the page lasts as many frames as it takes; the soloist may come in
// after the piano or the orchestra has begun, and may end before the recording does.
function alignFrames(evs, frames) {
  const n = evs.length, m = frames.length;
  if (n < 3 || m < n / 4) return null;
  const loud = Math.max(...frames.map((f) => f.rms), 1e-6);
  // (leaving out a moment of the recording costs as much as a note that does not fit: otherwise the
  // shortest path wins, and the whole page is squeezed into a few seconds)
  const SKIP = 0.45;
  let best = null;
  for (const sh of [0, 10, 2, 9, 3, 7, 5]) {
    // each note with a little of the one before (it rings on into the next)
    const tp = evs.map((e, i) => { const t = template(e.pcs.map((p) => (p + sh) % 12)); if (i) { const q = template(evs[i - 1].pcs.map((p) => (p + sh) % 12)); for (let x = 0; x < 12; x++) t[x] += q[x] * 0.35; } return t; });
    const cost = (i, j) => (frames[j].rms < loud * 0.02 ? 0.7 : 1 - cosine(frames[j].c, tp[i]));
    const W = m + 1, Dm = new Float64Array((n + 1) * W).fill(1e9), B = new Uint8Array((n + 1) * W);
    for (let j = 0; j <= m; j++) { Dm[j] = j * SKIP; B[j] = 3; }        // the soloist may come in later
    for (let i = 1; i <= n; i++) for (let j = 1; j <= m; j++) {
      const c = cost(i - 1, j - 1), k = i * W + j;
      const a = Dm[(i - 1) * W + j - 1] + c, st = Dm[i * W + j - 1] + c, up = Dm[(i - 1) * W + j] + c + 0.6;
      if (a <= st && a <= up) { Dm[k] = a; B[k] = 1; } else if (st <= up) { Dm[k] = st; B[k] = 3; } else { Dm[k] = up; B[k] = 2; }
    }
    let bc = 1e9, bj = m; for (let j = 1; j <= m; j++) { const v = Dm[n * W + j] + (m - j) * SKIP; if (v < bc) { bc = v; bj = j; } }
    // back along the path: where each note begins, and how well its frames fit
    const start = new Array(n).fill(-1), fitSum = new Float64Array(n), fitN = new Uint32Array(n);
    let i = n, j = bj;
    while (i > 0 && j > 0) {
      const b = B[i * W + j];
      fitSum[i - 1] += 1 - cost(i - 1, j - 1); fitN[i - 1]++; start[i - 1] = j - 1;
      if (b === 1) { i--; j--; } else if (b === 3) j--; else i--;
    }
    let good = 0; for (let q = 0; q < n; q++) if (fitN[q] && fitSum[q] / fitN[q] > 0.6) good++;
    const r = { good: good / n, cost: bc / Math.max(1, n), shift: sh, start };
    if (!best || r.good - (sh ? 0.06 : 0) > best.good - (best.shift ? 0.06 : 0)) best = r;
  }
  // (a note on the same pitches as the one before cannot be told from it by the harmony: where it
  // starts is a guess, and is not used for moving the line through the bar)
  const same = (p, q) => p.length === q.length && p.every((x) => q.includes(x));
  best.evs = evs.map((e, q) => ({ bar: e.bar, x: e.x, src: e.src, rep: q > 0 && same(e.pcs, evs[q - 1].pcs), t: best.start[q] >= 0 ? frames[best.start[q]].t : null }));
  best.how = 'harmony';
  return best;
}
async function autoSync(o, { from = 0 } = {}) {
  if (!ST.pcm) { D.toast('This recording has no sound to follow. Use Tap along.'); return; }
  // "Follow from here": the bars before this one stay where they are (set by hand, or right); the
  // playing is followed again from this bar's start to the end
  const full = o.layout;
  from = o.times && from > 0 && from < full.bars.length ? from : 0;
  const L = from ? { ...full, bars: full.bars.slice(from), notes: full.notes.filter((n) => n.bar >= from).map((n) => ({ ...n, bar: n.bar - from })), events: (full.events || []).filter((e) => e.bar >= from).map((e) => ({ ...e, bar: e.bar - from })) } : full;
  const A = from ? clamp(o.times[from] - 0.3, ST.P.trim.a, ST.P.trim.b - 1) : ST.P.trim.a, B = ST.P.trim.b;
  if (L.notes.length < 3) { D.toast('Not enough notes were found in the score to follow. Use Tap along.', 4000); return; }
  busy('Following your playing…', 'Listening to the recording.', 0);
  let cancelled = false; ST.busyCancel = () => { cancelled = true; };
  try {
    // two ways of listening: note by note (one line at a time) and chord by chord (the piano,
    // double stops, an ensemble). Both are tried; the one that fits the page best wins.
    const frames = await pitchTrack(ST.pcm, ST.sr, A, B, (f) => busy('Following your playing…', 'Listening to the recording.', f * 0.45));
    if (cancelled) return;
    const played = notesFrom(frames);
    let best = null;
    if (played.length >= 3) {
      // the page does not say which clef or instrument: try each and keep the best fit
      const clefs = L.clef ? [L.clef, ...['treble', 'bass', 'alto', 'tenor'].filter((c) => c !== L.clef)] : ['treble', 'bass', 'alto', 'tenor'];
      for (const clef of clefs) {
        for (const shift of [0, -12, 12, -2, -9, -7, 2, -24, 24]) {
          const sn = L.notes.map((nt) => ({ bar: nt.bar, midis: nt.ps.map(({ p, acc }) => { const s2 = CLEFS[clef].bottom + p; const a = acc !== undefined ? acc : keyAlter(L.key || 0, s2); return midiOf(s2, a) + shift; }) }));
          const r = align(sn, played);
          const score = r.cost - r.good * 0.8 + (clef === L.clef ? -0.15 : 0) + (shift ? 0.05 : 0);
          if (!best || score < best.score) best = { ...r, score, clef, shift };
        }
      }
      best.evs = L.notes.map((nt, i) => ({ bar: nt.bar, x: nt.x, src: nt.src, t: best.match[i] >= 0 ? played[best.match[i]].t : null }));
      best.how = 'notes';
    }
    if (L.events && L.events.length >= 3 && (!best || best.good < 0.8 || L.events.some((e) => e.pcs.length > 1))) {
      busy('Following your playing…', 'Listening for chords.', 0.5);
      const ons = await onsetsOf(ST.pcm, ST.sr, A, B, (f) => busy('Following your playing…', 'Listening for chords.', 0.5 + f * 0.35));
      if (cancelled) return;
      const ch = alignChords(L.events, ons);
      // a page with chords is better followed chord by chord, unless that clearly fails
      const chordy = L.events.filter((e) => e.pcs.length > 1).length > L.events.length * 0.2;
      if (ch) ch.alt = best ? best.good : null;
      if (ch && (!best || (chordy ? ch.good > 0.45 || ch.good > best.good : ch.good > best.good + 0.05))) best = ch;
    }
    // neither fits well (a piano or an orchestra behind the soloist): follow the harmony heard
    if (L.events && L.events.length >= 3 && (!best || best.good < 0.55)) {
      busy('Following your playing…', 'Listening to the harmony.', 0.85);
      const fr = await chromaFrames(ST.pcm, ST.sr, A, B, (f) => busy('Following your playing…', 'Listening to the harmony.', 0.85 + f * 0.05));
      if (cancelled) return;
      const hm = alignFrames(L.events, fr);
      try { window.__studioHarmony = hm ? { good: hm.good, shift: hm.shift, events: L.events.length } : { none: true, events: L.events.length }; } catch {}
      if (hm && (!best || hm.good > best.good + 0.1)) { hm.alt = best ? best.good : null; best = hm; }
    }
    if (!best) { busy(null); D.toast('Not enough clear notes were heard. Use Tap along.', 4500); return; }
    busy('Following your playing…', 'Lining them up with the score.', 0.9);
    await new Promise((r) => setTimeout(r, 30));
    // bar times from the first matched note of each bar
    const nb = L.bars.length;
    const first = new Array(nb).fill(null);
    const byBar = Array.from({ length: nb }, () => []);
    for (const e of best.evs) byBar[e.bar].push({ x: e.x, t: e.t, rep: e.rep });
    let prevLast = null;
    for (let k = 0; k < nb; k++) {
      const ns = byBar[k].sort((a, b) => a.x - b.x), hit = ns.filter((n) => n.t !== null);
      if (!hit.length) continue;
      const fm = hit[0];
      if (fm === ns[0]) first[k] = fm.t;
      else {
        // the first note of the bar was not heard: step back from the first one that was,
        // at the pace of the notes around it
        const nm = hit[1];
        let rate = nm && nm.x > fm.x ? (nm.t - fm.t) / (nm.x - fm.x) : prevLast && fm.x > prevLast.x ? (fm.t - prevLast.t) / (fm.x - prevLast.x) : 0;
        if (!(rate > 0) || !isFinite(rate)) rate = 0;
        let t = fm.t - (fm.x - ns[0].x) * rate;
        if (prevLast) t = Math.max(t, prevLast.t + 0.08);
        first[k] = Math.min(t, fm.t);
      }
      prevLast = hit[hit.length - 1];
    }
    const known = first.map((t, k) => (t !== null ? k : -1)).filter((k) => k >= 0);
    if (known.length < 2) { busy(null); D.toast('Your playing could not be matched with the score. Use Tap along.', 5000); return; }
    const times = new Array(nb + 1);
    for (let k = 0; k < nb; k++) {
      if (first[k] !== null) { times[k] = first[k] - 0.05; continue; }
      // in between two known bars: share the time out; before or after: keep the pace
      const prev = known.filter((q) => q < k).pop(), next = known.find((q) => q > k);
      if (prev !== undefined && next !== undefined) times[k] = first[prev] + ((first[next] - first[prev]) * (k - prev)) / (next - prev);
      else if (next !== undefined) { const pace = (first[known[1]] - first[known[0]]) / (known[1] - known[0]); times[k] = first[next] - pace * (next - k); }
      else { const a2 = known[known.length - 2], b2 = known[known.length - 1]; const pace = (first[b2] - first[a2]) / (b2 - a2); times[k] = first[b2] + pace * (k - b2); }
    }
    const lastPlayed = Math.max(...best.evs.map((e) => e.t || 0)) + 0.6;
    const pace = (times[nb - 1] - times[0]) / Math.max(1, nb - 1);
    times[nb] = Math.min(ST.P.trim.b, Math.max(times[nb - 1] + pace * 0.5, Math.min(lastPlayed, times[nb - 1] + pace * 1.5)));
    // (from a bar: that bar starts where it was put, the ones before are kept)
    if (from) times[0] = o.times[from];
    for (let k = 1; k <= nb; k++) if (times[k] < times[k - 1] + 0.12) times[k] = times[k - 1] + 0.12;
    const newTimes = times.map((t) => clamp(t, A, B));
    const allTimes = from ? [...o.times.slice(0, from), ...newTimes] : newTimes;
    // inside each bar: where each heard note is, as a share of the bar's width and of its time,
    // so the line moves note by note with the playing (and still fits if bars are moved by hand)
    const newKnots = knotsOf(byBar, newTimes, L.bars);
    o._evs = from ? null : best.evs;
    o.times = allTimes;
    // (the bars kept keep their own; one that had none gets none: the line then moves evenly in it)
    o.knots = from ? [...Array.from({ length: from }, (_, k) => (o.knots && o.knots[k]) || []), ...newKnots] : newKnots;
    o.synced = 'auto'; o.syncInfo = { good: best.good, clef: best.clef, shift: best.shift, how: best.how, alt: best.alt };
    busy(null);
    saveSoon(); renderSide(); renderTimeline(); frame();
    D.toast(best.good > 0.55 ? `Lined up with your playing (${Math.round(best.good * 100)}% of the notes matched).` : 'Lined up as well as possible. Check the bars on the timeline, or use Tap along.', 4200);
  } catch (err) { console.error(err); busy(null); D.toast('Following the playing did not work here. Use Tap along.'); }
}
// inside each bar: where each heard note is, as a share of the bar's width and of its time
function knotsOf(byBar, times, bars) {
  return byBar.map((ns, k) => {
    const T0 = times[k], T1 = times[k + 1], b = bars[k];
    const out = []; let lx = 0, lt = 0;
    for (const n of ns.filter((q) => q.t !== null && !q.rep).sort((p, q) => p.x - q.x)) {
      const fx = (n.x - b.x0) / Math.max(1, b.x1 - b.x0), ft = (n.t - T0) / Math.max(0.01, T1 - T0);
      // (a note heard far from where it stands in the bar is a mismatch: left out, the line keeps an even pace)
      if (fx > lx + 0.02 && ft > lt + 0.02 && fx < 0.98 && ft < 0.98 && Math.abs(fx - ft) < 0.38) { out.push([ft, fx]); lx = fx; lt = ft; }
    }
    return out;
  });
}
// A steady pace: a bar whose start sits well off the pace of the bars around it (a note heard in the
// wrong place, a bar where nothing clear was heard) is put back on it. Only clear slips are moved, so
// a real slowing down or speeding up stays.
function steadyTimes(times, known = null) {
  const T = times.slice(), n = T.length;
  if (n < 6) return T;
  const ok = T.map((_, k) => !known || known[k] !== false);
  // where bar k would start by the pace of the bars around it (the middle of their slopes and
  // offsets, so one slip among them does not move it; a bar where nothing was heard does not count)
  const want = (k, least) => {
    const ks = []; for (let q = Math.max(0, k - 3); q <= Math.min(n - 1, k + 3); q++) if (q !== k && ok[q]) ks.push(q);
    if (ks.length < 4) for (let q = Math.max(0, k - 6); q <= Math.min(n - 1, k + 6); q++) if (Math.abs(q - k) > 3 && ok[q]) ks.push(q);
    if (ks.length < least) return null;
    const sl = []; for (let i = 0; i < ks.length; i++) for (let j = i + 1; j < ks.length; j++) sl.push((T[ks[j]] - T[ks[i]]) / (ks[j] - ks[i]));
    sl.sort((p, q) => p - q); const pace = sl[sl.length >> 1];
    if (!(pace > 0.05)) return null;
    const off = ks.map((q) => T[q] - pace * q).sort((p, q) => p - q);
    return { t: (off[(off.length - 1) >> 1] + off[off.length >> 1]) / 2 + pace * k, pace };
  };
  // bars where nothing was heard: on the pace of the ones around them
  for (let k = 0; k < n; k++) if (!ok[k]) { const w = want(k, 2); if (w) T[k] = w.t; }
  // then the clearest slip first, and look again (each one put right helps to see the next)
  for (let it = 0; it < n; it++) {
    let worst = -1, by = 0.25, to = 0;
    for (let k = 0; k < n; k++) { const w = want(k, 4); if (!w) continue; const r = Math.abs(T[k] - w.t) / w.pace; if (r > by) { by = r; worst = k; to = w.t; } }
    if (worst < 0) break;
    T[worst] = to;
  }
  for (let k = 1; k < n; k++) if (T[k] < T[k - 1] + 0.12) T[k] = T[k - 1] + 0.12;
  return T;
}
// Two parts of one piece (a duet: often one plays while the other rests): followed together, as one
// score, so whoever is playing keeps the time for both, and both lines get the same bar times.
async function syncBoth() {
  const ls = scoreLines();
  const [a, b] = ls;
  if (!b || a.layout.bars.length !== b.layout.bars.length) { for (const x of ls) await autoSync(x); return; }
  if (!ST.pcm) { D.toast('This recording has no sound to follow. Use Tap along.'); return; }
  const A = a.layout, B = b.layout;
  const mapX = (x, k) => { const p = A.bars[k], q = B.bars[k]; return p.x0 + ((x - q.x0) / Math.max(1, q.x1 - q.x0)) * (p.x1 - p.x0); };
  const near = (k) => (A.bars[k].x1 - A.bars[k].x0) * 0.02;
  const merge = (xs, add) => {
    xs.sort((p, q) => p.bar - q.bar || p.x - q.x);
    const out = [];
    for (const e of xs) { const l = out[out.length - 1]; if (l && l.bar === e.bar && Math.abs(l.x - e.x) < near(e.bar)) { add(l, e); l.src.push(...e.src); } else out.push(e); }
    return out;
  };
  // the notes of both (when both are read the same way: the same clef and key)
  const sameRead = (A.clef || null) === (B.clef || null) && (A.key || 0) === (B.key || 0);
  const notes = merge([
    ...A.notes.map((nt) => ({ ...nt, ps: [...nt.ps], src: [{ line: 0, x: nt.x }] })),
    ...(sameRead ? B.notes.map((nt) => ({ ...nt, x: mapX(nt.x, nt.bar), ps: [...nt.ps], src: [{ line: 1, x: nt.x }] })) : []),
  ], (l, e) => { for (const q of e.ps) if (!l.ps.some((r) => r.p === q.p)) l.ps.push(q); });
  const events = merge([
    ...(A.events || []).map((e) => ({ ...e, pcs: [...e.pcs], src: [{ line: 0, x: e.x }] })),
    ...(B.events || []).map((e) => ({ ...e, x: mapX(e.x, e.bar), pcs: [...e.pcs], src: [{ line: 1, x: e.x }] })),
  ], (l, e) => { for (const pc of e.pcs) if (!l.pcs.includes(pc)) l.pcs.push(pc); });
  const j = { id: a.id, layout: { ...A, notes, events }, times: null, knots: null };
  await autoSync(j);
  if (!j.times || !j._evs) return;
  try { window.__jointRaw = j.times.slice(); } catch {}
  // (a bar start pushed against the start of the recording was not heard there: it starts before)
  const A0 = ST.P.trim.a, known = j.times.map((t, k) => !(t <= A0 + 0.02 && k < j.times.length - 1 && j.times[k + 1] - t < 1.2 * ((j.times[j.times.length - 1] - j.times[0]) / (j.times.length - 1))));
  const T = steadyTimes(j.times, known);
  // the end of the last bar is not heard (the next one is not on the page): at the pace of the bars
  // before it, unless the playing clearly stopped sooner
  { const m = T.length - 1, d = []; for (let k = Math.max(1, m - 4); k < m; k++) d.push(T[k] - T[k - 1]); d.sort((p, q) => p - q);
    const pace = d[d.length >> 1]; if (pace > 0) T[m] = Math.min(ST.P.trim.b + pace, Math.max(T[m], T[m - 1] + pace)); }
  // each line moves note by note with its own notes, on the shared bar times
  ls.forEach((x, li) => {
    const byBar = Array.from({ length: x.layout.bars.length }, () => []);
    for (const e of j._evs) for (const s of e.src || []) if (s.line === li) byBar[e.bar].push({ x: s.x, t: e.t, rep: e.rep });
    x.times = T.slice(); x.knots = knotsOf(byBar, T, x.layout.bars);
    x.synced = 'auto'; x.syncInfo = { ...j.syncInfo, both: true };
  });
  saveSoon(); renderSide(); renderTimeline(); frame();
}
// Tap along: a tap on each bar's first beat. A tap lands a little off the beat it means (the finger,
// and the sound reaching the ear a moment after the picture's clock), so each tap is then drawn to
// the note that starts nearest to it in the recording, when one starts clearly there.
function startTap(o, from = 0) {
  pause();
  // (from a bar: the bars before it are kept; the recording starts a little before that bar)
  from = o.times && from > 0 && from < o.layout.bars.length ? from : 0;
  ST.tapping = { o, k: from, from, times: from ? o.times.slice(0, from) : [] };
  const t0 = Math.max(ST.P.trim.a, (o.times ? o.times[from] : ST.P.trim.a) - 2);
  ST.media.currentTime = t0;
  $('#stTap').hidden = false; $('#stTapInfo').textContent = `Tap on the first beat of bar ${from + 1}`;
  // (the notes' starts, found while you tap)
  if (ST.pcm && !(ST.onsets && ST.onsets.a === ST.P.trim.a && ST.onsets.b === ST.P.trim.b)) {
    const a = ST.P.trim.a, b = ST.P.trim.b;
    ST.onsets = { a, b, list: null, job: onsetsOf(ST.pcm, ST.sr, a, b).then((l) => { if (ST.onsets && ST.onsets.a === a && ST.onsets.b === b) ST.onsets.list = l; return l; }).catch(() => null) };
  }
  play();
}
// the clock of what is heard: the media's own time, made smooth between its updates
function heardTime() {
  const m = ST.media, now = performance.now(), ct = m.currentTime;
  const c = ST.clk;
  if (!c || c.ct !== ct || m.paused) ST.clk = { ct, p: now };
  const at = ST.clk.ct + (m.paused ? 0 : Math.min(0.3, (now - ST.clk.p) / 1000) * (m.playbackRate || 1));
  return at;
}
function tap(e) {
  const T = ST.tapping; if (!T) return;
  // (the moment the finger landed, not when the page got round to it: a busy iPad may be a little late)
  const lag = e && e.timeStamp > 0 ? Math.max(0, Math.min(0.15, (performance.now() - e.timeStamp) / 1000)) : 0;
  const t = heardTime() - lag * (ST.media.playbackRate || 1);
  T.times.push(t); T.k++;
  const n = T.o.layout.bars.length;
  $('#stTapInfo').textContent = T.k < n ? `Bar ${T.k + 1} of ${n}` : 'Tap where the last bar ends';
  if (T.k > n) finishTap();
}
// each tap to the clearest note start near it (from a little before to a little after the tap)
export function snapTaps(times, onsets, sr = 48000, win = [-0.2, 0.12]) {
  if (!onsets || onsets.length < 2) return times.slice();
  // (a note start is found a little early, by most of the listening window: put back where it is heard)
  const late = 3072 / sr - 0.012;
  onsets = onsets.map((x) => ({ t: x.t + late, fl: x.fl }));
  const fls = onsets.map((x) => x.fl).sort((x, y) => x - y), med = fls[fls.length >> 1] || 1;
  const out = times.map((t) => {
    let best = null, bs = 0;
    for (const on of onsets) {
      const d = on.t - t; if (d < win[0] || d > win[1]) continue;
      const sc = (on.fl / med) * Math.exp(-Math.pow((d + 0.03) / 0.09, 2));
      if (sc > bs) { bs = sc; best = on.t; }
    }
    return best !== null && bs > 0.45 ? best : t - 0.03;
  });
  for (let i = 1; i < out.length; i++) if (out[i] <= out[i - 1] + 0.05) out[i] = Math.max(times[i], out[i - 1] + 0.05);
  return out;
}
async function finishTap() {
  const T = ST.tapping; if (!T) return; ST.tapping = null;
  $('#stTap').hidden = true;
  pause();
  const n = T.o.layout.bars.length, from = T.from || 0;
  if (T.times.length - from >= (from ? 1 : 2)) {
    let raw = T.times.slice(0, n + 1);
    if (ST.onsets && (ST.onsets.list || ST.onsets.job)) {
      if (!ST.onsets.list) busy('Lining up your taps…', 'Listening for the notes.', 0.5);
      const list = ST.onsets.list || await ST.onsets.job; busy(null);
      // (only the new taps: the bars kept stay exactly where they were)
      raw = [...raw.slice(0, from), ...snapTaps(raw.slice(from), list, ST.sr)];
      for (let i = Math.max(1, from); i < raw.length; i++) if (raw[i] <= raw[i - 1] + 0.05) raw[i] = raw[i - 1] + 0.05;
    }
    const times = raw;
    const old = T.o.times || [];
    // (stopped before the end: the bars after keep their times when they still come after the last
    // tap; else they go on at the pace of the taps)
    const pace = (times[times.length - 1] - times[0]) / Math.max(1, times.length - 1);
    const lastTap = times[times.length - 1];
    if (from && old.length === n + 1 && times.length < n + 1 && old[times.length] > lastTap + 0.12) times.push(...old.slice(times.length));
    while (times.length < n + 1) times.push(Math.min(ST.P.trim.b, times[times.length - 1] + pace));
    // (a tap clearly off the pace of the ones around it, a slip of the finger, is put back on it; a
    // real slowing down stays)
    const nt = Math.min(times.length, T.times.length) - from;
    if (nt >= 6) { const st2 = steadyTimes(times.slice(from, from + nt)); for (let i = 0; i < nt; i++) times[from + i] = st2[i]; }
    for (let i = Math.max(1, from); i < times.length; i++) if (times[i] <= times[i - 1] + 0.05) times[i] = times[i - 1] + 0.05;
    T.o.times = times; T.o.synced = 'tap';
    if (T.o.knots) T.o.knots = T.o.knots.map((kn, k) => (k < from || (from && k >= T.times.length && old[k] === times[k]) ? kn : []));
    // (two parts of one piece: the same bars at the same moments, in both lines)
    const other = scoreLines().find((x) => x !== T.o);
    if (other && other.layout.bars.length === n) { other.times = times.slice(); other.synced = 'tap'; other.knots = other.knots ? other.knots.map((kn, k) => (k < from ? kn : [])) : null; }
    saveSoon(); D.toast(from ? `Bars from ${from + 1} set from your taps.` : 'Bars set from your taps.', 2200);
  }
  renderSide(); renderTimeline(); frame();
}

// =====================================================================
// Drawing a frame
// =====================================================================
function outSize() {
  const f = FORMATS[ST.P.format] || FORMATS['9:16'];
  if (ST.P.format === 'orig') {
    const vw = ST.media.videoWidth || 1280, vh = ST.media.videoHeight || 720;
    const k = Math.min(1, 1920 / Math.max(vw, vh)); return [Math.round(vw * k / 2) * 2, Math.round(vh * k / 2) * 2];
  }
  return [f[0], f[1]];
}
function sizeCanvas() {
  const [W, H] = outSize();
  const stage = $('#stStage').getBoundingClientRect();
  const k = Math.min((stage.width - 36) / W, (stage.height - 36) / H);
  const c = $('#stCanvas');
  c.style.width = Math.round(W * k) + 'px'; c.style.height = Math.round(H * k) + 'px';
  const dpr = Math.min(2, devicePixelRatio || 1);
  const q = Math.min(1, (W * k * dpr) / W);
  c.width = Math.round(W * q); c.height = Math.round(H * q);
  ST.view = { W, H, q, k };
}
let blurC = null;
// The video, covering the frame, very soft and a little darker: behind a video shown whole.
function softBack(m, W, H) {
  const vw = m.videoWidth, vh = m.videoHeight;
  if (!blurC) blurC = { a: document.createElement('canvas'), b: document.createElement('canvas'), out: document.createElement('canvas') };
  // the frame's shape at 40 px across, the picture covering it
  const sw = W >= H ? 40 : Math.round(40 * W / H), sh = W >= H ? Math.round(40 * H / W) : 40;
  const A = blurC.a; A.width = sw; A.height = sh;
  const ga = A.getContext('2d'); ga.imageSmoothingEnabled = true; ga.imageSmoothingQuality = 'high';
  const cov = Math.max(sw / vw, sh / vh); ga.drawImage(m, (sw - vw * cov) / 2, (sh - vh * cov) / 2, vw * cov, vh * cov);
  // grown back in steps of two, to about a quarter of the frame
  let src = A, w = sw, h = sh; const tw = Math.max(sw, Math.round(W / 4)), th = Math.max(sh, Math.round(H / 4));
  let flip = false;
  while (w < tw) {
    const nw = Math.min(tw, w * 2), nh = Math.min(th, h * 2);
    const D = flip ? blurC.a : blurC.b; if (D === src) break;
    D.width = nw; D.height = nh; const gd = D.getContext('2d'); gd.imageSmoothingEnabled = true; gd.imageSmoothingQuality = 'high';
    gd.drawImage(src, 0, 0, w, h, 0, 0, nw, nh);
    src = D; w = nw; h = nh; flip = !flip;
  }
  const O = blurC.out; O.width = w; O.height = h;
  const go = O.getContext('2d'); go.imageSmoothingEnabled = true; go.imageSmoothingQuality = 'high';
  go.drawImage(src, 0, 0, w, h);
  go.fillStyle = 'rgba(0,0,0,0.28)'; go.fillRect(0, 0, w, h);
  return O;
}
// Draw the picture at time t into ctx sized W x H (any scale).
function drawFrame(g, W, H, t, forExport) {
  const P = ST.P, m = ST.media;
  g.save();
  // (the video made bigger or smaller with the best smoothing there is)
  g.imageSmoothingEnabled = true; g.imageSmoothingQuality = 'high';
  // (only what is drawn over the video, on a clear picture: for putting it over the original video
  // elsewhere, at the original's own quality)
  const onlyOver = !!globalThis.__studioOverlaysOnly;
  if (onlyOver) g.clearRect(0, 0, W, H); else { g.fillStyle = P.bg || '#14171f'; g.fillRect(0, 0, W, H); }
  const isVideo = ST.take.kind === 'video' && m.videoWidth;
  if (onlyOver) { /* nothing under the overlays */ }
  else if (isVideo) {
    const vw = m.videoWidth, vh = m.videoHeight;
    const cover = Math.max(W / vw, H / vh), contain = Math.min(W / vw, H / vh);
    if (P.fit === 'fit') {
      // a soft blurred copy fills the space around a fitted video
      // (a real blur, smooth at any size: the picture made very small, then grown back in gentle
      // steps, each step smoothing the last; one big step from a tiny picture showed squares)
      g.save(); g.drawImage(softBack(m, W, H), 0, 0, W, H); g.restore();
      const dw = vw * contain, dh = vh * contain;
      drawVideo(g, m, (W - dw) / 2, (H - dh) / 2, dw, dh);
    } else {
      const dw = vw * cover, dh = vh * cover;
      const x = (W - dw) * (P.pan ? P.pan.x : 0.5), y = (H - dh) * (P.pan ? P.pan.y : 0.5);
      drawVideo(g, m, x, y, dw, dh);
    }
  } else {
    const gr = g.createLinearGradient(0, 0, W, H); gr.addColorStop(0, '#1b2a4a'); gr.addColorStop(1, '#3a2433');
    g.fillStyle = gr; g.fillRect(0, 0, W, H);
    g.fillStyle = 'rgba(255,255,255,0.85)'; g.font = `600 ${Math.round(W * 0.045)}px ui-serif, Georgia, serif`; g.textAlign = 'center';
    g.fillText(ST.take.name || '', W / 2, H * 0.2);
  }
  for (const o of P.overlays) {
    if (o.kind === 'image') drawImage(g, W, H, o, t);
    else drawScore(g, W, H, o, t, forExport);
  }
  g.restore();
}
function drawVideo(g, m, x, y, w, h) {
  // the chosen look, worked out on the graphics chip for each frame
  let src = m;
  if (ST.P.look && !isNeutral(ST.P.look)) {
    const k = Math.min(1, 2048 / Math.max(w, h));
    const graded = grader.render(m, Math.min(m.videoWidth || w, w * k), Math.min(m.videoHeight || h, h * k), ST.P.look);
    if (graded) src = graded;
  }
  if (ST.take.mirror) { g.save(); g.translate(x + w, y); g.scale(-1, 1); g.drawImage(src, 0, 0, w, h); g.restore(); }
  else g.drawImage(src, x, y, w, h);
}
// a still of the current frame in a look, for the look buttons
function lookThumb(c, look) {
  const m = ST.media; if (!m || !m.videoWidth) return;
  const g = c.getContext('2d'); const vw = m.videoWidth, vh = m.videoHeight, s = Math.max(c.width / vw, c.height / vh);
  const graded = isNeutral(look) ? m : grader.render(m, vw * s, vh * s, look);
  g.drawImage(graded || m, (c.width - vw * s) / 2, (c.height - vh * s) / 2, vw * s, vh * s);
}
function rr(g, x, y, w, h, r) { g.beginPath(); if (g.roundRect) g.roundRect(x, y, w, h, r); else g.rect(x, y, w, h); }
function barAt(o, t) {
  const T = o.times; const n = o.layout.bars.length;
  if (!T || t < T[0]) return { b: -1, f: 0 };
  for (let k = 0; k < n; k++) if (t < T[k + 1]) return { b: k, f: (t - T[k]) / Math.max(0.01, T[k + 1] - T[k]) };
  return { b: n, f: 0 };
}
// where the music is at time t, in the strip: note by note when the playing was followed
function posAt(o, t) {
  const L = o.layout, bars = L.bars, n = bars.length;
  const { b, f } = barAt(o, t);
  if (b < 0) return bars[0].x0;
  if (b >= n) return bars[n - 1].x1;
  const kn = o.knots && o.knots[b];
  let fx = f;
  if (kn && kn.length) {
    let pt = 0, px = 0;
    for (const [ft, x] of kn) { if (f < ft) { fx = px + ((f - pt) / Math.max(1e-3, ft - pt)) * (x - px); pt = -1; break; } pt = ft; px = x; }
    if (pt >= 0) fx = px + ((f - pt) / Math.max(1e-3, 1 - pt)) * (1 - px);
  }
  return bars[b].x0 + fx * (bars[b].x1 - bars[b].x0);
}
// the same, smoothed over a quarter of a second, for moving the page without jolts
// Where the page is at time t: a gentle curve through the start of each bar (its speed changes
// smoothly from bar to bar, never in a jolt), so the music glides by.
function glide(ts, xs, t) {
  const n = ts.length; if (n < 2) return xs[0] || 0;
  if (t <= ts[0]) return xs[0]; if (t >= ts[n - 1]) return xs[n - 1];
  let k = 0; while (k < n - 2 && t >= ts[k + 1]) k++;
  const sl = (i) => (xs[i + 1] - xs[i]) / Math.max(1e-3, ts[i + 1] - ts[i]);
  // (the speed at each bar start: between the bars around it, never overshooting: Fritsch–Carlson)
  const m = (i) => { if (i <= 0) return sl(0); if (i >= n - 1) return sl(n - 2); const a = sl(i - 1), b = sl(i); return a * b <= 0 ? 0 : (2 * a * b) / (a + b); };
  const h = ts[k + 1] - ts[k], u = (t - ts[k]) / Math.max(1e-3, h), u2 = u * u, u3 = u2 * u;
  return (2 * u3 - 3 * u2 + 1) * xs[k] + (u3 - 2 * u2 + u) * h * m(k) + (-2 * u3 + 3 * u2) * xs[k + 1] + (u3 - u2) * h * m(k + 1);
}
// (held between two ends, coming to rest at them gently rather than stopping dead)
function softClamp(v, a, b, k) {
  if (b <= a) return a;
  k = Math.min(k, (b - a) / 3);
  const smax = (x, y) => (x + y + Math.sqrt((x - y) * (x - y) + k * k)) / 2, smin = (x, y) => (x + y - Math.sqrt((x - y) * (x - y) + k * k)) / 2;
  return clamp(smin(smax(v, a + k / 2), b - k / 2), a, b);
}
function viewAt(o, t) {
  const T = o.times, bars = o.layout.bars; if (!T) return posAt(o, t);
  const ts = [], xs = [];
  for (let k = 0; k < bars.length; k++) { ts.push(T[k]); xs.push(bars[k].x0); }
  ts.push(T[bars.length]); xs.push(bars[bars.length - 1].x1);
  return glide(ts, xs, t);
}
function drawScore(g, W, H, o, t) {
  const st = ST.strips.get(o.id); if (!st) return;
  const L = o.layout, bars = L.bars, n = bars.length;
  const { b, f } = barAt(o, t);
  const cb = clamp(b, 0, n - 1);
  // which part of the line is on show
  let vx0, vx1, cursor = null;
  const avg = L.width / n;
  if (o.mode === 'lines') {
    // one line of the page at a time; the next one fades in as you reach the end of a line
    const segs = L.segs;
    const segOf = (k) => bars[clamp(k, 0, n - 1)].seg;
    let si = segOf(cb);
    const lastOfSeg = (q) => { let k = n - 1; while (k > 0 && bars[k].seg !== q) k--; return k; };
    if (b >= 0 && b < n && b === lastOfSeg(si) && f > 0.72 && si < segs.length - 1) si++;
    const fullW = Math.max(...segs.map((q) => q.w));
    const view = (q) => [segs[q].sx, segs[q].sx + segs[q].w];
    // how far into the change from the previous line
    const firstBar = bars.findIndex((q) => q.seg === si);
    const lastPrev = firstBar > 0 ? firstBar - 1 : -1;
    let fade = 1;
    if (lastPrev >= 0 && o.times) {
      const tSwitch = o.times[lastPrev] + 0.72 * (o.times[lastPrev + 1] - o.times[lastPrev]);
      fade = clamp((t - tSwitch) / 0.28, 0, 1);
    }
    // (the paper stays; the old line's music goes, then the new one's comes: two lines faded over
    // each other at once showed a ghost of one in the other)
    if (fade < 1 && si > 0) {
      if (fade < 0.5) { const [p0, p1] = view(si - 1); paint(p0, p1, 1, null, fullW, 1 - fade * 2); }
      else { const [v0, v1] = view(si); paint(v0, v1, 1, null, fullW, fade * 2 - 1); }
      return;
    }
    const [v0, v1] = view(si);
    paint(v0, v1, 1, null, fullW);
    return;
  }
  const J = o.mode === 'scroll' ? jointOf(o) : null;
  if (J) {
    // two parts as one system: the same bar over the same bar, the page moving for both together
    const per = Math.max(1, o.perView), vw = Math.min(J.width, (J.width / n) * per);
    const smooth = J.viewAt(t);
    vx0 = softClamp(smooth - vw * (o.band ? 0.22 : 0.32), 0, Math.max(0, J.width - vw), vw * 0.12); vx1 = vx0 + vw;
    if (b >= 0 && b < n) cursor = J.toCommon(o, posAt(o, t), cb);
    else if (b >= n) cursor = J.width - 1;   // (at the end it stays on the last barline)
    paint(vx0, vx1, 1, cursor, null, 1, J);
    return;
  }
  if (o.mode === 'static') { vx0 = 0; vx1 = L.width; }
  else if (o.mode === 'bars') {
    const per = Math.max(1, o.perView | 0); const gidx = Math.floor(cb / per);
    vx0 = bars[gidx * per].x0; vx1 = bars[Math.min(n - 1, gidx * per + per - 1)].x1;
  } else {
    const per = Math.max(1, o.perView);
    const vw = Math.min(L.width, avg * per);
    const pos = posAt(o, t), smooth = viewAt(o, t);
    // the score slides under a still line, like a film; at the very start and end the music stays
    // put and the line moves instead, so there is never paper without music (or an empty band)
    vx0 = softClamp(smooth - vw * (o.band ? 0.22 : 0.32), 0, Math.max(0, L.width - vw), vw * 0.12);
    vx1 = vx0 + vw;
    if (b >= 0 && b < n) cursor = pos;
  }
  paint(vx0, vx1, 1, cursor, null);
  function paint(vx0, vx1, alpha, cursor, fullW, inkA = 1, joint = null) {
  o._motion = { vx0, cursor };   // (where the page and the line are: for the tests)
  // (the music made bigger smoothly, never in squares)
  g.imageSmoothingEnabled = true; g.imageSmoothingQuality = 'high';
  const vw = vx1 - vx0, vh = L.height, SK = st.k || 1;
  const band = !!o.band && o.mode === 'scroll';
  const boxW0 = band ? W : W * o.size, scale = boxW0 / (fullW || vw), boxW = vw * scale, boxH = vh * scale * (joint ? joint.r(o) : 1) * (band ? o.size / 0.96 : 1);
  const pad = band ? Math.round(boxH * 0.06) : o.look === 'lines' ? 0 : Math.round(boxW * 0.025);
  const cx = band ? W / 2 : clamp(o.pos.x * W, boxW / 2 + pad, W - boxW / 2 - pad), cy = clamp(o.pos.y * H, boxH / 2 + pad, H - boxH / 2 - pad);
  const x = cx - boxW / 2, y = cy - boxH / 2;
  // only the part of the strip that exists (an endless line starts and ends in blank paper)
  const sx0 = Math.max(0, vx0), sx1 = Math.min(L.width, vx1);
  const blit = joint ? (img) => {
    // bar by bar, each into its place on the shared grid (cut at the edges of the view)
    const ja = g.globalAlpha; g.globalAlpha = ja * inkA;
    bars.forEach((bb, k) => {
      const c0 = joint.cx[k], c1 = c0 + joint.cw[k], d0 = Math.max(c0, vx0), d1 = Math.min(c1, vx1);
      if (d1 <= d0) return;
      const s0 = bb.x0 + ((d0 - c0) / (c1 - c0)) * (bb.x1 - bb.x0), s1 = bb.x0 + ((d1 - c0) / (c1 - c0)) * (bb.x1 - bb.x0);
      if (s1 - s0 > 0.5) g.drawImage(img, s0 * SK, 0, (s1 - s0) * SK, vh * SK, x + (d0 - vx0) * scale, y, (d1 - d0) * scale, boxH);
    });
    g.globalAlpha = ja;
  } : (img) => { if (sx1 > sx0 && inkA > 0.001) { const a0 = g.globalAlpha; g.globalAlpha = a0 * inkA; g.drawImage(img, sx0 * SK, 0, (sx1 - sx0) * SK, vh * SK, x + (sx0 - vx0) * scale, y, (sx1 - sx0) * scale, boxH); ; g.globalAlpha = a0; } };
  o._box = { x: x - pad, y: y - pad, w: boxW + pad * 2, h: boxH + pad * 2, W, H };
  g.save(); g.globalAlpha = (o.opacity ?? 1) * alpha;
  if (o.look !== 'lines') {
    g.save(); g.shadowColor = 'rgba(0,0,0,0.35)'; g.shadowBlur = boxW * 0.03; g.shadowOffsetY = boxW * 0.006;
    g.fillStyle = o.look === 'warm' ? '#FBF6EA' : '#ffffff';
    const rad = band ? 0 : Math.round(boxW * 0.02);
    rr(g, x - (band ? 0 : pad), y - pad, boxW + (band ? 0 : pad * 2), boxH + pad * 2, rad); g.fill(); g.restore();
    g.save(); rr(g, x - (band ? 0 : pad), y - pad, boxW + (band ? 0 : pad * 2), boxH + pad * 2, rad); g.clip();
    if (o.highlight && b >= 0 && b < n && o.mode !== 'scroll' && bars[b].x0 >= vx0 - 1 && bars[b].x1 <= vx1 + 1) {
      g.fillStyle = 'rgba(255, 210, 90, 0.32)';
      const hx0 = x + (bars[b].x0 - vx0) * scale, hx1 = x + (bars[b].x1 - vx0) * scale;
      g.fillRect(hx0, y - pad, hx1 - hx0, boxH + pad * 2);
    }
    if (o.look === 'warm') g.globalCompositeOperation = 'multiply';
    blit(st.canvas);
    g.restore();
  } else {
    const ink = o.ink || '#ffffff';
    const mk = tintedMask(st, ink);
    // a soft shadow keeps white lines readable on bright video
    const shade = o.shade !== false;   // the soft shade behind the lines can be switched off
    g.save(); g.shadowColor = ink === '#ffffff' ? 'rgba(0,0,0,0.55)' : 'rgba(255,255,255,0.6)'; g.shadowBlur = shade ? Math.max(2, boxW * 0.006) : 0;
    if (band && shade) {
      // a soft band behind the music, fading out above and below (no hard dark strip)
      g.save(); g.shadowBlur = 0;
      const col = ink === '#ffffff' ? '0,0,0' : '255,255,255', a = ink === '#ffffff' ? 0.45 : 0.55, f = boxH * 0.22;
      const gr = g.createLinearGradient(0, y - pad - f, 0, y + boxH + pad + f);
      const H2 = boxH + pad * 2 + f * 2, e = f / H2;
      gr.addColorStop(0, `rgba(${col},0)`); gr.addColorStop(e, `rgba(${col},${a})`); gr.addColorStop(1 - e, `rgba(${col},${a})`); gr.addColorStop(1, `rgba(${col},0)`);
      g.fillStyle = gr; g.fillRect(0, y - pad - f, W, H2); g.restore();
    }
    blit(mk); g.restore();
    if (o.highlight && b >= 0 && b < n && o.mode !== 'scroll' && bars[b].x0 >= vx0 - 1 && bars[b].x1 <= vx1 + 1) {
      const hx0 = x + (bars[b].x0 - vx0) * scale, hx1 = x + (bars[b].x1 - vx0) * scale;
      g.fillStyle = ink === '#ffffff' ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.1)'; rr(g, hx0, y, hx1 - hx0, boxH, boxW * 0.01); g.fill();
    }
  }
  if (cursor !== null && o.highlight !== false) {
    const cxp = x + (cursor - vx0) * scale;
    g.fillStyle = o.look === 'lines' ? (o.ink === '#000000' ? 'rgba(216,52,58,0.9)' : 'rgba(255,90,95,0.95)') : 'rgba(216,52,58,0.85)';
    const lw = Math.max(2, boxW * 0.003);
    if (o.band) g.fillRect(cxp - lw / 2, y - boxH * 0.06, lw, boxH * 1.12); else g.fillRect(cxp - lw / 2, y + boxH * 0.12, lw, boxH * 0.76);
  }
  g.restore();
  }
}

function drawImage(g, W, H, o, t) {
  if (t < o.t0 || t > o.t1) return;
  const bmp = ST.images.get(o.id); if (!bmp) return;
  const w = W * o.size, h = (w * bmp.height) / bmp.width;
  const x = clamp(o.pos.x * W - w / 2, 0, W - w), y = clamp(o.pos.y * H - h / 2, 0, H - h);
  let a = o.opacity ?? 1;
  if (o.fade) a *= clamp(Math.min((t - o.t0) / 0.35, (o.t1 - t) / 0.35), 0, 1);
  g.save(); g.globalAlpha = a;
  if (o.round) { rr(g, x, y, w, h, w * 0.04); g.clip(); }
  g.drawImage(bmp, x, y, w, h);
  g.restore();
  o._box = { x, y, w, h, W, H };
}
function frame() {
  if (!ST.media || $('#studio').hidden) return;
  const c = $('#stCanvas'), g = c.getContext('2d');
  const { W, H, q } = ST.view;
  g.setTransform(q, 0, 0, q, 0, 0);
  drawFrame(g, W, H, ST.media.currentTime);
  // selection frame on the preview
  const o = selected();
  if (o && o._box && !ST.playing) { g.save(); g.strokeStyle = 'rgba(255,255,255,0.9)'; g.setLineDash([12, 8]); g.lineWidth = 3 / q; g.strokeRect(o._box.x, o._box.y, o._box.w, o._box.h); g.restore(); }
  updateHead();
}
function loop() { frame(); lsKeep(); if (ST.playing) ST.raf = requestAnimationFrame(loop); }
function play() {
  if (ST.media.currentTime >= ST.P.trim.b - 0.05 || ST.media.currentTime < ST.P.trim.a) ST.media.currentTime = ST.P.trim.a;
  ST.media.play().catch(() => {}); ST.playing = true; syncPlay(); loop();
  ST.stopAt = setInterval(() => { if (ST.media.currentTime >= ST.P.trim.b) { pause(); if (ST.tapping) finishTap(); } }, 50);
}
function pause() { if (!ST.media) return; ST.media.pause(); ST.playing = false; clearInterval(ST.stopAt); cancelAnimationFrame(ST.raf); syncPlay(); frame(); }
function syncPlay() { const b = $('#stPlay'); b.innerHTML = ST.playing ? '<svg><use href="#i-pause"/></svg><span>Pause</span>' : '<svg><use href="#i-play"/></svg><span>Play</span>'; if (!ST.playing) ST.playing = false; }
const selected = () => (ST.sel ? ST.P.overlays.find((o) => o.id === ST.sel.id) : null);

// =====================================================================
// Timeline
// =====================================================================
// (the part of the recording the timeline shows: all of it, or a few seconds around a trim handle held)
const tview = () => (ST.tv && ST.tv.b > ST.tv.a ? ST.tv : { a: 0, b: ST.dur });
function tx(t) { const lane = $('#stScoreLane').getBoundingClientRect(); const v = tview(); return ((t - v.a) / (v.b - v.a)) * lane.width; }
function tAt(clientX) { const lane = $('#stScoreLane').getBoundingClientRect(); const v = tview(); return clamp(v.a + ((clientX - lane.left) / lane.width) * (v.b - v.a), 0, ST.dur); }
function renderTimeline() {
  const ruler = $('#stRuler'); ruler.textContent = '';
  const V = tview(), span = V.b - V.a;
  const LW = $('#stScoreLane').getBoundingClientRect().width || 600;
  // (marks far enough apart to read: about one per 64 points)
  const step = [0.25, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300].find((q) => (span / q) * 64 <= LW) || 600;
  for (let s = Math.ceil(V.a / step) * step; s <= V.b + 1e-6; s += step) { const sp = el('span', '', step < 1 || s % 1 ? fmt(s) : fmt(s).replace(/\.\d$/, '')); sp.style.left = tx(s) + 'px'; ruler.append(sp); }
  const sl = $('#stScoreLane'); sl.textContent = '';
  const o = ST.P.overlays.find((x) => x.kind === 'score');
  if (o && o.times) {
    const { b } = barAt(o, ST.media ? ST.media.currentTime : 0);
    o.layout.bars.forEach((bar, k) => {
      const d = el('div', 'st-bar' + (k === b ? ' cur' : ''), String(k + 1));
      const l0 = tx(Math.max(0, o.times[k])); d.style.left = l0 + 'px'; d.style.width = Math.max(2, tx(o.times[k + 1]) - l0 - 1) + 'px';
      const edge = el('span', 'edge'); edge.dataset.k = k; d.append(edge);
      d.addEventListener('pointerdown', (e) => { if (e.target === edge) return; ST.sel = { id: o.id }; seek(Math.max(0, o.times[k] + 0.01)); renderSide(); });
      sl.append(d);
    });
    // the end of the last bar
    const end = el('div', 'st-bar'); end.style.left = tx(o.times[o.times.length - 1]) + 'px'; end.style.width = '0'; end.style.border = '0'; const e2 = el('span', 'edge'); e2.dataset.k = o.times.length - 1; end.append(e2); sl.append(end);
  } else {
    const hint = el('div', 'st-bar', 'Add the score to see its bars here'); hint.style.left = '6px'; hint.style.right = '6px'; hint.style.background = 'transparent'; hint.style.border = '1px dashed var(--line)'; hint.style.color = 'var(--muted)'; sl.append(hint);
  }
  const il = $('#stImgLane'); il.textContent = '';
  for (const im of ST.P.overlays.filter((x) => x.kind === 'image')) {
    const d = el('div', 'st-img' + (ST.sel && ST.sel.id === im.id ? ' sel' : ''));
    d.style.left = tx(im.t0) + 'px'; d.style.width = Math.max(14, tx(im.t1) - tx(im.t0)) + 'px';
    const bmp = ST.images.get(im.id);
    d.append(el('span', '', 'Image'));
    const l = el('span', 'edge l'), r = el('span', 'edge r'); l.dataset.img = im.id; l.dataset.side = 'a'; r.dataset.img = im.id; r.dataset.side = 'b';
    d.append(l, r); d.dataset.img = im.id; d.dataset.side = 'move';
    d.addEventListener('pointerdown', () => { ST.sel = { id: im.id }; renderSide(); renderTimeline(); frame(); });
    il.append(d);
    void bmp;
  }
  // trim handles, and the yellow frame between them
  placeTrim();
  updateHead();
}
function updateHead() {
  if (!ST.media) return;
  const t = ST.media.currentTime;
  $('#stHead').style.left = (40 + tx(t)) + 'px';
  $('#stTime').textContent = fmt(t) + ' / ' + fmt(ST.dur);
  const o = ST.P.overlays.find((x) => x.kind === 'score');
  if (o && o.times) {
    const { b } = barAt(o, t);
    const bars = $('#stScoreLane').querySelectorAll('.st-bar');
    bars.forEach((d, k) => d.classList.toggle('cur', k === b));
  }
}
function placeTrim() {
  const W = $('#stScoreLane').getBoundingClientRect().width;
  const xa = tx(ST.P.trim.a), xb = tx(ST.P.trim.b);
  const L = $('#stTrimL'), R = $('#stTrimR'), box = $('#stTrimBox');
  L.style.left = (40 + xa) + 'px'; R.style.left = (40 + xb) + 'px';
  L.style.visibility = xa >= -8 && xa <= W + 8 ? '' : 'hidden'; R.style.visibility = xb >= -8 && xb <= W + 8 ? '' : 'hidden';
  const c0 = clamp(xa, 0, W), c1 = clamp(xb, 0, W);
  box.style.left = (40 + c0) + 'px'; box.style.width = Math.max(0, c1 - c0) + 'px';
}
// The strip under the trim handles: small pictures of the video along it (as in Photos), with the
// sound's waveform over their lower part; what is trimmed away is dimmed.
const STRIP = { pics: [], key: '', busy: false };
async function makeStrip() {
  if (ST.take.kind !== 'video' || !ST.url) return;
  const key = ST.take.id; if (STRIP.key === key || STRIP.busy) return;
  STRIP.busy = true; STRIP.key = key; STRIP.pics = [];
  try {
    const v = document.createElement('video'); v.muted = true; v.playsInline = true; v.preload = 'auto'; v.src = ST.url;
    await new Promise((res) => { v.onloadeddata = res; v.onerror = res; setTimeout(res, 4000); });
    const ar = (v.videoWidth || 9) / (v.videoHeight || 16);
    const h = 112, w = Math.max(24, Math.round(h * ar));   // (sharp on the iPad's screen)
    const n = clamp(Math.round(ST.dur * 2), 12, 120);   // (two a second, enough to open out a little)
    for (let k = 0; k < n; k++) {
      if (STRIP.key !== key) return;
      const t = ((k + 0.5) / n) * ST.dur;
      await new Promise((res) => { const done = () => { v.removeEventListener('seeked', done); res(); }; v.addEventListener('seeked', done); v.currentTime = t; setTimeout(done, 1200); });
      const c = document.createElement('canvas'); c.width = w; c.height = h;
      try { c.getContext('2d').drawImage(v, 0, 0, w, h); } catch {}
      STRIP.pics.push({ t, c });
      if (k % 6 === 5) drawWave();
    }
    v.removeAttribute('src'); v.load();
  } finally { STRIP.busy = false; drawWave(); }
}
function drawWave() {
  const c = $('#stWave'); const r = c.getBoundingClientRect(); const dpr = Math.min(2, devicePixelRatio || 1);
  c.width = Math.max(10, r.width * dpr); c.height = Math.max(10, r.height * dpr);
  const g = c.getContext('2d'); g.clearRect(0, 0, c.width, c.height);
  const V = tview(), span = V.b - V.a;
  const X = (t) => ((t - V.a) / span) * c.width;
  const ax = X(ST.P.trim.a), bx = X(ST.P.trim.b);
  const pics = STRIP.key === (ST.take && ST.take.id) ? STRIP.pics : [];
  if (pics.length) {
    // the pictures, side by side, each the one nearest its place in time
    const ph = c.height, pw = Math.max(4, Math.round(ph * (pics[0].c.width / pics[0].c.height)));
    g.save(); rr(g, 0, 0, c.width, c.height, 9 * dpr); g.clip();
    for (let x = 0; x < c.width; x += pw) {
      const t = V.a + ((x + pw / 2) / c.width) * span;
      let best = pics[0]; for (const p of pics) if (Math.abs(p.t - t) < Math.abs(best.t - t)) best = p;
      g.drawImage(best.c, x, 0, pw, ph);
    }
    g.restore();
  }
  const peaks = ST.take.peaks;
  if (peaks && peaks.length) {
    let max = 0.0001; for (const p of peaks) max = Math.max(max, p);
    const n = Math.floor(c.width / (3 * dpr));
    const H = pics.length ? c.height * 0.42 : c.height - 10 * dpr, base = pics.length ? c.height - 3 * dpr : c.height / 2;
    for (let i = 0; i < n; i++) {
      const t0 = V.a + (i / n) * span, t1 = V.a + ((i + 1) / n) * span;
      const a = Math.floor((t0 / ST.dur) * peaks.length), b = Math.max(a + 1, Math.floor((t1 / ST.dur) * peaks.length));
      let m = 0; for (let j = Math.max(0, a); j < Math.min(peaks.length, b); j++) m = Math.max(m, peaks[j]);
      const h = Math.max(1.5 * dpr, Math.pow(m / max, 0.8) * H);
      const x = i * 3 * dpr;
      if (pics.length) { g.fillStyle = '#ffffff'; g.globalAlpha = 0.85; g.fillRect(x, base - h, 2 * dpr, h); }
      else { g.fillStyle = css('--accent-text'); g.globalAlpha = x >= ax && x <= bx ? 0.75 : 0.22; g.fillRect(x, (c.height - h) / 2, 2 * dpr, h); }
    }
  }
  g.globalAlpha = 1;
  // (what is cut away, dimmed)
  if (pics.length) { g.fillStyle = 'rgba(0,0,0,0.55)'; if (ax > 0) g.fillRect(0, 0, Math.min(c.width, ax), c.height); if (bx < c.width) g.fillRect(Math.max(0, bx), 0, c.width - Math.max(0, bx), c.height); }
}
function seek(t) { ST.media.currentTime = clamp(t, 0, ST.dur); frame(); }
// the time over a trim handle while it is moved (to the hundredth when opened out)
function trimTip(side) {
  const tip = $('#stTrimTip'), t = ST.P.trim[side];
  tip.hidden = false; tip.style.left = (40 + tx(t)) + 'px';
  const s2 = ST.tv ? (Math.floor(t / 60) + ':' + (t % 60).toFixed(2).padStart(5, '0')) : fmt(t);
  tip.innerHTML = ''; tip.append(s2); const sm = document.createElement('small'); sm.textContent = '· ' + fmt(ST.P.trim.b - ST.P.trim.a); tip.append(sm);
  { const W = $('#stScoreLane').getBoundingClientRect().width, half = (tip.offsetWidth || 120) / 2; tip.style.left = (40 + clamp(tx(t), half - 46, W - half)) + 'px'; }
}
// opening the strip out around a handle held still, and closing it again (a short glide each way)
function zoomTrim(drag, open) {
  const from = tview(), full = { a: 0, b: ST.dur };
  let to = full;
  if (open) {
    const span = clamp(ST.dur / 8, 2, 8), h = ST.P.trim[drag.side];
    if (span >= ST.dur * 0.8) return;
    // (the handle stays under the finger while the strip opens out around it)
    const frac = (h - from.a) / Math.max(0.001, from.b - from.a);
    const a2 = clamp(h - frac * span, 0, ST.dur - span); to = { a: a2, b: a2 + span };
    drag.zoomed = true; try { navigator.vibrate && navigator.vibrate(8); } catch {}
  }
  $('#stTrim' + (drag.side === 'a' ? 'L' : 'R')).classList.toggle('zoom', open);
  $('.st-media').classList.toggle('zoomed', open);
  const t0 = performance.now(), ms = 220;
  cancelAnimationFrame(ST.zoomRaf);
  const stepZ = () => {
    const f = Math.min(1, (performance.now() - t0) / ms), e2 = 1 - Math.pow(1 - f, 3);
    const v = { a: from.a + (to.a - from.a) * e2, b: from.b + (to.b - from.b) * e2 };
    ST.tv = open || f < 1 ? v : null;
    renderTimeline(); drawWave();
    if (f < 1) ST.zoomRaf = requestAnimationFrame(stepZ);
    else if (open) { drag.off = ST.P.trim[drag.side] - tAt(drag.lastX ?? drag.x0); trimTip(drag.side); }
  };
  stepZ();
}
function wireTimeline() {
  const tracks = $('#stTracks');
  let drag = null;
  tracks.addEventListener('pointerdown', (e) => {
    const t = tAt(e.clientX);
    const edge = e.target.closest('.edge');
    const trim = e.target.closest('.st-trim');
    const img = e.target.closest('[data-img]');
    try { tracks.setPointerCapture(e.pointerId); } catch {}
    if (trim) {
      // (held still for a moment: the strip opens out around the handle, for the exact moment)
      const side = trim.id === 'stTrimL' ? 'a' : 'b';
      drag = { kind: 'trim', side, x0: e.clientX, off: ST.P.trim[side] - t, hold: setTimeout(() => { if (drag && drag.kind === 'trim' && !drag.moved) zoomTrim(drag, true); }, 380) };
      trimTip(side); pause(); return;
    }
    if (edge && edge.dataset.k !== undefined) { drag = { kind: 'bar', k: +edge.dataset.k }; pause(); return; }
    if (img) { const o = ST.P.overlays.find((x) => x.id === img.dataset.img); drag = { kind: 'img', o, side: img.dataset.side, t0: t, a: o.t0, b: o.t1 }; return; }
    drag = { kind: 'seek' }; seek(t);
  });
  tracks.addEventListener('pointermove', (e) => {
    if (!drag) return;
    const t = tAt(e.clientX);
    if (drag.kind === 'seek') seek(t);
    else if (drag.kind === 'trim') {
      if (Math.abs(e.clientX - drag.x0) > 6) drag.moved = true;
      drag.lastX = e.clientX;
      const want = t + drag.off;
      if (drag.side === 'a') ST.P.trim.a = clamp(want, 0, ST.P.trim.b - 0.5); else ST.P.trim.b = clamp(want, ST.P.trim.a + 0.5, ST.dur);
      // (opened out: the view follows the handle when it nears an edge)
      if (ST.tv && drag.zoomed) { const v = ST.tv, span = v.b - v.a, h = ST.P.trim[drag.side]; if (h < v.a + span * 0.12 || h > v.b - span * 0.12) { const a2 = clamp(h - span / 2, 0, Math.max(0, ST.dur - span)); ST.tv = { a: a2, b: a2 + span }; drag.off = ST.P.trim[drag.side] - tAt(e.clientX); } }
      seek(ST.P.trim[drag.side]); renderTimeline(); drawWave(); trimTip(drag.side);
    }
    else if (drag.kind === 'bar') {
      const o = ST.P.overlays.find((x) => x.kind === 'score'); const T = o.times, k = drag.k;
      T[k] = clamp(t, k > 0 ? T[k - 1] + 0.08 : Math.min(0, T[0]), k < T.length - 1 ? T[k + 1] - 0.08 : ST.dur);
      o.synced = 'hand';
      // (two parts on one grid keep the same bar times: a bar moved is moved in both)
      const two = scoreLines()[1]; if (two && two.times && two.times.length === T.length) { two.times[k] = T[k]; two.synced = 'hand'; }
      seek(Math.max(0, T[k] + 0.01)); renderTimeline();
    } else if (drag.kind === 'img') {
      const o = drag.o, d = t - drag.t0;
      if (drag.side === 'a') o.t0 = clamp(drag.a + d, 0, o.t1 - 0.3);
      else if (drag.side === 'b') o.t1 = clamp(drag.b + d, o.t0 + 0.3, ST.dur);
      else { const len = drag.b - drag.a; o.t0 = clamp(drag.a + d, 0, ST.dur - len); o.t1 = o.t0 + len; }
      renderTimeline(); seek(o.t0 + 0.05);
    }
  });
  const end = () => {
    if (drag && drag.kind === 'trim') { clearTimeout(drag.hold); if (drag.zoomed) zoomTrim(drag, false); $('#stTrimTip').hidden = true; }
    if (drag && drag.kind !== 'seek') saveSoon(); const was = drag && drag.kind; drag = null; if ((was === 'bar' || was === 'seek') && ST.sel && ST.P.overlays.find((x) => x.id === ST.sel.id && x.kind === 'score')) renderSide(); };
  tracks.addEventListener('pointerup', end); tracks.addEventListener('pointercancel', end);
}
// Drag the score or an image on the picture to place it; pinch or the slider to size it.
function wireStage() {
  const c = $('#stCanvas');
  let d = null;
  c.addEventListener('pointerdown', (e) => {
    const r = c.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * ST.view.W, py = ((e.clientY - r.top) / r.height) * ST.view.H;
    const hit = [...ST.P.overlays].reverse().find((o) => o._box && px >= o._box.x && px <= o._box.x + o._box.w && py >= o._box.y && py <= o._box.y + o._box.h && (o.kind !== 'image' || (ST.media.currentTime >= o.t0 && ST.media.currentTime <= o.t1)));
    try { c.setPointerCapture(e.pointerId); } catch {}
    if (hit) { ST.sel = { id: hit.id }; d = { o: hit, x: e.clientX, y: e.clientY, pos: { ...hit.pos } }; renderSide(); frame(); return; }
    // drag the video itself to choose the part on show (filled formats)
    d = { video: true, x: e.clientX, y: e.clientY, pan: { ...(ST.P.pan || { x: 0.5, y: 0.5 }) } };
  });
  c.addEventListener('pointermove', (e) => {
    if (!d) return;
    const r = c.getBoundingClientRect();
    if (d.o) { d.o.pos = { x: clamp(d.pos.x + (e.clientX - d.x) / r.width, 0, 1), y: clamp(d.pos.y + (e.clientY - d.y) / r.height, 0, 1) }; frame(); }
    else if (d.video && ST.P.fit !== 'fit') { ST.P.pan = { x: clamp(d.pan.x - (e.clientX - d.x) / r.width, 0, 1), y: clamp(d.pan.y - (e.clientY - d.y) / r.height, 0, 1) }; frame(); }
  });
  const end = () => { if (d) saveSoon(); d = null; };
  c.addEventListener('pointerup', end); c.addEventListener('pointercancel', end);
}

// =====================================================================
// Side panel: what is selected
// =====================================================================
function seg(items, value, on) {
  const s = el('div', 'seg full');
  for (const [v, label] of items) { const b = el('button', v === value ? 'on' : '', label); b.addEventListener('click', () => on(v)); s.append(b); }
  return s;
}
function slider(label, value, min, max, step, fmtv, on) {
  const row = el('label', 'st-row'); row.append(el('span', '', label));
  const i = el('input'); i.type = 'range'; i.min = min; i.max = max; i.step = step; i.value = value;
  const v = el('span', 'num', fmtv(value));
  i.addEventListener('input', () => { v.textContent = fmtv(+i.value); on(+i.value); });
  row.append(i, v); return row;
}
function renderSide() {
  // on a phone a swipe up or down scrolls the Studio, except over something chosen to move
  try { $('#stCanvas').style.touchAction = matchMedia('(max-width: 600px), (max-height: 500px)').matches && !ST.sel ? 'pan-y' : 'none'; } catch {}
  const side = $('#stSide'); side.textContent = '';
  const o = selected();
  $('#stEmpty').hidden = !!ST.P.overlays.find((x) => x.kind === 'score');
  const change = (fn, re = false) => { fn(); saveSoon(); frame(); if (re) renderSide(); };
  if (o && o.kind === 'score') {
    const ls = scoreLines(), two = ls.length > 1;
    side.append(el('h3', '', two ? 'Score: two lines' : 'Score'));
    // (two lines: which one these settings are for; the look is the same for both)
    if (two) side.append(seg(ls.map((x, i) => [x.id, i === 0 ? 'Line 1 (top)' : 'Line 2 (under)']), o.id, (v) => { ST.sel = { id: v }; renderSide(); frame(); }));
    side.append(el('p', 'hint', `${o.title} · ${o.layout.bars.length} bars`));
    const looks = el('div', 'st-looks');
    for (const [k, label] of [['paper', 'Paper'], ['warm', 'Warm'], ['lines', 'Just the lines']]) {
      const b = el('button', o.look === k ? 'on' : ''); const sw = el('i', k); b.append(sw, document.createTextNode(label));
      b.addEventListener('click', () => change(() => { sharedChange(o, (x) => { x.look = k; }); stackLines(); }, true)); looks.append(b);
    }
    side.append(looks);
    if (o.look === 'lines') side.append(seg([['#ffffff', 'White ink'], ['#000000', 'Black ink']], o.ink, (v) => change(() => { sharedChange(o, (x) => { x.ink = v; }); }, true)));
    if (o.look === 'lines') side.append(seg([['on', 'Soft shade behind'], ['off', 'No shade']], o.shade === false ? 'off' : 'on', (v) => change(() => { sharedChange(o, (x) => { x.shade = v === 'on'; }); }, true)));
    side.append(el('div', 'ctl-head', 'On screen'));
    side.append(seg([['scroll', 'Endless line'], ['lines', 'Line by line'], ['bars', 'Bars'], ['static', 'All']], o.mode, (v) => change(() => { sharedChange(o, (x) => { x.mode = v; }); stackLines(); }, true)));
    if (o.mode === 'scroll') { const bl = el('label', 'check'); const bc = el('input'); bc.type = 'checkbox'; bc.checked = !!o.band; bl.append(bc, document.createTextNode(' Full width, sliding under a still line')); bc.addEventListener('change', () => change(() => { sharedChange(o, (x) => { x.band = bc.checked; }); stackLines(); }, true)); side.append(bl); }
    if (o.mode !== 'static' && o.mode !== 'lines') side.append(slider('Bars', o.perView, 1, Math.min(8, o.layout.bars.length), 1, (x) => String(x), (v) => change(() => { sharedChange(o, (x) => { x.perView = v; }); stackLines(); })));
    side.append(slider('Size', Math.round(o.size * 100), 30, 100, 1, (x) => x + '%', (v) => change(() => { sharedChange(o, (x) => { x.size = v / 100; }); stackLines(); })));
    side.append(seg([['0.16', 'Top'], ['0.5', 'Middle'], ['0.82', 'Bottom']], String((two ? ls[0] : o).pos.y), (v) => change(() => { (two ? ls[0] : o).pos = { x: 0.5, y: +v }; stackLines(); }, true)));
    side.append(slider('Opacity', Math.round((o.opacity ?? 1) * 100), 30, 100, 1, (x) => x + '%', (v) => change(() => { sharedChange(o, (x) => { x.opacity = v / 100; }); })));
    const hl = el('label', 'check'); const cb = el('input'); cb.type = 'checkbox'; cb.checked = o.highlight !== false; hl.append(cb, document.createTextNode(o.mode === 'scroll' ? ' Show where you are (a red line)' : ' Light up the bar being played'));
    cb.addEventListener('change', () => change(() => { o.highlight = cb.checked; })); side.append(hl);
    side.append(el('p', 'hint', 'Drag the score on the picture to move it.'));
    const sync = el('section', 'sub-card');
    const sh = el('div', 'sub-head'); sh.append(el('h3', '', 'Timing'));
    sync.append(sh);
    const state = el('p', 'st-sync-state ' + (o.synced === 'auto' && o.syncInfo && o.syncInfo.good > 0.55 ? 'good' : o.synced === 'even' ? 'warn' : ''),
      o.synced === 'auto' ? `Follows your playing${o.syncInfo ? ` (${Math.round(o.syncInfo.good * 100)}% of notes matched)` : ''}.` : o.synced === 'tap' ? 'Set by your taps.' : o.synced === 'hand' ? 'Adjusted by hand on the timeline.' : 'Spread evenly. Line it up with your playing:');
    sync.append(state);
    const row = el('div', 'row-even');
    const auto = el('button', 'btn small primary'); auto.append(el('span', '', 'Follow my playing')); auto.disabled = !ST.pcm;
    auto.addEventListener('click', () => (scoreLines().length === 2 && scoreLines().includes(o) ? syncBoth() : autoSync(o)));
    const tapB = el('button', 'btn small', 'Tap along'); tapB.addEventListener('click', () => startTap(o));
    row.append(auto, tapB); sync.append(row);
    // from the bar where the picture is now (put right by hand first, by dragging its start): the
    // bars before it stay as they are
    const here = o.times ? barAt(o, ST.media ? ST.media.currentTime + 0.02 : 0).b : -1;
    if (here > 0 && here < o.layout.bars.length) {
      const row2 = el('div', 'row-even');
      const fromB = el('button', 'btn small'); fromB.append(el('span', '', `Follow from bar ${here + 1}`)); fromB.disabled = !ST.pcm;
      fromB.addEventListener('click', () => autoSync(o, { from: here }));
      const tapFrom = el('button', 'btn small', `Tap from bar ${here + 1}`); tapFrom.addEventListener('click', () => startTap(o, here));
      row2.append(fromB, tapFrom); sync.append(row2);
    }
    sync.append(el('p', 'hint', 'Drag the start of a bar on the timeline to move it. Then “Follow from bar…” follows your playing again from there; the bars before stay as they are.'));
    side.append(sync);
    // another part, on a line of its own under this one
    if (!two) {
      const add2 = el('button', 'btn'); add2.append(el('span', '', 'Add a second line (another part)'));
      add2.addEventListener('click', () => addScore({ second: true }));
      side.append(add2);
      side.append(el('p', 'hint', 'For a duet: the other player’s part under yours, each line following its own player.'));
    }
    const del = el('button', 'btn danger-text', two ? 'Remove this line' : 'Remove the score'); del.addEventListener('click', () => { ST.P.overlays = ST.P.overlays.filter((x) => x !== o); const rest = scoreLines(); if (rest.length === 1) delete rest[0].line; ST.sel = rest[0] ? { id: rest[0].id } : null; saveSoon(); renderSide(); renderTimeline(); frame(); });
    side.append(del);
    return;
  }
  if (o && o.kind === 'image') {
    side.append(el('h3', '', 'Image'));
    side.append(slider('Size', Math.round(o.size * 100), 10, 100, 1, (x) => x + '%', (v) => change(() => { o.size = v / 100; })));
    side.append(slider('Opacity', Math.round((o.opacity ?? 1) * 100), 10, 100, 1, (x) => x + '%', (v) => change(() => { o.opacity = v / 100; })));
    side.append(seg([['0.16', 'Top'], ['0.5', 'Middle'], ['0.82', 'Bottom']], String(o.pos.y), (v) => change(() => { o.pos = { x: 0.5, y: +v }; }, true)));
    for (const [k, label] of [['round', 'Rounded corners'], ['fade', 'Fade in and out']]) {
      const l = el('label', 'check'); const cb = el('input'); cb.type = 'checkbox'; cb.checked = !!o[k]; l.append(cb, document.createTextNode(' ' + label));
      cb.addEventListener('change', () => change(() => { o[k] = cb.checked; })); side.append(l);
    }
    side.append(el('p', 'hint', 'On the timeline, drag the image to move it in time, or its ends to make it shorter or longer. Drag it on the picture to place it.'));
    const del = el('button', 'btn danger-text', 'Remove the image'); del.addEventListener('click', () => { ST.P.overlays = ST.P.overlays.filter((x) => x !== o); ST.sel = null; saveSoon(); renderSide(); renderTimeline(); frame(); });
    side.append(del);
    return;
  }
  renderFormat(side);
}
// The look of the video: a few ready-made looks, and four simple controls on top
function renderLook(side) {
  const card = el('section', 'sub-card st-look');
  const head = el('div', 'sub-head'); head.append(el('h3', '', 'Look'));
  const reset = el('button', 'btn small ghost', 'Reset'); reset.hidden = !ST.P.look || isNeutral(ST.P.look);
  reset.addEventListener('click', () => { ST.P.look = null; saveSoon(); frame(); renderSide(); });
  head.append(reset); card.append(head);
  // Auto: the video looked at, and set for its light, colour, noise and detail
  const autoRow = el('div', 'st-auto');
  const autoB = el('button', 'btn small ' + (ST.P.look && ST.P.look.auto && ST.P.look.autoOn !== false ? 'on-auto' : 'primary'));
  autoB.append(el('span', '', ST.P.look && ST.P.look.auto && ST.P.look.autoOn !== false ? 'Auto is on' : 'Auto: make it look its best'));
  autoB.addEventListener('click', async () => {
    const lk = ST.P.look || (ST.P.look = { preset: 'natural', adj: {} });
    if (lk.auto && lk.autoOn !== false) { lk.autoOn = false; saveSoon(); frame(); renderSide(); return; }
    autoB.disabled = true; autoB.querySelector('span').textContent = 'Looking at the video…';
    try { const fr = await grabFrames(8); if (!fr.length) throw new Error('no frames'); lk.auto = autoLook(fr); lk.autoOn = true; if (lk.autoAmt === undefined) lk.autoAmt = 1; } catch (e) { console.warn(e); D.toast('The video could not be looked at just now. Play it for a moment, then try again.', 4000); }
    saveSoon(); frame(); renderSide();
  });
  autoRow.append(autoB);
  card.append(autoRow);
  if (ST.P.look && ST.P.look.auto && ST.P.look.autoOn !== false) {
    card.append(slider('Auto amount', Math.round((ST.P.look.autoAmt ?? 1) * 100), 0, 150, 1, (x) => x + '%', (v) => { ST.P.look.autoAmt = v / 100; saveSoon(); frame(); }));
    card.append(el('p', 'hint', 'Light, white balance, contrast, noise and sharpness set for this video. A look and the sliders go on top.'));
  }
  const cur = (ST.P.look && ST.P.look.preset) || 'natural';
  const strip = el('div', 'st-look-strip');
  for (const [k, v] of Object.entries(LOOKS)) {
    const b = el('button', k === cur ? 'on' : ''); const c = el('canvas'); c.width = 96; c.height = 120;
    b.append(c, el('span', '', v.label));
    lookThumb(c, { preset: k });
    b.addEventListener('click', () => { const keep = ST.P.look || {}; ST.P.look = { preset: k, adj: {}, ...(keep.auto ? { auto: keep.auto, autoOn: keep.autoOn, autoAmt: keep.autoAmt } : {}) }; saveSoon(); frame(); renderSide(); });
    strip.append(b);
  }
  card.append(strip);
  const adj = () => { if (!ST.P.look) ST.P.look = { preset: 'natural', adj: {} }; if (!ST.P.look.adj) ST.P.look.adj = {}; return ST.P.look.adj; };
  const ctl = (key, label, lo = -100, hi = 100) => slider(label, Math.round(((ST.P.look && ST.P.look.adj && ST.P.look.adj[key]) || 0) * 100), lo, hi, 1, (x) => (x > 0 ? '+' : '') + x, (v) => { adj()[key] = v / 100; reset.hidden = isNeutral(ST.P.look); saveSoon(); frame(); });
  card.append(ctl('light', 'Light'), ctl('contrast', 'Contrast'), ctl('warmth', 'Warmth'), ctl('colour', 'Colour'));
  const more = el('details', 'st-look-more'); more.append(el('summary', '', 'More'));
  more.append(ctl('clarity', 'Clarity'), ctl('sharp', 'Sharpness'), ctl('denoise', 'Less noise', 0, 100), ctl('shadows', 'Shadows'), ctl('highlights', 'Highlights'), ctl('tint', 'Tint'), ctl('vignette', 'Vignette', 0, 100));
  card.append(more);
  side.append(card);
}
// a few frames from across the video (for Auto), the playing place put back after
async function grabFrames(n) {
  const m = ST.media, back = m.currentTime, out = [];
  if (!m.videoWidth) return out;
  const a = ST.P.trim ? ST.P.trim.a : 0, b = ST.P.trim ? ST.P.trim.b : ST.dur;
  for (let i = 0; i < n; i++) {
    const t = a + ((b - a) * (i + 0.5)) / n;
    await new Promise((res) => { const done = () => { m.removeEventListener('seeked', done); res(); }; m.addEventListener('seeked', done); m.currentTime = t; setTimeout(done, 1500); });
    // (the new frame must be there before it is copied: on an iPad it comes a moment after the jump)
    await new Promise((res) => { let ok = false; const go = () => { if (!ok) { ok = true; res(); } }; if (m.requestVideoFrameCallback) m.requestVideoFrameCallback(go); setTimeout(go, 160); });
    const c = document.createElement('canvas'); const k = 192 / Math.max(m.videoWidth, m.videoHeight); c.width = Math.round(m.videoWidth * k); c.height = Math.round(m.videoHeight * k);
    const g2 = c.getContext('2d', { willReadFrequently: true }); g2.drawImage(m, 0, 0, c.width, c.height);
    // (an empty frame, not yet drawn, is not looked at)
    const d = g2.getImageData(0, 0, c.width, c.height).data; let sum = 0; for (let j = 0; j < d.length; j += 16) sum += d[j] + d[j + 1] + d[j + 2];
    if (sum / (d.length / 16) > 4) out.push(c);
  }
  m.currentTime = back;
  return out;
}
function renderFormat(side) {
  side.append(el('h3', '', 'Picture'));
  const f = el('div', 'st-formats');
  for (const [k, [w, h, label]] of Object.entries(FORMATS)) {
    const b = el('button', ST.P.format === k ? 'on' : ''); const i = el('i');
    const vw = k === 'orig' ? (ST.media.videoWidth || 16) : w, vh = k === 'orig' ? (ST.media.videoHeight || 9) : h;
    const s = 26 / Math.max(vw, vh); i.style.width = Math.round(vw * s) + 'px'; i.style.height = Math.round(vh * s) + 'px';
    b.append(i, el('span', '', k === 'orig' ? 'Original' : `${k} ${label}`.replace(' Reels', '').replace(' Post', '').replace(' Square', '').replace(' Wide', '')));
    b.title = label;
    b.addEventListener('click', () => { ST.P.format = k; saveSoon(); sizeCanvas(); renderSide(); frame(); });
    f.append(b);
  }
  side.append(f);
  side.append(el('p', 'hint', ST.P.format === '9:16' ? 'Vertical, for Reels and Stories.' : ST.P.format === '4:5' ? 'For Instagram posts.' : ST.P.format === '1:1' ? 'Square.' : ST.P.format === '16:9' ? 'Wide, for YouTube.' : 'As it was filmed.'));
  if (ST.take.kind === 'video') {
    side.append(seg([['fill', 'Fill the frame'], ['fit', 'Show it all']], ST.P.fit || 'fill', (v) => { ST.P.fit = v; saveSoon(); frame(); renderSide(); }));
    if (ST.P.fit !== 'fit') side.append(el('p', 'hint', 'Drag the video to choose the part on show.'));
  }
  if (ST.take.kind === 'video') renderLook(side);
  side.append(el('div', 'ctl-head', 'Trim'));
  side.append(el('p', 'hint', `From ${fmt(ST.P.trim.a)} to ${fmt(ST.P.trim.b)}. Drag the dark handles on the timeline.`));
  const sd = el('section', 'sub-card'); sd.append(el('h3', '', 'Sound'));
  sd.append(seg([['dry', 'Dry'], ['studio', 'Studio'], ['hall', 'Hall'], ['church', 'Church']], ST.P.sound.room, (v) => { ST.P.sound.room = v; saveSoon(); lsApply(); renderSide(); }));
  sd.append(slider('Room', Math.round((ST.P.sound.wet ?? 0.18) * 100), 0, 100, 1, (x) => x + '%', (v) => { ST.P.sound.wet = v / 100; saveSoon(); lsApply(); }));
  const l = el('label', 'check'); const cb = el('input'); cb.type = 'checkbox'; cb.checked = ST.P.sound.level !== false; l.append(cb, document.createTextNode(' Bring the sound to a good level'));
  cb.addEventListener('change', () => { ST.P.sound.level = cb.checked; saveSoon(); lsApply(); }); sd.append(l);
  sd.append(el('p', 'hint', 'Room and level are added in the exported video.'));
  side.append(sd);
}

// =====================================================================
// Images
// =====================================================================
async function addImage(file) {
  const o = { id: uid(), kind: 'image', img: file, size: 0.4, pos: { x: 0.5, y: 0.2 }, opacity: 1, round: true, fade: true, t0: ST.media.currentTime, t1: Math.min(ST.P.trim.b, ST.media.currentTime + 4) };
  ST.P.overlays.push(o); await prepareOverlay(o); ST.sel = { id: o.id };
  saveSoon(); renderSide(); renderTimeline(); frame();
}

// =====================================================================
// Export: plays the edit once and records it (real time)
// =====================================================================
async function exportVideo() {
  if (videoOutNative()) {
    try { if (await exportNative()) return; }
    catch (err) { console.error(err); try { D.log && D.log('studio export (native): ' + (err && err.message)); } catch {} }
    if (ST.exportCancelled) { ST.exportCancelled = false; return; }
    // (if it could not be made that way, it is made the old way: played once and recorded)
  }
  return exportRealtime();
}
async function exportRealtime() {
  pause();
  const [W, H] = outSize();
  const canvas = document.createElement('canvas'); canvas.width = W; canvas.height = H;
  const g = canvas.getContext('2d');
  const ctx = getCtx();
  const a = ST.P.trim.a, b = ST.P.trim.b, total = b - a;
  // the sound: the recording with the room and level chosen
  const dest = ctx.createMediaStreamDestination();
  let src = null, mediaSrc = null;
  if (ST.pcm) {
    const i0 = Math.floor(a * ST.sr), i1 = Math.min(ST.pcm.length, Math.ceil(b * ST.sr));
    const part = ST.pcm.subarray(i0, i1);
    const buf = ctx.createBuffer(1, Math.max(1, part.length), ST.sr); buf.copyToChannel(part, 0);
    src = ctx.createBufferSource(); src.buffer = buf;
    const level = ctx.createGain(); const pk = peakOf(part); level.gain.value = ST.P.sound.level !== false && pk > 0.001 ? Math.min(8, 0.89 / pk) : 1;
    src.connect(level);
    level.connect(dest);
    const room = ROOMS[ST.P.sound.room];
    if (room) { const conv = ctx.createConvolver(); conv.buffer = makeImpulse(ctx, room); const wet = ctx.createGain(); wet.gain.value = (ST.P.sound.wet ?? 0.18) * 0.9; level.connect(conv).connect(wet).connect(dest); }
  } else if (ST.take.kind === 'video') {
    try { mediaSrc = ctx.createMediaElementSource(ST.media); mediaSrc.connect(dest); mediaSrc.connect(ctx.destination); } catch { /* no sound */ }
  }
  const stream = canvas.captureStream(30);
  for (const t of dest.stream.getAudioTracks()) stream.addTrack(t);
  const type = ['video/mp4;codecs=avc1.640028,mp4a.40.2', 'video/mp4', 'video/webm;codecs=vp9,opus', 'video/webm'].find((t) => window.MediaRecorder && MediaRecorder.isTypeSupported(t)) || '';
  let rec;
  try { rec = new MediaRecorder(stream, { mimeType: type || undefined, videoBitsPerSecond: W * H > 1.5e6 ? 10_000_000 : 6_000_000, audioBitsPerSecond: 192_000 }); }
  catch (err) { D.toast('Video export needs iPadOS 15 or newer.'); return; }
  const chunks = [];
  rec.ondataavailable = (e) => { if (e.data && e.data.size) chunks.push(e.data); };
  let cancelled = false;
  ST.busyCancel = () => { cancelled = true; try { rec.stop(); } catch {} ST.media.pause(); };
  ST.exporting = true; lsStop();
  busy('Making the video…', 'It plays once while it is recorded.', 0);
  const done = new Promise((res) => { rec.onstop = res; });
  ST.media.muted = !!src;
  ST.media.currentTime = a;
  await new Promise((r) => { ST.media.onseeked = () => { ST.media.onseeked = null; r(); }; setTimeout(r, 1500); });
  rec.start(500);
  const t0 = ctx.currentTime + 0.15;
  if (src) src.start(t0);
  await new Promise((r) => setTimeout(r, 150));
  if (ST.take.kind === 'video') ST.media.play().catch(() => {});
  const audioOnly = ST.take.kind !== 'video';
  await new Promise((resolve) => {
    const tick = () => {
      if (cancelled) { resolve(); return; }
      const t = audioOnly ? a + (ctx.currentTime - t0) : ST.media.currentTime;
      // keep the video in step with the sound
      if (!audioOnly && src && Math.abs(ST.media.currentTime - (a + ctx.currentTime - t0)) > 0.12) ST.media.currentTime = a + ctx.currentTime - t0;
      if (audioOnly) try { ST.media.currentTime = t; } catch {}
      drawFrame(g, W, H, t, true);
      busy('Making the video…', `${fmt(t - a)} of ${fmt(total)}`, clamp((t - a) / total, 0, 1));
      if (t >= b - 0.02) { resolve(); return; }
      requestAnimationFrame(tick);
    };
    tick();
  });
  try { rec.stop(); } catch {}
  await done;
  ST.media.pause(); ST.media.muted = false; ST.exporting = false;
  if (src) try { src.stop(); } catch {}
  if (mediaSrc) try { mediaSrc.disconnect(); } catch {}
  busy(null);
  if (cancelled) { D.toast('Export cancelled.'); return; }
  const blob = new Blob(chunks, { type: (type || 'video/mp4').split(';')[0] });
  if (blob.size < 5000) { D.toast('The video could not be made.'); return; }
  await keepExport(blob, a, b, total);
}
// the finished video: kept in Recordings, then shared
async function keepExport(blob, a, b, total, { share = true } = {}) {
  const id = uid();
  const take = { id, kind: 'video', mime: blob.type, scoreId: ST.take.scoreId, page: ST.take.page, name: (ST.take.name || 'Video') + ' · Studio', created: Date.now(), mirror: false, fav: false, thumb: await videoThumb(blob) };
  await db.put('files', { id: 'video:' + id, data: blob });
  if (ST.pcm) {
    const part = ST.pcm.slice(Math.floor(a * ST.sr), Math.min(ST.pcm.length, Math.ceil(b * ST.sr)));
    take.sr = ST.sr; take.dur = part.length / ST.sr; take.peaks = computePeaks(part); take.peak = peakOf(part); take.pcm = true;
    await db.put('files', { id: 'audio:' + id, data: part });
  } else { take.pcm = false; take.dur = total; }
  await db.put('takes', take);
  D.onSaved && D.onSaved(take);
  D.toast('Saved in Recordings.', 2500);
  const ext = blob.type.includes('webm') ? '.webm' : '.mp4';
  if (share) shareChooser(blob, (take.name || 'Studio').replace(/[\\/:*?"<>|]+/g, '') + ext);
  return take;
}

// ---------- Export in the app: every picture drawn here, the film made by iOS ----------
// Nothing is played in real time: each picture of the video is drawn exactly (the video's own frame
// at that moment, the score over it) and handed to iOS, which makes the film at the video's own frame
// rate and a high quality, with the original sound (or the one Studio makes with its room). Never a
// picture dropped because the iPad was busy, and the video is only made smaller once.
const videoOutNative = () => !!(window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.standVideoOut && (window.standCaps || {}).videoOut);
const OUTQ = new Map();   // id -> { evs: [], wake }
window.standVideoOutEvent = (ev) => { const q = ev && OUTQ.get(ev.id); if (!q) return; q.evs.push(ev); if (q.wake) { const w = q.wake; q.wake = null; w(); } };
async function outNext(id, types, ms = 120000) {
  const q = OUTQ.get(id); const t0 = Date.now();
  for (;;) {
    const k = q.evs.findIndex((e) => e.type === 'error' || types.includes(e.type));
    if (k >= 0) { const ev = q.evs.splice(k, 1)[0]; if (ev.type === 'error') throw new Error(ev.message || 'export'); return ev; }
    if (Date.now() - t0 > ms) throw new Error('no answer from iOS (' + types.join('/') + ')');
    await new Promise((r) => { q.wake = r; setTimeout(r, 1000); });
  }
}
const toB64 = (blob) => new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(String(r.result).split(',')[1] || ''); r.onerror = () => rej(r.error); r.readAsDataURL(blob); });
// a file handed to iOS in pieces (never whole in one message)
async function outUpload(id, op, blob, name) {
  const post = (m) => window.webkit.messageHandlers.standVideoOut.postMessage({ op, id, ...m });
  post({ part: 'begin', name }); await outNext(id, ['chunk']);
  const CH = 3 << 20;
  for (let o = 0; o < blob.size; o += CH) { post({ part: 'chunk', data: await toB64(blob.slice(o, o + CH)) }); await outNext(id, ['chunk']); }
  post({ part: 'end' });
  return op === 'src' ? outNext(id, ['src']) : outNext(id, ['chunk']);
}
// the sound as Studio makes it (level and room), worked out at once, not in real time
async function studioSound(a, b, { wetOnly = false } = {}) {
  const sr = ST.sr, i0 = Math.floor(a * sr), i1 = Math.min(ST.pcm.length, Math.ceil(b * sr));
  const part = ST.pcm.subarray(i0, i1);
  const room = ROOMS[ST.P.sound.room];
  const tail = room ? Math.round(sr * 2) : 0;
  const oc = new OfflineAudioContext(2, Math.max(1, part.length + tail), sr);
  const buf = oc.createBuffer(1, Math.max(1, part.length), sr); buf.copyToChannel(part, 0);
  const src = oc.createBufferSource(); src.buffer = buf;
  const level = oc.createGain(); const pk = peakOf(part); level.gain.value = ST.P.sound.level !== false && pk > 0.001 ? Math.min(8, 0.89 / pk) : 1;
  src.connect(level); if (!wetOnly) level.connect(oc.destination);
  if (room) { const conv = oc.createConvolver(); conv.buffer = makeImpulse(oc, room); const wet = oc.createGain(); wet.gain.value = (ST.P.sound.wet ?? 0.18) * 0.9; level.connect(conv).connect(wet).connect(oc.destination); }
  src.start(0);
  const out = await oc.startRendering();
  const n = part.length;   // (as long as the pictures)
  return encodeWav([out.getChannelData(0).subarray(0, n), out.getChannelData(1).subarray(0, n)], sr);
}
async function exportNative({ share = true } = {}) {
  pause();
  const [W, H] = outSize();
  const a = ST.P.trim.a, b = ST.P.trim.b, total = b - a;
  const id = 'x' + uid();
  OUTQ.set(id, { evs: [], wake: null });
  const post = (m) => window.webkit.messageHandlers.standVideoOut.postMessage({ id, ...m });
  let cancelled = false; ST.exportCancelled = false;
  ST.busyCancel = () => { cancelled = true; ST.exportCancelled = true; try { post({ op: 'cancel' }); } catch {} };
  ST.exporting = true; lsStop();
  busy('Making the video…', 'Getting the video ready.', 0);
  const isVideo = ST.take.kind === 'video';
  try {
    // the original video goes to iOS first: its frame rate, and its own sound
    let fps = 30, srcInfo = null;
    post({ op: 'begin', w: W, h: H, fps: 30 });
    await outNext(id, ['ready']);
    if (isVideo) {
      const vf = await db.get('files', 'video:' + ST.take.id);
      if (vf && vf.data) {
        srcInfo = await outUpload(id, 'src', vf.data, ST.take.mime && /mp4/.test(ST.take.mime) ? 'v.mp4' : 'v.mov');
        if (srcInfo.fps > 1) fps = Math.max(24, Math.min(60, Math.round(srcInfo.fps)));
      }
    }
    if (cancelled) return false;
    // (the film at the video's own frame rate)
    if (fps !== 30) { post({ op: 'set', fps }); await outNext(id, ['ready']); }
    // the sound: the original as it is (only made louder when Studio levels it), unless a room is
    // added: then the one Studio makes
    let audio = 'none', gain = 1;
    const room = ROOMS[ST.P.sound.room];
    if (isVideo && srcInfo && srcInfo.hasAudio && (!room || (ST.pcm && total <= 240))) {
      // the original sound as it is (both sides, its own quality); a room is added over it
      audio = room ? 'mix' : 'src';
      if (ST.P.sound.level !== false && ST.pcm) { const i0 = Math.floor(a * ST.sr), i1 = Math.min(ST.pcm.length, Math.ceil(b * ST.sr)); const pk = peakOf(ST.pcm.subarray(i0, i1)); gain = pk > 0.001 ? Math.min(8, 0.89 / pk) : 1; }
      if (room) { busy('Making the video…', 'Making the sound.', 0.01); await outUpload(id, 'wav', await studioSound(a, b, { wetOnly: true })); }
    } else if (ST.pcm) {
      busy('Making the video…', 'Making the sound.', 0.01);
      await outUpload(id, 'wav', await studioSound(a, b));
      audio = 'wav';
    }
    if (cancelled) return false;
    // every picture, drawn exactly at its moment
    const canvas = document.createElement('canvas'); canvas.width = W; canvas.height = H;
    const g = canvas.getContext('2d');
    const m = ST.media;
    const N = Math.max(1, Math.round(total * fps));
    const seekTo = (t) => new Promise((res) => {
      let ok = false; const done = (how) => { if (ok) return; ok = true; SEEKS[how] = (SEEKS[how] || 0) + 1; res(); };
      // (the picture shown from i/fps to (i+1)/fps: asking for its middle never lands on the one before)
      if (m.requestVideoFrameCallback) m.requestVideoFrameCallback(() => done('frame'));
      m.addEventListener('seeked', () => setTimeout(() => done('seeked'), m.requestVideoFrameCallback ? 120 : 30), { once: true });
      m.currentTime = t; setTimeout(() => done('late'), 3000);
    });
    let pending = null; const t0 = performance.now(); const SEEKS = {}; let tDraw = 0, tJpg = 0, tSeek = 0;
    let sent = 0, skipped = 0, rate = 0.5;
    const progress = (tt) => {
      const f = clamp((tt - a) / Math.max(0.01, total), 0, 1), left = f > 0.03 ? ((performance.now() - t0) / f) * (1 - f) / 1000 : null;
      busy('Making the video…', `${fmt(tt - a)} of ${fmt(total)}` + (left ? ` · about ${fmt(left)} left` : ''), 0.03 + 0.92 * f);
    };
    // one picture to iOS, in order (with its moment in the video, so the film keeps the video's own timing)
    let chain = Promise.resolve();
    const hand = (jpgP, t) => { const k = sent++; chain = chain.then(async () => {
      const data = await toB64(await jpgP);
      if (pending) await pending;
      if (cancelled) return;
      post({ op: 'frame', i: k, t: t - a, data });
      pending = outNext(id, ['ack'], 60000);
    }); return chain; };
    if (isVideo && m.requestVideoFrameCallback) {
      // The video plays (silently) and stops at each of its pictures: it is drawn the moment it is
      // shown, and the video goes on to the next. Every picture once, at its own time, without
      // looking for each one (much faster than seeking). A picture the iPad still let pass is looked
      // for and drawn before going on, so none is ever missing.
      await seekTo(a);
      m.muted = true; m.playbackRate = rate = 1;
      let last = null, inFlight = 0, drain = null;
      const doFrame = (t) => {
        const q = performance.now();
        drawFrame(g, W, H, t, true);
        tDraw += performance.now() - q;
        const jp = new Promise((r) => canvas.toBlob(r, 'image/jpeg', 0.97));
        inFlight++;
        hand(jp, t).then(() => { inFlight--; if (drain && inFlight < 3) { const d = drain; drain = null; d(); } });
        if (sent % 6 === 0) progress(t);
      };
      // (the first picture: the one shown at the start of the part)
      doFrame(a); last = a;
      await new Promise((resolve, reject) => {
        let over = false;
        const finish = () => { if (over) return; over = true; m.pause(); document.removeEventListener('visibilitychange', wake); resolve(); };
        const wake = () => { if (!document.hidden && !over && m.paused && !busyNow) m.play().catch(() => {}); };
        let busyNow = false;
        document.addEventListener('visibilitychange', wake);
        const onFrame = async (now, md) => {
          if (over) return;
          m.pause(); busyNow = true;
          try {
            if (cancelled) { finish(); return; }
            const t = md.mediaTime;
            if (t >= b - 0.25 / fps) { finish(); return; }
            if (t >= a - 0.5 / fps && (last === null || t > last + 0.001)) {
              if (last !== null && t - last > 1.6 / fps) {
                // (pictures passed by unseen: each looked for in turn, then back to this one)
                const n = Math.round((t - last) * fps) - 1;
                for (let k = 1; k <= n; k++) { const tt = last + (k * (t - last)) / (n + 1); await seekTo(tt + 0.3 / fps); doFrame(tt); skipped++; }
                await seekTo(t + 0.3 / fps);
              }
              doFrame(t); last = t;
              // (never more than a few pictures waiting for iOS: the video waits for them)
              if (inFlight >= 6) await new Promise((r) => { drain = r; });
            }
            busyNow = false;
            if (cancelled) { finish(); return; }
            m.requestVideoFrameCallback(onFrame);
            if (!document.hidden) m.play().catch((e) => { over = true; reject(e); });
          } catch (e) { over = true; reject(e); }
        };
        m.requestVideoFrameCallback(onFrame);
        m.addEventListener('ended', finish, { once: true });
        m.play().catch(reject);
      });
      m.playbackRate = 1; m.muted = false;
      await chain;
      if (cancelled) return false;
      SEEKS.playback = sent; SEEKS.skipped = skipped;
    } else {
      // (no way to see each picture as it is shown: each one looked for in turn, or a recording
      // without pictures)
      for (let i = 0; i < N; i++) {
        if (cancelled) return false;
        const t = a + i / fps;
        let q = performance.now();
        if (isVideo) await seekTo(Math.min(b - 0.001, t + 0.5 / fps));
        tSeek += performance.now() - q; q = performance.now();
        drawFrame(g, W, H, t, true);
        tDraw += performance.now() - q;
        await hand(new Promise((r) => canvas.toBlob(r, 'image/jpeg', 0.97)), t);
        if (i % 5 === 0) progress(t);
      }
    }
    if (pending) await pending;
    busy('Making the video…', 'Putting the sound in.', 0.96);
    post({ op: 'end', audio, a, b, gain, dur: total });
    const done = await outNext(id, ['done'], 600000);
    const res = await fetch(done.path); if (!res.ok) throw new Error('the film is missing');
    const blob = new Blob([await res.blob()], { type: 'video/mp4' });
    try { window.webkit.messageHandlers.standDone.postMessage({ path: done.path }); } catch {}
    busy(null);
    window.__studioExport = { w: W, h: H, fps, frames: sent, size: blob.size, audio, seeks: SEEKS, ms: { seek: Math.round(tSeek), draw: Math.round(tDraw), jpg: Math.round(tJpg), all: Math.round(performance.now() - t0) } };
    await keepExport(blob, a, b, total, { share });
    return true;
  } finally {
    ST.exporting = false; OUTQ.delete(id);
    if (cancelled) { busy(null); D.toast('Export cancelled.'); }
  }
}
// Where the finished video goes: straight to one of the apps people post in (the video is put in
// Photos and that app opens), or anywhere else with the usual share sheet.
// (plain symbols in the app's own style, not the apps' logos)
const SOCIAL = [
  ['instagram', 'Instagram', 'Reels and posts · 9:16 or 4:5', '<path d="M12 19s-6.5-4-6.5-8.6A3.6 3.6 0 0 1 12 8.4a3.6 3.6 0 0 1 6.5 2c0 4.6-6.5 8.6-6.5 8.6z"/>'],
  ['tiktok', 'TikTok', 'Upright · 9:16', '<circle cx="8.5" cy="17" r="2.5"/><path d="M11 17V5l7 2v3"/>'],
  ['youtube', 'YouTube', 'Shorts 9:16 · videos 16:9', '<rect x="4" y="5" width="16" height="14" rx="1.5"/><path d="M8 5v14M16 5v14M4 9.5h4M4 14.5h4M16 9.5h4M16 14.5h4"/>'],
  ['facebook', 'Facebook', 'Any shape', '<circle cx="9" cy="9" r="3"/><path d="M3.5 19a5.5 5.5 0 0 1 11 0"/><circle cx="16.5" cy="10" r="2.4"/><path d="M15 14.2a4.5 4.5 0 0 1 5.5 4.8"/>'],
  ['whatsapp', 'WhatsApp', 'To a person or a group', '<path d="M5 6.5A2.5 2.5 0 0 1 7.5 4h9A2.5 2.5 0 0 1 19 6.5v7a2.5 2.5 0 0 1-2.5 2.5H11l-4 3.5V16h0.5A2.5 2.5 0 0 1 5 13.5z"/>'],
];
export function shareChooser(blob, name) {
  const native = !!(window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.standShare);
  const wrap = el('div', 'st-busy st-share'); const card = el('div', 'st-busy-card');
  card.append(el('b', '', 'Share your video'), el('span', 'hint', 'It is saved in Recordings. Send it to:'));
  const grid = el('div', 'st-share-grid');
  const go = (to) => { wrap.remove(); D.shareBlob(blob, name, to); };
  if (native) for (const [k, label, tip, svg] of SOCIAL) {
    const b = el('button', 'st-share-btn');
    b.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${svg}</svg>`;
    b.append(el('span', 'st-share-name', label), el('span', 'st-share-tip', tip));
    b.addEventListener('click', () => go(k)); grid.append(b);
  }
  const more = el('button', 'st-share-btn');
  more.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 15V4M8 8l4-4 4 4"/><path d="M6 11v8h12v-8"/></svg>';
  more.append(el('span', 'st-share-name', 'Other apps'), el('span', 'st-share-tip', 'Messages, Mail, Files, AirDrop…'));
  more.addEventListener('click', () => go('')); grid.append(more);
  const close = el('button', 'btn small', 'Not now'); close.addEventListener('click', () => wrap.remove());
  card.append(grid, close); wrap.append(card);
  wrap.addEventListener('click', (e) => { if (e.target === wrap) wrap.remove(); });
  $('#studio').append(wrap);
}

// =====================================================================
// Busy card
// =====================================================================
function busy(title, text, f) {
  const b = $('#stBusy');
  if (title === null) { b.hidden = true; ST.busyCancel = null; return; }
  b.hidden = false; $('#stBusyTitle').textContent = title; $('#stBusyText').textContent = text || '';
  $('#stBusyBar').style.width = Math.round((f || 0) * 100) + '%';
}

function wire() {
  if (!$('#studio')) return;
  $('#stBack').addEventListener('click', close);
  $('#stPlay').addEventListener('click', () => (ST.playing ? pause() : play()));
  $('#stAddScore').addEventListener('click', addScore);
  $('#stEmptyAdd').addEventListener('click', addScore);
  $('#stAddImage').addEventListener('click', () => $('#stImageInput').click());
  $('#stImageInput').addEventListener('change', (e) => { const f = e.target.files[0]; e.target.value = ''; if (f) addImage(f); });
  // (each line follows its own player: two lines, one after the other)
  $('#stSyncBtn').addEventListener('click', async () => { const ls = scoreLines(); if (!ls.length) { addScore(); return; } ST.sel = { id: ls[0].id }; renderSide(); if (ls.length === 2) await syncBoth(); else for (const o of ls) await autoSync(o); });
  $('#stFormatBtn').addEventListener('click', () => { ST.sel = null; renderSide(); frame(); });
  $('#stExport').addEventListener('click', exportVideo);
  $('#stTap').addEventListener('pointerdown', (e) => { e.preventDefault(); tap(e); });
  $('#stBusyCancel').addEventListener('click', () => { if (ST.busyCancel) ST.busyCancel(); busy(null); });
  wireTimeline(); wireStage();
  window.addEventListener('resize', () => { if (!$('#studio').hidden) { sizeCanvas(); renderTimeline(); drawWave(); frame(); } });
  document.addEventListener('keydown', (e) => {
    if ($('#studio').hidden || e.target.matches('input, select, textarea')) return;
    if (e.key === ' ') { e.preventDefault(); if (ST.tapping) tap(e); else ST.playing ? pause() : play(); }
    if (e.key === 'Escape' && ST.tapping) finishTap();
  });
}
export const _studio = ST;
export const _posAt = (o, t) => posAt(o, t);
export const _alignChords = (e, o) => alignChords(e, o);
// (for the tests: a score put on the video without the picker)
export async function _addScoreFrom(canvas, opt = {}) {
  const A = await analyse(canvas);
  const blob = await new Promise((res) => canvas.toBlob(res, 'image/png'));
  const o = { id: uid(), kind: 'score', title: 'Score', src: {}, img: blob, look: 'paper', ink: '#ffffff', mode: 'scroll', band: true, perView: 2, size: 0.96, pos: { x: 0.5, y: 0.78 }, opacity: 1, highlight: true, layout: stripLayout(A, canvas.width, canvas.height), times: null, synced: 'even' };
  o.times = evenTimes(o.layout.bars.length);
  putScore(o, !!opt.second);
  await prepareOverlay(o); ST.sel = { id: o.id }; stackLines(); renderSide(); renderTimeline(); frame();
  return o;
}
export const _frame = () => frame();
// (for the tests: following the playing, and one frame of the export drawn at a time)
export const _autoSync = (o, opt) => autoSync(o, opt);
export const _syncBoth = () => syncBoth();
export const _steady = (t) => steadyTimes(t);
export const _tapFrom = (o, k) => startTap(o, k);
export const _finishTap = () => finishTap();
export function _drawAt(canvas, t) { const [W, H] = outSize(); if (canvas.width !== W || canvas.height !== H) { canvas.width = W; canvas.height = H; } drawFrame(canvas.getContext('2d'), W, H, t, true); }
export const _stack = () => stackLines();
export const _exportNative = (o) => exportNative(o);
// A video cut in Recordings, by iOS: what is kept is copied as it is (nothing made again, nothing lost,
// at once). null where iOS cannot do it (then it is cut the old way).
export async function cutVideoNative(blob, segs, mime) {
  if (!videoOutNative()) return null;
  const ext = /mp4/.test(mime || blob.type || '') ? 'mp4' : 'mov';
  const id = 'c' + uid(); OUTQ.set(id, { evs: [], wake: null });
  const post = (m) => window.webkit.messageHandlers.standVideoOut.postMessage({ id, ...m });
  try {
    post({ op: 'begin', w: 16, h: 16, fps: 30 }); await outNext(id, ['ready']);
    await outUpload(id, 'src', blob, 'v.' + ext);
    post({ op: 'cut', segs: segs.map((q) => [+q[0], +q[1]]) });
    const done = await outNext(id, ['done'], 600000);
    const res = await fetch(done.path); if (!res.ok) throw new Error('missing');
    const out = new Blob([await res.blob()], { type: ext === 'mp4' ? 'video/mp4' : 'video/quicktime' });
    try { window.webkit.messageHandlers.standDone.postMessage({ path: done.path }); } catch {}
    return out;
  } finally { OUTQ.delete(id); }
}
