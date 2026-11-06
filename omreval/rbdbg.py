import asyncio, base64, sys, json
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:8765/index.html'); await pg.wait_for_timeout(1200)
        for png in sys.argv[1:]:
            mime = 'image/jpeg' if png.endswith('.jpg') else 'image/png'
            data = f'data:{mime};base64,' + base64.b64encode(open(png, 'rb').read()).decode()
            r = await pg.evaluate("""async (src) => {
              const O = await import('/js/omr.js'); globalThis.__rbDbg = 1;
              const img = new Image(); img.src = src; await img.decode();
              const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; c.getContext('2d').drawImage(img, 0, 0);
              const r = await O.recogniseBest(c, {});
              return { fits: globalThis.__rbFits, fit: r.fitRead, staves: r.analysis.staves.map((s) => (s.clef || '-') + (s.key || 0)).join(' ') };
            }""", data)
            print(png.split('/')[-1], json.dumps(r))
        await b.close()
asyncio.run(main())
