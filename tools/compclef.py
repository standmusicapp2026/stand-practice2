# Compose: tap the clef, Change…, pick another clef: the staff's clef changes (also after undo, and on later bars)
import asyncio, os, json
from playwright.async_api import async_playwright
fails = []
def ok(c, msg):
    print(('ok   ' if c else 'FAIL ') + msg)
    if not c: fails.append(msg)
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport=json.loads(os.environ.get('VIEW', '{"width":1366,"height":1024}')), has_touch=True)).new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); }"); await pg.wait_for_timeout(800); await pg.evaluate("() => document.querySelectorAll('.tour').forEach(x => x.remove())")
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); const E = await import('/js/compose/editor.js'); const M = await import('/js/compose/model.js'); const C = window.__compose, T = window.__composeTest; " + js + " }")
        await J("await E.createComposition({ title: 'Clefs', insts: ['viola', 'piano'], time: [4, 4], bars: 8 }); await sleep(1000);")
        async def clefPt(stIndex, m=0):
            return await J(f"""const st = M.allStaves(C.score)[{stIndex}]; for (let i = 0; i < C.hits.length; i++) {{ const h = C.hits[i]; if (!h) continue; const mk = h.marks.find(q => q.kind === 'clef' && q.st === st.id && q.m === {m}); if (mk) {{ const r = C.pages[i].pg.getBoundingClientRect(), k = C.pages[i].k; return [r.left + (mk.x0 + mk.x1) / 2 * k, r.top + (mk.y0 + mk.y1) / 2 * k]; }} }} return null;""")
        async def clefs(): return await J("return M.allStaves(C.score).map(s => M.clefAt(s, 0) + (s.clefs ? JSON.stringify(s.clefs) : ''))")
        async def change(stIndex, name, how='mouse', m=0):
            pt = await clefPt(stIndex, m)
            if not pt: return 'no clef mark on page'
            if how == 'pen':
                await J(f"""const x = {pt[0]}, y = {pt[1]}; const t = document.elementFromPoint(x, y); const o = {{ bubbles: true, cancelable: true, pointerId: 9, pointerType: 'pen', clientX: x, clientY: y, isPrimary: true, buttons: 1, pressure: 0.5 }};
                  t.dispatchEvent(new PointerEvent('pointerdown', o)); await sleep(80); t.dispatchEvent(new PointerEvent('pointerup', {{ ...o, buttons: 0, pressure: 0 }})); t.dispatchEvent(new MouseEvent('click', {{ bubbles: true, clientX: x, clientY: y }}));""")
            elif how == 'touch': await pg.touchscreen.tap(pt[0], pt[1])
            else: await pg.mouse.click(pt[0], pt[1])
            await pg.wait_for_timeout(400)
            btn = pg.locator('button:visible', has_text='Change')
            if await btn.count() == 0: return 'no Change button, markSel=' + json.dumps(await J('return C.markSel || null'))
            if how == 'touch':
                bb = await btn.first.bounding_box(); await pg.touchscreen.tap(bb['x'] + bb['width'] / 2, bb['y'] + bb['height'] / 2)
            else: await btn.first.click()
            await pg.wait_for_timeout(400)
            card = pg.locator('#cpPal .cp-card:visible', has_text=name)
            n = await card.count()
            if n == 0: return 'no card ' + name
            for i in range(n):
                if (await card.nth(i).inner_text()).strip() == name:
                    if how == 'touch':
                        bb = await card.nth(i).bounding_box(); await pg.touchscreen.tap(bb['x'] + bb['width'] / 2, bb['y'] + bb['height'] / 2)
                    else: await card.nth(i).click()
                    break
            await pg.wait_for_timeout(500)
            return 'done'
        print('start', await clefs()); await pg.screenshot(path='/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad/clef0.png')
        r = await change(0, 'Treble'); c = await clefs(); ok(r == 'done' and c[0].startswith('treble'), f'viola alto → treble ({r}) {c}')
        r = await change(0, 'Bass', 'touch'); c = await clefs(); ok(r == 'done' and c[0].startswith('bass'), f'(touch) → bass ({r}) {c}')
        await J("document.querySelector('#cpUndo, #cpPalUndo')?.click(); await sleep(300);"); c = await clefs(); ok(c[0].startswith('treble'), f'undo → treble {c}')
        r = await change(0, 'Alto'); c = await clefs(); ok(r == 'done' and c[0].startswith('alto'), f'after undo → alto ({r}) {c}')
        r = await change(2, 'Tenor'); c = await clefs(); ok(r == 'done' and c[2].startswith('tenor'), f'piano LH → tenor ({r}) {c}')
        # an edit that is rolled back (returns false) must not leave the palette on a stale staff
        await J("T.selectBars(M.allStaves(C.score)[0], M.allStaves(C.score)[0], 2, 2); T.renderTab();")
        await J("C.tab = 'clef'; T.renderTab(); await sleep(200);")
        card = pg.locator('#cpPal .cp-card:visible', has_text='Bass')
        for i in range(await card.count()):
            if (await card.nth(i).inner_text()).strip() == 'Bass': await card.nth(i).click(); break
        await pg.wait_for_timeout(400)
        c = await J("const s = M.allStaves(C.score)[0]; return [M.clefAt(s, 1), M.clefAt(s, 2), M.clefAt(s, 7)]"); ok(c == ['alto', 'bass', 'bass'], f'bar 3 on → bass {c}')
        # the new clef from bar 3 is a mark that can be tapped and changed again
        r = await change(0, 'Treble', m=2); c = await J("const s = M.allStaves(C.score)[0]; return [M.clefAt(s, 1), M.clefAt(s, 2)]"); ok(r == 'done' and c == ['alto', 'treble'], f'mid clef → treble ({r}) {c}')
        for mode in ['write', 'select']:
            await J(f"C.mode = '{mode}'; document.querySelector('[data-mode={mode}]')?.click(); await sleep(200);")
            for how, (a, bname) in [('pen', ('treble', 'Treble')), ('touch', ('bass', 'Bass')), ('mouse', ('alto', 'Alto'))]:
                for sti in [0, 1, 2]:
                    r = await change(sti, bname, how); c = await clefs()
                    ok(r == 'done' and c[sti].startswith(a), f'{mode}/{how} staff {sti} → {a} ({r}) {c}')
        # a clef on the first note of a bar, or one kept as a change in bar 1: the staff's clef still changes
        await J("const s = M.allStaves(C.score)[0]; s.clef = 'alto'; s.clefs = { 0: 'alto' }; const f = s.bars[0][0]; f.clef = 'alto'; window.__composeRelayout(); await sleep(200);")
        r = await change(0, 'Bass'); c = await J("const s = M.allStaves(C.score)[0]; return [M.clefAtPos(C.score, s, 0, 0), M.clefAt(s, 0)]"); ok(r == 'done' and c == ['bass', 'bass'], f'stale bar-1 clefs → bass ({r}) {c}')
        # a staff held from before an undo still takes the change
        await J("const st = M.allStaves(C.score)[0]; T.selectBars(st, st, 0, 0); C.tab = 'clef'; T.renderTab(); await sleep(100); document.querySelector('#cpUndo, #cpPalUndo')?.click(); await sleep(200); C.selBars.st = JSON.parse(JSON.stringify(C.selBars.st)); T.renderTab();")
        cur = (await clefs())[0][:4]; target = 'Tenor'
        card = pg.locator('#cpPal .cp-card:visible', has_text=target)
        for i in range(await card.count()):
            if (await card.nth(i).inner_text()).strip() == target: await card.nth(i).click(); break
        await pg.wait_for_timeout(300); c = await clefs(); ok(c[0].startswith('tenor'), f'detached staff → tenor {c}')
        # after reopening the composition
        await J("const id = C.id; await E.closeComposer?.(); await sleep(300);")
        ok(not errs, 'no page errors ' + str(errs[:3]))
        await b.close()
    print('fails:', len(fails))
asyncio.run(main())
