# A huge scanned PDF (IMSLP, 7000 x 9300 dots a page): pages drawn at the screen's size, the
# time, and that the picture comes out (not blank)
import asyncio, os, sys, json, subprocess
def rss():
    out = subprocess.run(['ps','-eo','rss,comm'], capture_output=True, text=True).stdout
    return sum(int(l.split()[0]) for l in out.splitlines()[1:] if 'chrom' in l or 'headless' in l) // 1024
from playwright.async_api import async_playwright
PDF = sys.argv[1]
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type in ('error', 'warning') else None)
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1200)
        data = open(PDF, 'rb').read()
        await pg.evaluate("(n) => { window.__pdfBytes = new Uint8Array(n); }", len(data))
        # (sent in pieces)
        import base64
        for i in range(0, len(data), 2_000_000):
            await pg.evaluate("([o, s]) => { const b = atob(s); for (let k = 0; k < b.length; k++) window.__pdfBytes[o + k] = b.charCodeAt(k); }", [i, base64.b64encode(data[i:i+2_000_000]).decode()])
        if os.environ.get('LIVE'): await pg.evaluate('(v) => { window.__live = v; }', int(os.environ['LIVE']))
        if os.environ.get('PAGES'): await pg.evaluate('(v) => { window.__pages = v; }', [int(x) for x in os.environ['PAGES'].split(',')])
        await pg.wait_for_timeout(1500); base = rss(); peak = [base]
        async def samp():
            while True: peak[0] = max(peak[0], rss()); await asyncio.sleep(0.05)
        task = asyncio.create_task(samp())
        r = await pg.evaluate("""async (mp) => { if (mp) globalThis.__pdfMaxPix = mp; if (window.__live !== undefined) globalThis.__pdfLive = window.__live; const S = await import('/js/score.js?x=' + (mp || 0));
          const doc = await S.openDocument({ kind: 'pdf', data: window.__pdfBytes.buffer });
          const out = [];
          for (const i of (window.__pages || [0, 1, 2, 3, 4, 5])) { const c = document.createElement('canvas'); const t0 = performance.now(); await doc.render(i, c, 1600, Math.round(1600 * doc.sizes[i][1] / doc.sizes[i][0]));
            const g = c.getContext('2d'); const d = g.getImageData(0, 0, c.width, c.height).data; let dark = 0; for (let k = 0; k < d.length; k += 16) if (d[k] < 128) dark++;
            out.push({ ms: Math.round(performance.now() - t0), dark: +(dark / (d.length / 16)).toFixed(3) }); c.width = c.height = 0; }
          const mem = performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1e6) : null;
          doc.destroy(); return { out, mem }; }""", int(os.environ.get("MP", "0")))
        task.cancel(); print('render peak extra MB', peak[0] - base)
        print(json.dumps(r)); print(errs[:4]); await b.close()
asyncio.run(main())
