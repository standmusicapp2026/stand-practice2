import asyncio, base64, sys, json
from playwright.async_api import async_playwright
OUT = sys.argv[1]; keys = sys.argv[2:]
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width':1180,'height':820})).new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        if __import__('os').environ.get('PAL'): await pg.evaluate('(p) => { globalThis.__PAL = p; }', __import__('os').environ['PAL'])
        r = await pg.evaluate("""async (keys) => {
          const X = await import('/js/ink.js'); const out = {};
          for (const L of globalThis.__layouts) {
            if (keys.length && !keys.includes(L.k)) continue;
            const W = L.land ? 1000 : 707, H = L.land ? 707 : 1000; const c = document.createElement('canvas'); c.width = W; c.height = H; const g = c.getContext('2d');
            g.fillStyle = '#fff'; g.fillRect(0, 0, W, H);
            const items = globalThis.__PAL ? globalThis.__inPalette(L.make(), globalThis.__PAL) : L.make(); const probs = [];
            for (const it0 of items) {
              const it = it0.t === 'img' && !it0.id && it0.mask !== 'bloom' && it0.mask !== 'word' ? { t: 'shape', k: it0.mask || 'rect', x: it0.x, y: it0.y, w: it0.w, h: it0.h, rot: it0.rot||0, f: '#d9c7b4', a: 1 } : it0;
              g.save(); X.drawItem(g, it, W, H, false); g.restore();
            }
            const tbs = items.filter((x) => x.t === 'tb');
            for (const t of tbs) { if (t.x < 0 || t.x + t.w > 1.001 || t.y + (t.h||0) > 0.99) probs.push('off page: ' + t.txt.slice(0, 20)); }
            for (let i = 0; i < tbs.length; i++) for (let j = i + 1; j < tbs.length; j++) { const a = tbs[i], q = tbs[j];
              const ox = Math.min(a.x + a.w, q.x + q.w) - Math.max(a.x, q.x), oy = Math.min(a.y + (a.h||0), q.y + (q.h||0)) - Math.max(a.y, q.y);
              if (ox > 0.01 && oy > 0.004) probs.push('overlap: ' + a.txt.slice(0, 18) + ' / ' + q.txt.slice(0, 18)); }
            out[L.k] = { cat: L.cat, probs, png: c.toDataURL('image/png') };
          }
          return out; }""", keys)
        for k, v in r.items():
            open(f'{OUT}/lay_{k}.png', 'wb').write(base64.b64decode(v['png'].split(',')[1]))
            print(k, v['cat'], v['probs'])
        print('errors', errs); await b.close()
asyncio.run(main())
