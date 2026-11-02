# Make the templates for the music reader's marks (dynamics, fingering, ornaments, articulations,
# rests) from several music fonts and a text font, with the reader's own shapeOf.
import asyncio, json
from playwright.async_api import async_playwright
MUSIC = ['Bravura', 'Leland', 'Gootville', 'Petaluma', 'FinaleMaestro', 'MScore', 'Campania', 'FinaleBroadway']
TEXT = ['Edwin-Roman', 'Edwin-Bold', 'Edwin-BdIta', 'Edwin-Italic']
JS = r"""
async ([MUSIC, TEXT]) => {
  const { shapeOf } = await import('/js/omr.js');
  for (const f of [...MUSIC, ...TEXT]) { const ff = new FontFace(f, `url(/_fonts/${f}.otf)`); await ff.load(); document.fonts.add(ff); }
  const SPX = 20;
  const cut = (font, ch, px) => {
    const c = document.createElement('canvas'); c.width = SPX * 10; c.height = SPX * 10;
    const x = c.getContext('2d', { willReadFrequently: true }); x.fillStyle = '#000'; x.font = `${px}px "${font}"`; x.fillText(ch, SPX * 3, SPX * 6);
    const d = x.getImageData(0, 0, c.width, c.height).data, b = new Uint8Array(c.width * c.height);
    let x0 = c.width, y0 = c.height, x1 = -1, y1 = -1;
    for (let i = 0; i < b.length; i++) if (d[i * 4 + 3] > 110) { b[i] = 1; const px2 = i % c.width, py = (i - px2) / c.width; if (px2 < x0) x0 = px2; if (px2 > x1) x1 = px2; if (py < y0) y0 = py; if (py > y1) y1 = py; }
    if (x1 < 0) return null;
    return shapeOf(b, c.width, x0, y0, x1, y1, SPX);
  };
  const out = {};
  const add = (k, s) => { if (!s) return; const key = s.m; out[k] = out[k] || []; if (!out[k].some((q) => q.m === key)) out[k].push({ m: s.m, ws: +s.ws.toFixed(3), hs: +s.hs.toFixed(3) }); };
  const M = { Dp: 0xE520, Dm: 0xE521, Df: 0xE522, Dr: 0xE523, Ds: 0xE524, Dz: 0xE525,
    F0: 0xED10, F1: 0xED11, F2: 0xED12, F3: 0xED13, F4: 0xED14, F5: 0xED15,
    trill: 0xE566, turn: 0xE567, turnInv: 0xE568, prall: 0xE56C, mord: 0xE56D,
    ferm: [0xE4C0, 0xE4C1], acc: [0xE4A0, 0xE4A1], ten: 0xE4A4, stacciss: [0xE4A6, 0xE4A7], marc: [0xE4AC, 0xE4AD],
    down: 0xE610, up: 0xE612, breath: 0xE4CE, caes: 0xE4D1,
    r4: 0xE4E5, r8: 0xE4E6, r16: 0xE4E7, r32: 0xE4E8 };
  for (const f of MUSIC) for (const [k, cps] of Object.entries(M)) for (const cp of [].concat(cps)) add(k, cut(f, String.fromCodePoint(cp), SPX * 4));
  // text fonts: fingering digits about 1.1 to 1.5 spaces tall, dynamics letters as tall as the
  // music fonts' f, the letters of guitar fingering (p i m a) upright
  const heightOf = (font, ch, px) => { const x = document.createElement('canvas').getContext('2d'); x.font = `${px}px "${font}"`; const m = x.measureText(ch); return (m.actualBoundingBoxAscent + m.actualBoundingBoxDescent); };
  for (const f of TEXT) {
    for (const want of [1.05, 1.35, 1.7]) {
      const px = (want * SPX) / (heightOf(f, '3', 100) / 100);
      for (let n = 0; n <= 5; n++) add('F' + n, cut(f, String(n), px));
    }
    if (f === 'Edwin-BdIta' || f === 'Edwin-Italic') {
      for (const want of [1.6, 2.1]) { const px = (want * SPX) / (heightOf(f, 'f', 100) / 100); for (const L of 'pmfrsz') add('D' + L, cut(f, L, px)); }
    } else {
      for (const want of [0.75, 1.0]) { const px = (want * SPX) / (heightOf(f, 'x', 100) / 100); for (const L of 'pima') add('T' + L, cut(f, L, px)); }
    }
  }
  return out;
}
"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page()
        await pg.goto('http://localhost:8765/index.html'); await pg.wait_for_timeout(800)
        out = await pg.evaluate(JS, [MUSIC, TEXT])
        print({k: len(v) for k, v in out.items()})
        hdr = "// Templates for the music reader's marks: dynamics letters (D*), fingering digits (F*), guitar\n// fingers (T*), ornaments, articulations and rests, cut from the music fonts Bravura, Leland,\n// Gootville, Petaluma, Finale Maestro, MScore, Campania, Finale Broadway and the text font Edwin\n// (SIL Open Font License; MScore GPL with font exception), shrunk to the reader's 12x20 grid.\n// Made by tools/gen/marks_gen.py.\n"
        open('/home/claude/s24/Payload/Stand.app/www/js/omr-marks-shapes.js', 'w').write(hdr + 'export const MARKS = ' + json.dumps(out, separators=(',', ':')) + ';\n')
        await b.close()
asyncio.run(main())
