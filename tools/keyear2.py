import asyncio, json, os, sys
from playwright.async_api import async_playwright
async def main():
    seeds = [int(x) for x in sys.argv[1].split(',')]; combos = [json.loads(x) for x in sys.argv[2:]] or [{}]
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(800)
        if os.environ.get('G'): await pg.evaluate('(g) => Object.assign(globalThis, JSON.parse(g))', os.environ['G'])
        await pg.add_script_tag(content=open('/home/claude/tools/keyear2.js').read())
        for o in combos:
            found = 0; n = 0; wrong = 0; dl = []
            for s in seeds:
                r = await pg.evaluate('(o) => window.__keyEar2(o)', {'seed': s, **o})
                n += len(r['delays']); found += sum(1 for d in r['delays'] if d is not None); wrong += len(r['wrong']); dl += [d for d in r['delays'] if d is not None]
                if '-v' in os.environ.get('V', ''): print(r)
            print(json.dumps(o), f'found {found}/{n} wrong {wrong} delay avg {sum(dl)/max(1,len(dl)):.1f}s max {max(dl) if dl else 0}', flush=True)
        print(errs[:3]); await b.close()
asyncio.run(main())
