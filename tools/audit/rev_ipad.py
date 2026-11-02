import asyncio, json
from playwright.async_api import async_playwright
U='http://127.0.0.1:' + __import__('os').environ.get('PORT','8766') + '/index.html'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ipad = await (await b.new_context(viewport={'width':1180,'height':820})).new_page()
        await ipad.add_init_script('window.__noTour = true;')
        errs=[]; ipad.on('pageerror', lambda e: errs.append(str(e)))
        await ipad.goto(U); await ipad.wait_for_timeout(1200)
        await ipad.evaluate("() => document.querySelector('#welGo')?.click()")
        await ipad.set_input_files('#importInput', '/home/claude/fixtures/vector8.pdf'); await ipad.wait_for_timeout(5000)
        await ipad.set_input_files('#importInput', '/home/claude/fixtures/imslp12.pdf'); await ipad.wait_for_timeout(6000)
        L = await ipad.evaluate("async () => (await window.__answerPhone({ what: 'list' })).scores.map(s => [s.id, s.title, s.pages])")
        print('list', L)
        A, B = L[0][0], L[1][0]
        # baseline page 1 of A
        base = await ipad.evaluate("async (id) => { await window.__answerPhone({what:'scoreinfo', id}); const p = await window.__answerPhone({what:'page', id, i:1}); return p.img.length; }", A)
        await ipad.wait_for_timeout(500)
        # race: page of A in flight while scoreinfo B arrives
        r = await ipad.evaluate("""async ([a, b]) => {
          await window.__answerPhone({what:'scoreinfo', id: a});
          const pj = window.__answerPhone({what:'page', id: a, i: 1});
          await new Promise(r => setTimeout(r, 5));
          const ib = window.__answerPhone({what:'scoreinfo', id: b});
          const p = await pj; const i = await ib.catch(e => 'err ' + e);
          return [p.img ? p.img.length : null, i && i.n];
        }""", [A, B])
        print('baseline page bytes', base, 'raced page bytes', r[0], 'info B n', r[1])
        # concurrent scoreinfo for the same id (internet fan-out): how many documents opened?
        r2 = await ipad.evaluate("""async (b) => {
          const [x, y] = await Promise.all([window.__answerPhone({what:'scoreinfo', id: b}), window.__answerPhone({what:'scoreinfo', id: b})]);
          return [x.n, y.n];
        }""", B)
        print('double info', r2)
        print('errs', errs[:5]); await b.close()
asyncio.run(main())
