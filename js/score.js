// Score documents (PDF, photos, manuscript paper), page rendering, reading the title and
// composer from a PDF, and finding a clean gap between systems for half-page turns.
import * as pdfjsLib from '../vendor/pdf.min.mjs';
import { loadMusicFont } from './ink.js';
import { paintCover } from './covers.js';
import { pixGet, pixPut, pixHas, pixDel, lightGet, lightPut, lightKeys, lightDel } from './pixcache.js';
// heavy scans, for the whole app: their pages are drawn one at a time, wherever they are drawn
const HEAVY = { chain: Promise.resolve(), active: 0, fids: new Set(), lightening: new Set(), bg: null };
import { db } from './db.js';
import { drawNotebookPage, drawNotebookNumber, drawCover, PAGE_W as NB_W, PAGE_H as NB_H } from './notebook.js';

pdfjsLib.GlobalWorkerOptions.workerSrc = new URL('../vendor/pdf.worker.min.mjs', import.meta.url).href;
// drawn pages kept as pictures: up to this size, and only those slower than this to draw (ms)
const PIX_MAX = 7e6, PIX_SLOW = 120;
// Scanned pages can hold enormous pictures (an IMSLP scan: 7000 × 9300 dots, 260 MB once
// decoded, for one page). The reader shrinks every picture to a few million dots as it reads it
// (sharper than the screen still), so a page never takes more than about 30 MB: the big scans
// were what made iOS close Stand.
const PHONE_UA = typeof navigator !== 'undefined' && /iPhone|iPod/.test(navigator.userAgent || '');
const PDF_OPTS = {
  // (the names of a font's glyphs: LilyPond's music font is read by them, see pdf-music.js)
  fontExtraProperties: true,
  canvasMaxAreaInBytes: (globalThis.__pdfMaxPix || (PHONE_UA ? 5e6 : 8e6)) * 4,
  cMapUrl: new URL('../vendor/cmaps/', import.meta.url).href,
  cMapPacked: true,
  standardFontDataUrl: new URL('../vendor/standard_fonts/', import.meta.url).href,
};

// ---------- manuscript paper ----------
export const PAPERS = {
  treble: { label: 'Treble clef', staves: [['g']], systems: 12 },
  bass: { label: 'Bass clef', staves: [['f']], systems: 12 },
  alto: { label: 'Alto clef', staves: [['alto']], systems: 12 },
  tenor: { label: 'Tenor clef', staves: [['tenor']], systems: 12 },
  piano: { label: 'Piano (grand staff)', staves: [['g', 'f']], systems: 6, brace: true },
  cellopiano: { label: 'Cello and piano', staves: [['f', 'g', 'f']], systems: 4, brace: true, bracket: true },
  violinpiano: { label: 'Violin and piano', staves: [['g', 'g', 'f']], systems: 4, brace: true, bracket: true },
  duo: { label: 'Two staves (duet)', staves: [['g', 'f']], systems: 6, bracket: true },
  blank: { label: 'Blank staves', staves: [[null]], systems: 12 },
  wide: { label: 'Large staves (teaching)', staves: [[null]], systems: 8, space: 10 },
  tab: { label: 'Guitar tab', staves: [['tab']], systems: 10, lines: 6, space: 8 },
  lined: { label: 'Lined', kind: 'lined' },
  dots: { label: 'Dot grid', kind: 'dots' },
  grid: { label: 'Squared', kind: 'grid' },
  plain: { label: 'Plain', kind: 'plain' },
};
const PAPER_W = 595, PAPER_H = 842;
const CLEF = { g: ['', 3], f: ['', 1], alto: ['', 2], tenor: ['', 1] }; // glyph, line index from top (0..4)

function drawPaper(ctx, tpl, pageIndex, w, h) {
  const def = PAPERS[tpl] || PAPERS.treble;
  const k = w / PAPER_W;
  ctx.save();
  ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, w, h);
  ctx.scale(k, k);
  if (def.kind) {
    const step = 22, x0 = 40, x1 = PAPER_W - 40, y0 = 60, y1 = PAPER_H - 40;
    if (def.kind === 'lined') {
      ctx.strokeStyle = '#b9c3d6'; ctx.lineWidth = 0.6; ctx.beginPath();
      for (let y = y0 + step; y <= y1; y += step) { ctx.moveTo(x0, y); ctx.lineTo(x1, y); }
      ctx.stroke();
      ctx.strokeStyle = '#e7a3a3'; ctx.beginPath(); ctx.moveTo(x0 + 34, y0); ctx.lineTo(x0 + 34, y1); ctx.stroke();
    } else if (def.kind === 'grid') {
      ctx.strokeStyle = '#d3d9e6'; ctx.lineWidth = 0.5; ctx.beginPath();
      for (let y = y0; y <= y1 + 0.1; y += step / 1.5) { ctx.moveTo(x0, y); ctx.lineTo(x1, y); }
      for (let x = x0; x <= x1 + 0.1; x += step / 1.5) { ctx.moveTo(x, y0); ctx.lineTo(x, y1); }
      ctx.stroke();
    } else if (def.kind === 'dots') {
      ctx.fillStyle = '#9aa5ba';
      for (let y = y0; y <= y1 + 0.1; y += step / 1.5) for (let x = x0; x <= x1 + 0.1; x += step / 1.5) { ctx.beginPath(); ctx.arc(x, y, 0.8, 0, Math.PI * 2); ctx.fill(); }
    }
    ctx.restore();
    return;
  }
  const sp = def.space || 7.2;               // staff space in points
  const left = 54, right = PAPER_W - 46;
  const top = pageIndex === 0 ? 120 : 58, bottom = PAPER_H - 50;
  const nStaff = def.staves[0].length;
  const staffH = sp * ((def.lines || 5) - 1);
  const innerGap = sp * 5.2;                 // between staves of one system
  const sysH = nStaff * staffH + (nStaff - 1) * innerGap;
  const minGap = nStaff > 1 ? sp * 7 : sp * 4.5;
  const avail = bottom - top;
  const nSys = Math.max(1, Math.min(def.systems, Math.floor((avail + minGap) / (sysH + minGap))));
  const gap = nSys > 1 ? (avail - nSys * sysH) / (nSys - 1) : 0;
  ctx.strokeStyle = '#1b1d22'; ctx.fillStyle = '#1b1d22'; ctx.lineWidth = 0.75;
  for (let s = 0; s < nSys; s++) {
    const y0 = top + s * (sysH + gap);
    const sysTop = y0, sysBot = y0 + sysH;
    def.staves[0].forEach((clef, j) => {
      const sy = y0 + j * (staffH + innerGap);
      ctx.beginPath();
      const nl = def.lines || 5;
      for (let l = 0; l < nl; l++) { ctx.moveTo(left, sy + l * sp); ctx.lineTo(right, sy + l * sp); }
      ctx.stroke();
      if (clef === 'tab') {
        ctx.save(); ctx.font = `700 ${sp * 1.25}px "Helvetica Neue", Arial, sans-serif`; ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
        ['T', 'A', 'B'].forEach((ch, q) => ctx.fillText(ch, left + sp * 0.7, sy + sp * (1 + q * 1.5))); ctx.restore();
      } else if (clef && CLEF[clef]) {
        const [g, line] = CLEF[clef];
        ctx.font = `${sp * 4}px Bravura`; ctx.textBaseline = 'alphabetic'; ctx.textAlign = 'left';
        ctx.fillText(g, left + sp * 0.9, sy + line * sp);
      }
    });
    // system barline at the left, and the final barline
    ctx.lineWidth = 0.9;
    ctx.beginPath(); ctx.moveTo(left, sysTop); ctx.lineTo(left, sysBot); ctx.moveTo(right, sysTop); ctx.lineTo(right, sysBot); ctx.stroke();
    ctx.lineWidth = 0.75;
    if (def.brace && nStaff >= 2) {
      const bTop = y0 + (nStaff - 2) * (staffH + innerGap);
      const bh = 2 * staffH + innerGap;
      ctx.save(); ctx.font = `${bh}px Bravura`; ctx.textBaseline = 'alphabetic'; ctx.textAlign = 'right';
      ctx.fillText('', left - 3, bTop + bh); ctx.restore();
    }
    if (def.bracket && nStaff >= 2 && !def.brace) {
      ctx.save(); ctx.lineWidth = 2.6; ctx.beginPath(); ctx.moveTo(left - 5, sysTop - 2); ctx.lineTo(left - 5, sysBot + 2); ctx.stroke(); ctx.restore();
    }
  }
  ctx.restore();
}

