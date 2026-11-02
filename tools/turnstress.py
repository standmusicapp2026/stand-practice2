# Page turning under stress: very quick turns, back and forth, zoomed, after rotating, half-page.
# After each burst the page shown must match the label, and every page must be drawn (not blank).
import asyncio, json, random
from playwright.async_api import async_playwright
FIX = '/home/claude/fixtures/'
CHECK = """async () => {
  const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); await sleep(1800);
  const lab = document.querySelector('#pageLabel').textContent;
  const arts = [...document.querySelectorAll('#stage canvas.art')];
  const blank = arts.map(c => { try { const g=c.getContext('2d'); const w=c.width,h=c.height; const d=g.getImageData(0,0,w,h).data; let dark=0; for(let i=0;i<d.length;i+=4*97) if(d[i]<120) dark++; return dark; } catch(e) { return -1; } });
  return { lab, n: arts.length, dark: blank, pgs: document.querySelectorAll('#stage .pg').length };
}"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        R = []
        for vw, vh, name in ((1366, 1024, 'landscape'), (1024, 1366, 'portrait')):
            ctx = await b.new_context(viewport={'width': vw, 'height': vh}, has_touch=True)
            pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
            errs = []
            pg.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
            pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'peerjs' not in m.text and 'ERR_' not in m.text else None)
            await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
            await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); setTimeout(()=>{ document.querySelector('.tour-skip')?.click(); }, 300); }"); await pg.wait_for_timeout(700)
            await pg.set_input_files('#importInput', [FIX + 'scan10.pdf', FIX + 'imslp12.pdf'])
            await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 2", timeout=90000)
            for k in range(2):
                await pg.evaluate(f"() => document.querySelectorAll('#grid .card:not(.folder)')[{k}].click()")
                await pg.wait_for_function("document.querySelector('#stage canvas.art') && [...document.querySelectorAll('#stage canvas.art')].every(c=>c.width>10)", timeout=30000)
                total = int((await pg.evaluate("() => document.querySelector('#pageLabel').textContent")).split('/')[1])
                rnd = random.Random(k)
                for burst in range(6):
                    seq = [rnd.choice(['ArrowRight', 'ArrowRight', 'ArrowLeft']) for _ in range(rnd.randint(3, 9))]
                    gap = rnd.choice([0, 30, 80, 200])
                    for key in seq:
                        await pg.keyboard.press(key)
                        if gap: await pg.wait_for_timeout(gap)
                    st = await pg.evaluate(CHECK)
                    first = int(st['lab'].split('/')[0].split('–')[0].replace('½', ''))
                    ok = st['n'] == st['pgs'] and all(d > 3 for d in st['dark']) and 1 <= first <= total
                    R.append(ok)
                    if not ok: print('FAIL', name, k, burst, seq, gap, st)
                # zoom in, turn, zoom out
                await pg.evaluate("() => { document.querySelector('#zoomBtn').click(); document.querySelector('#zoomPresets [data-z=\"2\"]').click(); document.querySelector('#zoomBtn').click(); }")
                await pg.keyboard.press('ArrowRight'); st = await pg.evaluate(CHECK)
                ok = all(d > 3 for d in st['dark']); R.append(ok); print('zoom turn', name, k, st['lab'], 'ok' if ok else st)
                await pg.evaluate("() => { document.querySelector('#backBtn').click(); }"); await pg.wait_for_timeout(800)
            print(name, 'errors', errs[:5])
            await ctx.close()
        print('SUMMARY', sum(R), '/', len(R)); await b.close()
asyncio.run(main())
