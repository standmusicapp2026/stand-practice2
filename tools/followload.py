import asyncio, json, sys, os
from playwright.async_api import async_playwright
async def main():
    opts = json.loads(sys.argv[1])
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        ctx = await b.new_context(); pg = await ctx.new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(800)
        if os.environ.get('G'): await pg.evaluate('(g) => Object.assign(globalThis, JSON.parse(g))', os.environ['G'])
        cdp = await ctx.new_cdp_session(pg); await cdp.send('Emulation.setCPUThrottlingRate', {'rate': int(os.environ.get('THR', '4'))})
        await pg.add_script_tag(content=open('/home/claude/tools/followload.js').read())
        print(json.dumps(await pg.evaluate('(o) => window.__followLoad(o)', opts))); print(errs[:3]); await b.close()
asyncio.run(main())
