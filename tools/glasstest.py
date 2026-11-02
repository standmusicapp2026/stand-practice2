import asyncio, base64, sys
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(800)
        r = await pg.evaluate("""async () => {
          const X = await import('/js/inkx.js');
          const W = 1200, H = 900; const c = document.createElement('canvas'); c.width = W; c.height = H; const g = c.getContext('2d');
          const gr = g.createLinearGradient(0, 0, W, H); gr.addColorStop(0, '#e8907a'); gr.addColorStop(0.5, '#f3d9a4'); gr.addColorStop(1, '#6a8fb5'); g.fillStyle = gr; g.fillRect(0, 0, W, H);
          // things under the glass: a photo-like disc, big text, staff lines
          g.fillStyle = '#1d2233'; g.font = '700 120px Georgia'; g.fillText('Recital', 150, 380);
          g.fillStyle = '#2c5364'; g.beginPath(); g.arc(880, 330, 150, 0, 7); g.fill();
          g.strokeStyle = '#111'; g.lineWidth = 3; for (let k = 0; k < 5; k++) { g.beginPath(); g.moveTo(80, 560 + k * 22); g.lineTo(1120, 560 + k * 22); g.stroke(); }
          g.fillStyle = '#111'; for (let k = 0; k < 14; k++) { g.beginPath(); g.ellipse(140 + k * 70, 600 - (k % 5) * 11, 14, 10, -0.4, 0, 7); g.fill(); }
          g.save(); X.drawShape(g, { t: 'shape', k: 'glass', x: 0.5, y: 0.52, w: 0.7, h: 0.42, f: '#ffffff', a: 1, rot: 0 }, W, H); g.restore();
          return c.toDataURL('image/png'); }""")
        open(sys.argv[1], 'wb').write(base64.b64decode(r.split(',')[1])); print(errs); await b.close()
asyncio.run(main())
