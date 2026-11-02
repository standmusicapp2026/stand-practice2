import asyncio, json, sys
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-gl=swiftshader', '--enable-unsafe-swiftshader']); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(800)
        r = await pg.evaluate("""async (adjs) => {
          const G = await import('/js/grade.js');
          const c = document.createElement('canvas'); c.width = 64; c.height = 64; const g = c.getContext('2d');
          for (let x = 0; x < 64; x++) { const v = Math.round(x * 4); g.fillStyle = `rgb(${v},${v},${v})`; g.fillRect(x, 0, 1, 64); }
          const gr = new G.Grader(); const out = [];
          for (const adj of adjs) { const o = gr.render(c, 64, 64, { preset: 'natural', adj }); const d = document.createElement('canvas'); d.width = 64; d.height = 64; d.getContext('2d').drawImage(o, 0, 0); const px = d.getContext('2d').getImageData(0, 32, 64, 1).data; out.push([JSON.stringify(adj), [8, 16, 32, 48, 60].map((x) => px[x * 4])]); }
          return out; }""", json.loads(sys.argv[1]))
        for x in r: print(x)
        await b.close()
asyncio.run(main())
