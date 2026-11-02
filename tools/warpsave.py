# the phone-photo version of a page, flattened the way the app flattens photos, saved as PNG: warpsave.py PDF PAGE SEED OUT.png [DPI]
import asyncio, sys, os, base64, subprocess
from playwright.async_api import async_playwright
PDF, N, SEED, OUT = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]; DPI = sys.argv[5] if len(sys.argv) > 5 else '200'
tmp = '/tmp/claude-0/capeval'; os.makedirs(tmp, exist_ok=True); f = f'{tmp}/ws{os.getpid()}'
subprocess.run(['pdftoppm', '-r', DPI, '-f', str(N), '-l', str(N), '-png', '-singlefile', PDF, f], check=True)
subprocess.run(['python3', '/home/claude/tools/mkphoto.py', f + '.png', f + '.jpg', str(SEED)], check=True)
async def main():
    data = 'data:image/jpeg;base64,' + base64.b64encode(open(f + '.jpg', 'rb').read()).decode()
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(800)
        d = await pg.evaluate("""async (src) => {
          const S = await import('/js/scan.js');
          const img = new Image(); img.src = src; await img.decode();
          const canv = (im, k) => { const q = document.createElement('canvas'); q.width = Math.round(im.width * k); q.height = Math.round(im.height * k); q.getContext('2d').drawImage(im, 0, 0, q.width, q.height); return q; };
          const quad = S.detectPage(canv(img, 900 / Math.max(img.width, img.height)));
          const big = canv(img, Math.min(1, (3000 * 1.35) / Math.max(img.width, img.height)));
          const cr = quad ? S.warpPage(big, quad, 3000) : big;
          return cr.toDataURL('image/png');
        }""", data)
        open(OUT, 'wb').write(base64.b64decode(d.split(',')[1])); await b.close()
asyncio.run(main())
