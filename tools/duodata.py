# (duodata) The lines of music of every page of a PDF, found by Stand's own reader, and the words on
# each page read by tesseract (standing in for the iPad's text reader): the material for duo.js.
# usage: python3 duodata.py file.pdf out.json
import asyncio, base64, json, os, subprocess, sys, tempfile
from playwright.async_api import async_playwright
PDF, OUT = sys.argv[1], sys.argv[2]
PORT = os.environ.get('PORT', '8765')

def tess(png_b64):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, 'p.png'); open(p, 'wb').write(base64.b64decode(png_b64))
        subprocess.run(['tesseract', p, os.path.join(d, 'o'), '--psm', '11', 'tsv'], capture_output=True)
        rows = open(os.path.join(d, 'o.tsv')).read().splitlines()[1:]
        from PIL import Image
        W, H = Image.open(p).size
        out = []
        for r in rows:
            c = r.split('\t')
            if len(c) < 12 or not c[11].strip(): continue
            conf = float(c[10])
            if conf < 30: continue
            x, y, w, h = map(int, c[6:10])
            out.append({'s': c[11], 'x': x / W, 'y': y / H, 'w': w / W, 'h': h / H, 'c': conf / 100})
        return out

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await (await b.new_context(viewport={'width': 1200, 'height': 900})).new_page()
        await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(800)
        data = base64.b64encode(open(PDF, 'rb').read()).decode()
        n = await pg.evaluate("""async (b64) => {
          const { openDocument } = await import('/js/score.js');
          const bin = atob(b64), u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
          window.__doc = await openDocument({ kind: 'pdf', data: u.buffer });
          return window.__doc.pages; }""", data)
        pages = []
        for i in range(n):
            r = await pg.evaluate("""async (i) => {
              const doc = window.__doc, [pw, ph] = doc.sizes[i];
              const c = document.createElement('canvas'); await doc.render(i, c, 1700, Math.round(1700 * ph / pw));
              const [{ analyse }, { linesOf, cleanLines }] = await Promise.all([import('/js/omr.js'), import('/js/picker-lines.js')]);
              const lines = cleanLines(linesOf(await analyse(c, false, false, { stavesOnly: true })));
              const c2 = document.createElement('canvas'); await doc.render(i, c2, 1500, Math.round(1500 * ph / pw));
              const png = c2.toDataURL('image/png').split(',')[1];
              return { lines, png, size: [pw, ph] }; }""", i)
            words = tess(r['png'])
            pages.append({'lines': r['lines'], 'words': words, 'size': r['size']})
            print(i, len(r['lines']), 'lines', len(words), 'words', flush=True)
        json.dump(pages, open(OUT, 'w'))
        await b.close()
asyncio.run(main())
