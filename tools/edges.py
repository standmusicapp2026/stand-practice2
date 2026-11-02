import asyncio, sys
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for name, vp in [('ipad', {'width':820,'height':1180}), ('iphone', {'width':390,'height':844}), ('ipadl', {'width':1366,'height':1024})]:
            ctx = await b.new_context(viewport=vp, has_touch=True, device_scale_factor=2); pg = await ctx.new_page()
            await pg.add_init_script('window.__noTour = true;')
            await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1200); await pg.evaluate("() => document.querySelector('#welGo')?.click()"); await pg.wait_for_timeout(500)
            await pg.set_input_files('#importInput', '/home/claude/fixtures/photo.jpg'); await pg.wait_for_timeout(2500)
            await pg.evaluate("() => document.querySelector('#revEdges').click()"); await pg.wait_for_timeout(1500)
            await pg.evaluate("() => document.querySelector('#revWhole').click()"); await pg.wait_for_timeout(800)
            r = await pg.evaluate("() => { const a=document.querySelector('#revEdgeBar').getBoundingClientRect(), c=document.querySelector('#revCanvas').getBoundingClientRect(); return [a.bottom, c.top, c.bottom, innerHeight] }")
            print(name, r)
            await pg.screenshot(path=f'/home/claude/shots/edges_{name}.png')
            await ctx.close()
        await b.close()
asyncio.run(main())
