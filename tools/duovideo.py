# (duovideo) The two clarinet parts in Stand, Lines together, 4M30 from bar 2: the screens the app
# shows as the music goes on (a turn each time the music reaches the last pair on screen), put beside
# the players' own video, with its sound.
import asyncio, base64, json, os, subprocess, sys
from playwright.async_api import async_playwright
D = '/home/claude/dragon'
FILES = [f'{D}/out/How to Train Your Dragon 2 - Clarinet 1.pdf', f'{D}/out/How to Train Your Dragon 2 - Clarinet 2.pdf']
READ = [f'{D}/app1.json', f'{D}/app2.json']
CUE, FROM, TO = '4M30', 2, 19
T0, BAR = float(os.environ.get('T0', '0.36')), 4 * 60 / 135.99   # (bar 2 starts at T0; a bar of 4 beats at ♩≈136)
VW, VH = int(os.environ.get('VW', '820')), int(os.environ.get('VH', '1180'))
OUT = f'{D}/vid'; os.makedirs(OUT, exist_ok=True)
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={'width': VW, 'height': VH}, device_scale_factor=2)
        pg = await ctx.new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.add_init_script("window.__noTour = true; window.__noTempo = true; try { localStorage.setItem('standDuoMode', 'pairs'); } catch {}")
        await pg.goto('http://localhost:8765/index.html'); await pg.wait_for_timeout(1200)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); }")
        await pg.set_input_files('#importInput', FILES)
        await pg.wait_for_function("() => document.querySelectorAll('#grid .card:not(.folder)').length >= 2", timeout=180000)
        await pg.wait_for_timeout(2500)
        print('titles', await pg.evaluate("() => [...document.querySelectorAll('#grid .card:not(.folder) .ttl')].map((t) => t.textContent)"))
        # what the app read of each part (the same pages, read before): kept for it, so it is not read again here
        for x, f in enumerate(READ):
            pages = open(f).read()
            await pg.evaluate("""async ([x, pages]) => { const { db } = await import('/js/db.js');
              const ss = await db.all('scores'); const sc = ss.find((s) => new RegExp('Clarinet\\\\W*' + (x + 1)).test(s.title));
              await db.put('files', { id: window.__duoKey(sc), kind: 'duo', pages: JSON.parse(pages) }); }""", [x, pages])
        await pg.evaluate(r"() => [...document.querySelectorAll('#grid .card:not(.folder)')].find((c) => /Clarinet\W*1/.test(c.textContent)).click()")
        await pg.wait_for_function("() => !document.querySelector('#score').hidden", timeout=30000); await pg.wait_for_timeout(1200)
        await pg.evaluate("() => { document.querySelector('.tour-skip')?.click(); document.body.classList.remove('touring'); }")
        await pg.evaluate("() => document.querySelector('[data-panel=settings]').click()"); await pg.wait_for_timeout(500)
        await pg.evaluate("() => document.querySelector('#duoBtn').click()"); await pg.wait_for_timeout(600)
        await pg.evaluate("() => [...document.querySelectorAll('.choose-item')].find((c) => /Clarinet\\W*2/.test(c.textContent)).click()")
        await pg.wait_for_function("() => window.__duo.M && window.__duo.parts.every((P) => P && P.done)", timeout=60000)
        k = await pg.evaluate("(cue) => window.__duo.parts[0].map.lines.find((l) => l.label === cue).k", CUE)
        await pg.evaluate("([k, bar]) => { window.__duo.at = { k, bar }; window.__duo.back = []; }", [k, FROM])
        await pg.evaluate("() => { document.querySelector('#score').classList.add('chrome-off'); window.dispatchEvent(new Event('resize')); }")
        await pg.wait_for_timeout(2500)
        shots = []   # (time it shows from, file)
        t = 0.0; n = 0
        while True:
            f = f'{OUT}/s{n:02d}.png'; await pg.screenshot(path=f)
            st = await pg.evaluate("() => ({ next: window.__duo.pairNext, at: window.__duo.at })")
            shots.append((t, f, st))
            print(n, round(t, 2), st, flush=True)
            nx = st['next']
            if not nx or nx['k'] != k or nx['bar'] > TO: break
            # the player turns as the music reaches the last pair on screen (its first bar)
            t = max(0.0, T0 + (nx['bar'] - FROM) * BAR)
            await pg.keyboard.press('PageDown'); await pg.wait_for_timeout(1800)
            n += 1
        json.dump([(a, f) for a, f, _ in shots], open(f'{OUT}/shots.json', 'w'))
        print('errors', errs[:3])
        await b.close()
asyncio.run(main())
