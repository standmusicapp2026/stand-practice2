# picture of one place on a page as Capture reads it: python3 syscrop.py PDF PAGE SYS X0 X1 OUT.png  (x in the reader's working pixels)
import asyncio, sys, os, base64, subprocess, json
from playwright.async_api import async_playwright
from PIL import Image
PDF, N, SY, X0, X1, OUT = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), sys.argv[6]
async def main():
    tmp = '/tmp/claude-0/capeval'; os.makedirs(tmp, exist_ok=True)
    subprocess.run(['pdftoppm', '-r', '150', '-f', str(N), '-l', str(N), '-png', '-singlefile', PDF, f'{tmp}/s'], check=True)
    data = 'data:image/png;base64,' + base64.b64encode(open(f'{tmp}/s.png', 'rb').read()).decode()
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(800)
        r = await pg.evaluate("""async ([src, SY]) => {
          const O = await import('/js/omr.js');
          const img = new Image(); img.src = src; await img.decode();
          const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height); g.drawImage(img, 0, 0);
          const A = await O.analyse(c);
          const st = A.staves[A.systems[SY][0]];
          return { scale: A.scale, top: st.top, bottom: st.bottom, sp: st.sp };
        }""", [data, SY])
        await b.close()
    f = r['scale']; im = Image.open(f'{tmp}/s.png')
    box = (int(X0 / f), int((r['top'] - 5 * r['sp']) / f), int(X1 / f), int((r['bottom'] + 5 * r['sp']) / f))
    im.crop(box).resize(((box[2]-box[0]) * 3, (box[3]-box[1]) * 3)).save(OUT); print(r, box)
asyncio.run(main())
