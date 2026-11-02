# More fonts for the reader's core shapes (clefs, accidentals, time digits, rests), above all the
# handwritten jazz fonts (Petaluma, MuseJazz, Finale Broadway) and MScore / Campania, which the
# first set (Bravura, Leland, Leipzig, Gootville, Finale Maestro) does not cover.
import asyncio, json
from playwright.async_api import async_playwright
MUSIC = ['Emmentaler']
JS = r"""
async (MUSIC) => {
  const { shapeOf } = await import('/js/omr.js');
  for (const f of MUSIC) { const ff = new FontFace(f, `url(/_fonts/${f}.otf)`); await ff.load(); document.fonts.add(ff); }
  const SPX = 20;
  const cut = (font, ch, px) => {
    const c = document.createElement('canvas'); c.width = SPX * 12; c.height = SPX * 14;
    const x = c.getContext('2d', { willReadFrequently: true }); x.fillStyle = '#000'; x.font = `${px}px "${font}"`; x.fillText(ch, SPX * 3, SPX * 8);
    const d = x.getImageData(0, 0, c.width, c.height).data, b = new Uint8Array(c.width * c.height);
    let x0 = c.width, y0 = c.height, x1 = -1, y1 = -1;
    for (let i = 0; i < b.length; i++) if (d[i * 4 + 3] > 110) { b[i] = 1; const px2 = i % c.width, py = (i - px2) / c.width; if (px2 < x0) x0 = px2; if (px2 > x1) x1 = px2; if (py < y0) y0 = py; if (py > y1) y1 = py; }
    if (x1 < 0) return null;
    return shapeOf(b, c.width, x0, y0, x1, y1, SPX);
  };
  const out = {};
  const add = (k, s) => { if (!s) return; out[k] = out[k] || []; if (!out[k].some((q) => q.m === s.m)) out[k].push({ m: s.m, ws: +s.ws.toFixed(3), hs: +s.hs.toFixed(3) }); };
  // LilyPond's Emmentaler: its own places for the glyphs (from the font's own table)
  const M = { treble: 0xE085, bass: 0xE083, alto: 0xE07F, sharp: 0xE013, flat: 0xE021, natural: 0xE01D, dflat: 0xE02A, dsharp: 0xE01C,
    d0: 0x30, d1: 0x31, d2: 0x32, d3: 0x33, d4: 0x34, d5: 0x35, d6: 0x36, d7: 0x37, d8: 0x38, d9: 0x39, tC: 0xE091, tCut: 0xE092,
    r4: 0xE008, r8: 0xE00B, r16: 0xE00C, r32: 0xE00D };
  for (const f of MUSIC) for (const [k, cp] of Object.entries(M)) add(k, cut(f, String.fromCodePoint(cp), SPX * 4));
  return out;
}
"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page()
        await pg.goto('http://localhost:8765/index.html'); await pg.wait_for_timeout(800)
        out = await pg.evaluate(JS, MUSIC)
        print({k: len(v) for k, v in out.items()})
        hdr = "// The music reader's core shapes as LilyPond engraves them (its font Emmentaler, SIL Open Font\n// License): clefs, accidentals, time digits and rests — the look of Mutopia and of many editions —\n// shrunk to the reader's 12x20 grid. Made by tools/gen/shapes_ly.py.\n"
        open('/home/claude/s24/Payload/Stand.app/www/js/omr-shapes3.js', 'w').write(hdr + 'export const SHAPES3 = ' + json.dumps(out, separators=(',', ':')) + ';\n')
        await b.close()
asyncio.run(main())
