import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page()
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(800)
        r = await pg.evaluate("""async () => {
          const L = await import('/js/link.js');
          const h = new L.CameraHost(); h.state = 'linked'; const out = []; h.send = (m) => out.push(m);
          const big = { v: 1, log: Object.fromEntries(Array.from({length: 3000}, (_, i) => ['2026-' + i, i])) };
          h.sendPractice(big);
          const ph = new L.CameraPhone(); let got = null; ph.onPractice = (d) => { got = d; };
          for (const m of out.reverse()) await ph._cmd(m);
          return [out.length, got && Object.keys(got.log).length];
        }""")
        print(r); await b.close()
asyncio.run(main())
