// Review of pages before they join the library, like a scanner app: the page is found in the
// photo and flattened (its corners can be moved by hand), straightened by its staff lines, the
// shadows are taken out and the ink made black on white. Pages can be added, reordered, turned
// and trimmed. Used for the page scanner, the camera, and photos or images from Files.
import { ask } from './dialog.js';
import { detectPage, warpPage, estimateSkew, rotateSmall, whitenPaper, crispInk, levels, trueAspect, cleanPage } from './scan.js';

const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; };

const DEFAULTS = () => ({ rot: 0, look: 'grey', clean: true, straight: true, contrast: 55, crop: { t: 0, b: 0, l: 0, r: 0 }, quad: undefined, skew: undefined });
const R = { pages: [], cur: 0, name: '', paths: [], token: 0, busy: false, editing: false };
let deps = { commit: null, toast: () => {} };

export function initReview(d) { deps = { ...deps, ...d }; wire(); }

export function openReview(blobs, name, { paths = [], onDone = null } = {}) {
  if (!blobs.length) return;
  // (a page the scanner has already flattened is not looked for again: it would be cut a second time)
  R.pages = blobs.map((b) => ({ src: b, bmp: null, ...DEFAULTS(), ...(b && b.__flat ? { quad: null, flat: true } : {}) }));
  R.cur = 0; R.name = name; R.paths = paths; R.onDone = onDone; R.editing = false;
  $('#review').hidden = false;
  document.body.classList.add('reviewing');
  syncTools(); draw(); strip();
}
function closeReview() {
  $('#review').hidden = true;
  document.body.classList.remove('reviewing');
  for (const p of R.pages) if (p.bmp && p.bmp.close) p.bmp.close();
  const done = R.onDone; R.pages = []; R.onDone = null;
  if (done) done();
}

// ---------- image pipeline ----------
async function bitmapOf(p) { if (!p.bmp) p.bmp = await createImageBitmap(p.src); return p.bmp; }

// the photo turned by quarter turns, at most maxSide pixels
async function turned(p, maxSide) {
  const bmp = await bitmapOf(p);
  const rot = ((p.rot % 360) + 360) % 360, swap = rot === 90 || rot === 270;
  const W = swap ? bmp.height : bmp.width, H = swap ? bmp.width : bmp.height;
  const k = Math.min(1, maxSide / Math.max(W, H));
  const c = document.createElement('canvas'); c.width = Math.round(W * k); c.height = Math.round(H * k);
  const g = c.getContext('2d');
  g.translate(c.width / 2, c.height / 2); g.rotate((rot * Math.PI) / 180);
  g.drawImage(bmp, (-bmp.width * k) / 2, (-bmp.height * k) / 2, bmp.width * k, bmp.height * k);
  return c;
}
// the page found once, the first time it is shown
async function ensureFound(p) {
  if (p.quad !== undefined) return;
  try { p.quad = detectPage(await turned(p, 900)); } catch { p.quad = null; }
}
// The shapes of printed music paper (height over width): A4 (and every A and B size), Letter, the
// 9 × 12 inch concert size, Tabloid, Legal.
const PAPERS = [1.4142, 1.2941, 1.3333, 1.5455, 1.6471];
// one shape for all the pages of a scan: the pages of one score are all the same size, so the shape
// they show most (snapped to a paper size when it is that close) is given to every one near it
function batchShape() {
  const a = R.pages.filter((q) => (q.quad || q.flat) && q.asp).map((q) => (q.asp >= 1 ? q.asp : 1 / q.asp)).sort((x, y) => x - y);
  if (!a.length) return null;
  const m = a[a.length >> 1];
  const near = PAPERS.reduce((b, x) => (Math.abs(x / m - 1) < Math.abs(b / m - 1) ? x : b), PAPERS[0]);
  return Math.abs(near / m - 1) < 0.03 ? near : m;
}
// the page given its true shape (and the same size as the others): the photo's slant leaves it a
// little too short or too wide, never by more than a few hundredths
function giveShape(c, p, maxSide) {
  if (!(p.quad || p.flat) || !p.asp) return c;
  const own = p.asp >= 1 ? p.asp : 1 / p.asp, land = c.width > c.height;
  const all = R.pages.includes(p) ? batchShape() : null;
  const want = all && Math.abs(own / all - 1) < 0.08 ? all : own;
  const H = Math.round(land ? maxSide / want : maxSide), W = Math.round(land ? maxSide : maxSide / want);
  if (Math.abs(W - c.width) <= 1 && Math.abs(H - c.height) <= 1) return c;
  const o = document.createElement('canvas'); o.width = W; o.height = H;
  const g = o.getContext('2d'); g.imageSmoothingQuality = 'high'; g.drawImage(c, 0, 0, W, H);
  return o;
}
async function renderPage(p, maxSide) {
  await ensureFound(p);
  let c;
  if (p.quad) {
    const src = await turned(p, Math.round(maxSide * 1.35));
    // (the page's real shape, worked out from the slant of its corners)
    try { p.asp = trueAspect(p.quad.map(([x, y]) => [x * src.width, y * src.height]), src.width, src.height); } catch { p.asp = null; }
    c = warpPage(src, p.quad, maxSide);
  } else {
    c = await turned(p, maxSide);
    if (p.flat) p.asp = c.height / c.width;
  }
  const { t, b, l, r } = p.crop;
  const cropped = !!(t || b || l || r);
  if (!cropped) c = giveShape(c, p, maxSide);
  if (t || b || l || r) {
    const sx = Math.round(l * c.width), sy = Math.round(t * c.height), sw = Math.max(1, Math.round(c.width * (1 - l - r))), sh = Math.max(1, Math.round(c.height * (1 - t - b)));
    const c1 = document.createElement('canvas'); c1.width = sw; c1.height = sh; c1.getContext('2d').drawImage(c, sx, sy, sw, sh, 0, 0, sw, sh); c = c1;
  }
  if (p.straight) {
    if (p.skew === undefined) { try { p.skew = estimateSkew(c); } catch { p.skew = 0; } }
    if (p.skew) c = rotateSmall(c, p.skew);
  }
  if (p.look === 'none') return c;
  // (cleaned as a good scanner does: shadows and the paper's tint gone, white paper, crisp dark ink)
  if (p.clean || p.look === 'bw') cleanPage(c, { contrast: p.contrast, grey: p.look !== 'colour' });
  if (p.look === 'bw') crispInk(c, p.contrast);
  else if (!p.clean) tone(c, p);
  return c;
}
// contrast (and grey) for the colour and grey looks
function tone(c, p) {
  const g = c.getContext('2d'), img = g.getImageData(0, 0, c.width, c.height), d = img.data;
  const stretch = 0.8 + (p.contrast / 100) * 1.0, grey = p.look === 'grey';
  const cl = (v) => (v < 0 ? 0 : v > 255 ? 255 : v);
  for (let i = 0; i < d.length; i += 4) {
    let r = d[i], gg = d[i + 1], b = d[i + 2];
    if (grey) { const y = 0.299 * r + 0.587 * gg + 0.114 * b; r = gg = b = y; }
    d[i] = cl((r - 128) * stretch + 128); d[i + 1] = cl((gg - 128) * stretch + 128); d[i + 2] = cl((b - 128) * stretch + 128);
  }
  g.putImageData(img, 0, 0);
}