// ---------- documents ----------
// What identifies a file's pages, so their sizes can be kept and opening needn't measure every page.
export function sizesKey(file) {
  if (!file) return '';
  if (file.rot && Object.keys(file.rot).length) return sizesKey({ ...file, rot: null });   // (the sizes kept are those before turning)
  if (file.more && file.more.length) return sizesKey({ ...file, more: null }) + '+' + file.more.join(',');
  if (file.kind === 'pdf') return 'pdf:' + (file.data ? file.data.byteLength : 0);
  if (Array.isArray(file.data)) return 'img:' + file.data.length + ':' + file.data.map((b) => b && b.size).join(',');
  return '';
}
// A score with pages added from other files (file.more: the ids of those files, kept apart so the
// score's own file is never written again): one document, its own pages first.
export async function openDocument(file, known) {
  const d = await openJoined(file, known);
  return file && file.rot && Object.keys(file.rot).length ? rotateDoc(d, file.rot) : d;
}
// Pages turned a quarter (or half) round: rot = { page: 90 | 180 | 270 } (clockwise)
export function rotateDoc(doc, rot) {
  const deg = (i) => ((+rot[i] || 0) % 360 + 360) % 360;
  return {
    ...doc,
    rawSizes: doc.sizes,
    sizes: doc.sizes.map((s, i) => (deg(i) % 180 ? [s[1], s[0]] : s)),
    render: async (i, canvas, w, h, opts) => {
      const a = deg(i); if (!a) return doc.render(i, canvas, w, h, opts);
      const tmp = document.createElement('canvas'), side = a % 180;
      await doc.render(i, tmp, side ? h : w, side ? w : h, opts);
      canvas.width = Math.round(w); canvas.height = Math.round(h);
      const g = canvas.getContext('2d');
      g.translate(canvas.width / 2, canvas.height / 2); g.rotate((a * Math.PI) / 180);
      g.drawImage(tmp, -tmp.width / 2, -tmp.height / 2);
      tmp.width = tmp.height = 0;
    },
    pixHas: (i, w, h) => (deg(i) || !doc.pixHas ? Promise.resolve(true) : doc.pixHas(i, w, h)),
    music: (i, w, h) => (deg(i) || !doc.music ? Promise.resolve(null) : doc.music(i, w, h)),
    renderView: (i, canvas, view, w, h, opts) => (deg(i) || !doc.renderView ? Promise.resolve(false) : doc.renderView(i, canvas, view, w, h, opts)),
    destroy: () => doc.destroy(),
  };
}
async function openJoined(file, known) {
  if (file && file.more && file.more.length) {
    const own = await openDocumentOne({ ...file, more: null }, known && known.v && known.k === sizesKey(file) ? { k: sizesKey({ ...file, more: null }), v: known.v, prefix: true } : null);
    const parts = [own], kinds = [file.kind];
    for (const id of file.more) { const f = await db.get('files', id).catch(() => null); if (f) { try { parts.push(await openDocumentOne(f)); kinds.push(f.kind); } catch (e) { console.warn(e); } } }
    const at = []; parts.forEach((d, k) => { for (let i = 0; i < d.pages; i++) at.push([k, i]); });
    return {
      kindOf: (i) => kinds[at[i][0]] || file.kind,
      pages: at.length, sizes: parts.flatMap((d) => d.sizes), pdf: own.pdf, ownPages: own.pages,
      render(i, canvas, w, h, opts) { const [k, j] = at[i]; return parts[k].render(j, canvas, w, h, opts); },
      music(i, w, h) { const [k, j] = at[i]; return parts[k].music ? parts[k].music(j, w, h) : Promise.resolve(null); },
      pixHas: (i, w, h) => { const [k, j] = at[i]; return parts[k].pixHas ? parts[k].pixHas(j, w, h) : Promise.resolve(true); },
      renderView(i, canvas, view, w, h, opts) { const [k, j] = at[i]; return parts[k].renderView ? parts[k].renderView(j, canvas, view, w, h, opts) : Promise.resolve(false); },
      destroy() { for (const d of parts) try { d.destroy(); } catch {} },
    };
  }
  return openDocumentOne(file, known);
}
async function openDocumentOne(file, known) {
  const useKnown = (n) => (known && known.k && known.k === sizesKey(file) && Array.isArray(known.v) && (known.v.length === n || (known.prefix && known.v.length > n)) ? known.v.slice(0, n).map((x) => [x[0], x[1]]) : null);
  if (file.kind === 'paper') {
    await loadMusicFont();
    const paperKeep = new Map();   // (the paper of a page, by its look and size)
    const cover = file.cover ? 1 : 0;
    const pages = (file.pages || 1) + cover;
    return {
      pages, sizes: Array.from({ length: pages }, (_, i) => (file.pagesLand && file.pagesLand[i - cover] ? [NB_H, NB_W] : [NB_W, NB_H])), paper: true, cover: !!cover,
      async render(i, canvas, w, h) {
        canvas.width = Math.round(w); canvas.height = Math.round(h);
        const g = canvas.getContext('2d');
        if (cover && i === 0) { await paintCover(g, file, canvas.width, canvas.height); return; }
        const pi = i - cover, W = canvas.width, H = canvas.height;
        // every page after the first is the same paper (only its number differs): drawn once and kept,
        // so a page coming in while the pages are moved is a picture copied, not lines drawn again
        if (pi >= 1 && W <= H * 1.05) {
          const key = [(file.pagesTpl && file.pagesTpl[pi]) || file.template, JSON.stringify(file.opts || {}), file.paperColor || '', W, H].join('|');
          const c = paperKeep.get(key);
          if (c && c.width) { g.drawImage(c, 0, 0); drawNotebookNumber(g, file, pi, W, H); return; }
          // (the first page of this paper: drawn as before; kept a moment later, when nothing is happening)
          drawNotebookPage(g, file, pi, W, H, true);
          if (!paperKeep.has(key)) {
            paperKeep.set(key, null);
            setTimeout(() => { try { const k2 = document.createElement('canvas'); k2.width = W; k2.height = H; k2.getContext('2d').drawImage(canvas, 0, 0); paperKeep.set(key, k2); while (paperKeep.size > 4) { const [k0, c0] = paperKeep.entries().next().value; if (c0) c0.width = c0.height = 0; paperKeep.delete(k0); } } catch { paperKeep.delete(key); } }, 700);
          }
          drawNotebookNumber(g, file, pi, W, H);
          return;
        }
        drawNotebookPage(g, file, pi, W, H);
      },
      // Zoomed in: just the part of the page on screen (view: fractions of the page), drawn w × h,
      // so the paper's lines are as sharp as the screen at any zoom (the whole page can't be that big)
      async renderView(i, canvas, view, w, h) {
        canvas.width = Math.round(w); canvas.height = Math.round(h);
        const g = canvas.getContext('2d'), FW = canvas.width / view.w, FH = canvas.height / view.h;
        g.translate(-view.x * FW, -view.y * FH);
        if (cover && i === 0) await paintCover(g, file, FW, FH);
        else drawNotebookPage(g, file, i - cover, FW, FH);
        g.setTransform(1, 0, 0, 1, 0, 0);
        return true;
      },
      destroy() {},
    };
  }
  if (file.kind === 'pdf') {
    const fid = file.id ? `${file.id}:${file.data.byteLength}` : null;
    const pdf = await pdfjsLib.getDocument({ data: new Uint8Array(file.data.slice(0)), ...PDF_OPTS }).promise;
    // all pages are asked for at once (one after another took a long time on long scores)
    const sizes = useKnown(pdf.numPages) || await Promise.all(Array.from({ length: pdf.numPages }, (_, k) => pdf.getPage(k + 1).then((p) => { const vp = p.getViewport({ scale: 1 }); return [vp.width, vp.height]; })));

    // PDF.js keeps everything it read for a page (its pictures above all: a scanned page holds
    // tens of MB) until told to let go. Only the last few pages drawn keep theirs; the others
    // are cleaned up, or a long score (the Pages panel draws every page) runs the iPhone out
    // of memory and Stand is closed by iOS.
    const live = [], drawing = new Map();
    // A heavy scan (a page slow to draw: its pictures are huge): its pages are drawn one at a time
    // (two at once could take more memory than iOS allows), and, while nothing else is drawn, a
    // light copy is made, page by page, that is used from then on instead of the original.
    const LIGHT_LONG = PHONE_UA ? 1900 : 2600, HEAVY_MS = 650, scanLike = file.data.byteLength / Math.max(1, pdf.numPages) > 90e3;
    // (one queue for the whole app: the same scan open twice — on the stand and for the iPhone —
    // never draws two of its pages at once either)
    let heavy = !!(fid && HEAVY.fids.has(fid)), gone = false, lightening = false, lightHave = null, cur = 0;
    const lightOk = new Set(), pixOk = new Set();
    const lightenAll = async () => {
      if (lightening || !fid || gone || HEAVY.lightening.has(fid)) return; lightening = true; HEAVY.lightening.add(fid);
      try {
        lightHave = lightHave || await lightKeys(fid);
        // the pages just after the one on the stand first (the ones you are about to turn to)
        const nextK = () => { for (let d = 0; d < pdf.numPages; d++) { const k = (cur + d) % pdf.numPages; if (!lightHave.has(k)) return k; } return -1; };
        for (let k = nextK(); k >= 0 && !gone; k = nextK()) {
          // (only when nothing else is being drawn: never two of these pages at once)
          // (and only once Stand has drawn nothing for a while: slipped in between the pages being drawn
          // ahead, it was stopped each time and the work thrown away, and the next pages came late)
          const busyNow = () => HEAVY.active > 0 || globalThis.__busyUntil > performance.now() || (globalThis.__rqBusy && globalThis.__rqBusy());
          for (let w8 = 0, quiet = 0; quiet < 6 && w8 < 1200 && !gone; w8++) { await new Promise((r) => setTimeout(r, 250)); quiet = busyNow() ? 0 : quiet + 1; }
          if (gone) break;
          const pg = await pdf.getPage(k + 1); const v1 = pg.getViewport({ scale: 1 });
          const sc = LIGHT_LONG / Math.max(v1.width, v1.height);
          const c = document.createElement('canvas'); c.width = Math.round(v1.width * sc); c.height = Math.round(v1.height * sc);
          let ok = false;
          try {
            HEAVY.active++;
            // (stopped at once if a page is wanted meanwhile: it is made again later, when all is quiet.
            // Not stopped, a page turned to waited behind it, a second or more on an iPad)
            await (HEAVY.chain = HEAVY.chain.then(() => { if (gone || HEAVY.want > 0) return; const t = pg.render({ canvasContext: c.getContext('2d', { alpha: false }), viewport: pg.getViewport({ scale: sc }), background: 'rgb(255,255,255)' }); HEAVY.bg = t; return t.promise.then(() => { ok = true; }); }).catch(() => {}).finally(() => { HEAVY.bg = null; }));
          } finally { HEAVY.active--; }
          // (a page that did not draw is never kept: it would show black from then on)
          const b = ok && !looksBlack(c) && !looksBlank(c) ? await new Promise((r) => c.toBlob(r, 'image/jpeg', 0.86)) : null;
          c.width = c.height = 0; pg.cleanup();
          if (b && !gone) { await lightPut(fid, k, b); lightHave.add(k); }
          await new Promise((r) => setTimeout(r, 300));
        }
      } catch {} finally { lightening = false; HEAVY.lightening.delete(fid); }
    };
    const done = (i, page) => {
      drawing.set(i, (drawing.get(i) || 1) - 1);
      const at = live.indexOf(i); if (at >= 0) live.splice(at, 1); live.push(i);
      while (live.length > (globalThis.__pdfLive ?? (heavy ? 1 : ON_PHONE ? 2 : 4))) {   // (the iPhone has less memory: two pages kept)
        const old = live.shift();
        if (drawing.get(old) > 0) { live.push(old); break; }
        // (the document may have been closed meanwhile: then there is nothing to tidy)
        if (!gone) try { pdf.getPage(old + 1).then((pg) => { if (!(drawing.get(old) > 0)) pg.cleanup(); }).catch(() => {}); } catch {}
      }
    };
    const D = {
      pages: pdf.numPages, sizes, pdf,
      // the page's music as the PDF wrote it (signs of a music font, stems and beams), in the frame of
      // a picture of it w × h; nothing for a page without (a scan)
      async music(i, w, h) {
        if (gone) return null;
        const page = await pdf.getPage(i + 1).catch(() => null); if (!page) return null;
        const vp1 = page.getViewport({ scale: 1 }), vp = page.getViewport({ scale: Math.round(w) / vp1.width });
        const { pdfVectors } = await import('./pdf-music.js');
        const v = await pdfVectors(page, vp, pdfjsLib.OPS);
        // (only a page whose heads are characters this reader knows: a font it does not know reads by its picture)
        const mus = v.glyphs.filter((g) => !g.text);
        return mus.length >= 3 && mus.filter((g) => g.cp >= 0xe000 && g.cp < 0xf400).length >= mus.length * 0.9 ? v : null;
      },
      async render(i, canvas, w, h, opts = {}) {
        if (gone) return;   // (the score was closed while this page was waiting to be drawn)
        const W = Math.round(w), H = Math.round(h);
        if (Math.max(W, H) > 500) cur = i;   // (a page on the stand, not a small picture)
        // the light copy of a heavy scan, when its page is ready
        // (not when the page is wanted sharp, bigger than the light copy: the music cut out for a video)
        if (fid && !opts.sharp && (heavy || lightHave === null || lightHave.size)) {
          if (lightHave === null) lightHave = await lightKeys(fid);
          // (a heavy scan: light copies of more than its first page — that one is made when it is brought in)
          if ([...lightHave].some((k) => k > 0)) heavy = true;
          const lb = lightHave.has(i) ? await lightGet(fid, i) : null;
          if (lb) {
            try {
              // (decoded straight at the size shown when it is smaller: a light copy decoded whole and
              // then made smaller took half a second a page on an iPad, and turning quickly waited for it)
              const bmp = await fastBitmap(lb, W, H);
              canvas.width = W; canvas.height = H;
              const g = canvas.getContext('2d', { alpha: false });
              g.imageSmoothingQuality = 'high'; g.drawImage(bmp, 0, 0, W, H); if (bmp.close) bmp.close();
              // (a white copy kept by mistake: thrown away, the page drawn from the original; looked at
              // once per page, not at every turn: reading the picture back is slow)
              if (lightOk.has(i) || !looksBlank(canvas)) { lightOk.add(i); return; }
              lightHave.delete(i); lightDel(fid, i);
            } catch { /* drawn from the original below */ }
          }
        }
        // a page drawn slowly before is shown from its picture at once
        const key = fid && W * H <= PIX_MAX ? `${fid}|${i}|${W}x${H}` : null;
        if (key) {
          const b = await pixGet(key);
          if (b) {
            try {
              const bmp = await createImageBitmap(b);
              canvas.width = W; canvas.height = H;
              const g = canvas.getContext('2d', { alpha: false });
              g.drawImage(bmp, 0, 0, W, H); if (bmp.close) bmp.close();
              if (pixOk.has(key) || !looksBlank(canvas)) { pixOk.add(key); return; }
              pixDel(key);
            } catch { /* drawn again below */ }
          }
        }
        const t0 = performance.now();
        drawing.set(i, (drawing.get(i) || 0) + 1);
        let page = null;
        // (a heavy scan: after the page drawn before it)
        let release = null;
        if (heavy || scanLike) {
          // (a light copy being made quietly stops for this page)
          HEAVY.want = (HEAVY.want || 0) + 1; if (HEAVY.bg) try { HEAVY.bg.cancel(); } catch {}
          const prev = HEAVY.chain; HEAVY.chain = new Promise((r) => { release = r; });
          try { await Promise.race([prev.catch(() => {}), new Promise((r) => setTimeout(r, 15000))]); } finally { HEAVY.want--; }   // (never stuck behind a drawing that never ends)
        }
        HEAVY.active++;
        try {
        if (gone) return;
        // (the score closed while this page was being asked for: its document is gone, not an error)
        page = await pdf.getPage(i + 1).catch((e) => { if (gone) return null; throw e; });
        if (!page) return;
        const vp1 = page.getViewport({ scale: 1 });
        // A heavy scan's page not yet kept light: drawn once at the light copy's size, kept, and the
        // page shown from it. (Drawn at the page's size, it was drawn a second time later for the
        // light copy: the picture in the file, tens of millions of dots, read twice.)
        const asLight = heavy && fid && lightHave && !lightHave.has(i) && !opts.sharp && Math.max(W, H) < LIGHT_LONG * 0.75;
        let into = canvas;
        if (asLight) { const sc = LIGHT_LONG / Math.max(vp1.width, vp1.height); into = document.createElement('canvas'); into.width = Math.round(vp1.width * sc); into.height = Math.round(vp1.height * sc); }
        else { canvas.width = W; canvas.height = H; }
        const vp = page.getViewport({ scale: into.width / vp1.width });
        const task = page.render({ canvasContext: into.getContext('2d', { alpha: false }), viewport: vp, background: 'rgb(255,255,255)' });
        // a drawing no longer wanted (the page was turned past) stops at once
        if (opts.ctl) { if (opts.ctl.aborted) task.cancel(); else opts.ctl.fns.push(() => task.cancel()); }
        // (a drawing stopped because it is no longer wanted is not an error: whoever asked knows it was stopped)
        let stopped = false;
        await task.promise.catch((e) => { if (gone || (e && e.name === 'RenderingCancelledException' && opts.ctl && opts.ctl.aborted)) { stopped = true; return; } throw e; });
        if (stopped) { if (into !== canvas) into.width = into.height = 0; return; }
        if (into !== canvas) {
          canvas.width = W; canvas.height = H;
          const g = canvas.getContext('2d', { alpha: false }); g.imageSmoothingQuality = 'high'; g.drawImage(into, 0, 0, W, H);
          if (!looksBlack(into) && !looksBlank(into)) {
            lightHave.add(i);
            into.toBlob((b) => { into.width = into.height = 0; if (b && !gone) lightPut(fid, i, b).catch(() => lightHave.delete(i)); else lightHave.delete(i); }, 'image/jpeg', 0.86);
          } else into.width = into.height = 0;
          if (!lightening) setTimeout(lightenAll, 1500);
          return;
        }
        // only pages that were slow to draw are kept (quick vector pages are drawn sharp each time)
        if (key && (opts.keep || performance.now() - t0 > PIX_SLOW) && !looksBlank(canvas) && !looksBlack(canvas)) canvas.toBlob((b) => pixPut(key, b, fid), 'image/jpeg', 0.9);
        // a heavy page just drawn big enough is its own light copy (no need to draw it twice)
        if (heavy && fid && lightHave && !lightHave.has(i) && Math.max(W, H) >= LIGHT_LONG * 0.75 && !looksBlack(canvas) && !looksBlank(canvas)) {
          lightHave.add(i);
          canvas.toBlob((b) => { if (b && !gone) lightPut(fid, i, b).catch(() => lightHave.delete(i)); else lightHave.delete(i); }, 'image/jpeg', 0.86);
        }
        // (only a scan is made light: its file holds large pictures; music drawn as lines stays sharp at any zoom)
        if (performance.now() - t0 > HEAVY_MS && !heavy && fid && scanLike) { heavy = true; HEAVY.fids.add(fid); setTimeout(lightenAll, 1500); }
        else if (heavy && !lightening) setTimeout(lightenAll, 1500);
        } finally { HEAVY.active--; if (release) release(); done(i, page); }
      },
      // The first page of a scan, drawn for the library's picture when the score is brought in: drawn at
      // the light copy's size, and, a heavy scan (slow to draw), kept as its light copy. The score then
      // opens at once the first time (its first page would otherwise be read from the file again).
      async thumbLight(tw) {
        if (!fid || !scanLike || gone) return null;
        const pg = await pdf.getPage(1); const v1 = pg.getViewport({ scale: 1 });
        const sc = LIGHT_LONG / Math.max(v1.width, v1.height);
        const c = document.createElement('canvas'); c.width = Math.round(v1.width * sc); c.height = Math.round(v1.height * sc);
        const t0 = performance.now();
        HEAVY.active++;
        try { await pg.render({ canvasContext: c.getContext('2d', { alpha: false }), viewport: pg.getViewport({ scale: sc }), background: 'rgb(255,255,255)' }).promise; }
        catch { c.width = c.height = 0; return null; } finally { HEAVY.active--; }
        if (looksBlack(c) || looksBlank(c)) { c.width = c.height = 0; return null; }
        if (performance.now() - t0 > HEAVY_MS * 0.6) {
          const b = await new Promise((r) => c.toBlob(r, 'image/jpeg', 0.86));
          if (b && !gone) { await lightPut(fid, 0, b); if (lightHave) lightHave.add(0); }
        }
        const t = document.createElement('canvas'); t.width = tw; t.height = Math.round((tw * c.height) / c.width);
        const g = t.getContext('2d'); g.imageSmoothingQuality = 'high'; g.drawImage(c, 0, 0, t.width, t.height); c.width = c.height = 0;
        const out = await new Promise((r) => t.toBlob(r, 'image/jpeg', 0.82)); t.width = t.height = 0;
        pg.cleanup();
        return out;
      },
      pixHas: (i, w, h) => { const W = Math.round(w), H = Math.round(h); return fid && W * H <= PIX_MAX ? pixHas(`${fid}|${i}|${W}x${H}`) : Promise.resolve(true); },
      // Zoomed in: just the part on screen, drawn from the PDF itself at the screen's sharpness. (Not
      // for a heavy scan: its pictures are drawn one page at a time, and are no sharper this way.)
      async renderView(i, canvas, view, w, h, opts = {}) {
        if (gone || heavy || scanLike) return false;
        const W = Math.round(w), H = Math.round(h);
        drawing.set(i, (drawing.get(i) || 0) + 1);
        let page = null;
        try {
          page = await pdf.getPage(i + 1).catch(() => null);
          if (!page || gone) return false;
          const vp1 = page.getViewport({ scale: 1 }), FW = W / view.w, FH = H / view.h;
          const vp = page.getViewport({ scale: FW / vp1.width });
          canvas.width = W; canvas.height = H;
          const task = page.render({ canvasContext: canvas.getContext('2d', { alpha: false }), viewport: vp, transform: [1, 0, 0, FH / (vp1.height * FW / vp1.width), -view.x * FW, -view.y * FH], background: 'rgb(255,255,255)' });
          if (opts.ctl) { if (opts.ctl.aborted) task.cancel(); else opts.ctl.fns.push(() => task.cancel()); }
          let ok = true;
          await task.promise.catch(() => { ok = false; });
          return ok && !gone && !(opts.ctl && opts.ctl.aborted);
        } finally { done(i, page); }
      },
      destroy() { gone = true; pdf.destroy(); },
    };
    // (tests: how long each page takes to draw)
    if (globalThis.__renderLog) { const r0 = D.render; D.render = async function (i, c, w, h, o) { const t0 = performance.now(); try { return await r0.call(this, i, c, w, h, o); } finally { globalThis.__renderLog.push([i, Math.round(w), Math.round(t0), Math.round(performance.now() - t0), heavy ? 'H' : '', lightHave && lightHave.has(i) ? 'L' : '']); } }; }
    return D;
  }
  // Photos and scans: decode only the pages being shown (a few at a time), so a long scan
  // never holds every full-size photo in memory.
  let sizes = useKnown(file.data.length);
  if (!sizes) { sizes = []; for (const blob of file.data) { const b = await createImageBitmap(blob); sizes.push([b.width, b.height]); if (b.close) b.close(); } }
  // A few decoded pages are kept; one is only closed when no drawing is still using it (closing
  // a picture in use left pages or thumbnails blank now and then).
  const lru = new Map();
  const drop = (e) => { e.gone = true; if (!e.uses) e.p.then((b) => b.close && b.close(), () => {}); };
  const take = (i) => {
    let e = lru.get(i);
    if (e) { lru.delete(i); lru.set(i, e); }
    else {
      e = { p: createImageBitmap(file.data[i]), uses: 0, gone: false };
      lru.set(i, e);
      while (lru.size > 3) { const [k, old] = lru.entries().next().value; lru.delete(k); drop(old); }
    }
    e.uses++;
    return e;
  };
  const give = (e) => { e.uses--; if (e.gone && !e.uses) e.p.then((b) => b.close && b.close(), () => {}); };
  return {
    pages: sizes.length, sizes,
    async render(i, canvas, w, h) {
      const e = take(i);
      try {
        const bmp = await e.p;
        canvas.width = Math.round(w); canvas.height = Math.round(h);
        const c = canvas.getContext('2d', { alpha: false });
        c.fillStyle = '#fff'; c.fillRect(0, 0, w, h);
        c.imageSmoothingQuality = 'high';
        c.drawImage(bmp, 0, 0, w, h);
      } finally { give(e); }
    },
    // Zoomed in: the part on screen, from the full photo (sharper than the whole page can be drawn)
    async renderView(i, canvas, view, w, h) {
      const e = take(i);
      try {
        const bmp = await e.p;
        canvas.width = Math.round(w); canvas.height = Math.round(h);
        const c = canvas.getContext('2d', { alpha: false });
        c.fillStyle = '#fff'; c.fillRect(0, 0, canvas.width, canvas.height);
        c.imageSmoothingQuality = 'high';
        c.drawImage(bmp, view.x * bmp.width, view.y * bmp.height, view.w * bmp.width, view.h * bmp.height, 0, 0, canvas.width, canvas.height);
        return true;
      } finally { give(e); }
    },
    destroy() { for (const e of lru.values()) drop(e); lru.clear(); },
  };
}

