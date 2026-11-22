import { SMUFL_ALT } from './smufl-alt.js';

// What a page made by a notation program says of its music, as it wrote it: the signs (heads,
// clefs, accidentals, rests… characters of a SMuFL music font at their exact places) and the lines
// drawn (stems, barlines and staff lines stroked; beams filled). In the frame of a picture of the
// page drawn with the given viewport, so that the reader can take them as they are.

// the signs: each character of the Private Use Area of a music font, with its place (the left end of
// its baseline), the font's size and the character's width, in the picture's pixels
export async function pdfGlyphs(page, vp) {
  const tc = await page.getTextContent();
  const out = [];
  for (const it of tc.items) {
    const chars = [...(it.str || '')]; if (!chars.length) continue;
    if (!chars.some((ch) => { const c = ch.codePointAt(0); return c >= 0xe000 && c <= 0xf8ff; })) continue;
    const size = Math.hypot(it.transform[0], it.transform[1]);
    const n = chars.length, adv = (it.width || 0) / n;
    chars.forEach((ch, i) => {
      const c = ch.codePointAt(0); if (c < 0xe000 || c > 0xf8ff) return;
      const [x, y] = vp.convertToViewportPoint(it.transform[4] + adv * i, it.transform[5]);
      out.push({ cp: c, x, y, size: size * vp.scale, w: (n === 1 ? it.width : adv) * vp.scale });
    });
  }
  return out;
}

