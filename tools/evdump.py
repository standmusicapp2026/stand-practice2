# the notes Capture reads on one line of a page: python3 evdump.py PDF PAGE SYS
import asyncio, sys, os, base64, subprocess, json
from playwright.async_api import async_playwright
PDF, N, SY = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
async def main():
    tmp = '/tmp/claude-0/capeval'; os.makedirs(tmp, exist_ok=True)
    if PDF.endswith('.png'): import shutil; shutil.copy(PDF, f'{tmp}/e.png')
    else: subprocess.run(['pdftoppm', '-r', '150', '-f', str(N), '-l', str(N), '-png', '-singlefile', PDF, f'{tmp}/e'], check=True)
    data = 'data:image/png;base64,' + base64.b64encode(open(f'{tmp}/e.png', 'rb').read()).decode()
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(800)
        r = await pg.evaluate("""async ([src, SY, G]) => {
          Object.assign(globalThis, G);
          const O = await import('/js/omr.js');
          const img = new Image(); img.src = src; await img.decode();
          const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height); g.drawImage(img, 0, 0);
          const A = await O.analyse(c, true); globalThis.__f = A.work && A.work.f;
          const st = A.staves[A.systems[SY][0]];
          return st.heads.map((h) => [Math.round(h.x), Math.round(h.y), h.p, h.acc, Math.round(h.x * globalThis.__f), Math.round(h.y * globalThis.__f)]);
        }""", [data, SY, json.loads(os.environ.get('G', '{}'))])
        for x in r: print(x)
        w = await pg.evaluate('() => globalThis.__accWin || null')
        if w: [print('W', e) for e in w[2:]]
        await b.close()
asyncio.run(main())
