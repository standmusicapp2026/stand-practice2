import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width':1180,'height':820}, has_touch=True); pg = await ctx.new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1200)
        await pg.evaluate("() => document.querySelector('#welGo')?.click()")
        await pg.evaluate("""async () => { const E = await import('/js/compose/editor.js'); await E.createComposition({ insts: ['violin', 'cello'], time: [4, 4], bars: 40 }); await new Promise(r => setTimeout(r, 900)); window.__compose.mode = 'select'; document.querySelector('#compose').classList.add('selecting'); }""")
        await pg.wait_for_timeout(400)
        await pg.evaluate("async () => { for (let k = 0; k < 20 && document.querySelector('.tour'); k++) { document.querySelector('.tour-skip')?.click(); document.querySelector('.tour')?.click(); await new Promise(r => setTimeout(r, 150)); } }")
        box = await pg.evaluate("() => { const r = document.querySelector('#cpPages canvas').getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }")
        x, y = box[0] + box[2] * 0.5, box[1] + 280
        el = await pg.evaluate("([x, y]) => { const e = document.elementFromPoint(x, y); return e && (e.id + '.' + e.className); }", [x, y])
        print('box', box, el, await pg.evaluate("() => [document.querySelector('#cpScroll').scrollHeight, document.querySelector('#cpScroll').clientHeight]"))
        cdp = await ctx.new_cdp_session(pg)
        async def touch(kind, px, py):
            await cdp.send('Input.dispatchTouchEvent', {'type': kind, 'touchPoints': ([] if kind == 'touchEnd' else [{'x': px, 'y': py}])})
        # quick swipe up: scroll
        s0 = await pg.evaluate("() => document.querySelector('#cpScroll').scrollTop")
        await touch('touchStart', x, y)
        for k in range(1, 12): await touch('touchMove', x, y - k * 25); await pg.wait_for_timeout(16)
        await touch('touchEnd', x, y - 275); await pg.wait_for_timeout(500)
        s1 = await pg.evaluate("() => document.querySelector('#cpScroll').scrollTop")
        print('scrolled', s0, '->', s1, 'selection', await pg.evaluate("() => !!window.__compose.selBars"))
        # hold, then drag sideways: selects bars
        await touch('touchStart', x - 200, y); await pg.wait_for_timeout(600)
        for k in range(1, 10): await touch('touchMove', x - 200 + k * 40, y); await pg.wait_for_timeout(30)
        await touch('touchEnd', x + 160, y); await pg.wait_for_timeout(400)
        print('held drag', await pg.evaluate("() => { const b = window.__compose.selBars; return b ? [b.from, b.to] : null }"), 'scroll', await pg.evaluate("() => document.querySelector('#cpScroll').scrollTop"))
        # tap
        await pg.touchscreen.tap(x + 100, y + 120); await pg.wait_for_timeout(400)
        print('tap', await pg.evaluate("() => { const b = window.__compose.selBars; return b ? [b.from, b.to] : (window.__compose.sel.size) }"), errs)
        await b.close()
asyncio.run(main())
