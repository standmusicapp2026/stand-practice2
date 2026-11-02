# More fonts for the reader's core shapes (clefs, accidentals, time digits, rests), above all the
# handwritten jazz fonts (Petaluma, MuseJazz, Finale Broadway) and MScore / Campania, which the
# first set (Bravura, Leland, Leipzig, Gootville, Finale Maestro) does not cover.
import asyncio, json
from playwright.async_api import async_playwright
MUSIC = ['Petaluma', 'MuseJazz', 'FinaleBroadway', 'Campania', 'MScore']
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
  const M = { treble: 0xE050, bass: 0xE062, alto: 0xE05C, sharp: 0xE262, flat: 0xE260, natural: 0xE261, dflat: 0xE264, dsharp: 0xE263,
    d0: 0xE080, d1: 0xE081, d2: 0xE082, d3: 0xE083, d4: 0xE084, d5: 0xE085, d6: 0xE086, d7: 0xE087, d8: 0xE088, d9: 0xE089, tC: 0xE08A, tCut: 0xE08B,
    r4: 0xE4E5, r8: 0xE4E6, r16: 0xE4E7, r32: 0xE4E8 };
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
        hdr = "// More fonts for the music reader's core shapes: clefs, accidentals, time digits and rests from the\n// handwritten fonts Petaluma, MuseJazz and Finale Broadway, and from Campania and MScore (SIL Open\n// Font License; MScore GPL with font exception), shrunk to the reader's 12x20 grid.\n// Made by tools/gen/shapes_gen.py.\n"
        open('/home/claude/s24/Payload/Stand.app/www/js/omr-shapes2.js', 'w').write(hdr + 'export const SHAPES2 = ' + json.dumps(out, separators=(',', ':')) + ';\n')
        await b.close()
asyncio.run(main())
