# Letters and digits for the reader's finer comparison (dynamics, fingering), drawn in more music
# fonts and their text fonts, above all handwritten ones: Petaluma, MuseJazz, Finale Broadway,
# Leland, Gootville, MScore, Campania, Finale Maestro.
import asyncio, json
from playwright.async_api import async_playwright
MUSIC = ['Petaluma', 'MuseJazz', 'FinaleBroadway', 'Leland', 'Gootville', 'MScore', 'Campania', 'FinaleMaestro']
TEXT = ['PetalumaScript', 'PetalumaText', 'MuseJazzText', 'FinaleBroadwayText', 'LelandText', 'GootvilleText', 'MScoreText', 'Edwin-BdIta', 'Edwin-Roman', 'Edwin-Bold']
JS = r"""
async ([MUSIC, TEXT]) => {
  for (const f of [...MUSIC, ...TEXT]) { try { const ff = new FontFace(f, `url(/_fonts/${f}.otf)`); await ff.load(); document.fonts.add(ff); } catch (e) {} }
  const GX = 16, GY = 24;
  const gridOfBox = (get, x0, y0, x1, y1) => {
    const cw = x1 - x0 + 1, ch = y1 - y0 + 1, g = new Float32Array(GX * GY);
    for (let gy = 0; gy < GY; gy++) for (let gx = 0; gx < GX; gx++) {
      const ax = x0 + (gx * cw) / GX, bx = x0 + ((gx + 1) * cw) / GX, ay = y0 + (gy * ch) / GY, by = y0 + ((gy + 1) * ch) / GY;
      let sum = 0, n = 0;
      for (let y = Math.floor(ay); y < Math.max(Math.floor(ay) + 1, Math.ceil(by)); y++) for (let x = Math.floor(ax); x < Math.max(Math.floor(ax) + 1, Math.ceil(bx)); x++) { n++; sum += get(x, y); }
      g[gy * GX + gx] = sum / Math.max(1, n);
    }
    const o = new Float32Array(GX * GY);
    for (let y = 0; y < GY; y++) for (let x = 0; x < GX; x++) { let t = 0, n = 0; for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) { const xx = x + dx, yy = y + dy; if (xx < 0 || yy < 0 || xx >= GX || yy >= GY) continue; const wgt = dx || dy ? 1 : 2; t += g[yy * GX + xx] * wgt; n += wgt; } o[y * GX + x] = t / n; }
    return { g: o, ar: cw / ch };
  };
  const c = document.createElement('canvas'); c.width = 360; c.height = 260;
  const x = c.getContext('2d', { willReadFrequently: true });
  const out = [];
  const draw = (cls, font, ch) => {
    x.clearRect(0, 0, 360, 260); x.fillStyle = '#000'; x.font = font; x.textBaseline = 'alphabetic'; x.fillText(ch, 40, 180);
    const d = x.getImageData(0, 0, 360, 260).data;
    let x0 = 360, y0 = 260, x1 = -1, y1 = -1;
    for (let i = 0; i < 360 * 260; i++) if (d[i * 4 + 3] > 110) { const px = i % 360, py = (i - px) / 360; if (px < x0) x0 = px; if (px > x1) x1 = px; if (py < y0) y0 = py; if (py > y1) y1 = py; }
    if (x1 < 0) return;
    const r = gridOfBox((xx, yy) => (d[(yy * 360 + xx) * 4 + 3] > 110 ? 1 : 0), x0, y0, x1, y1);
    let bin = ''; for (const v of r.g) bin += String.fromCharCode(Math.round(v * 255));
    out.push({ cls, m: btoa(bin), ar: +r.ar.toFixed(3) });
  };
  const DYNW = { pp: 'E52B', ppp: 'E52A', mp: 'E52C', mf: 'E52D', ff: 'E52F', fff: 'E530', fp: 'E534', fz: 'E535', sf: 'E536', sfp: 'E537', sfz: 'E539', sffz: 'E53B', rf: 'E53C', rfz: 'E53D', p: 'E520', f: 'E522' };
  const LET = { p: 0xE520, m: 0xE521, f: 0xE522, r: 0xE523, s: 0xE524, z: 0xE525 };
  for (const f of MUSIC) {
    for (const [wd, cp] of Object.entries(DYNW)) { if (wd.length > 1) { draw('W' + wd, `160px "${f}"`, String.fromCodePoint(parseInt(cp, 16))); draw('W' + wd, `160px "${f}"`, [...wd].map((L) => String.fromCodePoint(LET[L])).join('')); } }
    for (const [L, cp] of Object.entries(LET)) draw('D' + L, `160px "${f}"`, String.fromCodePoint(cp));
    for (let n = 0; n <= 5; n++) draw('F' + n, `160px "${f}"`, String.fromCodePoint(0xED10 + n));
  }
  for (const f of TEXT) for (let n = 0; n <= 5; n++) draw('F' + n, `120px "${f}"`, String(n));
  return out;
}
"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page()
        await pg.goto('http://localhost:8765/index.html'); await pg.wait_for_timeout(800)
        out = await pg.evaluate(JS, [MUSIC, TEXT])
        from collections import Counter
        print(len(out), Counter(o['cls'][0] for o in out))
        hdr = "// Letters and digits for the music reader's finer comparison (dynamics letters and words, fingering\n// digits), drawn in the music fonts Petaluma, MuseJazz, Finale Broadway, Leland, Gootville, MScore,\n// Campania, Finale Maestro and their text fonts (SIL Open Font License; MScore GPL with font\n// exception), on the reader's 16x24 grid. Made by tools/gen/chars_gen.py.\n"
        open('/home/claude/s24/Payload/Stand.app/www/js/omr-chars2.js', 'w').write(hdr + 'export const CHARS2 = ' + json.dumps(out, separators=(',', ':')) + ';\n')
        await b.close()
asyncio.run(main())
