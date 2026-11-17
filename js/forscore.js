// forScore's own files, opened in Stand.
// A .4sc ("forScore container", what forScore makes when a score is shared) holds the score's PDF
// with forScore's own notes about it. Its inside is not published, so the PDF is looked for both
// ways it can be kept: as a file in a .zip, or as the PDF's own bytes inside the container.
// A .4ss (a forScore setlist written by hand) can carry its scores' PDFs as Base64.
import { isZip, zipEntries, zipRead } from './zipread.js';

const PDF_HEAD = [0x25, 0x50, 0x44, 0x46, 0x2d];   // %PDF-
const EOF = [0x25, 0x25, 0x45, 0x4f, 0x46];        // %%EOF

function find(bytes, pat, from = 0, back = false) {
  const n = pat.length;
  if (back) {
    for (let i = Math.min(bytes.length - n, from); i >= 0; i--) { let k = 0; while (k < n && bytes[i + k] === pat[k]) k++; if (k === n) return i; }
    return -1;
  }
  for (let i = from; i <= bytes.length - n; i++) { let k = 0; while (k < n && bytes[i + k] === pat[k]) k++; if (k === n) return i; }
  return -1;
}

// The PDFs in a forScore file: [{ name, data: ArrayBuffer }] (the biggest first: the score itself)
export async function forScorePdfs(blob, name = 'Score.4sc') {
  const base = String(name).split('/').pop().replace(/\.(4sc|4ss)$/i, '');
  const out = [];
  if (await isZip(blob)) {
    for (const e of await zipEntries(blob)) {
      if (/(^|\/)(__MACOSX|\.)/.test(e.name)) continue;
      if (/\.pdf$/i.test(e.name)) out.push({ name: base + '.pdf', inner: e.name, data: await (await zipRead(blob, e)).arrayBuffer() });
      else if (/\.(4sc)$/i.test(e.name)) out.push(...(await forScorePdfs(await zipRead(blob, e), e.name)));
    }
    if (!out.length) {
      // (a PDF kept under another name in it: known by its first bytes)
      for (const e of await zipEntries(blob)) {
        if (e.size < 200 || e.size > 4e8) continue;
        const b = await zipRead(blob, e);
        const head = new Uint8Array(await b.slice(0, 1024).arrayBuffer());
        if (find(head, PDF_HEAD) >= 0) out.push({ name: base + '.pdf', inner: e.name, data: await b.arrayBuffer() });
      }
    }
  } else {
    const bytes = new Uint8Array(await blob.arrayBuffer());
    // a setlist written as XML, with the scores' PDFs in it as Base64
    const head = new TextDecoder().decode(bytes.slice(0, 512));
    if (/<forScore\b/i.test(head)) {
      const xml = new TextDecoder().decode(bytes);
      const re = /<score\b[^>]*?\btitle="([^"]*)"[^>]*?\bdata="([A-Za-z0-9+/=\s]+)"/g;
      let m;
      while ((m = re.exec(xml))) {
        try {
          const bin = atob(m[2].replace(/\s+/g, ''));
          const u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
          if (find(u.subarray(0, 1024), PDF_HEAD) >= 0) out.push({ name: (m[1] || base) + '.pdf', data: u.buffer });
        } catch {}
      }
    } else {
      // the PDF's own bytes inside the container: from "%PDF-" to its last "%%EOF"
      let at = find(bytes, PDF_HEAD);
      while (at >= 0) {
        const next = find(bytes, PDF_HEAD, at + 5);
        const limit = next >= 0 ? next - 1 : bytes.length - 1;
        const end = find(bytes, EOF, limit, true);
        if (end > at) { out.push({ name: base + '.pdf', data: bytes.slice(at, Math.min(bytes.length, end + 5)).buffer }); }
        at = next;
      }
    }
  }
  return out.sort((a, b) => b.data.byteLength - a.data.byteLength);
}
