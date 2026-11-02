# accidental debugging: python3 accdbg.py PDF PAGE X0 X1 [Y0 Y1]  -> shapes in that window and how they were classed
import asyncio, sys, os, base64, subprocess, json
from playwright.async_api import async_playwright
PDF, N = sys.argv[1], int(sys.argv[2]); X0, X1 = int(sys.argv[3]), int(sys.argv[4])
Y0, Y1 = (int(sys.argv[5]), int(sys.argv[6])) if len(sys.argv) > 6 else (0, 99999)
async def main():
    tmp = '/tmp/claude-0/capeval'; os.makedirs(tmp, exist_ok=True)
    if PDF.endswith('.png'): import shutil; shutil.copy(PDF, f'{tmp}/d.png')
    else: subprocess.run(['pdftoppm', '-r', '150', '-f', str(N), '-l', str(N), '-png', '-singlefile', PDF, f'{tmp}/d'], check=True)
    data = 'data:image/png;base64,' + base64.b64encode(open(f'{tmp}/d.png', 'rb').read()).decode()
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(800)
        r = await pg.evaluate("""async ([src, X0, X1, Y0, Y1, G]) => {
          Object.assign(globalThis, G);
          const O = await import('/js/omr.js'); globalThis.__accLog = [];
          const img = new Image(); img.src = src; await img.decode();
          const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height); g.drawImage(img, 0, 0);
          const r = await O.recogniseBest(c, { lines: 'all' });
          return { log: globalThis.__accLog.filter((a) => a.x1 > X0 && a.x0 < X1 && a.y1 > Y0 && a.y0 < Y1), win: globalThis.__accWin || null };
        }""", [data, X0, X1, Y0, Y1, json.loads(os.environ.get('G', '{}'))])
        for a in r['log']: print(json.dumps(a))
        if r['win']:
            for e in r['win'][2:]:
                if not (isinstance(e, list) and e[0] == 'box' and not os.environ.get('BOX')): print('W', e)
        await b.close()
asyncio.run(main())
