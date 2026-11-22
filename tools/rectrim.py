# (rectrim) Recordings' trimmer, as in Photos, in the app's colour: pictures along the strip, the ends
# dragged (held still: opened out), "Keep this part" makes a new recording of just that part.
import asyncio, json
from playwright.async_api import async_playwright
SP = '/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad'
UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15'
async def run(b, name, vp, ua):
    ctx = await b.new_context(viewport=vp, device_scale_factor=2, user_agent=ua, has_touch=True)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.add_init_script("window.__noTour = true; window.__noTempo = true;")
    await pg.goto('http://localhost:8765/index.html'); await pg.wait_for_timeout(1500)
    await pg.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); document.querySelectorAll('.ask-back button').forEach(b=>/Not now/.test(b.textContent)&&b.click()); }")
    await pg.evaluate("() => { const b = [...document.querySelectorAll('[data-panel=takes]')].find((x) => x.offsetParent) || document.querySelector('[data-panel=takes]'); b && b.click(); }")
    await pg.wait_for_timeout(600)
    await pg.set_input_files('#takeImportFile', '/home/claude/dragon/4M30 clarinetes.webm')
    await pg.wait_for_function("() => document.querySelector('#trimHost .trimmer')", timeout=90000)
    await pg.wait_for_timeout(3500)
    await pg.evaluate("() => document.querySelector('#cutBox').scrollIntoView({ block: 'center' })"); await pg.wait_for_timeout(300)
    R = await pg.evaluate("() => { const r = document.querySelector('#trimHost .tr-h.r').getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; }")
    L = await pg.evaluate("() => { const r = document.querySelector('#trimHost .tr-h.l').getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; }")
    w = await pg.evaluate("() => document.querySelector('#trimHost .trimmer').clientWidth")
    # the start in by a fifth, the end in by a fifth (held still first: opened out)
    await pg.mouse.move(L['x'], L['y']); await pg.mouse.down()
    for k in range(10): await pg.mouse.move(L['x'] + w * 0.02 * (k + 1), L['y']); await pg.wait_for_timeout(16)
    await pg.mouse.up(); await pg.wait_for_timeout(200)
    await pg.mouse.move(R['x'], R['y']); await pg.mouse.down(); await pg.wait_for_timeout(700)
    zoomed = await pg.evaluate("() => document.querySelector('#trimHost .trimmer').classList.contains('zoomed')")
    await pg.screenshot(path=f'{SP}/rectrim-{name}-zoom.png')
    for k in range(8): await pg.mouse.move(R['x'] - 5 * (k + 1), R['y']); await pg.wait_for_timeout(16)
    await pg.mouse.up(); await pg.wait_for_timeout(400)
    await pg.mouse.move(R['x'], R['y']); await pg.mouse.down()
    for k in range(10): await pg.mouse.move(R['x'] - w * 0.02 * (k + 1), R['y']); await pg.wait_for_timeout(16)
    await pg.mouse.up(); await pg.wait_for_timeout(300)
    st = await pg.evaluate("() => ({ range: document.querySelector('#cutRange').textContent, keep: document.querySelector('#cutKeep').disabled, zoomedAfter: document.querySelector('#trimHost .trimmer').classList.contains('zoomed') })")
    await pg.screenshot(path=f'{SP}/rectrim-{name}.png')
    n0 = await pg.evaluate("async () => (await (await import('/js/db.js')).db.all('takes')).length")
    await pg.evaluate("() => document.querySelector('#cutKeep').click()")
    await pg.wait_for_function(f"async () => (await (await import('/js/db.js')).db.all('takes')).length > {n0}", timeout=120000)
    newt = await pg.evaluate("async () => { const t = (await (await import('/js/db.js')).db.all('takes')).sort((a, b) => b.created - a.created)[0]; return { name: t.name, dur: +t.dur.toFixed(2) }; }")
    print(name, json.dumps({'zoomed': zoomed, **st, 'new': newt}))
    ok = zoomed and not st['zoomedAfter'] and not st['keep'] and 15 < newt['dur'] < 24
    print('PASS' if ok and not errs else 'FAIL', name, 'Recordings trimmer', errs[:2])
    await ctx.close(); return ok and not errs
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        a = await run(b, 'ipad', {'width': 1180, 'height': 820}, None)
        c = await run(b, 'phone', {'width': 390, 'height': 844}, UA)
        await b.close()
        print('PASS' if a and c else 'FAIL', 'Recordings trimmer on iPad and iPhone')
asyncio.run(main())
