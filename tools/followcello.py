# Turning pages by listening, with real sound: a bowed voice playing the score, heard by the listener
import asyncio, json, sys
from playwright.async_api import async_playwright
async def main():
    seeds = [int(x) for x in sys.argv[1].split(',')]
    opts = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        pg = await (await b.new_context()).new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(800)
        if __import__('os').environ.get('G'): await pg.evaluate('(g) => Object.assign(globalThis, JSON.parse(g))', __import__('os').environ['G'])
        await pg.add_script_tag(content=open('/home/claude/tools/followcello.js').read())
        for s in seeds:
            r = await pg.evaluate('(o) => window.__followCello(o)', {'seeds': [s], **opts})
            x = r[0]; print(json.dumps({k: x[k] for k in ('seed','pages','notes','good','early','late','missed','det','shift')}), flush=True)
            if __import__('os').environ.get('DBG'): print(json.dumps({'turns': x['turns'], 'firstNext': x['firstNext'], 'lastStart': x['lastStart']}))
        print(errs[:3]); await b.close()
asyncio.run(main())
