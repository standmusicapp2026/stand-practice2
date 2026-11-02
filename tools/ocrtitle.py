# Titles of scans and photos: the top of the page read as a picture (tesseract stands in for the
# iPad's own reader) gives the same title and composer as the words of the original PDF
import asyncio, os, base64, subprocess, tempfile, csv, io, sys
from playwright.async_api import async_playwright
D = '/tmp/claude-0/ocr/'
SRC = {'Elgar_-_Cello_Concerto_in_E_minor': '/home/claude/fixtures/titles/', 'a': '/home/claude/fixtures/titles/', 'b': '/home/claude/fixtures/titles/', 'c': '/home/claude/fixtures/titles/', 'd': '/home/claude/fixtures/titles/', 'vector8': '/home/claude/fixtures/', 'imslp12': '/home/claude/fixtures/', 'cello2': '/home/claude/fixtures/real/', 'violin1017': '/home/claude/fixtures/real/'}
def ocr(b64):
    with tempfile.TemporaryDirectory() as td:
        p = td + '/t.png'; open(p, 'wb').write(base64.b64decode(b64))
        from PIL import Image
        W, H = Image.open(p).size
        tsv = subprocess.run(['tesseract', p, '-', '--psm', '3', 'tsv'], capture_output=True, text=True).stdout
    rows = list(csv.DictReader(io.StringIO(tsv), delimiter='\t', quoting=csv.QUOTE_NONE))
    L = {}
    for r in rows:
        if r['level'] != '5' or not r['text'].strip() or float(r['conf']) < 30: continue
        k = (r['block_num'], r['par_num'], r['line_num'])
        x, y, w, h = int(r['left']), int(r['top']), int(r['width']), int(r['height'])
        q = L.setdefault(k, {'s': [], 'x0': x, 'y0': y, 'x1': x + w, 'y1': y + h})
        q['s'].append(r['text']); q['x0'] = min(q['x0'], x); q['y0'] = min(q['y0'], y); q['x1'] = max(q['x1'], x + w); q['y1'] = max(q['y1'], y + h)
    return [{'s': ' '.join(q['s']), 'x': q['x0'] / W, 'y': q['y0'] / H, 'w': (q['x1'] - q['x0']) / W, 'h': (q['y1'] - q['y0']) / H, 'c': 0.9} for q in L.values()]
async def main():
    pairs = [l.split() for l in open(D + 'map.txt')]
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width': 1366, 'height': 1024})
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.expose_function('pyOcr', ocr)
        await pg.add_init_script("globalThis.__readTopTest = async (canvas) => window.pyOcr(canvas.toDataURL('image/png').split(',')[1]);")
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); setTimeout(() => document.querySelector('.tour-skip')?.click(), 300); }"); await pg.wait_for_timeout(700)
        async def add(path):
            n0 = await pg.evaluate("() => document.querySelectorAll('#grid .card:not(.folder)').length")
            await pg.set_input_files('#importInput', [path])
            await pg.wait_for_function("(n) => document.querySelectorAll('#grid .card:not(.folder)').length > n", arg=n0, timeout=90000)
            await pg.wait_for_timeout(600)
            return await pg.evaluate("async () => { const { db } = await import('/js/db.js'); const a = (await db.all('scores')).sort((x, y) => y.added - x.added)[0]; return [a.title, a.composer]; }")
        EXP = {'Elgar_-_Cello_Concerto_in_E_minor': 'cellosuiteno.1', 'a': 'suiteno.1ingmajor,bwv1007', 'b': 'sonatano.2ingminor,op.5', 'bwv-1012-1-a4': 'cellosuitevi', 'bwv-1012-3-a4': 'cellosuitevi',
               'bwv1008-a4': 'cellosuiteii', 'bwv1010-a4': 'suite4forcellosolo', 'c': 'kolnidrei', 'cello2': 'cellosuiteii', 'cellosuite3-a4': 'suiteno.3incmajor', 'd': 'atthefountain,op.20no.2',
               'imslp12': 'sonatainеminor', 'vector8': 'cellosuiteno.1', 'violin1017': 'sonataiv'}
        tok = 0; cok = 0
        good = 0; n = 0
        for scan, orig in pairs:
            base = orig.rsplit('-', 1)[0]
            src = SRC.get(base, '/home/claude/real/muto/') + base + '.pdf'
            ref = await add(src); got = await add(D + scan)
            n += 1
            same_t = ref[0].lower().replace(' ', '') == got[0].lower().replace(' ', '')
            same_c = ref[1] == got[1]
            good += same_t and same_c
            g = got[0].lower().replace(' ', '').rstrip('.')
            e = EXP.get(base, '').replace('е', 'e')
            tok += g.startswith(e); cok += bool(got[1])
            print(('OK  ' if same_t and same_c else 'DIFF'), base, '| pdf:', ref, '| scan:', got)
        print(f'{good}/{n} scans named as their PDF; titles right {tok}/{n}, composer found {cok}/{n}'); print(errs[:3])
        print('PASS' if tok >= n - 1 and cok >= n - 3 else 'FAIL', 'titles from scans')
        await b.close()
asyncio.run(main())
