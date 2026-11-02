# The sound of the metronome, the drone and the scale changes while they play: the beat goes on in time,
# nothing stops, the new sound is heard from the next beat or note
import asyncio, os
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        ctx = await b.new_context(viewport={'width': 1180, 'height': 820}, has_touch=True)
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(1500)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
        await J("document.querySelector('#welGo')?.click(); document.querySelectorAll('.tour').forEach(x=>x.remove());")
        fails = 0
        # metronome: 120 bpm, change the sound 3 times while it plays, collect every click
        r = await J("""const T = globalThis.__tools, m = T.metro; m.bpm = 120; m.subdiv = 1; m.sound = 'click'; m.start(); const seen = new Map();
          const sel = document.querySelector('#soundSel'); const order = ['wood', 'soft', 'beep'];
          for (let k = 0; k < 40; k++) { await sleep(100); for (const c of globalThis.__clicks || []) seen.set(c.t.toFixed(4), c.d);
            if (k % 10 === 9 && order.length) { sel.value = order.shift(); sel.dispatchEvent(new Event('change')); } }
          const running = m.running; m.stop(true);
          return { running, clicks: [...seen.entries()].map(([t, d]) => [+t, +d.toFixed(3)]).sort((a, b) => a[0] - b[0]) };""")
        c = r['clicks']; iv = [round(c[i + 1][0] - c[i][0], 4) for i in range(len(c) - 1)]
        durs = []
        for _, d in c:
            if not durs or durs[-1] != d: durs.append(d)
        print('metronome: still running', r['running'], ' clicks', len(c), ' intervals', min(iv), max(iv), ' sounds heard in turn', durs)
        if not r['running'] or max(iv) - min(iv) > 0.002: print('FAIL metronome beat disturbed'); fails += 1
        if len(durs) < 3: print('FAIL metronome sound did not change while playing'); fails += 1
        # drone: change sound while it sounds; it must stay on, in the same sound system
        r = await J("""const d = globalThis.__tools.drone; document.querySelector('[data-tile=drone]')?.click(); await sleep(400);
          d.start(); await sleep(300); const { getCtx } = await import('/js/audio.js'); const c0 = getCtx(); const v0 = d.voices.slice();
          const sel = document.querySelector('#droneSound'); const opts = [...sel.options].map(o => o.value).filter(v => v !== d.sound);
          const res = [];
          for (const v of opts) { sel.value = v; sel.dispatchEvent(new Event('change')); await sleep(250); res.push([v, d.sound, d.running, getCtx() === c0, d.voices.length]); }
          d.stop(); return res;""")
        for x in r: print('drone ->', x)
        if any(not (x[0] == x[1] and x[2] and x[3] and x[4] > 0) for x in r): print('FAIL drone change'); fails += 1
        # scale: change sound, click and drone while it plays: no restart (the note index keeps going)
        r = await J("""const s = globalThis.__tools.scale; s.countIn = false; s.bpm = 120; s.perBeat = 2; s.repeat = true; s.start(); await sleep(1200);
          const i0 = s._i; const sel = document.querySelector('#scaleSound'); sel.value = [...sel.options].map(o => o.value).find(v => v !== s.sound); sel.dispatchEvent(new Event('change')); await sleep(30);
          const i1 = s._i; const cl = document.querySelector('#scaleClick'); cl.checked = !cl.checked; cl.dispatchEvent(new Event('change')); await sleep(30);
          const dr = document.querySelector('#scaleDrone'); dr.checked = !dr.checked; dr.dispatchEvent(new Event('change')); await sleep(30);
          const i2 = s._i, drone = !!s._drone, want = s.drone, snd = s.sound; await sleep(600); const i3 = s._i; s.stop(true); return { i0, i1, i2, i3, drone, want, snd, sel: sel.value };""")
        print('scale', r)
        if not (r['i1'] >= r['i0'] and r['i2'] >= r['i1'] and r['i3'] > r['i2'] and r['drone'] == r['want'] and r['snd'] == r['sel']): print('FAIL scale restarted or did not change'); fails += 1
        print('errors', errs[:3]); print('fails', fails + len(errs))
        await b.close()
asyncio.run(main())
