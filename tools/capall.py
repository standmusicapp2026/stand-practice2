# For one page of the test PDF: capture each staff line on its own (as the app does when one line is
# chosen) and make a picture with the original above and the app's writing below, per line.
import asyncio, json, sys, base64
from playwright.async_api import async_playwright
PAGE = int(sys.argv[1]); INST = sys.argv[2] if len(sys.argv) > 2 else 'violin'; ONLY = [int(x) for x in sys.argv[3].split(',')] if len(sys.argv) > 3 else None
async def main():
    from PIL import Image
    import io
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width': 1700, 'height': 1200})).new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1000)
        await pg.evaluate("() => document.querySelector('#welGo')?.click()")
        data = 'data:image/jpeg;base64,' + base64.b64encode(open(f'/home/claude/tc/raw-00{PAGE}.jpg','rb').read()).decode()
        lines = await pg.evaluate("""async (src) => { const O = await import('/js/omr.js'); const img = new Image(); img.src = src; await img.decode(); window.__img = img;
          const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; c.getContext('2d').drawImage(img, 0, 0);
          const A = await O.analyse(c, false); return A.staves.map(s => [Math.round(s.x0), Math.round(s.top), Math.round(s.x1), Math.round(s.bottom), s.sp]); }""", data)
        for i, (x0, top, x1, bot, sp) in enumerate(lines):
            if ONLY and i not in ONLY: continue
            prev_bot = lines[i-1][3] if i else 0; next_top = lines[i+1][1] if i + 1 < len(lines) else 10**6
            y0 = int(max(prev_bot + 1, top - sp * 6, 0)); y1 = int(min(next_top - 1, bot + sp * 6))
            crop = [max(0, x0 - int(sp * 3)), y0, (x1 + int(sp * 2)) - max(0, x0 - int(sp * 3)), y1 - y0]
            r = await pg.evaluate("""async ([crop, inst]) => {
              const O = await import('/js/omr.js'); const E = await import('/js/compose/editor.js'); const M = await import('/js/compose/model.js');
              const img = window.__img; const [x, y, w, h] = crop;
              const c = document.createElement('canvas'); c.width = w; c.height = h; const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, w, h); g.drawImage(img, -x, -y);
              const shot = c.toDataURL('image/jpeg', 0.85);
              const res = await O.recogniseBest(c, { lines: 'all' });
              if (!res || !res.bars) return { shot, err: 'nothing' };
              await E.createComposition({ insts: [inst], time: res.time || [4, 4], bars: Math.max(2, res.bars.length), key: 0 });
              await new Promise((r) => setTimeout(r, 400));
              const C = window.__compose; C.capture = { ...res, clef: res.clef || 'treble', key: res.key || 0 }; document.querySelector('#capTo').value = '';
              window.__composeTest.pasteCapture(M.allStaves(C.score)[0], 0);
              await new Promise((r) => setTimeout(r, 1500));
              const b0 = JSON.stringify(M.allStaves(C.score)[0].bars[0].map(e => e.rest ? 'r' + e.t : e.t)); const rb0 = JSON.stringify(res.bars[0].map(e => e.rest ? 'r' + e.t : e.t));
              return { b0, rb0, shot, clef: res.clef, key: res.key, time: res.time, bars: res.bars.length, fit: +res.fitRead.toFixed(2) };
            }""", [crop, INST])
            src = Image.open(io.BytesIO(base64.b64decode(r['shot'].split(',')[1])))
            if r.get('err'): print(i, 'ERR', r['err']); continue
            await pg.evaluate("() => { document.querySelectorAll('.tour, .tour-card').forEach(t=>t.remove()); document.querySelectorAll('.toast').forEach(t=>t.style.visibility='hidden'); document.querySelector('#cpPal')?.classList.add('folded'); }")
            el = await pg.query_selector('#cpPages .cp-page, #cpPages canvas, #cpPages')
            png = await el.screenshot()
            out = Image.open(io.BytesIO(png))
            W = 1600
            s1 = src.resize((W, int(src.height * W / src.width)))
            # the engraved staff lines only (skip the title area)
            o = out.crop((0, int(out.height * 0.12), out.width, out.height))
            s2 = o.resize((W, int(o.height * W / o.width)))
            comb = Image.new('RGB', (W, s1.height + s2.height + 6), 'red'); comb.paste(s1, (0, 0)); comb.paste(s2, (0, s1.height + 6))
            comb.save(f'/home/claude/shots/rev_{PAGE}_{i}.png')
            print(i, crop, json.dumps({k: v for k, v in r.items() if k != 'shot'}))
        if errs: print(errs[:3])
        await b.close()
asyncio.run(main())
