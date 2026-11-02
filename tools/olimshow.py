# show ground truth and the app's reading of one OLiMPiC system, one staff
import sys, asyncio, base64, json
sys.argv = [sys.argv[0], 'dev', '1', '1', '/dev/null'] + sys.argv[1:]
SID, ST = sys.argv[5], int(sys.argv[6])
import importlib.util
spec = importlib.util.spec_from_file_location('olim0', '/home/claude/tools/olim.py')
src = open('/home/claude/tools/olim.py').read().split('async def main')[0]
ns = {}; exec(src, ns)
from playwright.async_api import async_playwright
NAMES = ['C','C#','D','Eb','E','F','F#','G','Ab','A','Bb','B']
nm = lambda m: NAMES[m % 12] + str(m // 12 - 1)
async def main():
    ROOT = ns['ROOT']; gt = ns['gt_of'](f'{ROOT}/samples/{SID}.musicxml')[ST + 1]
    for i, m in enumerate(gt): print('GT', i + 1, ' '.join(('r' if x[3] else '+'.join(nm(p) for p in x[1])) + '/' + (str(x[2][0]) + '.' * x[2][1] if x[2] else '?') for x in m))
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1000)
        src = 'data:image/png;base64,' + base64.b64encode(open(f'{ROOT}/samples/{SID}.png', 'rb').read()).decode()
        r = await pg.evaluate(ns['JS'], [src, ST])
        print('clef', r['clef'], 'key', r['key'], 'time', r['time'])
        for i, bar in enumerate(r['bars']): print('RD', i + 1, ' '.join(('r' if it.get('rest') else '+'.join(nm(p) for p in it['midi'])) + '/' + str(it['t']) + '.' * it['dots'] for it in bar))
        await b.close()
asyncio.run(main())
