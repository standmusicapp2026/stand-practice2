// Choose music from a score: pick a score from the library (or a photo / PDF), turn to the page,
// and draw a loop around the part you want, like the Select tool in Markings. Returns the
// picture of that part at a good resolution, and where it came from.
import { db, getSetting, setSetting } from './db.js';
import { openDocument, mapDoc } from './score.js';
import { analyse } from './omr.js';
import { linesOf } from './picker-lines.js';
import { cleanPhoto } from './review.js';

const $ = (s) => document.querySelector(s);
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; };
const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

const PK = { picks: new Map(), doc: null, page: 0, resolve: null, box: null, pts: null, thumbs: [], lines: null, sel: [], trim: null, cut: null, linesCache: new Map() };

export function pickRegion(src, file, opts = {}) {
  return new Promise(async (resolve) => {
    PK.resolve = resolve; PK.box = null; PK.opts = opts; PK.picks = new Map(); PK.long = opts.long || 2600;
    $('#picker').hidden = false; $('#pkDone').disabled = true;
    $('#pkTitle').textContent = opts.title || 'Choose the music';
    $('#pkDone').textContent = opts.done || 'Use this';
    if (src === 'file' && file) { await openFile(file); return; }
    if (src && src.scoreId) { await openLibraryScore(src.scoreId, src.page || 0); return; }
    showLibrary();
  });
}
function finish(result) {
  $('#picker').hidden = true;
  // (a page still being read is let go: nothing keeps working, and warming the iPad, once closed)
  try { dropReader(); closeGrid(); } catch {}
  for (const u of PK.thumbs) URL.revokeObjectURL(u); PK.thumbs = [];
  if (PK.doc && PK.ownDoc) try { PK.doc.destroy(); } catch {}
  PK.doc = null;
  const r = PK.resolve; PK.resolve = null; if (r) r(result);
}
async function showLibrary() {
  $('#pkLib').hidden = false; $('#pkStage').hidden = true; $('#pkBar').hidden = true; $('#pkDone').hidden = true;
  $('#pkSub').textContent = 'Choose a score';
  const box = $('#pkLib'); box.textContent = '';
  const list = (await db.all('scores')).filter((s) => s.kind !== 'comp').sort((a, b) => (b.opened || b.added) - (a.opened || a.added));
  // a photo or a PDF from Files works too
  const fb = el('button', 'card pk-file');
  const ft = el('div', 'thumb pk-file-tile'); ft.innerHTML = '<svg><use href="#i-image"/></svg>';
  fb.append(ft, el('div', 'ttl', 'Photo or file'), el('div', 'cmp', 'An image or a PDF'));
  const inp = el('input'); inp.type = 'file'; inp.accept = 'image/*,application/pdf,.pdf'; inp.hidden = true;
  inp.addEventListener('change', () => { const f = inp.files[0]; if (f) openFile(f); });
  fb.addEventListener('click', () => inp.click());
  box.append(fb, inp);
  if (!list.length) box.append(el('p', 'hint', 'Your library is empty. Import a score first, or choose a photo.'));
  for (const s of list) {
    const b = el('button', 'card');
    const th = el('div', 'thumb');
    if (s.thumb) { const u = URL.createObjectURL(s.thumb); PK.thumbs.push(u); th.style.backgroundImage = `url(${u})`; }
    b.append(th, el('div', 'ttl', s.title), el('div', 'cmp', s.composer || ''));
    b.addEventListener('click', () => openLibraryScore(s.id, s.lastPage || 0));
    box.append(b);
  }
}
async function openLibraryScore(id, page) {
  const score = await db.get('scores', id);
  const file = score && await db.get('files', score.fileId);
  if (!file) return;
  const base = await openDocument(file);
  PK.picks = new Map();
  PK.doc = mapDoc(base, score.pageMap); PK.ownDoc = true; PK.source = { scoreId: id, title: score.title, fileId: score.fileId }; PK.kept = null;
  PK.page = Math.min(page, PK.doc.pages - 1);
  await showPage();
}
async function openFile(f) {
  const isPdf = f.type === 'application/pdf' || /\.pdf$/i.test(f.name);
  // a photo of a page: find the page and take the perspective out first (the reader straightens
  // small tilts itself, and does that better on the untouched picture)
  let img = f;
  if (!isPdf) { try { const r = await cleanPhoto(f, { maxSide: 3000, look: 'none', straight: false }); if (r.found) img = await new Promise((res) => r.canvas.toBlob(res, 'image/jpeg', 0.92)); } catch (err) { console.warn(err); } }
  const base = await openDocument(isPdf ? { kind: 'pdf', data: await f.arrayBuffer() } : { kind: 'images', data: [img] });
  PK.picks = new Map();
  PK.doc = mapDoc(base, null); PK.ownDoc = true; PK.source = { file: f.name }; PK.kept = null;
  PK.page = 0;
  await showPage();
}
async function showPage() {
  $('#pkLib').hidden = true; $('#pkStage').hidden = false; $('#pkBar').hidden = false; $('#pkDone').hidden = false;
  $('#pkSub').textContent = (PK.source.title || PK.source.file || '') ;
  $('#pkPageNo').textContent = `Page ${PK.page + 1} of ${PK.doc.pages}`;
  $('#pkPrev').disabled = PK.page === 0; $('#pkNext').disabled = PK.page >= PK.doc.pages - 1;
  // what was chosen on this page before (several pages can be chosen, one after another)
  const was = PK.picks.get(PK.page);
  PK.box = null; PK.sel = was ? was.sel.slice() : []; PK.trim = was ? { ...was.trim } : null; PK.cut = was && was.cut ? { ...was.cut } : null; PK.lines = null; $('#pkHandleL').hidden = $('#pkHandleR').hidden = $('#pkHandleT').hidden = $('#pkHandleB').hidden = true;
  syncDone();
  const stage = $('#pkStage'), r = stage.getBoundingClientRect();
  const [pw, ph] = PK.doc.sizes[PK.page];
  const k = Math.min((r.width - 28) / pw, (r.height - 28) / ph);
  const w = Math.round(pw * k), h = Math.round(ph * k);
  const pg = $('#pkPage'); pg.style.width = w + 'px'; pg.style.height = h + 'px';
  const dpr = Math.min(2, devicePixelRatio || 1);
  // (drawn aside, then shown: turning quickly never draws two pages into one picture at once)
  const page = PK.page, tmp = document.createElement('canvas');
  const d = $('#pkDraw'); d.width = w * dpr; d.height = h * dpr;
  drawSel();
  findLines();
  try { await PK.doc.render(page, tmp, w * dpr, h * dpr); } catch (err) { console.warn(err); }
  if (PK.doc && PK.page === page) { const c = $('#pkCanvas'); c.width = tmp.width; c.height = tmp.height; c.getContext('2d').drawImage(tmp, 0, 0); }
  tmp.width = tmp.height = 0;
}
// ---------- the lines of music on the page ----------
// Finding the lines takes the music reader a few seconds a page. So: the page shown is read first,
// in a thread of its own, then the pages next to it, while you look (turning to them, their lines
// are already there); what was read is kept for the score, so the next time it is there at once;
// and the page itself never waits for any of it (no reading on the screen's own thread, which froze
// every turn once the thread had been slow once).
let LW = null, lwBroken = false, lwBusy = null, lwSeq = 0;
const RQ = { want: [], running: false };
const pageKey = (page) => PK.doc.id + ':' + page + ':' + (PK.source.scoreId || PK.source.file || '');
// (v2: the lines know their staves; lines kept before that are read again once)
const keepKey = () => (PK.source.fileId ? 'pklines2:' + PK.source.fileId : null);
const origOf = (page) => { try { return String(PK.doc.orig ? PK.doc.orig(page) : page); } catch { return String(page); } };
function dropReader() {
  if (LW) { try { LW.terminate(); } catch {} LW = null; }
  if (lwBusy) { clearTimeout(lwBusy.t); lwBusy.res(null); lwBusy = null; }
  RQ.want = [];
}
function reader() {
  if (LW || lwBroken) return LW;
  if (typeof Worker === 'undefined' || typeof OffscreenCanvas === 'undefined' || typeof createImageBitmap === 'undefined') { lwBroken = true; return null; }
  try {
    LW = new Worker(new URL('./picker-worker.js', import.meta.url), { type: 'module' });
    LW.onmessage = (e) => { const d = e.data || {}; if (!lwBusy || lwBusy.id !== d.id) return; const b = lwBusy; lwBusy = null; clearTimeout(b.t); b.res(d.error ? [] : (d.lines || [])); };
    // (the thread itself could not be made to work: then, and only then, the page shown is read here)
    LW.onerror = () => { lwBroken = true; const b = lwBusy; lwBusy = null; if (b) { clearTimeout(b.t); b.res(null); } try { LW.terminate(); } catch {} LW = null; };
  } catch { lwBroken = true; LW = null; }
  return LW;
}
// read one page in the thread: its lines, or null (gave up: the music can still be chosen with a loop)
async function readInThread(page) {
  const [pw, ph] = PK.doc.sizes[page];
  const sc = Math.min(3, Math.max(1, 1700 / pw));
  const c = document.createElement('canvas');
  await PK.doc.render(page, c, pw * sc, ph * sc);
  if (!reader()) { c.width = c.height = 0; return null; }
  const bmp = await createImageBitmap(c).catch(() => null); c.width = c.height = 0;
  if (!bmp) return null;
  return new Promise((res) => {
    const id = ++lwSeq;
    // (a page that takes very long: let go, the thread made anew; nothing moves to the screen's thread)
    const t = setTimeout(() => { if (lwBusy && lwBusy.id === id) { lwBusy = null; try { LW.terminate(); } catch {} LW = null; res(null); } }, 30000);
    lwBusy = { id, page, res, t };
    try { LW.postMessage({ id, page: bmp }, [bmp]); } catch { clearTimeout(t); lwBusy = null; res(null); }
  });
}
async function keepLines(page, lines) {
  // (the picker closed while the page was being read: nothing to keep it for)
  if (!PK.doc) return;
  PK.linesCache.set(pageKey(page), lines);
  const k = keepKey(); if (!k || !lines) return;
  try { const cur = (await getSetting(k, null)) || {}; cur[origOf(page)] = lines; await setSetting(k, cur); } catch {}
}
async function keptLines(page) {
  if (!PK.doc) return null;
  const mem = PK.linesCache.get(pageKey(page)); if (mem) return mem;
  const k = keepKey(); if (!k) return null;
  try { if (!PK.kept) PK.kept = (await getSetting(k, null)) || {}; const l = PK.kept[origOf(page)]; if (l) { PK.linesCache.set(pageKey(page), l); return l; } } catch {}
  return null;
}
// what to read, most wanted first: the page shown, then the next, the one before, the one after next
function wantAround(page) {
  const n = PK.doc.pages, list = [page, page + 1, page - 1, page + 2].filter((p) => p >= 0 && p < n);
  RQ.want = list;
  // (the thread busy with a page far from here: let go, the page shown comes first)
  if (lwBusy && !list.includes(lwBusy.page)) { const b = lwBusy; lwBusy = null; clearTimeout(b.t); b.res('dropped'); try { LW.terminate(); } catch {} LW = null; }
  pump();
}
async function pump() {
  if (RQ.running || !PK.doc) return;
  RQ.running = true; let again = false;
  try {
    while (PK.doc && RQ.want.length) {
      const page = RQ.want[0];
      // (the pages at a glance are open: reading ahead waits, the small pages come first)
      if (RQ.paused && page !== PK.page) break;
      if (await keptLines(page)) { RQ.want.shift(); if (page === PK.page) linesReady(page); continue; }
      // (pages ahead: only once the screen is idle, and never while one is being turned)
      if (page !== PK.page) await idle();
      if (!PK.doc || RQ.want[0] !== page) continue;
      if (page === PK.page) $('#pkFinding').hidden = false;
      let lines = null; const doc0 = PK.doc;
      try {
        if (lwBroken) {
          // (no thread at all on this device: the page shown only, read here once it is shown)
          if (page === PK.page) { const [pw, ph] = PK.doc.sizes[page]; const sc = Math.min(3, Math.max(1, 1700 / pw)); const c = document.createElement('canvas'); await PK.doc.render(page, c, pw * sc, ph * sc); await idle(); if (PK.page === page) lines = linesOf(await analyse(c)); c.width = c.height = 0; }
        } else lines = await readInThread(page);
      } catch (err) { console.warn(err); lines = null; }
      if (lines === 'dropped') continue;
      // (closed, or another score opened, while this page was read: its lines belong to neither)
      if (!PK.doc || PK.doc !== doc0) { again = !!PK.doc; break; }
      if (RQ.want[0] === page) RQ.want.shift();
      if (lines) await keepLines(page, lines);
      if (page === PK.page) { if (lines) linesReady(page); else { PK.lines = []; linesReady(page, true); } }
    }
  } finally { RQ.running = false; if (again) setTimeout(pump, 0); }
}
function linesReady(page, failed) {
  if (PK.page !== page || !PK.doc) return;
  if (!failed) PK.lines = PK.linesCache.get(pageKey(page)) || [];
  $('#pkFinding').hidden = true;
  if (PK.lines && !PK.lines.length) $('#pkHint').textContent = 'Draw a loop around the music you want.';
  $('#pkAll').hidden = !(PK.lines && PK.lines.length);
  drawSel(); drawTray();
}
// the main thread reads only in small steps of time it can spare (never frozen for seconds)
const idle = () => new Promise((r) => (window.requestIdleCallback ? requestIdleCallback(() => r(), { timeout: 600 }) : setTimeout(r, 60)));
async function findLines() {
  const page = PK.page;
  const have = await keptLines(page);
  if (PK.page !== page) return;
  if (have) { PK.lines = have; linesReady(page); wantAround(page); return; }
  $('#pkFinding').hidden = false;
  // (a moment first: turning through the pages quickly reads none of the pages passed by)
  await new Promise((r) => setTimeout(r, 350));
  if (PK.page !== page || !PK.doc) return;
  wantAround(page);
}
// remember this page's choice, and whether there is anything to use
function savePick() {
  if (PK.sel.length && PK.trim) PK.picks.set(PK.page, { sel: PK.sel.slice(), trim: { ...PK.trim }, cut: PK.cut ? { ...PK.cut } : null }); else PK.picks.delete(PK.page);
  syncDone();
}
function syncDone() {
  $('#pkDone').disabled = !PK.box && !PK.picks.size;
  $('#pkClear').hidden = !PK.box && !PK.picks.size;
}
// the bar of a line under a point (0 = the first bar)
function barIdx(L, fx) { let j = 0; for (let k = 0; k < L.cuts.length - 1; k++) if (fx >= L.cuts[k]) j = k; return j; }
// the nearest line to a height (when the finger slides between lines)
function nearLine(fy) { let best = -1, bd = 1e9; (PK.lines || []).forEach((L, i) => { const d = fy < L.y0 ? L.y0 - fy : fy > L.y1 ? fy - L.y1 : 0; if (d < bd) { bd = d; best = i; } }); return best; }
// from one bar to another, across lines
function selectRange(i1, j1, i2, j2) {
  if (i2 < i1 || (i2 === i1 && j2 < j1)) [i1, j1, i2, j2] = [i2, j2, i1, j1];
  PK.sel = []; for (let i = i1; i <= i2; i++) PK.sel.push(i);
  PK.trim = { a: j1, b: j2 + 1 }; fitCut();
  PK.box = null;
  drawSel(); drawTray();
}
function lineAt(fx, fy) { return (PK.lines || []).findIndex((L) => fy >= L.y0 && fy <= L.y1 && fx >= L.x0 - 0.02 && fx <= L.x1 + 0.02); }
function toggleLine(i) {
  const k = PK.sel.indexOf(i);
  if (k >= 0) PK.sel.splice(k, 1); else PK.sel.push(i);
  PK.sel.sort((a, b) => a - b);
  PK.box = null; PK.trim = null;
  if (PK.sel.length) { const last = PK.lines[PK.sel[PK.sel.length - 1]]; PK.trim = { a: 0, b: last.cuts.length - 1 }; }
  fitCut();
  savePick();
  drawSel(); drawTray();
}
function rr(g, x, y, w, h, r) { g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r); g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath(); }
// ---------- some of the staves only (a piano's right hand, one part of a quartet) ----------
// The chosen lines' box can be pulled in from the top and from the bottom, a staff at a time. It
// works when every chosen line has the same staves (a page of piano music): the same staves of each.
function staffCount(lines, sel) {
  const ns = sel.map((i) => (lines[i] && lines[i].staves ? lines[i].staves.length : 0));
  return ns.length && ns.every((n) => n === ns[0]) ? ns[0] : 0;
}
function fitCut() {
  const n = PK.lines ? staffCount(PK.lines, PK.sel) : 0;
  if (n < 2 || !PK.cut) { PK.cut = null; return; }
  PK.cut.from = Math.max(0, Math.min(PK.cut.from, n - 1)); PK.cut.to = Math.max(PK.cut.from, Math.min(PK.cut.to, n - 1));
  if (PK.cut.from === 0 && PK.cut.to === n - 1) PK.cut = null;
}
// the top and bottom of a line, with only its kept staves (half way to the staves left out)
export function lineSpan(L, cut) {
  if (!cut || !L.staves || L.staves.length < 2) return [L.y0, L.y1];
  const S = L.staves, n = S.length, from = Math.min(cut.from, n - 1), to = Math.min(Math.max(cut.to, from), n - 1);
  const y0 = from === 0 ? L.y0 : (S[from - 1][1] + S[from][0]) / 2;
  const y1 = to === n - 1 ? L.y1 : (S[to][1] + S[to + 1][0]) / 2;
  return [y0, y1];
}
// The chosen lines get a blue box; its two ends can be pulled in, bar by bar.
const TRAY = {};
function drawTray() {
  const hl = $('#pkHandleL'), hr = $('#pkHandleR');
  const others = [...PK.picks.keys()].filter((p) => p !== PK.page);
  const elsewhere = others.length ? ` Also chosen: ${others.length === 1 ? 'page' : 'pages'} ${others.map((p) => p + 1).join(', ')}.` : '';
  const ht = $('#pkHandleT'), hb = $('#pkHandleB');
  if (!PK.sel.length || !PK.lines) { hl.hidden = hr.hidden = ht.hidden = hb.hidden = true; $('#pkHint').textContent = (PK.lines && PK.lines.length ? 'Tap a line, or slide from the first bar to the last.' : 'Draw a loop around the music you want.') + elsewhere; return; }
  const first = PK.lines[PK.sel[0]], last = PK.lines[PK.sel[PK.sel.length - 1]];
  const place = (h, L, f) => { const [y0, y1] = lineSpan(L, PK.cut); h.hidden = false; h.style.left = (f * 100) + '%'; h.style.top = ((y0 + 0.004) * 100) + '%'; h.style.height = ((y1 - y0 - 0.008) * 100) + '%'; };
  place(hl, first, first.cuts[PK.trim.a]);
  place(hr, last, last.cuts[PK.trim.b]);
  // top and bottom: only with two staves or more in the line
  const nst = staffCount(PK.lines, PK.sel);
  ht.hidden = hb.hidden = nst < 2;
  if (nst >= 2) {
    const fa = first.cuts[PK.trim.a], fb = PK.sel.length === 1 ? first.cuts[PK.trim.b] : first.x1;
    const la = PK.sel.length === 1 ? first.cuts[PK.trim.a] : last.x0, lb = last.cuts[PK.trim.b];
    ht.style.left = (((fa + fb) / 2) * 100) + '%'; ht.style.top = (lineSpan(first, PK.cut)[0] * 100) + '%';
    hb.style.left = (((la + lb) / 2) * 100) + '%'; hb.style.top = (lineSpan(last, PK.cut)[1] * 100) + '%';
  }
  const nb = barsChosen();
  const which = PK.cut ? (PK.cut.from === PK.cut.to ? ` Staff ${PK.cut.from + 1} of ${nst} only.` : ` Staves ${PK.cut.from + 1}–${PK.cut.to + 1} of ${nst}.`) : '';
  const how = nst >= 2 ? ' Pull the top or bottom to keep one staff.' : '';
  $('#pkHint').textContent = `${nb} ${nb === 1 ? 'bar' : 'bars'} on this page — pull the ends to change.` + which + (PK.cut ? '' : how) + (elsewhere || (PK.page < PK.doc.pages - 1 ? ' Turn the page to add more.' : ''));
}
function barsChosen() {
  let n = 0;
  PK.sel.forEach((i, k) => { const L = PK.lines[i]; const a = k === 0 ? PK.trim.a : 0, b = k === PK.sel.length - 1 ? PK.trim.b : L.cuts.length - 1; n += Math.max(0, b - a); });
  return n;
}
function wireTray() {
  for (const [id, end] of [['#pkHandleT', 'top'], ['#pkHandleB', 'bottom']]) {
    const h = $(id);
    h.addEventListener('pointerdown', (e) => {
      e.preventDefault(); e.stopPropagation(); try { h.setPointerCapture(e.pointerId); } catch {}
      const move = (ev) => {
        const n = staffCount(PK.lines, PK.sel); if (n < 2) return;
        const L = PK.lines[end === 'top' ? PK.sel[0] : PK.sel[PK.sel.length - 1]];
        const r = $('#pkDraw').getBoundingClientRect(), fy = (ev.clientY - r.top) / r.height;
        const cut = PK.cut ? { ...PK.cut } : { from: 0, to: n - 1 };
        // the nearest gap between staves (or the very edge) to the finger
        const edges = [L.y0, ...L.staves.slice(1).map((q, k) => (L.staves[k][1] + q[0]) / 2), L.y1];
        let best = 0, bd = 1e9; edges.forEach((y, k) => { const d = Math.abs(y - fy); if (d < bd) { bd = d; best = k; } });
        if (end === 'top') cut.from = Math.max(0, Math.min(best, cut.to)); else cut.to = Math.min(n - 1, Math.max(best - 1, cut.from));
        PK.cut = cut; fitCut();
        savePick(); drawSel(); drawTray();
      };
      const up = () => { h.removeEventListener('pointermove', move); h.removeEventListener('pointerup', up); h.removeEventListener('pointercancel', up); window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); };
      h.addEventListener('pointermove', move); h.addEventListener('pointerup', up); h.addEventListener('pointercancel', up);
      window.addEventListener('pointermove', move); window.addEventListener('pointerup', up);
    });
  }
  for (const [id, end] of [['#pkHandleL', 'a'], ['#pkHandleR', 'b']]) {
    const h = $(id);
    h.addEventListener('pointerdown', (e) => {
      e.preventDefault(); e.stopPropagation(); try { h.setPointerCapture(e.pointerId); } catch {}
      const move = (ev) => {
        const L = PK.lines[end === 'a' ? PK.sel[0] : PK.sel[PK.sel.length - 1]];
        const r = $('#pkDraw').getBoundingClientRect();
        const fx = (ev.clientX - r.left) / r.width;
        let best = 0, bd = 1e9;
        L.cuts.forEach((f, j) => { const d = Math.abs(f - fx); if (d < bd) { bd = d; best = j; } });
        const single = PK.sel.length === 1;
        if (end === 'a') PK.trim.a = Math.max(0, Math.min(best, single ? PK.trim.b - 1 : L.cuts.length - 2));
        else PK.trim.b = Math.min(L.cuts.length - 1, Math.max(best, single ? PK.trim.a + 1 : 1));
        savePick(); drawSel(); drawTray();
      };
      const up = () => { h.removeEventListener('pointermove', move); h.removeEventListener('pointerup', up); h.removeEventListener('pointercancel', up); window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); };
      h.addEventListener('pointermove', move); h.addEventListener('pointerup', up); h.addEventListener('pointercancel', up);
      window.addEventListener('pointermove', move); window.addEventListener('pointerup', up);
    });
  }
}
// the chosen lines as one picture: each line with its clef and key, trimmed to the chosen bars
async function linesOut() {
  savePick();
  const pages = [...PK.picks.keys()].sort((x, y) => x - y);
  const parts = [];
  let outScale = 0;
  for (const page of pages) {
    const pick = PK.picks.get(page);
    const key = PK.doc.id + ':' + page + ':' + (PK.source.scoreId || PK.source.file || '');
    const lines = page === PK.page ? PK.lines : PK.linesCache.get(key);
    if (!lines) continue;
    const [pw, ph] = PK.doc.sizes[page];
    const scale = outScale ? outScale * (PK.doc.sizes[pages[0]][0] / pw) : Math.min(PK.long > 2600 ? 6 : 4, Math.max(1.6, (PK.long || 2600) / pw));
    if (!outScale) outScale = scale;
    const full = document.createElement('canvas');
    await PK.doc.render(page, full, pw * scale, ph * scale);
    const W = full.width, H = full.height;
    pick.sel.forEach((i, k) => {
      const L = lines[i];
      const a = k === 0 ? pick.trim.a : 0, b = k === pick.sel.length - 1 ? pick.trim.b : L.cuts.length - 1;
      const [sy0, sy1] = lineSpan(L, pick.cut); const y0 = Math.floor(sy0 * H), y1 = Math.ceil(sy1 * H);
      const pieces = [];
      const pad = 0.004 * W;
      if (a > 0) pieces.push([L.x0 * W, L.cuts[0] * W]);       // keep the clef and key of the line
      const xa = a > 0 ? L.cuts[a] * W + pad * 0.6 : L.x0 * W;   // just past the barline, so the join is not read as one
      const xb = b < L.cuts.length - 1 ? L.cuts[b] * W + pad : L.x1 * W;
      pieces.push([xa, xb]);
      // each piece is copied now, so the page can be let go
      const cv = pieces.map(([x0, x1]) => { const w = Math.max(1, Math.round(x1 - x0)), h = y1 - y0; const c = document.createElement('canvas'); c.width = w; c.height = h; c.getContext('2d').drawImage(full, Math.round(x0), y0, w, h, 0, 0, w, h); return c; });
      // some of the staves only: the barlines ran on to the staves left out; the pieces of them
      // sticking out past the kept staves are taken away (the reader would not see them as barlines)
      if (pick.cut && L.staves && L.staves.length > 1) for (const c of cv) cutStubs(c, (L.staves[Math.min(pick.cut.from, L.staves.length - 1)][0] * H) - y0, (L.staves[Math.min(pick.cut.to, L.staves.length - 1)][1] * H) - y0, pick.cut.from > 0, pick.cut.to < L.staves.length - 1);
      parts.push({ h: y1 - y0, cv, gap: Math.round(0.01 * H) });
    });
    full.width = full.height = 0;
  }
  const outW = Math.ceil(Math.max(...parts.map((p) => p.cv.reduce((s, c) => s + c.width, 0)))) + 20;
  const outH = parts.reduce((s, p) => s + p.h + p.gap, 0);
  const c = document.createElement('canvas'); c.width = outW; c.height = outH;
  const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, outW, outH);
  let y = 0;
  for (const p of parts) {
    let x = 10;
    for (const piece of p.cv) { g.drawImage(piece, x, y); x += piece.width; piece.width = piece.height = 0; }
    y += p.h + p.gap;
  }
  return c;
}
// The barlines of a system run from its first staff to its last. Keeping some staves only, what is
// left of them above or below the kept staves is whitened: a column dark all down the kept staves
// and on, unbroken, to the cut edge.
function cutStubs(c, top, bot, above, below) {
  const g = c.getContext('2d'), W = c.width, H = c.height; if (W < 2 || H < 2) return;
  const im = g.getImageData(0, 0, W, H), d = im.data;
  const dark = (x, y) => { const i = (y * W + x) * 4; return d[i] + d[i + 1] + d[i + 2] < 400; };
  const t = Math.max(0, Math.round(top)), b = Math.min(H - 1, Math.round(bot));
  if (b - t < 8) return;
  let changed = false;
  for (let x = 0; x < W; x++) {
    let n = 0; for (let y = t; y <= b; y++) if (dark(x, y)) n++;
    if (n < (b - t + 1) * 0.9) continue;
    const wipe = (y0, y1) => {
      let m = 0; for (let y = y0; y <= y1; y++) if (dark(x, y)) m++;
      if (y1 - y0 < 2 || m < (y1 - y0 + 1) * 0.92) return;
      for (let y = y0; y <= y1; y++) { const i = (y * W + x) * 4; d[i] = d[i + 1] = d[i + 2] = 255; }
      changed = true;
    };
    if (below) wipe(b + 3, H - 1);
    if (above) wipe(0, t - 3);
  }
  if (changed) g.putImageData(im, 0, 0);
}
function drawSel() {
  const d = $('#pkDraw'), g = d.getContext('2d');
  g.clearRect(0, 0, d.width, d.height);
  const W = d.width, H = d.height;
  // the lines: a faint outline on each, the chosen ones tinted
  if (PK.lines && !PK.pts) {
    PK.lines.forEach((L, i) => {
      const k = PK.sel.indexOf(i), on = k >= 0;
      let xa = L.x0, xb = L.x1;
      if (on && PK.trim) {
        if (k === 0 && PK.trim.a > 0) xa = L.cuts[PK.trim.a];
        if (k === PK.sel.length - 1 && PK.trim.b < L.cuts.length - 1) xb = L.cuts[PK.trim.b];
      }
      const [sy0, sy1] = on ? lineSpan(L, PK.cut) : [L.y0, L.y1];
      const y = sy0 * H, h = (sy1 - sy0) * H, r = Math.min(18, h * 0.18);
      // the staves left out stay visible but pale
      if (on && (sy0 > L.y0 || sy1 < L.y1)) { g.fillStyle = 'rgba(255,255,255,0.6)'; if (sy0 > L.y0) g.fillRect(L.x0 * W, L.y0 * H, (L.x1 - L.x0) * W, (sy0 - L.y0) * H); if (sy1 < L.y1) g.fillRect(L.x0 * W, sy1 * H, (L.x1 - L.x0) * W, (L.y1 - sy1) * H); }
      g.setLineDash([]);
      if (on) {
        // the bars left out stay visible but pale
        g.fillStyle = 'rgba(255,255,255,0.6)';
        if (xa > L.x0) g.fillRect(L.x0 * W, y, (xa - L.x0) * W, h);
        if (xb < L.x1) g.fillRect(xb * W, y, (L.x1 - xb) * W, h);
        rr(g, xa * W, y + 2, (xb - xa) * W, h - 4, r);
        g.fillStyle = 'rgba(43,111,214,0.12)'; g.fill(); g.lineWidth = 3; g.strokeStyle = 'rgba(43,111,214,0.9)'; g.stroke();
      } else { rr(g, L.x0 * W, y + 2, (L.x1 - L.x0) * W, h - 4, r); g.lineWidth = 1.5; g.strokeStyle = 'rgba(43,111,214,0.22)'; g.stroke(); }
    });
  }
  g.lineWidth = 2; g.setLineDash([8, 6]); g.strokeStyle = css('--accent-text') || '#1F3A8F'; g.fillStyle = 'rgba(43,111,214,0.10)';
  if (PK.pts && PK.pts.length > 1) {
    g.beginPath(); PK.pts.forEach(([x, y], i) => (i ? g.lineTo(x * W, y * H) : g.moveTo(x * W, y * H))); g.closePath(); g.fill(); g.stroke();
  } else if (PK.box) {
    const b = PK.box;
    g.fillStyle = 'rgba(10,14,30,0.28)';
    g.fillRect(0, 0, W, b.y0 * H); g.fillRect(0, b.y1 * H, W, H - b.y1 * H); g.fillRect(0, b.y0 * H, b.x0 * W, (b.y1 - b.y0) * H); g.fillRect(b.x1 * W, b.y0 * H, W - b.x1 * W, (b.y1 - b.y0) * H);
    g.strokeRect(b.x0 * W, b.y0 * H, (b.x1 - b.x0) * W, (b.y1 - b.y0) * H);
  }
}
// ---------- all the pages at a glance: tap "Page 3 of 12", then the page wanted ----------
function closeGrid() {
  const g = $('#pkGrid'); if (!g) return;
  if (g._io) g._io.disconnect();
  RQ.paused = false; if (PK.doc) setTimeout(() => { if (PK.doc && !$('#pkGrid')) wantAround(PK.page); }, 300);
  for (const c of g.querySelectorAll('canvas')) { c.width = c.height = 0; }
  g.remove();
}
function openGrid() {
  if (!PK.doc || $('#pkGrid')) { closeGrid(); return; }
  RQ.paused = true;
  const g = el('div', 'pk-grid'); g.id = 'pkGrid'; g.setAttribute('role', 'dialog'); g.setAttribute('aria-label', 'All the pages');
  const head = el('div', 'pk-grid-head'); head.append(el('strong', '', 'Go to a page')); const x = el('button', 'btn small', 'Close'); x.addEventListener('click', closeGrid); head.append(x);
  const list = el('div', 'pk-grid-list');
  g.append(head, list);
  // (each page drawn small only when it comes into view, one at a time)
  const queue = []; let busy = 0;
  const next = async () => {
    // (one at a time: two drawings of the same document at once spoil each other)
    while (busy < 1 && queue.length && PK.doc && $('#pkGrid')) {
      const { i, c } = queue.shift(); busy++;
      (async () => { try { const [pw, ph] = PK.doc.sizes[i]; const W = 150 * Math.min(2, devicePixelRatio || 1); await PK.doc.render(i, c, W, W * ph / pw); } catch {} busy--; next(); })();
    }
  };
  const io = new IntersectionObserver((es) => { for (const e of es) if (e.isIntersecting && !e.target._drawn) { e.target._drawn = true; queue.push({ i: +e.target.dataset.i, c: e.target.querySelector('canvas') }); io.unobserve(e.target); } queue.sort((a, b) => Math.abs(a.i - PK.page) - Math.abs(b.i - PK.page)); next(); }, { root: list, rootMargin: '200px' });
  g._io = io;
  for (let i = 0; i < PK.doc.pages; i++) {
    const b = el('button', 'pk-grid-page' + (i === PK.page ? ' on' : '') + (PK.picks.has(i) ? ' picked' : '')); b.dataset.i = i;
    const [pw, ph] = PK.doc.sizes[i]; const c = el('canvas'); c.style.aspectRatio = `${pw} / ${ph}`;
    b.append(c, el('span', 'num', String(i + 1)));
    b.addEventListener('click', () => { closeGrid(); if (i !== PK.page) { savePick(); PK.page = i; showPage(); } });
    list.append(b); io.observe(b);
  }
  $('#picker').append(g);
  requestAnimationFrame(() => { const on = list.querySelector('.on'); if (on) on.scrollIntoView({ block: 'center' }); });
}
async function cropOut() {
  const b = PK.box;
  const [pw, ph] = PK.doc.sizes[PK.page];
  // render the page big enough that the staff lines are about 14-20 px apart
  const scale = Math.min(PK.long > 2600 ? 6 : 4, Math.max(1.6, (PK.long || 2600) / pw));
  const full = document.createElement('canvas');
  await PK.doc.render(PK.page, full, pw * scale, ph * scale);
  const x = Math.floor(b.x0 * full.width), y = Math.floor(b.y0 * full.height);
  const w = Math.max(8, Math.ceil((b.x1 - b.x0) * full.width)), h = Math.max(8, Math.ceil((b.y1 - b.y0) * full.height));
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, w, h); g.drawImage(full, x, y, w, h, 0, 0, w, h);
  full.width = full.height = 0;
  return c;
}
(function wire() {
  if (!$('#picker')) return;
  $('#pkCancel').addEventListener('click', () => { if (!$('#pkStage').hidden && PK.opts && PK.opts.canGoBack !== false && !PK.direct) { showLibrary(); return; } finish(null); });
  $('#pkPrev').addEventListener('click', () => { if (PK.page > 0) { PK.page--; showPage(); } });
  $('#pkPageNo').addEventListener('click', openGrid);
  $('#pkPageNo').setAttribute('role', 'button'); $('#pkPageNo').title = 'All the pages';
  $('#pkNext').addEventListener('click', () => { if (PK.page < PK.doc.pages - 1) { PK.page++; showPage(); } });
  $('#pkDone').addEventListener('click', async () => {
    savePick();
    if ((!PK.box && !PK.picks.size) || !PK.doc) return;
    $('#pkDone').disabled = true;
    if (!PK.box && PK.picks.size) { const pages = [...PK.picks.keys()].sort((x, y) => x - y); const canvas = await linesOut(); finish({ canvas, box: null, lines: PK.picks.get(pages[0]).sel.slice(), page: pages[0], pages, source: PK.source }); return; }
    const canvas = await cropOut();
    finish({ canvas, box: { ...PK.box }, page: PK.page, source: PK.source });
  });
  const d = $('#pkDraw');
  let drawing = null;
  const rel = (e) => { const r = d.getBoundingClientRect(); return [Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)), Math.max(0, Math.min(1, (e.clientY - r.top) / r.height))]; };
  d.addEventListener('pointerdown', (e) => {
    e.preventDefault(); try { d.setPointerCapture(e.pointerId); } catch {}
    const [fx, fy] = rel(e);
    drawing = { id: e.pointerId, x: e.clientX, y: e.clientY, t: performance.now(), moved: false };
    // starting on a line of music: slide from bar to bar. Anywhere else: draw a loop.
    const i = PK.lines && PK.lines.length ? lineAt(fx, fy) : -1;
    if (i >= 0) drawing.range = { i, j: barIdx(PK.lines[i], fx) };
    PK.pts = [[fx, fy]];
  });
  d.addEventListener('pointermove', (e) => {
    if (!drawing) return;
    if (!drawing.moved && Math.hypot(e.clientX - drawing.x, e.clientY - drawing.y) < 10) return;
    if (drawing.range) {
      drawing.moved = true; PK.pts = null;
      const [fx, fy] = rel(e); const i = nearLine(fy);
      if (i >= 0) selectRange(drawing.range.i, drawing.range.j, i, barIdx(PK.lines[i], fx));
      return;
    }
    if (!drawing.moved) { drawing.moved = true; PK.box = null; PK.sel = []; PK.trim = null; PK.cut = null; PK.picks.clear(); syncDone(); drawTray(); }
    const list = (e.getCoalescedEvents && e.getCoalescedEvents()) || []; for (const ev of (list.length ? list : [e])) PK.pts.push(rel(ev)); drawSel();
  });
  const end = (e) => {
    if (!drawing) return;
    const tap = !drawing.moved, range = drawing.range; drawing = null;
    if (range && !tap) { PK.pts = null; savePick(); drawSel(); drawTray(); return; }
    const pts = PK.pts; PK.pts = null;
    if (!pts) { drawSel(); return; }
    if (tap) { const [fx, fy] = pts[0]; const i = lineAt(fx, fy); if (i >= 0) toggleLine(i); else drawSel(); return; }
    if (!pts || pts.length < 2) { drawSel(); return; }
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    const box = { x0: Math.min(...xs), y0: Math.min(...ys), x1: Math.max(...xs), y1: Math.max(...ys) };
    if (box.x1 - box.x0 < 0.04 || box.y1 - box.y0 < 0.015) { PK.box = null; drawSel(); return; }
    PK.box = box; syncDone(); drawSel();
  };
  $('#pkAll').addEventListener('click', () => { if (!PK.lines || !PK.lines.length) return; PK.box = null; selectRange(0, 0, PK.lines.length - 1, PK.lines[PK.lines.length - 1].cuts.length - 2); savePick(); drawTray(); });
  $('#pkClear').addEventListener('click', () => { PK.picks.clear(); PK.sel = []; PK.trim = null; PK.cut = null; PK.box = null; syncDone(); drawSel(); drawTray(); });
  wireTray();
  d.addEventListener('pointerup', end); d.addEventListener('pointercancel', end);
  d.style.touchAction = 'none';
})();
export const _pk = PK;
export const _tray = TRAY;
