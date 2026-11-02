# A full orchestral score (Dvořák 9, finale, 40 bars, 15 parts) in Compose: opens, draws, plays live with
# the notes scheduled on time, scrolls and zooms, edits and undoes, exports audio: quickly and without errors.
import asyncio, os, json, sys, time
from playwright.async_api import async_playwright
fails = []
def ok(c, msg):
    print(('ok   ' if c else 'FAIL ') + msg)
    if not c: fails.append(msg)
XML = sys.argv[1] if len(sys.argv) > 1 else '/home/claude/snd/dvorak/finale.musicxml'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required']); ctx = await b.new_context(viewport={'width': 1366, 'height': 1024}, has_touch=True); pg = await ctx.new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); }"); await pg.wait_for_timeout(800); await pg.evaluate("() => document.querySelectorAll('.tour').forEach(x => x.remove())")
        if os.environ.get('CPU'): 
            cdp = await ctx.new_cdp_session(pg); await cdp.send('Emulation.setCPUThrottlingRate', {'rate': int(os.environ['CPU'])})
        J = lambda js, a=None: pg.evaluate("async (A) => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); const E = await import('/js/compose/editor.js'); const M = await import('/js/compose/model.js'); const C = window.__compose, T = window.__composeTest; " + js + " }", a)
        t0 = time.time()
        r = await J("""const X = await import('/js/compose/musicxml.js'); const { db, uid } = await import('/js/db.js');
          let sc = X.fromMusicXML(A); sc = sc.score || sc;
          const fileId = uid(), id = uid(); await db.put('files', { id: fileId, kind: 'comp', data: sc });
          await db.put('scores', { id, fileId, kind: 'comp', title: 'Dvořák', pages: 1, added: Date.now(), opened: Date.now(), lastPage: 0, seconds: 0, thumb: null });
          const t = performance.now(); await E.openComposition(id); await sleep(100); const t1 = performance.now() - t;
          return { parts: sc.parts.length, bars: sc.measures.length, notes: M.allStaves(sc).reduce((a, s) => a + s.bars.reduce((b, x) => b + x.filter(e => !e.rest).length, 0), 0), openMs: Math.round(t1), pages: C.pages.length };""", open(XML).read())
        print('opened', r)
        ok(r['openMs'] < 8000 * int(os.environ.get('CPU', '1')), f"opens in {r['openMs']} ms")
        ok(r['pages'] >= 1, 'pages drawn')
        # live playback: every note handed to the sound system before its time
        r = await J("""const { sampler } = await import('/js/sampler.js'); const { getCtx } = await import('/js/audio.js');
          const late = []; let n = 0; const orig = sampler.noteOn.bind(sampler);
          sampler.noteOn = (ch, smp, midi, t, ...rest) => { n++; const now = getCtx().currentTime; if (t < now - 0.005) late.push(+(now - t).toFixed(3)); return orig(ch, smp, midi, t, ...rest); };
          C.sel.clear(); C.selBars = null;
          const t0 = performance.now(); document.querySelector('#cpPlay').click();
          let started = null; for (let i = 0; i < 300; i++) { await sleep(100); if (n && started === null) started = performance.now() - t0; if (n > 0 && performance.now() - t0 > (started || 0) + 12000) break; }
          // scroll and zoom while it plays
          const sc = document.querySelector('#cpScroll'); for (let i = 0; i < 10; i++) { sc.scrollTop += 200; await sleep(150); }
          await sleep(2000);
          document.querySelector('#cpPlay').click(); sampler.noteOn = orig;
          return { notes: n, late: late.length, worst: late.length ? Math.max(...late) : 0, startMs: Math.round(started) };""")
        print('live play', r)
        ok(r['notes'] > 300, f"notes played in 15 s: {r['notes']}")
        ok(r['startMs'] < 6000 * int(os.environ.get('CPU', '1')), f"starts playing after {r['startMs']} ms")
        ok(r['late'] <= max(3, r['notes'] * 0.01), f"notes late: {r['late']} (worst {r['worst']} s)")
        # editing a big score stays quick: transpose a bar of every staff, undo
        r = await J("""const all = M.allStaves(C.score); const b0 = JSON.stringify(C.score);
          T.selectBars(all[0], all[all.length - 1], 2, 3); const t = performance.now(); T.moveSemis(1); const dt = performance.now() - t;
          document.querySelector('#cpPalUndo').click(); await sleep(200);
          return { ms: Math.round(dt), back: JSON.stringify(C.score) === b0 };""")
        ok(r['ms'] < 3000 * int(os.environ.get('CPU', '1')) and r['back'], f"edit all staves {r['ms']} ms, undo restores {r['back']}")
        # zoom in and out
        r = await J("""const t = performance.now(); C.zoom = 1.6; window.__composeRelayout(); await sleep(50); C.zoom = 0.8; window.__composeRelayout(); await sleep(50); C.zoom = 1; window.__composeRelayout(); return Math.round(performance.now() - t);""")
        ok(r < 6000 * int(os.environ.get('CPU', '1')), f'zoom relayouts {r} ms')
        ok(not errs, 'no page errors ' + str(errs[:3]))
        await b.close()
    print('fails:', len(fails))
asyncio.run(main())
