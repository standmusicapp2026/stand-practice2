# Winks count only while looking at the iPad: the iPad's face tracking says "look" with each level and
# each wink. Looking away (at a teacher), a wink, or what looks like one, never turns the page; looking
# at the music it does; with the option off, as before.
import asyncio, os
from playwright.async_api import async_playwright
F = '/home/claude/fixtures/'
res = []
def ok(c, m): res.append(bool(c)); print('PASS' if c else 'FAIL', m, flush=True)
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width': 1366, 'height': 1024})
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); setTimeout(()=>document.querySelector('.tour-skip')?.click(),300); }"); await pg.wait_for_timeout(700)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
        await pg.set_input_files('#importInput', [F + 'scan10.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=60000)
        await J("const w = document.querySelector('#winkOn'); w.checked = true; w.dispatchEvent(new Event('change'));")
        await J("document.querySelector('#grid .card:not(.folder)').click(); await sleep(3000); document.querySelector('.tour-skip')?.click();")
        page = lambda: J("return document.querySelector('#pageLabel').textContent")
        # levels at 30 a second (as the iPad sends them: its left = your right); a right wink of yours
        LV = """const send = async (l, r, look, ms) => { for (let t = 0; t < ms; t += 33) { window.standFaceEvent({ type: 'levels', l, r, hand: false, look, head: look ? 8 : 60, gaze: look ? 10 : 65 }); await sleep(33); } };"""
        async def wink_by_levels(look):
            await J(LV + f" await send(0.05, 0.05, {str(look).lower()}, 1200); await send(0.85, 0.08, {str(look).lower()}, 330); await send(0.05, 0.05, {str(look).lower()}, 900);")
        async def wink_by_ipad(look):
            l = 'undefined' if look is None else str(look).lower()
            await J(LV + f" const lk = {'true' if look is None else l}; await send(0.05, 0.05, lk, 1200); window.__fastOff = true; for (let t = 0; t < 400; t += 33) {{ window.standFaceEvent({{ type: 'levels', l: 0.85, r: 0.08, hand: false, ...({l} === undefined ? {{}} : {{ look: lk }}) }}); await sleep(33); }} window.standFaceEvent({{ type: 'wink', eye: 'left', look: {l} }}); await send(0.05, 0.05, lk, 1500);")
        p0 = await page()
        await wink_by_levels(False); p1 = await page()
        ok(p1 == p0, f'looking away, a wink seen in the levels: the page stays ({p0} -> {p1})')
        await wink_by_ipad(False); p2 = await page()
        ok(p2 == p0, f"looking away, the iPad's own wink: the page stays ({p2})")
        await wink_by_levels(True); p3 = await page()
        ok(p3 != p0, f'looking at the music, a wink: the page turns ({p0} -> {p3})')
        await wink_by_ipad(True); p4 = await page()
        ok(p4 != p3, f"looking at the music, the iPad's own wink: the page turns ({p3} -> {p4})")
        await wink_by_ipad(None); p5 = await page()
        ok(p5 != p4, f'an older iPad app that does not say where you look: winks turn as before ({p4} -> {p5})')
        await J("const w = document.querySelector('#winkLook'); w.checked = false; w.dispatchEvent(new Event('change'));")
        await wink_by_ipad(False); p6 = await page()
        ok(p6 != p5, f'option off: a wink turns even looking away, as before ({p5} -> {p6})')
        print('errors', errs[:3]); ok(not errs, 'no page errors')
        print('PASS' if all(res) else 'FAIL', 'winks only while looking at the iPad')
        await b.close()
asyncio.run(main())