// a picture that came out (almost) all black: the page did not really draw (out of memory, or
// stopped half way), never something to keep
// A page that came out white, with no ink at all (iOS short of memory draws a scan's picture as
// nothing): never kept, and one kept before is thrown away and drawn again.
// a picture decoded at the size it is shown (when smaller), where the browser can
async function fastBitmap(blob, W, H) {
  if ((globalThis.__fastBmp ?? true) && W > 0 && H > 0) {
    try {
      const b = await createImageBitmap(blob, { resizeWidth: W, resizeHeight: H, resizeQuality: 'high' });
      if (b.width === W && b.height === H) return b;
      if (b.close) b.close();
    } catch {}
  }
  return createImageBitmap(blob);
}
export function looksBlank(src, w = 64, h = 88) {
  try {
    const c = document.createElement('canvas'); c.width = w; c.height = h;
    const g = c.getContext('2d', { willReadFrequently: true }); g.drawImage(src, 0, 0, w, h);
    const d = g.getImageData(0, 0, w, h).data; let s = 0, s2 = 0; const n = d.length / 4;
    for (let i = 0; i < d.length; i += 4) { const l = (d[i] + d[i + 1] + d[i + 2]) / 3; s += l; s2 += l * l; }
    const m = s / n, sd = Math.sqrt(Math.max(0, s2 / n - m * m));
    return m > 238 && sd < 2.5;
  } catch { return false; }
}
export function looksBlack(src, w = 24, h = 32) {
  try {
    const c = document.createElement('canvas'); c.width = w; c.height = h;
    const g = c.getContext('2d', { willReadFrequently: true }); g.drawImage(src, 0, 0, w, h);
    const d = g.getImageData(0, 0, w, h).data; let sum = 0;
    for (let i = 0; i < d.length; i += 4) sum += d[i] + d[i + 1] + d[i + 2];
    return sum / (d.length / 4) / 3 < 14;
  } catch { return false; }
}
export async function makeThumb(doc, { dark = false } = {}) {
  const [pw, ph] = doc.sizes[0];
  const w = 360, h = Math.round((w * ph) / pw);
  if (doc.thumbLight && !dark) try { const b = await doc.thumbLight(w); if (b) return b; } catch {}
  for (let attempt = 0; attempt < 2; attempt++) {
    const c = document.createElement('canvas');
    try { await doc.render(0, c, w, h); } catch { c.width = c.height = 0; await new Promise((r) => setTimeout(r, 800)); continue; }
    if ((!dark && looksBlack(c)) || (attempt === 0 && looksBlank(c))) { c.width = c.height = 0; await new Promise((r) => setTimeout(r, 800)); continue; }
    const b = await new Promise((res) => c.toBlob((x) => res(x), 'image/jpeg', 0.82));
    c.width = c.height = 0;
    return b;
  }
  // (a first page left white — the back of a cover, an empty sheet: the first page with something on
  // it is the picture, so the library shows the music, never a blank card)
  if (!dark && doc.pages > 1) for (let k = 1; k < Math.min(doc.pages, 4); k++) {
    const [qw, qh] = doc.sizes[k] || [pw, ph], c = document.createElement('canvas');
    try { await doc.render(k, c, w, Math.round((w * qh) / qw)); } catch { c.width = c.height = 0; continue; }
    if (looksBlank(c) || looksBlack(c)) { c.width = c.height = 0; continue; }
    const b = await new Promise((res) => c.toBlob((x) => res(x), 'image/jpeg', 0.82));
    c.width = c.height = 0;
    return b;
  }
  return null;
}

