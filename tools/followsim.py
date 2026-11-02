import asyncio, json, sys
from playwright.async_api import async_playwright
async def main():
    seeds = [int(x) for x in sys.argv[1].split(',')]
    combos = [c.split(':') for c in sys.argv[2].split(',')]
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(800)
        if __import__('os').environ.get('G'): await pg.evaluate('(g) => Object.assign(globalThis, JSON.parse(g))', __import__('os').environ['G'])
        await pg.add_script_tag(content=open('/home/claude/tools/followsim.js').read())
        for audio, gaze in combos:
            r = await pg.evaluate('(o) => window.__followSim(o)', {'seeds': seeds, 'audio': audio, 'gazeMode': gaze, 'when': __import__('os').environ.get('WHEN', 'bar')})
            tot = {k: sum(x[k] for x in r) for k in ('good', 'early', 'late', 'missed')}
            print(f'{audio:6s} {gaze:7s}', tot, 'trust', [x['trust'] for x in r], [x['det'] for x in r], flush=True)
        print(errs[:3]); await b.close()
asyncio.run(main())
