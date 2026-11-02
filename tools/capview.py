# Capture a region of a real scan the way the app does, paste it into a new composition, and save
# the original crop above the app's engraving: shots/cap_<name>.png
# usage: capview.py IMAGE x,y,w,h NAME [staff] [inst]
import asyncio, json, sys, base64
from playwright.async_api import async_playwright
FILE, CROP, NAME = sys.argv[1], [int(v) for v in sys.argv[2].split(',')], sys.argv[3]
STAFF = int(sys.argv[4]) if len(sys.argv) > 4 else 0
INST = sys.argv[5] if len(sys.argv) > 5 else 'violin'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width': 1600, 'height': 1100})).new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1000)
        await pg.evaluate("() => document.querySelector('#welGo')?.click()")
        data = 'data:image/jpeg;base64,' + base64.b64encode(open(FILE,'rb').read()).decode()
        r = await pg.evaluate("""async ([src, crop, staff, inst]) => {
          const O = await import('/js/omr.js'); const E = await import('/js/compose/editor.js'); const M = await import('/js/compose/model.js');
          const img = new Image(); img.src = src; await img.decode();
          const [x, y, w, h] = crop;
          const c = document.createElement('canvas'); c.width = w; c.height = h; const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, w, h); g.drawImage(img, -x, -y);
          const shot = c.toDataURL('image/jpeg', 0.85);
          const t0 = performance.now();
          const res = await O.recogniseBest(c, staff ? { staff } : { lines: 'all' });
          const ms = performance.now() - t0;
          if (!res || !res.bars) return { err: 'nothing', shot };
          await E.createComposition({ insts: [inst], time: res.time || [4, 4], bars: Math.max(4, res.bars.length + 1), key: 0 });
          await new Promise((r) => setTimeout(r, 500));
          const C = window.__compose;
          C.capture = { ...res, clef: res.clef || 'treble', key: res.key || 0 };
          document.querySelector('#capTo').value = '';
          const st = M.allStaves(C.score)[0];
          window.__composeTest.pasteCapture(st, 0);
          await new Promise((r) => setTimeout(r, 900));
          return { shot, ms: Math.round(ms), clef: res.clef, key: res.key, time: res.time, bars: res.bars.length };
        }""", [data, CROP, STAFF, INST])
        if r.get('err'): print('ERR', r['err'], errs); await b.close(); return
        open(f'/home/claude/shots/cap_{NAME}_src.jpg', 'wb').write(base64.b64decode(r['shot'].split(',')[1]))
        await pg.evaluate("() => { document.querySelectorAll('.tour, .tour-card').forEach(t=>t.remove()); document.querySelector('#cpPal')?.classList.add('folded'); }")
        el = await pg.query_selector('#cpPages')
        await el.screenshot(path=f'/home/claude/shots/cap_{NAME}_out.png')
        print(json.dumps({k: v for k, v in r.items() if k != 'shot'}), errs[:3])
        await b.close()
asyncio.run(main())