// the lines: stroked straight segments (with their width) and filled polygons of straight sides
export async function pdfVectors(page, vp, OPS) {
  const ol = await page.getOperatorList();
  const font = (name) => { try { return page.commonObjs.has(name) ? page.commonObjs.get(name) : null; } catch { return null; } };
  const mul = (a, b) => [a[0] * b[0] + a[2] * b[1], a[1] * b[0] + a[3] * b[1], a[0] * b[2] + a[2] * b[3], a[1] * b[2] + a[3] * b[3], a[0] * b[4] + a[2] * b[5] + a[4], a[1] * b[4] + a[3] * b[5] + a[5]];
  let ctm = vp.transform.slice(); const stack = []; let lw = 1, path = [];
  const pt = (x, y) => [ctm[0] * x + ctm[2] * y + ctm[4], ctm[1] * x + ctm[3] * y + ctm[5]];
  const scaleW = () => Math.sqrt(Math.abs(ctm[0] * ctm[3] - ctm[1] * ctm[2]));
  const lines = [], polys = [], glyphs = [];
  // the text state, to place each character exactly (its advance from the font's widths)
  let fam = null, Tm = [1, 0, 0, 1, 0, 0], Tlm = [1, 0, 0, 1, 0, 0], fs = 1, Tc = 0, Tw = 0, Th = 1, Ts = 0, TL = 0, fontMat = [0.001, 0, 0, 0.001, 0, 0];
  const tStack = [];
  const flush = (kind) => {
    for (const sub of path) {
      if (kind === 'stroke') { for (let i = 1; i < sub.length; i++) if (!sub[i].curve && !sub[i - 1].curve) lines.push({ x0: sub[i - 1][0], y0: sub[i - 1][1], x1: sub[i][0], y1: sub[i][1], w: lw * scaleW() }); }
      else if (sub.length >= 3 && sub.length <= 6 && !sub.some((q) => q.curve)) polys.push(sub.map((q) => [q[0], q[1]]));
    }
    path = [];
  };
  for (let i = 0; i < ol.fnArray.length; i++) {
    const fn = ol.fnArray[i], a = ol.argsArray[i];
    if (fn === OPS.save) { stack.push([ctm, lw]); tStack.push([fs, Tc, Tw, Th, Ts, TL, fontMat, fam]); }
    else if (fn === OPS.restore) { const s = stack.pop(); if (s) [ctm, lw] = s; const t = tStack.pop(); if (t) [fs, Tc, Tw, Th, Ts, TL, fontMat, fam] = t; }
    else if (fn === OPS.beginText) { Tm = [1, 0, 0, 1, 0, 0]; Tlm = Tm.slice(); }
    else if (fn === OPS.setFont) {
      fs = a[1]; const f = font && font(a[0]); fontMat = (f && f.fontMatrix) || [0.001, 0, 0, 0.001, 0, 0];
      // (the font's family, for its own characters: Bravura, Leland, Petaluma)
      const nm = (f && (f.name || f.loadedName || '')) + ''; fam = Object.keys(SMUFL_ALT).find((k) => nm.includes(k)) || null;
    }
    else if (fn === OPS.setTextMatrix) { Tm = a.slice(0, 6); Tlm = Tm.slice(); }
    else if (fn === OPS.moveText) { Tlm = mul(Tlm, [1, 0, 0, 1, a[0], a[1]]); Tm = Tlm.slice(); }
    else if (fn === OPS.setLeadingMoveText) { TL = -a[1]; Tlm = mul(Tlm, [1, 0, 0, 1, a[0], a[1]]); Tm = Tlm.slice(); }
    else if (fn === OPS.nextLine) { Tlm = mul(Tlm, [1, 0, 0, 1, 0, -TL]); Tm = Tlm.slice(); }
    else if (fn === OPS.setLeading) TL = a[0];
    else if (fn === OPS.setCharSpacing) Tc = a[0];
    else if (fn === OPS.setWordSpacing) Tw = a[0];
    else if (fn === OPS.setHScale) Th = a[0] / 100;
    else if (fn === OPS.setTextRise) Ts = a[0];
    else if (fn === OPS.showText || fn === OPS.showSpacedText || fn === OPS.nextLineShowText || fn === OPS.nextLineSetSpacingShowText) {
      const run = fn === OPS.showText || fn === OPS.showSpacedText ? a[0] : a[a.length - 1];
      for (const g of run || []) {
        if (typeof g === 'number') { Tm = mul(Tm, [1, 0, 0, 1, (-g / 1000) * fs * Th, 0]); continue; }
        if (!g) continue;
        let cp = g.unicode && g.unicode.length ? g.unicode.codePointAt(0) : 0;
        if (fam && cp >= 0xf400 && SMUFL_ALT[fam][cp]) cp = SMUFL_ALT[fam][cp];
        const adv = ((g.width || 0) * fontMat[0] * fs + Tc + (g.isSpace ? Tw : 0)) * Th;
        if ((cp >= 0xe000 && cp <= 0xf8ff) || (cp >= 0x30 && cp <= 0x39)) {
          const M = mul(ctm, Tm), x = M[4] + M[2] * Ts, y = M[5] + M[3] * Ts;
          const sz = fs * Math.sqrt(Math.abs(M[0] * M[3] - M[1] * M[2]));
          const wv = adv * Math.hypot(M[0], M[1]);
          glyphs.push({ cp, x, y, size: sz, w: wv, ...(cp < 0xe000 ? { text: true } : {}) });
        }
        Tm = mul(Tm, [1, 0, 0, 1, adv, 0]);
      }
    }
    else if (fn === OPS.transform) ctm = mul(ctm, a);
    else if (fn === OPS.setLineWidth) lw = a[0];
    else if (fn === OPS.constructPath) {
      const [ops, args] = a; let k = 0, cur = null;
      for (const op of ops) {
        if (op === OPS.moveTo) { cur = [pt(args[k], args[k + 1])]; path.push(cur); k += 2; }
        else if (op === OPS.lineTo) { if (cur) cur.push(pt(args[k], args[k + 1])); k += 2; }
        else if (op === OPS.curveTo) { if (cur) { const q = pt(args[k + 4], args[k + 5]); q.curve = true; cur.push(q); } k += 6; }
        else if (op === OPS.curveTo2 || op === OPS.curveTo3) { if (cur) { const q = pt(args[k + 2], args[k + 3]); q.curve = true; cur.push(q); } k += 4; }
        else if (op === OPS.rectangle) { const [x, y, w, h] = args.slice(k, k + 4); cur = [pt(x, y), pt(x + w, y), pt(x + w, y + h), pt(x, y + h)]; path.push(cur); k += 4; }
        else if (op === OPS.closePath) { /* the polygon closes itself */ }
      }
    }
    else if (fn === OPS.stroke || fn === OPS.closeStroke) flush('stroke');
    else if (fn === OPS.fill || fn === OPS.eoFill || fn === OPS.fillStroke || fn === OPS.eoFillStroke || fn === OPS.closeFillStroke || fn === OPS.closeEOFillStroke) flush('fill');
    else if (fn === OPS.endPath) path = [];
  }
  return { lines, polys, glyphs };
}