// ---------- reading title and composer ----------
const fold = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
const JUNK = /(©|copyright|imslp|mutopia|lilypond|public domain|edition|verlag|publish|printed|all rights|\bpage\b|^\d+$|www\.|http|plate|stich|lith)/i;
// lines that are never the title: tempo marks, an instrument on its own, editors and arrangers
const TEMPO = /^\(?\s*(tempo|allegr\w*|andant\w*|adagi\w*|moderato|presto|prestissimo|largo|larghetto|lento|vivace|vivo|grave|maestoso|sostenuto|cantabile|con moto|tranquillo|animato|risoluto|scherzando|rubato|a tempo)\b[^]{0,40}$/i;
const NOT_TITLE = /^(((solo\s+)?(violoncello|cello|violino|violin|viola|contrabass\w*|double bass|kontrabass|flute|flauto|fl[oö]te|oboe|clarinet\w*|klarinette|fagott\w*|bassoon|horn|corno|trumpet|tromba|trombone|piano|pianoforte|klavier|organ|orgel|soprano|alto|tenor|bass|basso|voice|guitar|gitarre|harp|arpa)(\s+(i{1,3}|\d|solo|principale|and piano|e pianoforte|und klavier|et piano))?\s*\.?)|(edited|edition|ed\.|herausgegeben|hrsg|revised|revidiert|arr\.?|arranged|arrangement|bearbeitet|bearb\.|transcri\w+|fingered|fingering|fingersatz|doigt\w*)\b.*)$/i;
// ("Var. II", "II", "3.", "Mvt. 2": which movement or variation, never the piece's title)
const MOVEMENT_NO = /^(var\.?|variation|variazione|mvt\.?|movement|satz|no\.?|nr\.?)?\s*([ivxlc]{1,5}|\d{1,2})\.?$/i;
const looksLikeName = (s) => !MOVEMENT_NO.test(s.trim()) && /\p{L}{3}/u.test(s) && /^(\p{Lu}[\p{L}'’.-]*\s+){0,3}\p{Lu}[\p{L}'’-]+$/u.test(s) && !/\d/.test(s) && s.length < 36;
const GENERIC = /^(sonat[ae]n?|sonatin[ae]|suite|concert[oe]?|konzert|etude|étude|studie|study|caprice|capriccio|fantasi[ae]|fantaisie|nocturne|prelude|prélude|präludium|romance|romanze|serenade|sérénade|variations?|variationen|partita|trio|quartet|quartett|duo|rondo|scherzo|menuet|minuet|waltz|valse|walzer|march|marsch|marche|élégie|elegie|elegy|air|aria|lied|song|dance|danse|tanz)$/i;
const tidy = (s) => s.replace(/\s+/g, ' ').replace(/^[\s.,:;-]+|[\s.,:;-]+$/g, '').trim();
// (a line all in capitals in ordinary letters; catalogue letters and Roman numbers stay capitals: "SONATA IV, BWV 1017" → "Sonata IV, BWV 1017")
const titleCase = (s) => (s === s.toUpperCase() && /[A-Z]{3}/.test(s) ? s.toLowerCase().replace(/(^|[\s(-])(\p{L})/gu, (m, a, b) => a + b.toUpperCase())
  .replace(/\b(Bwv|Hwv|Twv|Rv|Kv|Hob|Woo|Sz)\b/g, (w) => w.toUpperCase()).replace(/\b(I{2,3}|Iv|Vi{0,3}|Ix|Xi{0,3}|Xiv|Xv)\b\.?/g, (w) => w.toUpperCase()) : s);

export function findComposer(text, composers) {
  const f = ' ' + fold(text) + ' ';
  let best = null, score = 0;
  for (const c of composers) for (const k of c.k) {
    if (k.length < 4 || !f.includes(' ' + k + ' ')) continue;
    let sc = k.length + c.p * 3;
    for (const g of c.g) if (f.includes(' ' + g + ' ')) sc += 5;
    if (sc > score) { score = sc; best = c; }
  }
  return best;
}

export async function readScoreInfo(doc, fileName, composers, opts = {}) {
  const out = { title: '', composer: '' };
  let lines = [], meta = null;
  if (doc.pdf) {
    try {
      meta = await doc.pdf.getMetadata().catch(() => null);
      const page = await doc.pdf.getPage(1);
      const vp = page.getViewport({ scale: 1 });
      const tc = await page.getTextContent();
      // (the music's own signs come through as text from their font — control characters, private
      // letters, a dynamic like "mf" set as big as a heading: they are no words, and were taken for the
      // biggest words on the page, the title)
      const DYN = /^(p{1,4}|pf|m[pf]|f{1,4}|s?fz?p?|sfp|fp|rf|rfz|sff|z|cresc\.?|dim\.?|decresc\.?)$/i;
      const items = tc.items.map((it) => ({ ...it, str: String(it.str || '').replace(/[\u0000-\u001f\u007f-\u009f\ue000-\uf8ff\ufffd]/g, '') }))
        .filter((it) => it.str.trim() && /[\p{L}\p{N}]/u.test(it.str) && !DYN.test(it.str.trim())).map((it) => ({
        s: it.str, x: it.transform[4], y: vp.height - it.transform[5], size: Math.hypot(it.transform[2], it.transform[3]) || it.height || 10,
      }));
      items.sort((a, b) => a.y - b.y || a.x - b.x);
      // (words at one height but far apart — "Violoncello" on the left, "Max Bruch, Op. 47" on the
      // right — are separate lines: a gap wider than a fifth of the page)
      const ends = (l) => Math.max(...l.parts.map((q) => q.x + q.s.length * q.size * 0.5));
      for (const it of items) {
        const L = lines.find((l) => Math.abs(l.y - it.y) < Math.max(2.5, it.size * 0.35) && !(it.x - ends(l) > vp.width * 0.2 || Math.min(...l.parts.map((q) => q.x)) - (it.x + it.s.length * it.size * 0.5) > vp.width * 0.2));
        if (L) { L.parts.push(it); L.size = Math.max(L.size, it.size); }
        else lines.push({ y: it.y, size: it.size, parts: [it] });
      }
      lines = lines.map((l) => {
        l.parts.sort((a, b) => a.x - b.x);
        let text = '', lastX = -1e9;
        for (const p of l.parts) { text += (text && p.x - lastX > p.size * 0.25 ? ' ' : '') + p.s; lastX = p.x + p.s.length * p.size * 0.5; }
        return { text: tidy(text), y: l.y, size: l.size, x: l.parts[0].x, right: l.parts[l.parts.length - 1].x, H: vp.height, W: vp.width };
      }).filter((l) => l.text.length > 1);
    } catch (e) { console.warn('read info', e); lines = []; }
  }
  // A scan or photo (no text in the file): the top of the first page is read as a picture, the way
  // the words of a printed page are read, and the same rules find the title and the composer.
  if (!lines.filter((l) => l.y < l.H * 0.45 && /\p{L}{3}/u.test(l.text)).length && opts.ocr) {
    try { lines = (await opts.ocr(doc)) || []; } catch (e) { console.warn('read info (picture)', e); lines = []; }
  }
  if (lines.length || meta) {
    try {
      // (a title has a word in it: "8 pf", "14", a dynamic beside a bar number, never)
      let topLines = lines.filter((l) => l.y < l.H * 0.42 && /\p{L}{3}/u.test(l.text) && !JUNK.test(l.text) && !NOT_TITLE.test(l.text) && !MOVEMENT_NO.test(l.text.trim()) && /\p{L}{2}/u.test(l.text) && l.text.length < 90);
      // a tempo mark is not the title, unless it is clearly the biggest words on the page ("Allegro appassionato")
      // (and only when it is set larger than the words of the music itself: a tempo alone at the top
      // of a later page or of a part, "Allegro con brio", is the movement, not the piece)
      { const mx = Math.max(0, ...topLines.map((l) => l.size));
        const body = lines.filter((l) => l.y > l.H * 0.2).map((l) => l.size).sort((a, b) => a - b), med = body.length ? body[body.length >> 1] : 0;
        topLines = topLines.filter((l) => !TEMPO.test(l.text) || l.size >= mx * 0.98 && topLines.filter((o) => o.size >= mx * 0.8).length === 1 && topLines.length > 1 && (!med || l.size >= med * 1.5)); }
      // the biggest line is sometimes the composer's name: that is the composer, and the title is the next
      const nameOnly = (l) => { const c = findComposer(l.text, composers); return c && l.text.length < 40 && fold(l.text).split(' ').length <= 4 ? c : null; };
      if (topLines.length) {
        const sizes = topLines.map((l) => l.size).sort((a, b) => a - b);
        const median = sizes[sizes.length >> 1];
        const bySize = [...topLines].sort((a, b) => b.size - a.size || a.y - b.y);
        let big = bySize[0];
        const nc = nameOnly(big);
        if (nc) { out.composer = nc.n; topLines = topLines.filter((l) => l !== big); big = bySize.find((l) => topLines.includes(l) && !nameOnly(l)); }
        // (or, the biggest words being also the first on the page: a title set only a little bigger)
        const first = big && topLines.every((l) => l.y >= big.y);
        if (big && (big.size >= median * 1.15 || topLines.length <= 3 || nc || (first && big.size >= median * 1.0))) {
          out.title = titleCase(big.text);
          // "Sonata" alone: the line under it says which ("No. 2 in G minor, Op. 5")
          const nearBelow = (l) => l !== big && l.y > big.y && l.y - big.y < big.size * 3 && l.size >= big.size * 0.45 && l.text.length < 60 && !nameOnly(l);
          const next = topLines.find((l) => nearBelow(l) && (GENERIC.test(big.text.trim()) || /(op\.?\s*\d|no\.?\s*\d|nr\.?\s*\d|bwv|hob|k\.\s*\d|kv|d\.\s*\d|in [a-h](\s|$|-|♭|♯)|in [a-h] (major|minor|dur|moll)|en [a-z]+ (majeur|mineur)|for |pour |für |per )/i.test(l.text)));
          // (the composer's name on that line — "M. Clementi, Opus 36 No. 1" — is the composer, not the title)
          let nx = next ? next.text : '';
          if (nx) { const c2 = findComposer(nx, composers); if (c2) { const last = c2.n.split(' ').pop(), f2 = nx.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase(), at = f2.lastIndexOf(last.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()); if (at >= 0) nx = tidy(nx.slice(at + last.length).replace(/^\s*\(.*?\)/, '')); } }
          if (next && nx && /\p{L}|\d/u.test(nx)) out.title += (GENERIC.test(big.text.trim()) && !/^[,(]/.test(nx) ? ' ' : ', ') + titleCase(nx);
          // a word above it that belongs to the title ("Six Suites" / "for Cello Solo" are fine; "Sonata" over "No. 1" too)
          const above = topLines.find((l) => l !== big && l.y < big.y && big.y - l.y < big.size * 2 && l.size >= big.size * 0.7 && GENERIC.test(l.text.trim()));
          if (above && !out.title.toLowerCase().includes(above.text.toLowerCase())) out.title = titleCase(above.text) + ' ' + out.title;
        }
      }
      const pdfTitle = meta && meta.info && meta.info.Title;
      // (not a name a scanner or a program gave it: "SKM_C300i22020317080", "Scan_0001", "IMG_2041")
      const machine = (t) => /^mutopia-\d/i.test(t.trim()) || (/^[\w.-]+$/.test(t.trim()) && (/\d{5,}/.test(t) || /^(skm|km|img|scan|doc|ccf|mx|bizhub|xerox|canon|epson|hp|brother|ricoh)[_\-\d]/i.test(t.trim())));
      if (!out.title && pdfTitle && !/untitled|microsoft|\.pdf|\.mus|sibelius|finale/i.test(pdfTitle) && !machine(pdfTitle)) out.title = tidy(pdfTitle);
      const allTop = lines.filter((l) => l.y < l.H * 0.5).map((l) => l.text).join('  ');
      // (the composer stands on the right, above the music: a known name there comes first — a word of
      // the title that is also a name, "Rieselnder Bach" (a brook), is not the composer)
      const rightTop = lines.filter((l) => l.y < l.H * 0.42 && l.x > l.W * 0.45);
      const cRight = findComposer(rightTop.map((l) => l.text).join('  '), composers);
      let c = cRight || findComposer(allTop, composers) || findComposer((meta && meta.info && meta.info.Author) || '', composers);
      if (c && !cRight && (globalThis.__composerRight ?? 1)) {
        const k0 = c.k.find((k) => (' ' + fold(allTop) + ' ').includes(' ' + k + ' '));
        // (the name found only inside a line of the title or subtitle, never with its own first names)
        const has = (t, w) => (' ' + fold(t) + ' ').includes(' ' + w + ' ');
        const inTitle = k0 && lines.some((l) => l.y < l.H * 0.42 && !rightTop.includes(l) && has(l.text, k0) && !c.g.some((g) => has(l.text, g)));
        const nm = rightTop.map((l) => tidy(l.text.replace(/\(.*?\)|\d{4}\s*[-–]\s*\d{0,4}|^(music by|composed by|komponiert von|von|by|de|par|di)\s+/gi, ''))).find((t) => looksLikeName(t) && !NOT_TITLE.test(t) && !TEMPO.test(t));
        if (inTitle && nm) { c = null; out.composer = titleCase(nm); }
      }
      if (c) out.composer = c.n;
      else {
        // "Music by …", "Words and Music by …", "Composed by …" (not "Arranged by …")
        if (!out.composer) for (const l of lines) {
          if (l.y > l.H * 0.42) continue;
          const m = l.text.match(/\b(?:words and music|music and words|music|composed|komponiert|musique|musica|música)\s+(?:by|von|de|di|par)\s+(.+)$/i);
          if (m) { const nm = tidy(m[1].replace(/\(.*?\)|\d{4}\s*[-–]\s*\d{0,4}/g, '').split(/\s*(?:,|;|\barr\.|\barranged\b)\s*/i)[0]); if (looksLikeName(nm)) { out.composer = titleCase(nm); break; } }
        }
        // a name on the right above the music ("Carl Davidoff (1838-1889)"), but only if it looks like a name
        if (!out.composer) for (const l of lines) {
          if (!(l.y < l.H * 0.42 && l.x > l.W * 0.45) || JUNK.test(l.text) || NOT_TITLE.test(l.text) || TEMPO.test(l.text) || out.title.includes(l.text)) continue;
          const nm = tidy(l.text.replace(/\(.*?\)|\d{4}\s*[-–]\s*\d{0,4}|^(music by|composed by|komponiert von|von|by|de|par|di)\s+/gi, ''));
          if (looksLikeName(nm)) { out.composer = titleCase(nm); break; }
        }
      }
    } catch (e) { console.warn('read info', e); }
  }
  if (!out.composer) { const c = findComposer(fileName.replace(/[_-]+/g, ' '), composers); if (c) out.composer = c.n; }
  // a title that is only a composer's name, a number or a generic word is no title
  if (out.title && (findComposer(out.title, composers) && fold(out.title).split(' ').length <= 3 || !/\p{L}{3}/u.test(out.title))) out.title = '';
  // ("1. Prayer", "I. Prélude": the number of the piece in its set is not part of its name)
  if (out.title) { const t = out.title.replace(/^(\d{1,2}|[IVX]{1,4})\.\s+(?=\p{L}{3})/u, ''); if (t !== out.title && /\p{L}{3}/u.test(t)) out.title = t; }
  if (out.title.length > 80) out.title = out.title.slice(0, 80).replace(/\s+\S*$/, '') + '…';
  return out;
}

// ---------- half-page turn: find a gap between systems ----------
function inkProfile(canvas, rows) {
  const w = 160, h = rows;
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  const g = c.getContext('2d', { willReadFrequently: true });
  g.drawImage(canvas, 0, 0, w, h);
  const d = g.getImageData(0, 0, w, h).data;
  const prof = new Float32Array(h);
  for (let y = 0; y < h; y++) {
    let dark = 0;
    for (let x = 8; x < w - 8; x++) { const i = (y * w + x) * 4; if (d[i] + d[i + 1] + d[i + 2] < 560) dark++; }
    prof[y] = dark / (w - 16);
  }
  return prof;
}
// Returns a split position (0..1): the middle of the page, as on the music stand, moved to the gap
// between systems nearest to it (blank across the width on both pages), so no line of music is cut.
// The middle wins over a wider gap further away: what is left of this page stays about half.
export function findSplit(curCanvas, nextCanvas) {
  try {
    const rows = 400;
    const a = inkProfile(curCanvas, rows), b = inkProfile(nextCanvas, rows);
    const gaps = [];
    let start = -1;
    for (let y = 0; y <= rows; y++) {
      const blank = y < rows && a[y] < 0.012 && b[y] < 0.012;
      if (blank && start < 0) start = y;
      if (!blank && start >= 0) { if (y - start >= 3) gaps.push({ mid: (start + y - 1) / 2 / rows, len: (y - start) / rows }); start = -1; }
    }
    // (nearest the middle first, within a third of a page of it; a wider gap only breaks a near tie)
    for (const reach of [0.12, 0.2]) {
      const near = gaps.filter((g) => Math.abs(g.mid - 0.5) <= reach);
      if (near.length) return near.sort((x, y) => (Math.abs(x.mid - 0.5) - x.len * 0.25) - (Math.abs(y.mid - 0.5) - y.len * 0.25))[0].mid;
    }
    return 0.5;
  } catch { return 0.5; }
}

// ---------- page order (deleted pages are hidden, never destroyed) ----------
// A page can also be cut into pieces (cuts: heights 0..1 where it is cut); each piece shows as
// its own page. Markings stay with the original page, so nothing is lost.
const ON_PHONE = typeof navigator !== 'undefined' && /iPhone|iPod/.test(navigator.userAgent || '');
export function mapDoc(doc, map, cuts, glue) {
  const order = (map || [...Array(doc.pages).keys()]).filter((i) => i >= 0 && i < doc.pages);
  const pieces = [];
  for (const o of order) {
    const ys = [0, ...((cuts && cuts[o]) || []).filter((y) => y > 0.02 && y < 0.98).sort((a, b) => a - b), 1];
    for (let k = 0; k < ys.length - 1; k++) pieces.push({ o, box: ys.length > 2 ? { x: 0, y: ys[k], w: 1, h: ys[k + 1] - ys[k] } : null });
  }
  // lines glued from the next page onto the end of this one, so a turn falls where it should
  let glued = false;
  if (glue) {
    for (let i = 0; i + 1 < pieces.length; i++) {
      const p = pieces[i], q = pieces[i + 1], g = glue[p.o];
      if (!g || p.box || q.box || q.o !== g.next || !(g.cut > 0.03 && g.cut < 0.97)) continue;
      p.parts = [{ o: p.o, y0: 0, y1: Math.min(1, Math.max(0.2, g.end || 1)) }, { o: q.o, y0: g.top || 0, y1: g.cut }];
      q.box = { x: 0, y: g.cut, w: 1, h: 1 - g.cut };
      glued = true;
    }
  }
  if (!map && !glued && !pieces.some((p) => p.box)) return { ...doc, orig: (i) => i, piece: () => null, composite: () => false };
  const sizeOf = (p) => {
    if (!p.parts) return doc.sizes[p.o];
    const [w0] = doc.sizes[p.parts[0].o];
    let h = 0; for (const q of p.parts) { const [pw, ph] = doc.sizes[q.o]; h += (q.y1 - q.y0) * ph * (w0 / pw); }
    return [w0, h];
  };
  return {
    ...doc,
    pages: pieces.length,
    sizes: pieces.map(sizeOf),
    music: (i, w, h) => { const p = pieces[i]; return !p || p.parts || p.box || !doc.music ? Promise.resolve(null) : doc.music(p.o, w, h); },
    render: async (i, canvas, w, h, opts) => {
      const p = pieces[i];
      if (!p.parts) return doc.render(p.o, canvas, w, h, opts);
      // draw each part one under the other at the width of the page
      canvas.width = Math.round(w); canvas.height = Math.round(h);
      const g = canvas.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, canvas.width, canvas.height);
      const [W0, H0] = sizeOf(p); const k = canvas.width / W0;
      let y = 0;
      for (const q of p.parts) {
        const [pw, ph] = doc.sizes[q.o];
        const tmp = document.createElement('canvas');
        const tw = canvas.width, th = Math.round(tw * ph / pw);
        await doc.render(q.o, tmp, tw, th);
        const sy = q.y0 * tmp.height, sh = (q.y1 - q.y0) * tmp.height;
        g.drawImage(tmp, 0, sy, tmp.width, sh, 0, y, canvas.width, sh * (canvas.width / tmp.width));
        y += sh * (canvas.width / tmp.width);
        tmp.width = tmp.height = 0;
      }
      void H0; void k;
    },
    pixHas: (i, w, h) => (pieces[i].parts || !doc.pixHas ? Promise.resolve(true) : doc.pixHas(pieces[i].o, w, h)),
    renderView: (i, canvas, view, w, h, opts) => (pieces[i].parts || !doc.renderView ? Promise.resolve(false) : doc.renderView(pieces[i].o, canvas, view, w, h, opts)),
    orig: (i) => pieces[i].o,
    piece: (i) => pieces[i].box,
    composite: (i) => !!pieces[i].parts,
    gluedFrom: (i) => (pieces[i].parts ? pieces[i].parts[1].o : null),
    destroy: () => doc.destroy(),
    base: doc,
  };
}

// Blank rows across the width of a page (0..1), for cutting between systems.
export function pageGaps(canvas) {
  const rows = 500;
  const prof = inkProfile(canvas, rows);
  const gaps = [];
  let start = -1;
  for (let y = 0; y <= rows; y++) {
    const blank = y < rows && prof[y] < 0.01;
    if (blank && start < 0) start = y;
    if (!blank && start >= 0) { if (y - start >= 3) gaps.push({ mid: (start + y - 1) / 2 / rows, len: (y - start) / rows }); start = -1; }
  }
  return gaps;
}
// Places where both pages are blank, for half-page turns that stay between the systems.
export function commonGaps(curCanvas, nextCanvas) {
  const rows = 400;
  const a = inkProfile(curCanvas, rows), b = inkProfile(nextCanvas, rows);
  const out = [];
  let start = -1;
  for (let y = 0; y <= rows; y++) {
    const blank = y < rows && a[y] < 0.012 && b[y] < 0.012;
    if (blank && start < 0) start = y;
    if (!blank && start >= 0) { if (y - start >= 2) out.push({ mid: (start + y - 1) / 2 / rows, len: (y - start) / rows }); start = -1; }
  }
  return out.filter((g) => g.mid > 0.08 && g.mid < 0.92);
}

// ---------- trim white margins ----------
// Returns the box (0..1) that holds the printed content, with a little air around it.
export function contentBox(canvas) {
  const w = 220, h = Math.max(1, Math.round((220 * canvas.height) / canvas.width));
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  const g = c.getContext('2d', { willReadFrequently: true });
  g.drawImage(canvas, 0, 0, w, h);
  const d = g.getImageData(0, 0, w, h).data;
  const rowInk = new Uint16Array(h), colInk = new Uint16Array(w);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const i = (y * w + x) * 4;
    if (d[i] + d[i + 1] + d[i + 2] < 600) { rowInk[y]++; colInk[x]++; }
  }
  // ignore specks: a row/column counts only with a few dark pixels
  const firstRow = rowInk.findIndex((v) => v > 1), lastRow = h - 1 - [...rowInk].reverse().findIndex((v) => v > 1);
  const firstCol = colInk.findIndex((v) => v > 1), lastCol = w - 1 - [...colInk].reverse().findIndex((v) => v > 1);
  if (firstRow < 0 || firstCol < 0) return { x: 0, y: 0, w: 1, h: 1 };
  const pad = 0.018;
  const x0 = Math.max(0, firstCol / w - pad), x1 = Math.min(1, (lastCol + 1) / w + pad);
  const y0 = Math.max(0, firstRow / h - pad), y1 = Math.min(1, (lastRow + 1) / h + pad);
  return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
}
export function unionBox(a, b) {
  if (!a) return b; if (!b) return a;
  const x0 = Math.min(a.x, b.x), y0 = Math.min(a.y, b.y), x1 = Math.max(a.x + a.w, b.x + b.w), y1 = Math.max(a.y + a.h, b.y + b.h);
  return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
}
