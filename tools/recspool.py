# A long recording goes into the database every 10 s (never all in memory); stopped, it is one whole
# take and the pieces go; Stand ended while recording: the next start keeps what was recorded.
import asyncio, os
from playwright.async_api import async_playwright
FIX = '/home/claude/fixtures/'
res = []
def ok(c, m): res.append(bool(c)); print('PASS' if c else 'FAIL', m, flush=True)
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream', '--autoplay-policy=no-user-gesture-required'])
        ctx = await b.new_context(viewport={'width': 1180, 'height': 820}, has_touch=True, permissions=['camera', 'microphone'])
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        base = 'http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'
        await pg.goto(base); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); setTimeout(() => document.querySelector('.tour-skip')?.click(), 300); }"); await pg.wait_for_timeout(700)
        await pg.set_input_files('#importInput', [FIX + 'vector8.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=60000)
        await pg.evaluate("() => document.querySelector('#grid .card:not(.folder)').click()"); await pg.wait_for_timeout(2500)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); const { db } = await import('/js/db.js'); " + js + " }")
        spools = "return (await db.keys('files')).map(String).filter(k => k.startsWith('recspool:')).length"
        # ---- 1. a 45 s take
        await J("document.querySelector('#recBtn').click(); await sleep(500); document.querySelector('#recAudio').click();")
        await pg.wait_for_timeout(27000); mid = await J(spools)
        await pg.wait_for_timeout(20000)
        await J("document.querySelector('#recStop').click(); await sleep(4000);")
        t1 = await J("const t = (await db.all('takes')).sort((a, b) => b.created - a.created)[0]; const f = await db.get('files', 'audio:' + t.id); return [t.dur, f.data.length / t.sr, t.name];")
        left = await J(spools)
        print('spooled during', mid, 'take', t1, 'pieces left', left)
        ok(mid >= 1 and 40 < t1[0] < 52 and abs(t1[1] - t1[0]) < 0.1 and left == 0, 'a 45 s take: kept whole, its pieces gone')
        # ---- 2. Stand ended while recording
        await J("for (const c of document.querySelectorAll('aside.panel:not([hidden]) [data-close]')) c.click(); await sleep(300); document.querySelector('#recBtn').click(); await sleep(500); document.querySelector('#recAudio').click();")
        await pg.wait_for_timeout(26000)
        before = await J(spools)
        await pg.reload(); await pg.wait_for_timeout(9000)
        r = await J("const t = (await db.all('takes')).filter(x => x.name === 'Recovered take'); return [t.length, t[0] ? t[0].dur : 0, t[0] ? !!(await db.get('files', 'audio:' + t[0].id)) : false];")
        left2 = await J(spools)
        print('pieces before ending', before, 'recovered', r, 'pieces left', left2)
        ok(before >= 1 and r[0] == 1 and r[1] >= 15 and r[2] and left2 == 0, 'Stand ended while recording: what was recorded is kept as a take')
        print(errs[:3]); ok(not errs, 'no page errors')
        print('PASS' if all(res) else 'FAIL', 'recordings kept safe')
        await b.close()
asyncio.run(main())
