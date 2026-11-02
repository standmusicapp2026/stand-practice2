import asyncio, json, sys, os
from playwright.async_api import async_playwright
async def main():
    fn, opts = sys.argv[1], json.loads(sys.argv[2])
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        pg = await (await b.new_context()).new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(800)
        if os.environ.get('G'): await pg.evaluate('(g) => Object.assign(globalThis, JSON.parse(g))', os.environ['G'])
        await pg.add_script_tag(content=open('/home/claude/tools/followreal.js').read())
        r = await pg.evaluate(f'(o) => window.{fn}(o)', opts)
        print(json.dumps(r)); print(errs[:3]); await b.close()
asyncio.run(main())
