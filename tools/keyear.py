import asyncio, json, os, sys
from playwright.async_api import async_playwright
async def main():
    seeds = [int(x) for x in sys.argv[1].split(',')]; opts = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        pg = await (await b.new_context()).new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(800)
        await pg.add_script_tag(content=open('/home/claude/tools/keyear.js').read())
        for s in seeds:
            print(json.dumps(await pg.evaluate('(o) => window.__keyEar(o)', {'seed': s, **opts})), flush=True)
        print(errs[:3]); await b.close()
asyncio.run(main())
