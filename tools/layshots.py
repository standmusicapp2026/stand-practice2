# Every notebook layout drawn as it appears on a page (the app's own drawing), saved one by one and
# as contact sheets, to look at them. PAL=<palette> (default cream), OUT=<folder>
import asyncio, os, base64
from playwright.async_api import async_playwright
OUT = os.environ.get('OUT', '/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad/lay')
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width': 1200, 'height': 900})).new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(2500)
        shots = await pg.evaluate("""async (pal) => {
          const ink = await import('/js/ink.js'); await ink.loadMusicFont(); try { await ink.preloadAssets && ink.preloadAssets(); } catch {}
          await new Promise((r) => setTimeout(r, 800));
          const out = [];
          for (const L of globalThis.__layouts) {
            const W = L.land ? 848 : 600, H = L.land ? 600 : 848;
            const c = document.createElement('canvas'); c.width = W; c.height = H; const g = c.getContext('2d');
            g.fillStyle = '#fff'; g.fillRect(0, 0, W, H);
            let items; try { items = globalThis.__inPalette(L.make(), pal); } catch (e) { out.push([L.k, L.label, null, 'make failed: ' + e.message]); continue; }
            let err = '';
            for (const it0 of items) {
              const it = it0.t === 'img' && !it0.id && it0.mask !== 'bloom' && it0.mask !== 'word' ? { t: 'shape', k: it0.mask || (it0.rr ? 'round' : 'rect'), x: it0.x, y: it0.y, w: it0.w, h: it0.h, rot: it0.rot, f: '#d9c7b4', a: 1 } : it0;
              try { ink.drawItem(g, it, W, H, false); } catch (e) { err = err || ('draw ' + it.t + ': ' + e.message); }
            }
            // what falls off the page
            const off = items.filter((it) => it.t !== 'bg' && it.x !== undefined && (it.x < -0.01 || it.y < -0.01 || (it.w && it.x + it.w > 1.01) || (it.h && it.y + it.h > 1.01))).map((it) => it.t + (it.txt ? ':' + String(it.txt).slice(0, 14) : '')).slice(0, 4);
            out.push([L.k, L.label, c.toDataURL('image/png'), err + (off.length ? ' | off page: ' + off.join(', ') : '')]);
          }
          return out;
        }""", os.environ.get('PAL', 'cream'))
        for k, label, data, note in shots:
            if data: open(f'{OUT}/{k}.png', 'wb').write(base64.b64decode(data.split(',')[1]))
            print(k, '|', label, '|', note or 'ok')
        print('errors', errs[:3])
        await b.close()
asyncio.run(main())
