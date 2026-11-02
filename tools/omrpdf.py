import asyncio, json, sys, base64
from playwright.async_api import async_playwright
FILE = sys.argv[1]; PAGE = int(sys.argv[2]) if len(sys.argv) > 2 else 0
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1200)
        data = base64.b64encode(open(FILE,'rb').read()).decode()
        r = await pg.evaluate("""async ([d, page]) => {
          const S = await import('/js/score.js'); const O = await import('/js/omr.js');
          const bin = Uint8Array.from(atob(d), c => c.charCodeAt(0)).buffer;
          const doc = await S.openDocument({ kind: 'pdf', data: bin });
          const [pw, ph] = doc.sizes[page]; const c = document.createElement('canvas');
          await doc.render(page, c, 1600, Math.round(1600 * ph / pw));
          const r = await O.recognise(c, {});
          if (!r) return null;
          const all = r.bars.flat();
          return { bars: r.bars.length, notes: r.notes.length, fit: r.fitRead, ties: all.filter(x => x.ties && x.ties.length).length, slurS: all.filter(x => x.slurStart).length, slurE: all.filter(x => x.slurEnd).length,
            art: all.flatMap(x => x.art || []).reduce((a, k) => (a[k] = (a[k] || 0) + 1, a), {}), tup: all.filter(x => x.tup).length, png: c.toDataURL('image/jpeg', 0.7) };
        }""", [data, PAGE])
        if r: open('/home/claude/shots/omrpdf.jpg','wb').write(base64.b64decode(r.pop('png').split(',')[1]))
        print(json.dumps(r), errs); await b.close()
asyncio.run(main())
