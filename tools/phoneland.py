# The iPhone on its side: every tool panel opened, a picture of each (and what does not fit:
# content cut off with no way to scroll to it).
import asyncio, os, sys
from playwright.async_api import async_playwright
PORT = os.environ.get('PORT', '8765'); OUT = sys.argv[1] if len(sys.argv) > 1 else '/tmp/pl'
W, H = (int(os.environ.get('W', 852)), int(os.environ.get('H', 393)))
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'])
        ctx = await b.new_context(viewport={'width': W, 'height': H}, is_mobile=True, has_touch=True, device_scale_factor=2,
                                  user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)')
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true; try { localStorage.setItem("standLinkIntro", "1"); } catch {}')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(2000)
        J = lambda js, a=None: pg.evaluate("async (a) => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }", a)
        await J("document.querySelector('#welGo')?.click(); await sleep(400); document.querySelector('.tour-skip')?.click(); await sleep(300); document.querySelector('.tour-skip')?.click();")
        os.makedirs(OUT, exist_ok=True)
        await pg.screenshot(path=f'{OUT}/home.png')
        panels = (os.environ.get('PANELS') or 'tuner metronome scales pomodoro record takes reps passages goal app settings listen').split()
        for pn in panels:
            ok = await J("const bs = [...document.querySelectorAll('[data-panel=\"' + a + '\"]')]; const b = bs.find((x) => x.offsetParent) || bs[0]; if (!b) return false; b.click(); await sleep(900); document.querySelector('.tour-skip')?.click(); await sleep(200); return !document.querySelector('#panel-' + a).hidden;", pn)
            if not ok: print(pn, 'did not open'); continue
            info = await J("""const P = document.querySelector('#panel-' + a); const r = P.getBoundingClientRect(); const body = P.querySelector('.panel-body') || P;
              const cut = []; for (const e of P.querySelectorAll('button, input, select, .tuner-face, #tNote, svg, canvas')) { if (!e.offsetParent) continue; const q = e.getBoundingClientRect(); if (q.width < 2) continue;
                if (q.bottom > innerHeight + 1 || q.top < -1 || q.right > innerWidth + 1 || q.left < -1) { const canScroll = body.scrollHeight > body.clientHeight + 2 && getComputedStyle(body).overflowY !== 'hidden'; if (!canScroll) cut.push((e.id || e.className || e.tagName).toString().slice(0, 30)); } }
              return { r: [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)], scroll: [body.scrollHeight, body.clientHeight, getComputedStyle(body).overflowY], cut: cut.slice(0, 8) };""", pn)
            print(pn, info, flush=True)
            await pg.screenshot(path=f'{OUT}/{pn}.png')
            await J("document.querySelectorAll('.panel:not([hidden]) [data-close]').forEach((x) => x.click()); await sleep(500);")
        print('errors', errs[:3]); await b.close()
asyncio.run(main())
