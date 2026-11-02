# the clef and sign trace of one line: python3 signdump.py PDF PAGE SYS X0 X1 (canvas pixels at 150 dpi)
import asyncio, sys, os, base64, subprocess, json
from playwright.async_api import async_playwright
PDF, N, SY, X0, X1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5])
async def main():
    tmp = '/tmp/claude-0/capeval'; os.makedirs(tmp, exist_ok=True); f = f'{tmp}/sg{os.getpid()}'
    subprocess.run(['pdftoppm', '-r', '150', '-f', str(N), '-l', str(N), '-png', '-singlefile', PDF, f], check=True)
    data = 'data:image/png;base64,' + base64.b64encode(open(f + '.png', 'rb').read()).decode()
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(800)
        r = await pg.evaluate("""async ([src, SY, X0, X1]) => {
          const O = await import('/js/omr.js');
          const img = new Image(); img.src = src; await img.decode();
          const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height); g.drawImage(img, 0, 0);
          const A0 = await O.analyse(c, true); const f = A0.work.f;
          globalThis.__compX = [X0 * f, X1 * f]; globalThis.__sigDbg = 1;
          const A = await O.analyse(c, true);
          const st = A.staves[A.systems[SY][0]]; const all = A.systems.map((sy) => [Math.round(A.staves[sy[0]].top / f), (A.staves[sy[0]].signTrace || []).length, A.staves[sy[0]].signs.length]);
          return { f, all, signs: st.signs, trace: st._ && st._.signTrace };
        }""", [data, SY, X0, X1])
        print('f', r['f'], r['all']); print('signs', json.dumps(r['signs']))
        for t in r['trace'] or []: print(json.dumps(t)[:400])
        await b.close()
asyncio.run(main())