// ---------- the screen ----------
let drawT = 0;
function draw() {
  clearTimeout(drawT);
  drawT = setTimeout(async () => {
    const token = ++R.token;
    const p = R.pages[R.cur]; if (!p) return;
    $('#revBusy').hidden = false;
    const c = R.editing ? await turned(p, 1400) : await renderPage(p, 1300);
    if (token !== R.token) return;
    const view = $('#revCanvas');
    view.width = c.width; view.height = c.height;
    const g = view.getContext('2d'); g.drawImage(c, 0, 0);
    if (R.editing) { R.photo = c; await ensureFound(p); if (!R.q) R.q = (p.quad || [[0.04, 0.04], [0.96, 0.04], [0.96, 0.96], [0.04, 0.96]]).map((x) => x.slice()); paintEdges(); }
    $('#revBusy').hidden = true;
    $('#revSub').textContent = `Page ${R.cur + 1} of ${R.pages.length}`;
    $('#revTitle').textContent = R.editing ? 'Page edges' : 'Review';
    $('#revSave').disabled = !R.pages.length || R.editing;
  }, 40);
}
function paintEdges() {
  const view = $('#revCanvas'), g = view.getContext('2d'), W = view.width, H = view.height;
  g.drawImage(R.photo, 0, 0);
  const q = R.q.map(([x, y]) => [x * W, y * H]);
  g.save();
  g.fillStyle = 'rgba(8,12,24,0.45)';
  g.beginPath(); g.rect(0, 0, W, H); g.moveTo(q[0][0], q[0][1]); for (let i = 3; i >= 0; i--) g.lineTo(q[i][0], q[i][1]); g.closePath(); g.fill('evenodd');
  g.strokeStyle = '#3d7bff'; g.lineWidth = Math.max(2, W / 400);
  g.beginPath(); q.forEach(([x, y], i) => (i ? g.lineTo(x, y) : g.moveTo(x, y))); g.closePath(); g.stroke();
  const r = Math.max(10, W / 60);
  for (const [x, y] of q) { g.beginPath(); g.arc(x, y, r, 0, 7); g.fillStyle = 'rgba(255,255,255,0.9)'; g.fill(); g.lineWidth = Math.max(2, W / 300); g.stroke(); }
  g.restore();
}
async function strip() {
  const box = $('#revStrip'); box.textContent = '';
  R.pages.forEach((p, i) => {
    const b = el('button', 'rev-thumb' + (i === R.cur ? ' on' : ''));
    b.setAttribute('aria-label', `Page ${i + 1}`);
    const cv = el('canvas'); b.append(cv, el('span', 'num', String(i + 1)));
    b.addEventListener('click', () => { if (R.editing) return; R.cur = i; syncTools(); draw(); strip(); });
    box.append(b);
    renderPage(p, 200).then((c) => { cv.width = c.width; cv.height = c.height; cv.getContext('2d').drawImage(c, 0, 0); }).catch(() => {});
  });
  const add = el('button', 'rev-add'); add.append(el('b', '', '+'), document.createTextNode('Page'));
  add.setAttribute('aria-label', 'Add a page');
  add.addEventListener('click', () => $('#revAddInput').click());
  box.append(add);
  const on = box.querySelector('.on'); if (on) on.scrollIntoView({ inline: 'center', block: 'nearest' });
}
const LOOK_HINT = { grey: 'White paper and dark ink, like a good scanner.', bw: 'Pure black and white: the sharpest print, smallest file. Very faint pencil may disappear.', colour: 'Keeps coloured markings and the paper tone.' };
function syncTools() {
  const p = R.pages[R.cur] || DEFAULTS();
  $$('#revColour button').forEach((b) => b.classList.toggle('on', b.dataset.look === p.look));
  $('#revLookHint').textContent = LOOK_HINT[p.look];
  $('#revContrastLabel').textContent = p.look === 'bw' ? 'Ink (more keeps faint marks)' : 'Darkness of the ink';
  $('#revClean').checked = !!p.clean; $('#revClean').disabled = p.look === 'bw';
  $('#revStraight').checked = !!p.straight;
  $('#revContrast').value = p.contrast;
  for (const k of ['t', 'b', 'l', 'r']) $('#crop' + k.toUpperCase()).value = Math.round(p.crop[k] * 100);
  $('#revApplyAll').disabled = R.pages.length < 2;
  $('#revMoveL').disabled = R.cur === 0; $('#revMoveR').disabled = R.cur >= R.pages.length - 1;
}
function change(fn) {
  const p = R.pages[R.cur]; if (!p) return;
  fn(p); syncTools(); draw(); strip();
}
// quarter turns carry the page corners with them
function turnQuad(p, cw) {
  if (p.quad) {
    const q = p.quad.map(([x, y]) => (cw ? [1 - y, x] : [y, 1 - x]));
    p.quad = cw ? [q[3], q[0], q[1], q[2]] : [q[1], q[2], q[3], q[0]];
  }
  p.skew = undefined;
}

