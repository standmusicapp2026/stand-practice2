# The small corrections of 2 Nov: metronome pill slide, recording metronome button, goal to 6 h,
# drone list per score, pages flying to Deleted pages, tuner lines that never shrink, Capture's
# words under the staff selectable / movable / deletable, title typed then Back kept.
import asyncio, os, json
from playwright.async_api import async_playwright
FIX = '/home/claude/fixtures/'
res = []
def ok(c, m): res.append(bool(c)); print('PASS' if c else 'FAIL', m)
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width': 1366, 'height': 1024}, has_touch=True)
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); setTimeout(() => document.querySelector('.tour-skip')?.click(), 300); }"); await pg.wait_for_timeout(700)
        await pg.set_input_files('#importInput', [FIX + 'vector8.pdf', FIX + 'scan10.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 2", timeout=60000)
        await pg.wait_for_timeout(1500)
        titles = await pg.evaluate("() => [...document.querySelectorAll('#grid .card:not(.folder) .ttl')].map(x => x.textContent)")
        A, B = titles[0], titles[1]
        async def open_(t):
            await pg.evaluate("(t) => [...document.querySelectorAll('#grid .card:not(.folder)')].find((c) => c.querySelector('.ttl').textContent === t).click()", t)
            await pg.wait_for_function("document.querySelector('#stage canvas.art')", timeout=20000); await pg.wait_for_timeout(900)
        async def back(): await pg.evaluate("() => document.querySelector('#backBtn').click()"); await pg.wait_for_timeout(900)
        sett = "async () => { const { getSetting } = await import('/js/db.js'); const s = await getSetting('settings', {}); return { list: s.droneList || [], key: s.droneListKey || '' }; }"
        async def setList(l):
            # the list made in the drone panel: notes added with Add notes
            await pg.evaluate("() => { document.querySelector('[data-panel=tuner]')?.click(); }"); await pg.wait_for_timeout(500)
            await pg.evaluate("() => document.querySelector('#tunerTabs button[data-tab=drone]').click()"); await pg.wait_for_timeout(400)
            await pg.evaluate("() => document.querySelector('#droneModeSeg button[data-mode=list]')?.click()"); await pg.wait_for_timeout(200)
            await pg.evaluate("() => document.querySelector('#droneListClear').click()"); await pg.wait_for_timeout(100)
            await pg.evaluate("() => document.querySelector('#droneListAdd').click()")
            for pc in l: await pg.evaluate("(pc) => document.querySelector('#droneNotes button[data-pc=\"' + pc + '\"]').click()", pc); await pg.wait_for_timeout(80)
            await pg.evaluate("() => document.querySelector('#droneListAdd').click()"); await pg.wait_for_timeout(200)
            await pg.evaluate("() => document.querySelector('#panel-tuner [data-close]')?.click()"); await pg.wait_for_timeout(500)
        async def chips(): return await pg.evaluate("() => [...document.querySelectorAll('#droneListChips button')].map(b => b.firstChild.textContent)")
        # ---- drone list per score
        await open_(A); await setList([2, 9]); la = (await pg.evaluate(sett))['list']; await back()
        await open_(B); lb0 = (await pg.evaluate(sett))['list']; await setList([5]); await back()
        home = (await pg.evaluate(sett))['list']
        await open_(A); la2 = (await pg.evaluate(sett))['list']; await back()
        await open_(B); lb2 = (await pg.evaluate(sett))['list']
        print('drone lists', la, lb0, home, la2, lb2)
        ok(la == [2, 9] and lb0 == [] and la2 == [2, 9] and lb2 == [5], 'My list: each score keeps its own sequence')
        await pg.reload(); await pg.wait_for_timeout(2000)
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 2", timeout=30000)
        await open_(A); la3 = (await pg.evaluate(sett))['list']; await back()
        ok(la3 == [2, 9], f'My list: kept after the app starts again ({la3})')
        # ---- metronome pill: slide up and down
        await open_(A)
        await pg.evaluate("() => { document.querySelector('[data-panel=metronome]')?.click(); }"); await pg.wait_for_timeout(400)
        await pg.evaluate("() => document.querySelector('#metroToggle, #metroStart, #metroPlay')?.click()"); await pg.wait_for_timeout(300)
        await pg.evaluate("() => document.querySelector('#panel-metronome [data-close]')?.click()"); await pg.wait_for_timeout(500)
        vis = await pg.evaluate("() => !document.querySelector('#metroPill').hidden")
        if not vis: print('metro pill not shown; ids:', await pg.evaluate("() => [...document.querySelectorAll('#panel-metronome button[id]')].map(b => b.id).join(' ')"))
        bb = await pg.evaluate("() => { const r = document.querySelector('#metroPill .pill-main').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2, +document.querySelector('#metroPillBpm').textContent]; }")
        x, y, b0 = bb
        await pg.mouse.move(x, y); await pg.mouse.down()
        for k in range(1, 11): await pg.mouse.move(x, y - k * 6); await pg.wait_for_timeout(16)
        mid = await pg.evaluate("() => +document.querySelector('#metroPillBpm').textContent")
        await pg.mouse.up(); await pg.wait_for_timeout(300)
        opened = await pg.evaluate("() => !document.querySelector('#panel-metronome').hidden")
        await pg.mouse.move(x, y); await pg.mouse.down()
        for k in range(1, 11): await pg.mouse.move(x, y + k * 6); await pg.wait_for_timeout(16)
        await pg.mouse.up(); await pg.wait_for_timeout(300)
        low = await pg.evaluate("() => +document.querySelector('#metroPillBpm').textContent")
        print('pill bpm', b0, mid, low, 'panel opened', opened)
        ok(vis and mid > b0 + 5 and low < mid - 5 and not opened, 'Metronome pill: up faster, down slower, no panel opened by the slide')
        await pg.mouse.click(x, y); await pg.wait_for_timeout(500)
        tap = await pg.evaluate("() => !document.querySelector('#panel-metronome').hidden")
        ok(tap, 'Metronome pill: a tap still opens the metronome')
        await pg.evaluate("() => document.querySelector('#panel-metronome [data-close]')?.click()"); await pg.wait_for_timeout(300)
        # ---- recording metronome button
        rm = await pg.evaluate("() => { const b = document.querySelector('#recMetro'); return [b.querySelector('use').getAttribute('href'), getComputedStyle(b).backgroundColor, document.querySelector('#recMetroBpm').textContent, +document.querySelector('#metroPillBpm').textContent]; }")
        print('rec metro', rm)
        ok(rm[0] == '#i-metro' and 'rgb(10, 132, 255)' not in rm[1] and rm[2] == str(rm[3]), 'Recording bar: a quiet metronome button with the tempo')
        await back()
        # ---- goal
        g = await pg.evaluate("() => [...document.querySelectorAll('#goalSel option')].map(o => +o.value)")
        ok(max(g) == 360, f'Daily goal up to 6 hours ({g})')
        # ---- pages: deleted pages go to Deleted pages at once
        await open_(A)
        await pg.evaluate("() => document.querySelector('[data-panel=pages]')?.click()"); await pg.wait_for_timeout(1200)
        await pg.evaluate("() => document.querySelector('#pgSelect').click()"); await pg.wait_for_timeout(200)
        await pg.evaluate("() => { const t = document.querySelectorAll('#pageGrid .pthumb'); t[2].click(); t[3].click(); }"); await pg.wait_for_timeout(200)
        n0 = await pg.evaluate("() => document.querySelectorAll('#pageGrid .pthumb').length")
        await pg.evaluate("() => document.querySelector('#pgDelete').click()"); await pg.wait_for_timeout(450)
        now = await pg.evaluate("() => [document.querySelector('#pgTrash').hidden, document.querySelectorAll('#pgTrashGrid .pthumb').length, document.querySelectorAll('#pageGrid .pthumb').length, document.querySelectorAll('.pg-fly').length]")
        await pg.wait_for_timeout(1800)
        after = await pg.evaluate("async () => { const { db } = await import('/js/db.js'); const s = (await db.all('scores')).find(x => x.pageMap); return [document.querySelectorAll('#pgTrashGrid .pthumb').length, s ? s.pageMap.length : null, document.querySelectorAll('.pg-fly').length]; }")
        print('pages now', now, 'after', after)
        ok(now[0] is False and now[1] == 2 and now[2] == n0 - 2 and now[3] == 2 and after[0] == 2 and after[1] == n0 - 2 and after[2] == 0, 'Pages: the deleted pages drop to Deleted pages at once, and are saved')
        await pg.evaluate("() => document.querySelector('#pgRestoreAll').click()"); await pg.wait_for_timeout(300)
        await pg.evaluate("() => document.querySelector('#panel-pages [data-close]')?.click()"); await pg.wait_for_timeout(1500)
        # ---- title typed then Back straight away
        await pg.evaluate("() => document.querySelector('#score [data-panel=settings]').click()"); await pg.wait_for_timeout(400)
        await pg.evaluate("() => { const i = document.querySelector('#metaTitle'); i.value = 'Typed then back'; i.dispatchEvent(new Event('input')); }")
        await pg.evaluate("() => document.querySelector('#backBtn').click()"); await pg.wait_for_timeout(900)
        await pg.reload(); await pg.wait_for_timeout(2000)
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 2", timeout=30000)
        tt = await pg.evaluate("() => [...document.querySelectorAll('#grid .card:not(.folder) .ttl')].map(x => x.textContent)")
        ok('Typed then back' in tt and B in tt, f'A title typed and then Back at once is kept, the other score untouched ({tt})')
        # opening the other score and leaving it does not give it the first one's name
        await open_(B); await back(); await pg.reload(); await pg.wait_for_timeout(2000)
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 2", timeout=30000)
        tt2 = await pg.evaluate("() => [...document.querySelectorAll('#grid .card:not(.folder) .ttl')].map(x => x.textContent)")
        ok(sorted(tt2) == sorted(tt), f'other scores keep their names ({tt2})')
        # ---- tuner: the lines keep their height
        await pg.evaluate("() => document.querySelector('[data-panel=tuner]')?.click()"); await pg.wait_for_timeout(500)
        await pg.evaluate("() => document.querySelector('#tunerTabs button[data-tab=tune]').click()"); await pg.wait_for_timeout(300)
        h = await pg.evaluate("""async () => { const sleep = (ms) => new Promise(r => setTimeout(r, ms)); const t = document.querySelector('#tendText');
          t.textContent = 'Tendency: high by 12 cents. 60% of notes high, 10% low. And a few more words so that it surely takes two lines here, even on a wide screen, two lines or even three lines of words.'; await sleep(200); const h1 = t.offsetHeight;
          t.textContent = 'Play a few notes.'; await sleep(200); return [h1, t.offsetHeight]; }""")
        ok(h[1] >= h[0], f'Tuner: a shorter line keeps the height, nothing jumps ({h})')
        await pg.evaluate("() => document.querySelector('#panel-tuner [data-close]')?.click()"); await pg.wait_for_timeout(300)
        await back()
        # ---- Compose: words under the staff (as Capture writes them)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); const E = await import('/js/compose/editor.js'); const M = await import('/js/compose/model.js'); const C = window.__compose, T = window.__composeTest; " + js + " }")
        await J("await E.createComposition({ title: 'Words', insts: ['cello'], time: [4, 4], bars: 4 }); await sleep(900);")
        r = await J("""const st = M.allStaves(C.score)[0]; const ev = st.bars[0][0]; ev.rest = false; ev.notes = ev.notes && ev.notes.length ? ev.notes : [{ s: 0, a: 0 }];
          const ev2 = st.bars[1][0]; if (ev2) { ev2.rest = false; ev2.notes = ev2.notes && ev2.notes.length ? ev2.notes : [{ s: 1, a: 0 }]; }
          ev.txt = 'sonore'; ev.txtBelow = true; ev.txtStyle = 'expr'; window.__composeRelayout(); await sleep(300);
          const hits = C.hits.flatMap(h => (h && h.marks) || []).filter(h => h.kind === 'txt'); return { n: hits.length, id: ev.id, hit: hits[0] || null, ev2: ev2 ? ev2.id : null };""")
        ok(r['n'] >= 1, f'Compose: words under the staff can be tapped ({r["n"]})')
        r2 = await J(f"""C.markSel = {{ id: {json.dumps(r['id'])}, kind: 'txt', name: 'sonore', page: 0 }}; T.syncSelBar(); await sleep(100);
          const bs = [...document.querySelectorAll('#cpSel button, .cp-sel-more button')]; const names = bs.map(b => b.textContent.trim());
          bs.find(b => b.textContent.trim() === '▶').click(); await sleep(150);
          const st = M.allStaves(C.score)[0]; const a = st.bars[0][0].txt || null, b2 = (st.bars[1][0] || {{}}).txt || null, below = !!(st.bars[1][0] || {{}}).txtBelow;
          [...document.querySelectorAll('#cpSel button, .cp-sel-more button')].find(b => b.textContent.trim() === 'Above').click(); await sleep(150);
          const below2 = !!st.bars[1][0].txtBelow;
          [...document.querySelectorAll('#cpSel button, .cp-sel-more button')].find(b => b.textContent.trim() === 'Delete').click(); await sleep(150);
          const gone = !st.bars[1][0].txt;
          document.querySelector('#cpPalUndo').click(); await sleep(100);
          return {{ names, a, b2, below, below2, gone, back: M.allStaves(C.score)[0].bars[1][0].txt }};""")
        print('words', r2)
        ok(r2['a'] is None and r2['b2'] == 'sonore' and r2['below'] and not r2['below2'] and r2['gone'] and r2['back'] == 'sonore', 'Compose: words moved to the next note, put above, deleted, and undone')
        print(errs[:3])
        ok(not errs, 'no page errors')
        print('PASS' if all(res) else 'FAIL', 'small corrections 2 Nov')
        await b.close()
asyncio.run(main())
