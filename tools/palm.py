import asyncio, os, json
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width': 1180, 'height': 820})
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        base = 'http://localhost:' + os.environ.get('PORT','8765') + '/index.html'
        await pg.goto(base); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); }")
        await pg.set_input_files('#importInput', ['/home/claude/fixtures/vector8.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=60000)
        await pg.evaluate("async () => { document.querySelector('#grid .card:not(.folder)').click(); await new Promise(r => setTimeout(r, 2500)); }")
        js = """async ([mode, gap, w]) => {
          const sleep = (ms) => new Promise(r => setTimeout(r, ms)); const st = document.querySelector('#stage');
          const ev = (type, o) => { const e = new PointerEvent(type, { bubbles: true, cancelable: true, pointerId: o.id, pointerType: o.t, clientX: o.x, clientY: o.y, width: o.w || 1, height: o.w || 1, buttons: type === 'pointerup' ? 0 : 1 }); (type === 'pointerdown' ? st : window).dispatchEvent(e); };
          const lbl = () => document.querySelector('#pageLabel').textContent;
          const inkOn = document.querySelector('#score').classList.contains('inking') || document.body.classList.contains('inking');
          if (mode === 'pen') { ev('pointerdown', { id: 7, t: 'pen', x: 500, y: 400 }); for (let i = 0; i < 5; i++) { ev('pointermove', { id: 7, t: 'pen', x: 500 + i * 5, y: 400 }); await sleep(16); } ev('pointerup', { id: 7, t: 'pen', x: 520, y: 400 }); }
          await sleep(gap);
          const before = lbl();
          ev('pointerdown', { id: 9, t: 'touch', x: 1100, y: 400, w }); await sleep(80); ev('pointerup', { id: 9, t: 'touch', x: 1100, y: 400, w }); await sleep(700);
          return [before, lbl()]; }"""
        print('no ink, finger tap:', await pg.evaluate(js, ['none', 0, 20]))
        # open the markings (the pen opens them)
        await pg.evaluate("() => { const st = document.querySelector('#stage'); st.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, pointerId: 3, pointerType: 'pen', clientX: 500, clientY: 400 })); window.dispatchEvent(new PointerEvent('pointerup', { bubbles: true, pointerId: 3, pointerType: 'pen', clientX: 500, clientY: 400 })); }")
        await pg.wait_for_timeout(2000)
        print('ink, palm 0.3 s after pen:', await pg.evaluate(js, ['pen', 300, 20]))
        await pg.wait_for_timeout(1600)
        print('ink, palm-size contact 0.8 s after pen (no turn):', await pg.evaluate(js, ['pen', 800, 150]))
        print('ink, ordinary 60 px finger, no pen (turns):', await pg.evaluate(js, ['none', 0, 60]))
        print('ink, ordinary 60 px finger 3 s after pen (turns):', await pg.evaluate(js, ['pen', 3000, 60]))
        print('ink, finger 0.7 s after pen:', await pg.evaluate(js, ['pen', 700, 20]))
        print('errors', errs[:4]); await b.close()
asyncio.run(main())
