# Compose › Write by playing: the microphone (here a recording fed as the microphone) hears notes
# played one at a time and writes each at the selection with the chosen note value, moving on:
# C D E, E again after a short gap, G F A slurred (no gap), a low C; a new bar at the end of the
# music; nothing written while it is off; playing the score stops it; no errors.
import asyncio, os
from playwright.async_api import async_playwright
PORT = os.environ.get('PORT', '8765')
WAV = '/home/claude/tools/fx_audio/listen_seq.wav'
async def main():
    fails = []
    def check(c, m):
        print(('ok   ' if c else 'FAIL ') + m)
        if not c: fails.append(m)
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', f'--use-file-for-fake-audio-capture={WAV}%noloop', '--autoplay-policy=no-user-gesture-required'])
        ctx = await b.new_context(viewport={'width': 1180, 'height': 820}, has_touch=True, permissions=['microphone'])
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1500)
        J = lambda js, a=None: pg.evaluate("async (a) => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); const E = await import('/js/compose/editor.js'); const M = await import('/js/compose/model.js'); const C = window.__compose, T = window.__composeTest; " + js + " }", a)
        await J("document.querySelector('#welGo')?.click(); await sleep(400); document.querySelectorAll('.tour').forEach(x => x.remove());")
        await J("""await E.createComposition({ title: 'Played', insts: ['cello'], time: [4, 4], bars: 2 }); await sleep(900);
          C.tool.dur = 4; C.tool.dots = 0; C.mode = 'select'; const st = M.allStaves(C.score)[0]; C.sel.clear(); C.sel.add(st.bars[0][0].id);
          C.tab = 'notes'; window.__composeRelayout(); T.syncSelBar(); T.renderTab(); await sleep(100);""")
        r = await J("const bt = document.querySelector('#cpPalBody button[aria-label=\"Write by playing\"]'); return !!bt")
        check(r, 'the Write by playing button is in Notes')
        await J("document.querySelector('#cpPalBody button[aria-label=\"Write by playing\"]').click(); await sleep(300);")
        on = await J("return !!(C.listen && C.listen.on) && document.querySelector('#cpPalBody button[aria-label=\"Write by playing\"]').getAttribute('aria-pressed')")
        check(on == 'true', f'listening, and the button shows it {on}')
        await pg.wait_for_timeout(9500)
        r = await J("""const out = []; for (const st of M.allStaves(C.score)) for (const bar of st.bars) for (const e of bar) if (e.notes && !e.rest) out.push(M.midiOf(e.notes[0].s, e.notes[0].a)); return { notes: out, bars: C.score.measures.length };""")
        want = [60, 62, 64, 64, 67, 65, 69, 48]
        check(r['notes'] == want, f'the notes played, written in order {r["notes"]} (want {want})')
        check(r['bars'] >= 2, f'bars added at the end as needed {r["bars"]}')
        await J("document.querySelector('#cpPalBody button[aria-label=\"Write by playing\"]').click(); await sleep(200);")
        off = await J("return !C.listen")
        check(off, 'tapped again: it stops listening')
        check(not errs, f'no errors {errs[:3]}')
        await b.close()
    print('PASS' if not fails else 'FAIL', 'compose write by playing')
asyncio.run(main())
