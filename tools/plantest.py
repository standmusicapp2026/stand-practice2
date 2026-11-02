# Practice plan: a tap plans one half hour; a finger that moves at once scrolls and plans nothing;
# held, then slid, plans several; each week its own plan unless "Same plan every week"
import asyncio, os
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width': 1366, 'height': 1024}, has_touch=True)
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); setTimeout(() => document.querySelector('.tour-skip')?.click(), 300); }"); await pg.wait_for_timeout(700)
        await pg.evaluate("() => { document.querySelector('[data-panel=goal]').click(); }"); await pg.wait_for_timeout(800)
        await pg.evaluate("() => document.querySelector('#plNext').click()"); await pg.wait_for_timeout(300)
        cdp = await ctx.new_cdp_session(pg)
        async def center(id):
            await pg.evaluate("(id) => document.querySelector(`#planGrid [data-id='${id}']`).scrollIntoView({ block: 'center' })", id); await pg.wait_for_timeout(200)
            return await pg.evaluate("(id) => { const r = document.querySelector(`#planGrid [data-id='${id}']`).getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2, r.height]; }", id)
        async def touch(pts, hold=0, step=30):
            x, y = pts[0]
            await cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y}]})
            if hold: await pg.wait_for_timeout(hold)
            for (x, y) in pts[1:]:
                await cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x, 'y': y}]}); await pg.wait_for_timeout(step)
            await cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []}); await pg.wait_for_timeout(400)
        planned = lambda: pg.evaluate("() => [...document.querySelectorAll('#planGrid .pl-cell.plan')].map((c) => c.dataset.id).sort()")
        res = {}
        x, y, h = await center('2-30')
        await touch([(x, y)]); res['tap'] = await planned()
        await touch([(x, y)]); res['tap again'] = await planned()
        # a quick swipe down over the cells: a scroll
        x, y, h = await center('3-28')
        await touch([(x, y)] + [(x, y + k * 12) for k in range(1, 12)], 0, 16); res['swipe'] = await planned()
        # held, then slid down three rows
        x, y, h = await center('4-28')
        await touch([(x, y)] + [(x, y + k * (h + 2) / 3) for k in range(1, 10)], 450, 40); res['hold+slide'] = await planned()
        # the mouse drags at once
        x, y, h = await center('1-20')
        await pg.mouse.move(x, y); await pg.mouse.down(); await pg.mouse.move(x, y + h + 2, steps=3); await pg.mouse.move(x, y + 2 * (h + 2), steps=3); await pg.mouse.up(); await pg.wait_for_timeout(400)
        res['mouse drag'] = await planned()
        nxt = res['mouse drag']
        await pg.evaluate("() => document.querySelector('#plNext').click()"); await pg.wait_for_timeout(300)
        res['week after (own)'] = await planned()
        await pg.evaluate("() => document.querySelector('#plPrev').click()"); await pg.wait_for_timeout(300)
        await pg.evaluate("() => { const c = document.querySelector('#planRepeat'); c.checked = true; c.dispatchEvent(new Event('change')); }"); await pg.wait_for_timeout(300)
        await pg.evaluate("() => { document.querySelector('#plNext').click(); document.querySelector('#plNext').click(); }"); await pg.wait_for_timeout(300)
        res['two weeks after (repeat)'] = await planned()
        await pg.evaluate("() => { document.querySelector('#plPrev').click(); document.querySelector('#plPrev').click(); }"); await pg.wait_for_timeout(300); await pg.screenshot(path='/tmp/claude-0/fz/plan.png')
        for k, v in res.items(): print(k, v)
        ok = (res['tap'] == ['2-30'] and res['tap again'] == [] and res['swipe'] == [] and res['hold+slide'] == ['4-28', '4-29', '4-30', '4-31']
              and res['mouse drag'] == ['1-20', '1-21', '1-22', '4-28', '4-29', '4-30', '4-31'] and res['week after (own)'] == [] and res['two weeks after (repeat)'] == nxt)
        print('PASS' if ok else 'FAIL', 'practice plan selection'); print(errs[:3])
        await b.close()
asyncio.run(main())