function editEdges(on) {
  const p = R.pages[R.cur]; if (!p) return;
  R.editing = on; R.q = null;
  $('#revStage').classList.toggle('editing', on);
  $('#revEdgeBar').hidden = !on;
  if (on) $('#revStage').style.setProperty('--barh', ($('#revEdgeBar').offsetHeight + 12 + 32) + 'px');
  $('.rev-side').style.opacity = on ? 0.4 : ''; $('.rev-side').style.pointerEvents = on ? 'none' : '';
  draw();
}

function wire() {
  $('#revCancel').addEventListener('click', async () => {
    if (R.editing) { editEdges(false); return; }
    if (R.pages.length && !(await ask(R.pages.length === 1 ? 'Discard this page?' : `Discard these ${R.pages.length} pages?`, { ok: 'Discard', danger: true }))) return;
    closeReview();
    deps.toast('Nothing was added.');
  });
  $('#revRotL').addEventListener('click', () => change((p) => { p.rot = (p.rot + 270) % 360; turnQuad(p, false); }));
  $('#revRotR').addEventListener('click', () => change((p) => { p.rot = (p.rot + 90) % 360; turnQuad(p, true); }));
  $('#revDelete').addEventListener('click', () => {
    if (!R.pages.length) return;
    R.pages.splice(R.cur, 1);
    if (!R.pages.length) { closeReview(); deps.toast('No pages left.'); return; }
    R.cur = Math.min(R.cur, R.pages.length - 1); syncTools(); draw(); strip();
  });
  const move = (d) => { const j = R.cur + d; if (j < 0 || j >= R.pages.length) return; const [p] = R.pages.splice(R.cur, 1); R.pages.splice(j, 0, p); R.cur = j; syncTools(); draw(); strip(); };
  $('#revMoveL').addEventListener('click', () => move(-1));
  $('#revMoveR').addEventListener('click', () => move(1));
  $$('#revColour button').forEach((b) => b.addEventListener('click', () => change((p) => { p.look = b.dataset.look; })));
  $('#revClean').addEventListener('change', (e) => change((p) => { p.clean = e.target.checked; }));
  $('#revStraight').addEventListener('change', (e) => change((p) => { p.straight = e.target.checked; }));
  $('#revContrast').addEventListener('input', (e) => change((p) => { p.contrast = +e.target.value; }));
  for (const k of ['t', 'b', 'l', 'r']) $('#crop' + k.toUpperCase()).addEventListener('input', (e) => change((p) => { p.crop[k] = Math.min(0.4, +e.target.value / 100); }));
  $('#revApplyAll').addEventListener('click', () => {
    const p = R.pages[R.cur]; if (!p) return;
    for (const q of R.pages) { q.look = p.look; q.clean = p.clean; q.straight = p.straight; q.contrast = p.contrast; q.crop = { ...p.crop }; }
    deps.toast('Applied to all pages.'); draw(); strip();
  });
  $('#revAddInput').addEventListener('change', (e) => {
    const files = [...e.target.files]; e.target.value = ''; if (!files.length) return;
    const p0 = R.pages[R.cur] || DEFAULTS();
    for (const f of files) R.pages.push({ src: f, bmp: null, ...DEFAULTS(), look: p0.look, contrast: p0.contrast, clean: p0.clean, straight: p0.straight });
    R.cur = R.pages.length - 1; syncTools(); draw(); strip();
  });
  // page edges: drag the corners
  $('#revEdges').addEventListener('click', () => editEdges(true));
  $('#revEdgeDone').addEventListener('click', () => { const p = R.pages[R.cur]; if (p && R.q) { p.quad = R.q.map((x) => x.slice()); p.skew = undefined; } editEdges(false); strip(); });
  $('#revWhole').addEventListener('click', () => { R.q = [[0, 0], [1, 0], [1, 1], [0, 1]]; paintEdges(); });
  $('#revFind').addEventListener('click', () => { const q = detectPage(R.photo); if (q) { R.q = q; paintEdges(); } else deps.toast('No page edges found. Drag the corners by hand.'); });
  const cv = $('#revCanvas');
  let drag = -1;
  const at = (e) => { const r = cv.getBoundingClientRect(); return [Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)), Math.max(0, Math.min(1, (e.clientY - r.top) / r.height)), r]; };
  cv.addEventListener('pointerdown', (e) => {
    if (!R.editing || !R.q) return;
    const [x, y, r] = at(e);
    let best = -1, bd = 1e9;
    R.q.forEach(([qx, qy], i) => { const d = Math.hypot((qx - x) * r.width, (qy - y) * r.height); if (d < bd) { bd = d; best = i; } });
    if (bd < 70) { drag = best; try { cv.setPointerCapture(e.pointerId); } catch {} e.preventDefault(); }
  });
  cv.addEventListener('pointermove', (e) => { if (drag < 0) return; const [x, y] = at(e); R.q[drag] = [x, y]; paintEdges(); });
  const up = () => { drag = -1; };
  cv.addEventListener('pointerup', up); cv.addEventListener('pointercancel', up);
  $('#revSave').addEventListener('click', save);
}

