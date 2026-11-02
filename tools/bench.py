import asyncio, json, sys
from playwright.async_api import async_playwright
FONTS = (sys.argv[1] if len(sys.argv) > 1 else 'Bravura,Leland,Petaluma,Gootville,FinaleMaestro').split(',')
SEEDS = [int(x) for x in (sys.argv[2] if len(sys.argv) > 2 else '1,2,3').split(',')]
LOOKS = (sys.argv[3] if len(sys.argv) > 3 else 'clean,scan,small').split(',')
VERB = '-v' in sys.argv
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(800)
        import os
        if os.environ.get('G'): await pg.evaluate('(g) => Object.assign(globalThis, JSON.parse(g))', os.environ['G'])
        await pg.add_script_tag(content=open('/home/claude/tools/omrbench.js').read())
        res = await pg.evaluate('(o) => window.__bench(o)', {'fonts': FONTS, 'seeds': SEEDS, 'looks': LOOKS, 'verbose': VERB, 'png': '-png' in sys.argv, 'ott': '-ott' in sys.argv})
        tot = {}; acc = []; keys = 0; times = 0
        import base64
        for i, r in enumerate(res):
            if r.get('png'): open(f'/home/claude/shots/bench_{i}.png','wb').write(base64.b64decode(r.pop('png').split(',')[1]))
            if r.get('mimg'): open(f'/home/claude/shots/benchm_{i}.png','wb').write(base64.b64decode(r.pop('mimg').split(',')[1]))
            if 'err' in r: print('ERR', r); continue
            acc.append(r['acc']); keys += r['key']; times += r['time']
            line = f"{r['font']:13s} s{r['seed']} {r['look']:5s} notes {r['exact']:3d}/{r['notes']:3d} ({r['acc']*100:5.1f}%) read {r['read']:3d} key {'ok' if r['key'] else 'X '} time {'ok' if r['time'] else 'X '} " + ' '.join(f"{k}:{v['tp']}/{v['tp']+v['fn']}+{v['fp']}" for k, v in sorted(r['marks'].items()))
            print(line + ('' if r['time'] else ' TIME ' + r.get('gotTime','')))
            if VERB: print('   T', r['truth']); print('   R', r['got']); [print('   F', q) for q in (r.get('fingBad') or [])]; [print('   S', q) for q in (r.get('slurs') or [])]; [print('   G', q) for q in (r.get('signs') or [])]; [print('   W', q) for q in (r.get('words') or [])[:2000] if ('L' in q or os.environ.get('WALL'))]
            for k, v in r['marks'].items():
                t = tot.setdefault(k, {'tp': 0, 'fp': 0, 'fn': 0})
                for q in t: t[q] += v[q]
        print(f"MEAN note accuracy {sum(acc)/max(1,len(acc))*100:.1f}%  keys {keys}/{len(acc)}  times {times}/{len(acc)}")
        for k, v in sorted(tot.items()):
            rec = v['tp'] / max(1, v['tp'] + v['fn']); prec = v['tp'] / max(1, v['tp'] + v['fp'])
            print(f"  {k:8s} recall {rec*100:5.1f}%  precision {prec*100:5.1f}%  ({v['tp']} found, {v['fn']} missed, {v['fp']} wrong)")
        if errs: print(errs[:3])
        await b.close()
asyncio.run(main())
