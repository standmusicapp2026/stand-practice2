# A photographed page (slanted, unevenly lit, a little blurred) read the way the app reads a photo,
# against the same page read from the clean file: how many notes come out the same.
import asyncio, json, sys, base64
from playwright.async_api import async_playwright
PHOTO = sys.argv[1]; CLEAN = sys.argv[2]; LENV = sys.argv[3] if len(sys.argv)>3 else '0'
def durl(f): return ('data:image/jpeg;base64,' if f.endswith('.jpg') else 'data:image/png;base64,') + base64.b64encode(open(f,'rb').read()).decode()
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(800)
        import os
        if os.environ.get('G'): await pg.evaluate('(g) => Object.assign(globalThis, JSON.parse(g))', os.environ['G'])
        r = await pg.evaluate("""async ([ph, cl, LEN]) => {
          const O = await import('/js/omr.js'); globalThis.__lenient = LEN; const S = await import('/js/scan.js');
          const load = async (src) => { const img = new Image(); img.src = src; await img.decode(); return img; };
          const canv = (img, k) => { const c = document.createElement('canvas'); c.width = Math.round(img.width * k); c.height = Math.round(img.height * k); c.getContext('2d').drawImage(img, 0, 0, c.width, c.height); return c; };
          const seq = (res) => res ? res.bars.map((b) => b.map((e) => e.rest ? 'r' + e.t : (e.ps || []).join('+') + '/' + e.t + (e.dots ? '.' : '')).join(' ')) : [];
          const imgP = await load(ph), imgC = await load(cl);
          const small = canv(imgP, 900 / Math.max(imgP.width, imgP.height));
          const quad = S.detectPage(small);
          const maxSide = 3000;
          const big = canv(imgP, Math.min(1, (maxSide * 1.35) / Math.max(imgP.width, imgP.height)));
          let c = quad ? S.warpPage(big, quad, maxSide) : big;
          let skew = 0;
          if (skew) c = S.rotateSmall(c, skew);
          const a = await O.recogniseBest(c, { lines: 'all' });
          const cc = canv(imgC, 1);
          const bres = await O.recogniseBest(cc, { lines: 'all' });
          const sys = (res) => res ? res.barSys : []; window.__ph = c; return { sysP: sys(a), sysC: sys(bres), staves: [a && a.staves, bres && bres.staves], quad: !!quad, skew, photo: seq(a), clean: seq(bres), pk: a && [a.clef, a.key, a.time], ck: bres && [bres.clef, bres.key, bres.time] };
        }""", [durl(PHOTO), durl(CLEAN), float(LENV)])
        # note-level similarity (longest common subsequence over all tokens)
        A = ' | '.join(r['photo']).split(); B = ' | '.join(r['clean']).split()
        n, m = len(A), len(B); L = [[0]*(m+1) for _ in range(n+1)]
        for i in range(n-1, -1, -1):
            for j in range(m-1, -1, -1):
                L[i][j] = L[i+1][j+1] + 1 if A[i] == B[j] else max(L[i+1][j], L[i][j+1])
        d = await pg.evaluate("() => window.__ph.toDataURL('image/jpeg', 0.85)")
        open('/home/claude/shots/warped.jpg','wb').write(base64.b64decode(d.split(',')[1]))
        print('quad', r['quad'], 'skew', r['skew'], 'photo', r['pk'], 'clean', r['ck'])
        if os.environ.get('DUMP'):
            open(os.environ['DUMP'] + '.photo', 'w').write('\n'.join(r['photo'])); open(os.environ['DUMP'] + '.clean', 'w').write('\n'.join(r['clean']))
        print('bars photo', len(r['photo']), 'clean', len(r['clean']), 'tokens', n, m, 'same', L[0][0], f"{L[0][0]/max(1,m)*100:.1f}%")
        from collections import Counter
        print('staves', r['staves'], 'per system photo', sorted(Counter(r['sysP']).items()), 'clean', sorted(Counter(r['sysC']).items()))
        if errs: print(errs[:3])
        await b.close()
asyncio.run(main())
