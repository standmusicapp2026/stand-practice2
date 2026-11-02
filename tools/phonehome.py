import asyncio, sys
from playwright.async_api import async_playwright
S='/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad/lay'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width':393,'height':852}, device_scale_factor=2, has_touch=True, is_mobile=True); pg = await ctx.new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); setTimeout(()=>document.querySelector('.tour-skip')?.click(),300); }"); await pg.wait_for_timeout(1200)
        for v in ['list','groups','hero','grid','dock']:
            await pg.evaluate(f"() => window.__homeLook('{v}')"); await pg.wait_for_timeout(300)
            await pg.screenshot(path=S+f'/home_{v}.png', full_page=True)
        print(errs); await b.close()
asyncio.run(main())
