# Is the ink drawn as sharp as the screen? Ratio of canvas pixels to screen pixels for the page,
# the ink and the live layer, at rest, zoomed, after writing, on iPad (2x) and iPhone (3x).
import asyncio, json, sys
from playwright.async_api import async_playwright
PEN = open('/home/claude/tools/smoke.py').read().split("PEN = '''")[1].split("'''")[0]
PROBE = """() => { const dpr = devicePixelRatio; const out = [];
  for (const pg of document.querySelectorAll('#stage .pg')) { const a = pg.querySelector('canvas.art'), k = pg.querySelector('canvas.ink:not(.ink-base)');
    const ra = a.getBoundingClientRect(), rk = k.getBoundingClientRect();
    out.push({ art: +(a.width / (ra.width * dpr)).toFixed(2), ink: +(k.width / (rk.width * dpr)).toFixed(2), inkH: +(k.height / (rk.height * dpr)).toFixed(2) }); }
  const lv = document.querySelector('canvas.live, #liveInk, canvas#live'); 
  return { dpr, pages: out, live: lv ? +(lv.width / (lv.getBoundingClientRect().width * dpr)).toFixed(2) : null }; }"""
async def run(b, vw, vh, dpr, phone, fix):
    ctx = await b.new_context(viewport={'width': vw, 'height': vh}, device_scale_factor=dpr, has_touch=True, is_mobile=phone)
    pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
    await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
    await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); setTimeout(()=>{ document.querySelector('.tour-skip')?.click(); }, 300); }"); await pg.wait_for_timeout(700)
    J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
    if phone: print('phone: no scores on iPhone'); await ctx.close(); return
    await pg.set_input_files('#importInput', [fix])
    await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=60000)
    await J("document.querySelector('#grid .card:not(.folder)').click()"); await pg.wait_for_timeout(4000)
    print(vw, vh, dpr, 'rest', await pg.evaluate(PROBE))
    await J("document.querySelector('#inkBtn').click(); await sleep(500);")
    r = await J("const r=document.querySelector('#stage .pg').getBoundingClientRect(); return [r.left,r.top]")
    await pg.evaluate(PEN, [[r[0]+100+i*8, r[1]+250+i*2] for i in range(15)]); await pg.wait_for_timeout(800)
    print(' after stroke', await pg.evaluate(PROBE))
    await J("document.querySelector('#zoomBtn').click(); await sleep(100); document.querySelector('#zoomPresets [data-z=\"1.5\"]').click(); await sleep(100); document.querySelector('#zoomBtn').click(); await sleep(2500);")
    print(' zoom 1.5', await pg.evaluate(PROBE))
    await pg.evaluate(PEN, [[r[0]+150+i*8, r[1]+350+i*2] for i in range(15)]); await pg.wait_for_timeout(1500)
    print(' zoom 1.5 after stroke', await pg.evaluate(PROBE))
    await ctx.close()
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for fix in sys.argv[1:]:
            await run(b, 1366, 1024, 2, False, fix)
            await run(b, 1024, 1366, 2, False, fix)
        await b.close()
asyncio.run(main())
