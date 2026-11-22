# A page turn shows itself gently: the new page comes in a few points from the side it is turned
# from, and lighter at first, settling in about a quarter of a second. No flash of the whole
# screen (the spread is never dimmed), nothing for "reduce motion".
import asyncio, os, sys
from playwright.async_api import async_playwright
PORT = os.environ.get('PORT', '8765'); BR = os.environ.get('BR', 'chromium')
fails = []
def check(c, m):
    print(('ok   ' if c else 'FAIL ') + m)
    if not c: fails.append(m)
PROBE = """async (dir) => { const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const lab = document.querySelector('#pageLabel'), before = lab.textContent;
  window.standTurn(dir);
  for (let i = 0; i < 200 && lab.textContent === before; i++) await new Promise((r) => requestAnimationFrame(r));
  const pg = document.querySelector('#stage .pg'), sp = document.querySelector('#stage .spread');
  const a = pg.getAnimations ? pg.getAnimations() : [];
  const at = []; for (const t of [30, 90, 400]) { await sleep(t - (at.length ? [30, 90, 400][at.length - 1] : 0)); const r = pg.getBoundingClientRect(); at.push([r.left, +getComputedStyle(pg).opacity, +getComputedStyle(sp).opacity]); }
  return { anims: a.length, at, label: lab.textContent };
}"""
async def run(b, name, vw, vh, reduce=False, half=False):
    ctx = await b.new_context(viewport={'width': vw, 'height': vh}, device_scale_factor=2, has_touch=True, reduced_motion='reduce' if reduce else 'no-preference')
    pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1500)
    J = lambda js, a=None: pg.evaluate("async (a) => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }", a)
    await J("document.querySelector('#welGo')?.click(); await sleep(400); document.querySelector('.tour-skip')?.click(); await sleep(300); [...document.querySelectorAll('.ask-back button')].find((b) => /Not now/.test(b.textContent))?.click();")
    await pg.set_input_files('#importInput', ['/home/claude/fixtures/vector8.pdf'])
    await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=60000)
    await J("document.querySelector('#grid .card:not(.folder)').click()"); await pg.wait_for_timeout(2500)
    tag = f'{name}{" (reduce motion)" if reduce else ""}'
    fwd = await pg.evaluate(PROBE, 1); await pg.wait_for_timeout(500)
    back = await pg.evaluate(PROBE, -1); await pg.wait_for_timeout(500)
    if reduce:
        check(fwd['anims'] == 0 and back['anims'] == 0, f'{tag}: no movement {fwd["anims"]} {back["anims"]}')
    else:
        f = fwd['at']; k = back['at']
        check(fwd['anims'] >= 1 and f[0][0] > f[2][0] + 3 and f[1][0] >= f[2][0] - 0.5 and abs(f[1][0] - f[2][0]) < abs(f[0][0] - f[2][0]), f'{tag}: going on, the page comes in from the right and settles {[round(x[0], 1) for x in f]}')
        check(back['anims'] >= 1 and k[0][0] < k[2][0] - 3, f'{tag}: going back, it comes in from the left {[round(x[0], 1) for x in k]}')
        check(f[0][1] < 0.98 and f[2][1] == 1, f'{tag}: lighter for a moment, then whole {[x[1] for x in f]}')
        check(abs(f[0][0] - f[2][0]) <= 24, f'{tag}: only a few points of movement ({abs(f[0][0] - f[2][0]):.0f})')
    check(all(x[2] == 1 for x in fwd['at'] + back['at']), f'{tag}: the screen is never dimmed (no flash)')
    check(not errs, f'{tag}: no page errors {errs[:2]}')
    await ctx.close()
async def main():
    async with async_playwright() as p:
        b = await getattr(p, BR).launch()
        for d in [('ipad-land', 1180, 820), ('ipad-portrait', 820, 1180), ('ipad-pro13', 1376, 1032), ('ipad-mini', 744, 1133)]:
            await run(b, *d)
        await run(b, 'ipad-portrait', 820, 1180, reduce=True)
        await b.close()
    print('FAILS', len(fails)); sys.exit(1 if fails else 0)
asyncio.run(main())
