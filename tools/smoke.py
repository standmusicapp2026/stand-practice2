# Quick end-to-end checks on the main flows. Prints PASS/FAIL lines and page errors.
import asyncio, sys, json, time
from playwright.async_api import async_playwright
FIX = '/home/claude/fixtures/'
R = []
# a Pencil stroke, as pointer events with pointerType 'pen'
PEN = '''async (pts) => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const t = document.elementFromPoint(pts[0][0], pts[0][1]);
  const ev = (type, [x, y]) => t.dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true, composed: true, pointerId: 77, pointerType: 'pen', isPrimary: true, clientX: x, clientY: y, pressure: type === 'pointerup' ? 0 : 0.5, buttons: type === 'pointerup' ? 0 : 1 }));
  ev('pointerdown', pts[0]);
  for (const q of pts.slice(1)) { ev('pointermove', q); await sleep(16); }
  ev('pointerup', pts[pts.length - 1]);
}'''
def ok(name, cond, info=''):
    R.append((name, bool(cond))); print(('PASS ' if cond else 'FAIL ') + name, info if not cond else '')
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', '--autoplay-policy=no-user-gesture-required'])
        ctx = await b.new_context(viewport={'width': 1366, 'height': 1024}, has_touch=True)
        pg = await ctx.new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs = []
        pg.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
        pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'peerjs' not in m.text and 'ERR_' not in m.text else None)
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); setTimeout(()=>{ document.querySelector('.tour-skip')?.click(); }, 300); }"); await pg.wait_for_timeout(700)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
        # import three files at once
        await pg.set_input_files('#importInput', [FIX + 'vector8.pdf', FIX + 'scan10.pdf', FIX + 'imslp12.pdf'])
        try:
            await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 3", timeout=60000); ok('import 3 pdfs', True)
        except Exception as e: ok('import 3 pdfs', False, str(e)[:100])
        titles = await J("return [...document.querySelectorAll('#grid .card:not(.folder) .ttl')].map(x=>x.textContent)")
        print('  titles', titles)
        # open each, turn, back
        for k in range(3):
            await J(f"document.querySelectorAll('#grid .card:not(.folder)')[{k}].click()")
            try:
                await pg.wait_for_function("document.querySelector('#stage canvas.art') && [...document.querySelectorAll('#stage canvas.art')].every(c=>c.width>10)", timeout=20000); ok(f'open score {k}', True)
            except Exception: ok(f'open score {k}', False)
            lab = await J("return document.querySelector('#pageLabel').textContent")
            await pg.keyboard.press('ArrowRight'); await pg.wait_for_timeout(3000)
            lab2 = await J("return document.querySelector('#pageLabel').textContent")
            ok(f'turn score {k}', lab != lab2, f'{lab} -> {lab2}')
            await pg.keyboard.press('ArrowLeft'); await pg.wait_for_timeout(1200)
            ok(f'turn back score {k}', (await J("return document.querySelector('#pageLabel').textContent")) == lab)
            if k == 0:
                # draw a line with the pen
                await J("document.querySelector('#inkBtn').click(); await sleep(400);")
                r = await J("const r=document.querySelector('#stage .pg').getBoundingClientRect(); return [r.left,r.top,r.width,r.height]")
                await pg.evaluate(PEN, [[r[0]+100+i*10, r[1]+200+i*2] for i in range(20)]); await pg.wait_for_timeout(800)
                n = await J("const { db } = await import('/js/db.js'); const all = await db.all('ink'); return all.reduce((a,r)=>a+r.items.length,0)")
                ok('pen stroke saved', n >= 1, n)
                await J("document.querySelector('#inkBtn').click(); await sleep(300);")
            await J("document.querySelector('#backBtn').click(); await sleep(700);")
            ok(f'back home {k}', await J("return !document.querySelector('#library').hidden"))
        # tuner and metronome
        await J("document.querySelector('.tile[data-tile=\"metronome\"]').click(); await sleep(500); document.querySelector('#metroToggle').click(); await sleep(1500);")
        ok('metronome running', await J("return !document.querySelector('#metroPill').hidden || /Stop/.test(document.querySelector('#metroToggle').textContent)"))
        await J("document.querySelector('#metroToggle').click(); await sleep(300); document.querySelector('[data-close]:not([hidden])')?.click();")
        await J("document.querySelector('.tile[data-tile=\"tuner\"]').click(); await sleep(1500);")
        ok('tuner listening', await J("return /Stop/.test(document.querySelector('#tunerToggle').textContent)"), await J("return document.querySelector('#tunerToggle').textContent"))
        await J("document.querySelector('#panel-tuner [data-close]').click(); await sleep(500);")
        # notebook
        await J("document.querySelector('#newNotebookBtn').click(); await sleep(1500); document.querySelector('#nbCreate').click(); await sleep(2500);")
        ok('notebook opens', await J("return !document.querySelector('#score').hidden && document.querySelectorAll('#stage canvas.art').length > 0"))
        await J("document.querySelector('#backBtn').click(); await sleep(700);")
        # compose
        await J("document.querySelector('.tile[data-tile=\"compose\"]').click(); await sleep(800);")
        print('  errors:', errs[:10])
        print('SUMMARY', sum(1 for _, c in R if c), '/', len(R))
        await b.close()
asyncio.run(main())
