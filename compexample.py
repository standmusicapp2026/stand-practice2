# Compose: the example (Holst, Jupiter, for orchestra) opens from the Compose panel, is drawn
# (24 instruments as in the full score, 41 bars), plays without errors, and goes out as MusicXML and comes back the same.
import asyncio, os, sys
from playwright.async_api import async_playwright
PORT = os.environ.get('PORT', '8765'); OUT = sys.argv[1] if len(sys.argv) > 1 else '/tmp/claude-0/compex'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        pg = await (await b.new_context(viewport={'width': 1180, 'height': 820}, device_scale_factor=2)).new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1500)
        J = lambda js, a=None: pg.evaluate("async (a) => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }", a)
        await J("document.querySelector('#welGo')?.click(); await sleep(400); document.querySelector('.tour-skip')?.click(); await sleep(200);")
        await J("const bs = [...document.querySelectorAll('[data-panel=\"compose\"]')]; (bs.find((x) => x.offsetParent) || bs[0]).click(); await sleep(700);")
        await J("document.querySelector('#cnExample').click(); await sleep(3500); document.querySelector('.tour-skip')?.click(); await sleep(500);")
        info = await J("""const open = !document.querySelector('#compose').hidden; const { db } = await import('/js/db.js');
          const comps = (await db.all('scores')).filter((s) => s.kind === 'comp');
          const f = comps.length ? await db.get('files', comps[0].fileId) : null; const sc = f && f.data;
          return { open, n: comps.length, title: sc && sc.title, parts: sc && sc.parts.map((x) => x.inst), bars: sc && sc.measures.length, pickup: sc && sc.measures[0].pickup };""")
        print(info)
        await pg.screenshot(path=OUT + '_page.png')
        # MusicXML out and back
        rt = await J("""const { db } = await import('/js/db.js'); const X = await import('/js/compose/musicxml.js');
          const comps = (await db.all('scores')).filter((s) => s.kind === 'comp'); const sc = (await db.get('files', comps[0].fileId)).data;
          const xml = X.toMusicXML(sc); const back = X.fromMusicXML(xml);
          const M = await import('/js/compose/model.js');
          const pitches = (s) => s.parts.map((p) => p.staves[0].bars.map((b) => b.filter((e) => e.notes).map((e) => M.midiOf(e.notes[0].s, e.notes[0].a)).join(',')).join('|'));
          const pa = pitches(sc), pc = pitches(back); const same = pa.every((x, i) => x === pc[i]);
          return { same, len: xml.length };""")
        print('musicxml round trip', rt)
        # play a few seconds
        await J("const b = document.querySelector('#cpPlay') || [...document.querySelectorAll('#compose button')].find((x) => /play/i.test(x.getAttribute('aria-label') || x.textContent)); b && b.click(); await sleep(4000); b && b.click();")
        await pg.wait_for_timeout(500)
        ok = info['open'] and info['n'] == 1 and info['title'] == 'Jupiter' and len(info['parts']) == 24 and info['bars'] == 41 and info['pickup'] == 960 and rt['same'] and not errs
        print('errors', errs[:3]); print('PASS' if ok else 'FAIL', 'the Compose example opens, is drawn, plays and goes out as MusicXML')
        await b.close()
asyncio.run(main())
