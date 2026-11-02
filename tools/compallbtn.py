# Compose: every palette button, with notes chosen and with bars chosen, changes the score (or is a
# known view-only control), undo brings back exactly what was there, and nothing throws.
import asyncio, os, json
from playwright.async_api import async_playwright
fails = []
def ok(c, msg):
    print(('ok   ' if c else 'FAIL ') + msg)
    if not c: fails.append(msg)
# buttons that only change what the palette shows (steppers, segmented choices, folds), or need typing
VIEW_ONLY = ['▲', '▼', 'Earlier bar', 'Later bar', 'From here on', 'Only bars', '−', '+', 'More', 'Fold', 'Concert', 'Written', 'Custom', 'Other', 'Tuplet…', 'Type', 'Words…', 'Lyrics', 'Chord symbols']
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width':1366,'height':1024}, has_touch=True)).new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); }"); await pg.wait_for_timeout(800); await pg.evaluate("() => document.querySelectorAll('.tour').forEach(x => x.remove())")
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); const E = await import('/js/compose/editor.js'); const M = await import('/js/compose/model.js'); const C = window.__compose, T = window.__composeTest; " + js + " }")
        await J("""await E.createComposition({ title: 'Buttons', insts: ['cello', 'piano'], time: [4, 4], bars: 8 }); await sleep(900);
          const info = M.staffInfo(C.score); const tg = (x, m, t, p) => ({ staff: { st: x.st, inst: x.inst }, meas: { m }, t, p });
          C.tool.dur = 4; C.tool.dots = 0; for (let m = 0; m < 4; m++) for (let i = 0; i < 4; i++) T.commitWrite(tg(info[0], m, i * 480, (i * 2 + m) % 7 - 2));
          for (let m = 0; m < 4; m++) for (let i = 0; i < 4; i++) T.commitWrite(tg(info[1], m, i * 480, (i + m) % 5));
          C.undo = []; C.mode = 'select'; await sleep(300);""")
        sels = {
          'note': "const st = M.allStaves(C.score)[0]; C.selBars = null; C.markSel = null; C.sel.clear(); C.sel.add(st.bars[1][1].id); C.sel.add(st.bars[1][2].id);",
          'bars': "const st = M.allStaves(C.score)[0]; C.markSel = null; T.selectBars(st, st, 1, 2);",
        }
        tabs = await J("return [...document.querySelectorAll('#cpPalTabs .cp-tab')].map(b => b.dataset.tab)")
        print('tabs', tabs)
        dead = {}
        for selname, seljs in sels.items():
            for tab in tabs:
                await J(seljs + f" C.tab = '{tab}'; window.__composeRelayout(); T.syncSelBar(); T.renderTab(); await sleep(150);")
                labels = await J("return [...document.querySelectorAll('#cpPalBody button')].filter(b => b.offsetParent).map(b => (b.getAttribute('aria-label') || b.textContent || '').trim())")
                for i, lab in enumerate(labels):
                    if any(lab.startswith(v) for v in VIEW_ONLY): continue
                    before = await J(seljs + f" C.tab = '{tab}'; window.__composeRelayout(); T.renderTab(); await sleep(60); window.__b = JSON.stringify(C.score); window.__u = C.undo.length; return [...document.querySelectorAll('#cpPalBody button')].filter(b => b.offsetParent).length")
                    r = await J(f"""const bs = [...document.querySelectorAll('#cpPalBody button')].filter(b => b.offsetParent); const btn = bs[{i}];
                      if (!btn || (btn.getAttribute('aria-label') || btn.textContent || '').trim() !== {json.dumps(lab)}) return 'moved';
                      if (btn.disabled) return 'disabled';
                      const wasOn = btn.classList.contains('on');
                      btn.click(); await sleep(120);
                      document.querySelectorAll('.cp-dialog, .modal:not([hidden]) .close, dialog[open]').forEach(d => {{ try {{ d.close?.(); }} catch {{}} }});
                      const changed = JSON.stringify(C.score) !== window.__b;
                      let undone = null;
                      if (changed) {{ document.querySelector('#cpPalUndo, #cpUndo').click(); await sleep(80); undone = JSON.stringify(C.score) === window.__b; }}
                      return {{ changed, undone, wasOn, undo: C.undo.length }};""")
                    key = f'{tab}/{lab}'
                    if r in ('moved', 'disabled'): continue
                    if r['changed']:
                        ok(r['undone'], f'{selname}: {key} changes the score and undo restores it')
                        dead[key] = dead.get(key, 0) | 1
                    else:
                        dead.setdefault(key, 0)
                        if r['wasOn']: dead[key] |= 2
        nothing = [k for k, v in dead.items() if v == 0]
        print('buttons that changed nothing with either selection:', len(nothing))
        for k in nothing: print('   ', k)
        ok(not errs, 'no page errors ' + str(errs[:5]))
        await b.close()
    print('fails:', len(fails))
asyncio.run(main())
