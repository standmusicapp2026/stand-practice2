import asyncio, json, sys, base64
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width': 1600, 'height': 1100})).new_page()
        await pg.add_init_script("""window.__noTour = true; window.webkit = { messageHandlers: { standRecognize: { postMessage: (m) => { const k = +m.id.slice(4); const ans = ['Lent', 'p dolcissimo', '', '3x'][k] || ''; setTimeout(() => window.standRecognized({ id: m.id, text: ans }), 50); } } } };""")
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1000)
        await pg.evaluate("() => document.querySelector('#welGo')?.click()")
        data = 'data:image/jpeg;base64,' + base64.b64encode(open('/home/claude/tc/raw-003.jpg','rb').read()).decode()
        r = await pg.evaluate("""async (src) => {
          const O = await import('/js/omr.js'); const E = await import('/js/compose/editor.js'); const M = await import('/js/compose/model.js');
          const img = new Image(); img.src = src; await img.decode();
          const c = document.createElement('canvas'); c.width = 2303; c.height = 317; const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, 2303, 317); g.drawImage(img, -40, -615);
          const res = await O.recogniseBest(c, { lines: 'all' });
          await E.createComposition({ insts: ['cello'], time: res.time, bars: res.bars.length, key: 0 }); await new Promise((r) => setTimeout(r, 400));
          const T = window.__composeTest; const ans = await T.readTextBoxes(res, c);
          const C = window.__compose; C.capture = { ...res, clef: res.clef, clef0: res.clef, key: res.key }; T.placeCaptureTexts(C.capture, ans);
          document.querySelector('#capTo').value = ''; T.pasteCapture(M.allStaves(C.score)[0], 0); await new Promise((r) => setTimeout(r, 800));
          const st = M.allStaves(C.score)[0];
          return { ans, tempo: C.score.measures[0].tempo, txts: st.bars.flatMap((b, i) => b.filter(e => e.txt).map(e => [i, e.txt, e.txtStyle])) };
        }""", data)
        print(r, errs[:3])
        el = await pg.query_selector('#cpPages'); await el.screenshot(path='/home/claude/shots/ocrtest.png')
        await b.close()
asyncio.run(main())
