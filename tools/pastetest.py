import asyncio, json, sys, base64
from playwright.async_api import async_playwright
FILE, CROP = sys.argv[1], [int(v) for v in sys.argv[2].split(',')]
INST = sys.argv[3] if len(sys.argv) > 3 else 'violin'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width': 1600, 'height': 1100})).new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type in ('error','warning') else None)
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1000)
        await pg.evaluate("() => document.querySelector('#welGo')?.click()")
        data = 'data:image/jpeg;base64,' + base64.b64encode(open(FILE,'rb').read()).decode()
        r = await pg.evaluate("""async ([src, crop, inst]) => {
          const O = await import('/js/omr.js'); const E = await import('/js/compose/editor.js'); const M = await import('/js/compose/model.js');
          const img = new Image(); img.src = src; await img.decode();
          const [x, y, w, h] = crop; const c = document.createElement('canvas'); c.width = w; c.height = h; const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, w, h); g.drawImage(img, -x, -y);
          const res = await O.recogniseBest(c, { lines: 'all' });
          await E.createComposition({ insts: [inst], time: res.time, bars: res.bars.length, key: 0 });
          await new Promise((r) => setTimeout(r, 400));
          const C = window.__compose; C.capture = { ...res, clef: res.clef || 'treble', key: res.key || 0 }; document.querySelector('#capTo').value = '';
          const st = M.allStaves(C.score)[0];
          window.__composeTest.pasteCapture(st, 0);
          await new Promise((r) => setTimeout(r, 800));
          window.__bar1 = JSON.stringify(st.bars[0]);
          const nm = (n) => M.noteName(n.s, n.a);
          return st.bars.slice(0, 6).map((b) => b.map((e) => e.rest ? 'r' + e.t + '.'.repeat(e.dots || 0) : e.notes.map(nm).join('+') + '/' + e.t + '.'.repeat(e.dots || 0) + (e.tup ? 't' : '')).join(' '));
        }""", [data, CROP, INST])
        for i, x in enumerate(r): print(i + 1, x)
        print(await pg.evaluate('window.__bar1'))
        el = await pg.query_selector('#cpPages'); await el.screenshot(path='/home/claude/shots/pastetest.png')
        print(errs[:5])
        await b.close()
asyncio.run(main())