// Render every page at full size and add the result as one score.
async function save() {
  if (!R.pages.length || R.busy) return;
  R.busy = true; $('#revSave').disabled = true; $('#revBusy').hidden = false;
  try {
    const blobs = [];
    for (let i = 0; i < R.pages.length; i++) {
      $('#revSub').textContent = `Preparing page ${i + 1} of ${R.pages.length}…`;
      await new Promise((r) => setTimeout(r, 0));
      const p = R.pages[i];
      const c = await renderPage(p, 2600);
      // black and white pages are small as PNG and stay sharp; colour as JPEG
      blobs.push(await new Promise((res) => c.toBlob(res, p.look === 'bw' ? 'image/png' : 'image/jpeg', 0.9)));
    }
    const name = R.name || 'Scan.jpg';
    await deps.commit(blobs, name);
    closeReview();
  } catch (err) {
    console.error(err); deps.toast('Those pages could not be saved.', 3500);
  } finally {
    R.busy = false; $('#revSave').disabled = false; $('#revBusy').hidden = true;
  }
}

// A photo made ready to read: page found and flattened, straightened, paper whitened.
// Used by Capture and Studio when the music comes from a photo.
export async function cleanPhoto(src, { maxSide = 2600, look = 'grey', straight = true, clean = true } = {}) {
  const p = { src, bmp: null, ...DEFAULTS(), look, clean, straight };
  const c = await renderPage(p, maxSide);
  if (p.bmp && p.bmp.close) p.bmp.close();
  return { canvas: c, found: !!p.quad, skew: p.skew || 0 };
}
