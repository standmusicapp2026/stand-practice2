# The metronome away from Stand (the screen locked): iOS wakes the page only every second or two,
# and every click must still sound exactly in time; back in Stand a change of tempo is heard at once.
# And the lock screen's "Now Playing": Stand's name for what plays, pause and play (stops the
# metronome and drone, then starts them again where they were).
import asyncio, os, json
from playwright.async_api import async_playwright
PORT = os.environ.get('PORT', '8765')
async def main():
    fails = 0
    def check(ok, what):
        nonlocal fails
        print(('ok   ' if ok else 'FAIL ') + what, flush=True)
        if not ok: fails += 1
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        ctx = await b.new_context(viewport={'width': 1024, 'height': 768})
        pg = await ctx.new_page()
        # (the page's Media Session handlers, kept to press them as iOS would)
        await pg.add_init_script("""window.__noTour = true; window.__ms = {};
          { const n = AudioContext.prototype.resume; AudioContext.prototype.resume = function (...a) { if (window.__refuseResume) return Promise.resolve(); return n.apply(this, a); }; }
          if (navigator.mediaSession) { const s = navigator.mediaSession.setActionHandler.bind(navigator.mediaSession);
            navigator.mediaSession.setActionHandler = (a, f) => { window.__ms[a] = f; try { s(a, f); } catch {} }; }""")
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); }")
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
        hide = "Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'hidden' }); Object.defineProperty(document, 'hidden', { configurable: true, get: () => true }); document.dispatchEvent(new Event('visibilitychange'));"
        show = "Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' }); Object.defineProperty(document, 'hidden', { configurable: true, get: () => false }); document.dispatchEvent(new Event('visibilitychange'));"
        # every click the metronome gives the sound system, with its time
        await J("""window.__all = []; const AC = window.AudioContext.prototype, cbs = AC.createBufferSource;
          AC.createBufferSource = function () { const s = cbs.call(this); const st = s.start.bind(s); s.start = (t, ...r) => { s.__t = t; window.__all.push({ t, s }); return st(t, ...r); }; const sp = s.stop.bind(s); s.stop = (...r) => { s.__stopped = true; return sp(...r); }; return s; };""")
        await J("document.querySelector('[data-panel=metronome], [data-tile=metronome]')?.click(); await sleep(600);")
        await J("document.querySelector('#metroToggle')?.click(); await sleep(1200);")
        bpm = await J("return document.querySelector('#bpmVal').textContent")
        print('bpm', bpm)
        # away: the page is woken only every 1.6 s (as iOS does), for 12 s
        await J(hide + """ window.__realSI = window.setInterval; await sleep(50);""")
        res = await J("""
          // (the metronome's own timer stopped, its tick called only every 1.6 s instead)
          const m = window.__standMetro; clearInterval(m._timer); m._timer = null;
          const t0 = m._ctx.currentTime;
          for (let i = 0; i < 8; i++) { await sleep(1600); m._tick(); }
          const ts = window.__all.filter((x) => !x.s.__stopped && x.t > t0 + 0.3 && x.t < m._ctx.currentTime).map((x) => x.t).sort((a, b) => a - b);
          const d = []; for (let i = 1; i < ts.length; i++) d.push(+(ts[i] - ts[i - 1]).toFixed(4));
          return { n: ts.length, d, expect: 60 / m.bpm };""")
        d = res['d']; ex = res['expect']
        bad = [x for x in d if abs(x - ex) > 0.002]
        print('away: clicks', res['n'], 'intervals', sorted(set(d))[:6], 'expected', round(ex, 4))
        check(res['n'] >= int(11 / ex) - 2 and not bad, f'away with the page woken every 1.6 s: every click in time ({len(bad)} out of time)')
        # away, the page woken late once (4 s), then quickly again and again (as the simulator does):
        # the clicks given far ahead are kept, none given twice
        res3 = await J("""
          const m = window.__standMetro; const t0 = m._ctx.currentTime;
          await sleep(4000); m._tick(); for (let i = 0; i < 120; i++) { await sleep(25); m._tick(); }
          for (let i = 0; i < 4; i++) { await sleep(1600); m._tick(); }
          const ts = window.__all.filter((x) => !x.s.__stopped && x.t > t0 + 0.3 && x.t < m._ctx.currentTime).map((x) => x.t).sort((a, b) => a - b);
          const d = []; for (let i = 1; i < ts.length; i++) d.push(+(ts[i] - ts[i - 1]).toFixed(4));
          return { n: ts.length, d, expect: 60 / m.bpm };""")
        bad3 = [x for x in res3['d'] if abs(x - res3['expect']) > 0.002]
        print('away, late then quick: clicks', res3['n'], 'out of time', bad3[:8])
        check(res3['n'] > 10 and not bad3, 'away, woken late then quickly: every click in time, none twice')
        # back: the far-ahead clicks taken back, a change of tempo heard within a moment
        r2 = await J(show + """ const m = window.__standMetro; m._timer = setInterval(() => m._tick(), 25); await sleep(100);
          const now = m._ctx.currentTime; const ahead = window.__all.filter((x) => x.t > now + 0.3);
          // (stopped clicks: their stop was called; kept ones are in the metronome's own list)
          const kept = [...(m._sched || [])].filter((s) => s._t > now + 0.3).length;
          document.querySelector('#bpmUp, [data-bpm=up], .bpm-up')?.click();
          m.bpm = m.bpm + 40; await sleep(1500);
          const ts = window.__all.filter((x) => !x.s.__stopped).map((x) => x.t).filter((t) => t > m._ctx.currentTime - 1.3 && t < m._ctx.currentTime + 0.12).sort((a, b) => a - b);
          const u = [...new Set(ts.map((t) => +t.toFixed(4)))]; const dd = []; for (let i = 1; i < u.length; i++) dd.push(+(u[i] - u[i - 1]).toFixed(3));
          return { kept, dd, expect: 60 / m.bpm };""")
        print('back: clicks still ahead', r2['kept'], 'intervals after tempo change', r2['dd'], 'expected', round(r2['expect'], 3))
        check(r2['kept'] == 0, 'back in Stand: clicks given far ahead are taken back')
        check(len(r2['dd']) >= 1 and all(abs(x - r2['expect']) < 0.01 for x in r2['dd']), 'back in Stand: a change of tempo is heard at once')
        # Now Playing
        np = await J("await sleep(1300); const md = navigator.mediaSession && navigator.mediaSession.metadata; return md ? { title: md.title, artist: md.artist, art: (md.artwork || []).length, state: navigator.mediaSession.playbackState } : null")
        print('now playing', np)
        check(bool(np) and np['title'].startswith('Metronome') and np['artist'] == 'Stand' and np['art'] >= 1 and np['state'] == 'playing', 'now playing: "Metronome · … bpm", Stand, its icon, playing')
        await J("document.querySelector('[data-panel=tuner], [data-tile=tuner]')?.click(); await sleep(500);")
        await J("document.querySelector('[data-tab=drone]')?.click(); await sleep(300); document.querySelector('#droneToggle')?.click(); await sleep(1300);")
        np2 = await J("const md = navigator.mediaSession.metadata; return md && md.title")
        print('now playing with drone', np2)
        check(bool(np2) and 'Drone' in np2 and 'Metronome' in np2, 'now playing: metronome and drone together')
        await J(hide)
        st = await J("""const m = window.__standMetro; const beat0 = m._beatCount; window.__ms.pause(); await sleep(400);
          const after = { metro: m.running, drone: window.__standDrone.running, state: navigator.mediaSession.playbackState, title: navigator.mediaSession.metadata && navigator.mediaSession.metadata.title };
          await sleep(6500);   // (longer than the 5 s after which a silent Stand away lets go of the sound)
          after.ctx = m._ctx.state; after.beat0 = beat0;
          window.__ms.play(); await sleep(600);
          after.metroAgain = m.running; after.droneAgain = window.__standDrone.running; after.beatAgain = m._beatCount; after.state2 = navigator.mediaSession.playbackState;
          return after;""")
        print('pause/play', st)
        check(not st['metro'] and not st['drone'] and st['state'] == 'paused' and bool(st['title']), 'lock screen pause: metronome and drone stop, shown as paused')
        check(st['ctx'] == 'running', 'paused away from Stand: the sound system kept awake, so play stays there')
        check(st['metroAgain'] and st['droneAgain'] and st['state2'] == 'playing' and st['beatAgain'] >= st['beat0'], 'lock screen play: both start again, the beat where it was')
        # as iOS does it: the sound system paused from outside (no Media Session handler called), later started again
        await J(hide)
        st2 = await J("""const m = window.__standMetro, c = m._ctx; const b0 = m._beatCount; await window.__standOutside.pause(c); await sleep(1500);
          const a = { metro: m.running, drone: window.__standDrone.running, ctx: c.state, state: navigator.mediaSession.playbackState };
          await sleep(6000); a.ctx2 = c.state; a.metro2 = m.running;
          await window.__standOutside.play(c); await sleep(800);
          a.metro3 = m.running; a.drone3 = window.__standDrone.running; a.beat3 = m._beatCount; a.b0 = b0; a.state3 = navigator.mediaSession.playbackState; return a;""")
        print('outside pause/play', st2)
        check(not st2['metro'] and not st2['drone'] and st2['ctx'] == 'suspended' and st2['state'] == 'paused', 'paused by iOS: metronome and drone stop, not woken again')
        check(st2['ctx2'] == 'suspended' and not st2['metro2'], 'paused by iOS: stays paused')
        check(st2['metro3'] and st2['drone3'] and st2['state3'] == 'playing' and st2['beat3'] >= st2['b0'], 'played by iOS: both start again where they were')
        await J(show + " await sleep(300);")
        # in Stand: Stand pausing and waking the sound at once (before it has even paused), then
        # iOS pausing it (Control Center); a touch and the sound check after it do not wake it
        st3 = await J("""const m = window.__standMetro, c = m._ctx; c.suspend(); c.resume(); await sleep(600);
          const a = { before: c.state, metro0: m.running };
          await window.__standOutside.pause(c); await sleep(800);
          document.body.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true })); window.standAudioWake && window.standAudioWake('check'); await sleep(1500);
          a.metro = m.running; a.ctx = c.state; a.state = navigator.mediaSession.playbackState;
          await window.__standOutside.play(c); await sleep(800); a.metro2 = m.running; a.ctx2 = c.state; return a;""")
        print('in Stand, Control Center pause/play', st3)
        check(st3['metro0'] and not st3['metro'] and st3['ctx'] == 'suspended' and st3['state'] == 'paused', 'in Stand, paused by iOS after Stand paused and woke the sound itself: stops, a touch does not wake it')
        check(st3['metro2'] and st3['ctx2'] == 'running', 'in Stand, played by iOS: starts again')
        # Stand rested the sound (really suspended), woke it again, and later iOS pauses it: that pause is iOS's
        st5 = await J("""const m = window.__standMetro, c = m._ctx; await c.suspend(); const s0 = c.state; await c.resume(); await sleep(900);
          const a = { s0, before: c.state, metro0: m.running };
          await window.__standOutside.pause(c); await sleep(2500);
          a.metro = m.running; a.ctx = c.state;
          await window.__standOutside.play(c); await sleep(900); a.metro2 = m.running; a.ctx2 = c.state; return a;""")
        print('rested and woken by Stand, then paused by iOS', st5)
        check(st5['s0'] == 'suspended' and st5['metro0'] and not st5['metro'] and st5['ctx'] == 'suspended', 'after Stand rested and woke the sound, a pause by iOS stops the metronome')
        check(st5['metro2'] and st5['ctx2'] == 'running', 'and play by iOS starts it again')
        # a click started just as iOS pauses (the metronome's next one, before the pause is seen): it must not wake it
        st6 = await J("""const m = window.__standMetro, c = m._ctx; const a = { metro0: m.running, before: c.state };
          const click = () => { const s = c.createBufferSource(); s.buffer = c.createBuffer(1, 1, c.sampleRate); s.connect(c.destination); s.start(); };
          const p = window.__standOutside.pause(c); p.then(click); await p; click(); await sleep(2500);
          a.metro = m.running; a.ctx = c.state;
          await window.__standOutside.play(c); await sleep(900); a.metro2 = m.running; a.ctx2 = c.state; return a;""")
        print('a click just as iOS pauses', st6)
        check(st6['metro0'] and not st6['metro'] and st6['ctx'] == 'suspended', 'a click starting just as iOS pauses does not wake the sound: the metronome stops')
        check(st6['metro2'] and st6['ctx2'] == 'running', 'and play by iOS starts it again')
        await J("window.__ms.pause(); await sleep(300);")
        await J("document.querySelector('#droneToggle')?.click(); await sleep(200); document.querySelector('[data-panel=metronome], [data-tile=metronome]')?.click(); await sleep(300); document.querySelector('#metroToggle')?.click(); await sleep(1300);")
        np3 = await J("return { md: navigator.mediaSession.metadata && navigator.mediaSession.metadata.title, state: navigator.mediaSession.playbackState, metro: window.__standMetro.running }")
        print('started in Stand after a remote pause', np3)
        await J("if (window.__standMetro.running) document.querySelector('#metroToggle')?.click(); if (window.__standDrone.running) document.querySelector('#droneToggle')?.click(); await sleep(1300);")
        np4 = await J("return { md: navigator.mediaSession.metadata, state: navigator.mediaSession.playbackState }")
        # Stand rested the sound itself, then a wake that iOS did not take at once (coming back to
        # Stand): starting the metronome must play, never be taken for a pause from outside
        st4 = await J("""const m = window.__standMetro, c = m._ctx; await sleep(300); c.suspend(); await sleep(400); const s0 = c.state;
          window.__refuseResume = true; document.body.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true })); await sleep(100);
          document.querySelector('[data-panel=metronome], [data-tile=metronome]')?.click(); await sleep(300);
          document.querySelector('#metroToggle')?.click(); await sleep(300); window.__refuseResume = false; await sleep(1500);
          const r = { s0, metro: m.running, ctx: m._ctx.state }; if (m.running) document.querySelector('#metroToggle')?.click(); await sleep(300); return r;""")
        print('rested by Stand, a wake not taken, then started', st4)
        check(st4['s0'] == 'suspended' and st4['metro'] and st4['ctx'] == 'running', 'after Stand rested the sound and a wake was not taken: the metronome starts and plays')
        print('all stopped in Stand', np4)
        check(np4['md'] is None and np4['state'] == 'none', 'nothing playing: nothing shown')
        print('page errors', errs[:3]); check(not errs, 'no page errors')
        await b.close()
    print('DONE', 'fails', fails)
asyncio.run(main())
