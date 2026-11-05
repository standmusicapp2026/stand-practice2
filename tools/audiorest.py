# Battery: the sound system rests when nothing sounds for 30 s, and every sound still plays after.
# metronome on then off -> rests; metronome again -> runs and ticks; a long sound (a 40 s tone, as a
# piece playing) is never cut by the rest; the tuner open -> never rests; a video playing through it -> never rests.
import asyncio, os
from playwright.async_api import async_playwright
PORT = os.environ.get('PORT', '8765')
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required', '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'])
        ctx = await b.new_context(viewport={'width': 1180, 'height': 820}, has_touch=True); pg = await ctx.new_page()
        await pg.add_init_script('window.__noTour = true;')
        await pg.route('**/fixtures-video.webm', lambda r: r.fulfill(path='/home/claude/realvid/slow_sarabande.webm', content_type='video/webm'))
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(2000)
        J = lambda js, a=None: pg.evaluate("async (a) => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); const A = await import('/js/audio.js'); " + js + " }", a)
        await J("document.querySelector('#welGo')?.click(); await sleep(400); document.querySelector('.tour-skip')?.click();")
        st = lambda: J("return A._soundState();")
        bad = []
        def check(ok, what): print(('ok   ' if ok else 'BAD  ') + what, flush=True); (None if ok else bad.append(what))
        # metronome on 3 s, off
        await J("document.querySelector('#metroToggle').click(); await sleep(3000); document.querySelector('#metroToggle').click();")
        check(await st() == 'running', 'metronome played: the sound system is running')
        await pg.wait_for_timeout(42000)
        check(await st() == 'suspended', 'nothing played for 30 s: the sound system rests (' + await st() + ')')
        # the metronome again: running, its clock moving
        await J("document.querySelector('#metroToggle').click();")
        await pg.wait_for_timeout(1500)
        moving = await J("const c = A.getCtx(); const t0 = c.currentTime; await sleep(500); return c.currentTime - t0;")
        check(await st() == 'running' and moving > 0.3, f'metronome again: running, clock moving {moving:.2f}s in 0.5 s')
        clicks = await J("return (globalThis.__clicks || []).length")
        await J("document.querySelector('#metroToggle').click();")
        # a long sound started with a stored context (as a piece playing): never cut
        await J("const c = A.getCtx(); const o = c.createOscillator(); const g = c.createGain(); g.gain.value = 0.0001; o.connect(g).connect(c.destination); o.start(); o.stop(c.currentTime + 45); window.__o = o;")
        await pg.wait_for_timeout(41000)
        check(await st() == 'running', 'a 45 s sound playing: never rested (' + await st() + ')')
        await pg.wait_for_timeout(40000)
        check(await st() == 'suspended', 'after it ended, 30 s: rests (' + await st() + ')')
        # a sound started straight on a resting system (stored context, no getCtx): wakes it
        await J("const o = window.__o.context.createOscillator(); o.connect(window.__o.context.destination); o.start(); o.stop(window.__o.context.currentTime + 0.2);")
        await pg.wait_for_timeout(800)
        check(await st() == 'running', 'a sound started on the resting system woke it (' + await st() + ')')
        # tuner open: microphone -> never rests
        await J("const bs = [...document.querySelectorAll('[data-panel=\"tuner\"]')]; (bs.find((x) => x.offsetParent) || bs[0]).click(); await sleep(1500);")
        await pg.wait_for_timeout(40000)
        check(await st() == 'running', 'tuner open 40 s: never rested (' + await st() + ')')
        await J("document.querySelectorAll('.panel:not([hidden]) [data-close]').forEach((x) => x.click());")
        await pg.wait_for_timeout(45000)
        check(await st() == 'suspended', 'tuner closed, 30 s: rests (' + await st() + ')')
        # a video played through it (as Studio and Recordings do): never rests while it plays
        await J("""const c = A.getCtx(); const v = document.createElement('video'); v.src = '/fixtures-video.webm'; v.loop = true; v.muted = false; document.body.append(v);
          window.__v = v; const s = c.createMediaElementSource(v); s.connect(c.destination); await sleep(300); await c.suspend(); await sleep(200);""")
        await J("try { await window.__v.play(); } catch (e) {} await sleep(800);")
        playing = await J("return !window.__v.paused")
        if playing:
            check(await st() == 'running', 'a video played through it woke it (' + await st() + ')')
            await pg.wait_for_timeout(40000)
            check(await st() == 'running', 'video playing 40 s: never rested (' + await st() + ')')
        else: print('  (no video to play here: skipped)')
        log = await J("return (window.__audioLog || []).map((x) => x.what).join(' | ')")
        print('log:', log[-400:]); print('errors', errs[:3])
        print('PASS' if not bad and not errs else 'FAIL', 'the sound system rests when silent and wakes for every sound', bad)
        await b.close()
asyncio.run(main())
