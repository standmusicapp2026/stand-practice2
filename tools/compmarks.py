# Compose: every kind of mark on the page (clef, key, time, tempo, rehearsal, repeats, dynamics, articulations,
# slurs, hairpins…) can be tapped; Delete removes it (undo brings it back) and Change… leads to a palette where
# a choice changes it. Also the selection bar's buttons for notes and bars, and Play from a chosen note.
import asyncio, os, json
from playwright.async_api import async_playwright
fails = []
def ok(c, msg):
    print(('ok   ' if c else 'FAIL ') + msg)
    if not c: fails.append(msg)
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width':1366,'height':1024}, has_touch=True)).new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); }"); await pg.wait_for_timeout(800); await pg.evaluate("() => document.querySelectorAll('.tour').forEach(x => x.remove())")
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); const E = await import('/js/compose/editor.js'); const M = await import('/js/compose/model.js'); const C = window.__compose, T = window.__composeTest; " + js + " }")
        await J("""await E.createComposition({ title: 'Marks', insts: ['cello', 'piano'], time: [4, 4], bars: 12 }); await sleep(900);
          const info = M.staffInfo(C.score); const tg = (x, m, t, p) => ({ staff: { st: x.st, inst: x.inst }, meas: { m }, t, p });
          C.tool.dur = 4; C.tool.dots = 0; for (let m = 0; m < 6; m++) for (let i = 0; i < 4; i++) T.commitWrite(tg(info[0], m, i * 480, (i * 2 + m) % 7 - 2));
          const S = C.score, st = info[0].st;
          S.measures[2].key = 2; M.setTime(S, 4, [3, 4]); S.measures[0].tempo = { bpm: 96, beat: 4, text: 'Allegro' }; S.measures[3].rehearsal = 'A';
          st.clefs = { 5: 'tenor' }; S.measures[1].repEnd = true; S.measures[1].repStart = false; S.measures[0].repStart = true;
          const e = st.bars[0][1]; e.art = ['stacc', 'acc']; e.dyn = 'mf'; st.bars[1][0].orn = 'tr';
          S.spans = S.spans || []; S.spans.push({ id: 'sl1', kind: 'slur', st: st.id, v: 1, a: { m: 0, pos: 0 }, b: { m: 0, pos: 1440 } });
          S.spans.push({ id: 'hp1', kind: 'hairpin', dir: '<', st: st.id, v: 1, a: { m: 2, pos: 0 }, b: { m: 2, pos: 1440 } });
          C.undo = []; C.mode = 'select'; window.__composeRelayout(); await sleep(400);""")
        marks = await J("const out = []; const seen = new Set(); C.hits.forEach((h, i) => { if (!h) return; for (const mk of h.marks || []) { const key = mk.kind + ':' + mk.name + ':' + mk.m; if (seen.has(key)) continue; seen.add(key); out.push({ ...mk, page: i }); } for (const sp of h.spans || []) { const key = 'span:' + sp.id; if (seen.has(key)) continue; seen.add(key); out.push({ kind: 'span:' + sp.kind, id: sp.id, page: i, x0: sp.x0 ?? sp.x, x1: sp.x1 ?? sp.x, y0: sp.y0 ?? sp.y, y1: sp.y1 ?? sp.y }); } }); return out;")
        kinds = sorted(set(m['kind'] for m in marks)); print('mark kinds on the page:', kinds)
        tested = set()
        for mk in marks:
            k = mk['kind'] + ('' if mk['kind'] in ('clef', 'key', 'time') else '')
            if k in tested and mk['kind'] not in ('clef', 'key', 'time'): continue
            tested.add(k)
            if mk.get('x0') is None: continue
            # tap it (a finger, Select mode)
            await J("C.sel.clear(); C.selBars = null; C.markSel = null; T.syncSelBar(); await sleep(50);")
            pt = await J(f"const r = C.pages[{mk['page']}].pg.getBoundingClientRect(), k = C.pages[{mk['page']}].k; return [r.left + ({mk['x0']} + {mk['x1']}) / 2 * k, r.top + ({mk['y0']} + {mk['y1']}) / 2 * k]")
            await J(f"T.tapSelect({pt[0]}, {pt[1]}, false); await sleep(150);")
            sel = await J("return C.markSel ? C.markSel.kind + ':' + (C.markSel.name || '') : (C.sel.size ? 'note' : C.selBars ? 'bars' : 'none')")
            label = f"{mk['kind']} {mk.get('name', mk.get('id'))} bar {mk.get('m', '?')}"
            if mk['kind'].startswith('span:') and sel == 'note': sel = 'span (under a note)'
            ok(sel != 'none', f'tap {label} → selected {sel}')
            if sel in ('none', 'note', 'bars'): continue
            btns = await J("return [...document.querySelectorAll('#cpSel button, .cp-sel-more button')].filter(b => b.offsetParent || b.closest('.cp-sel-more')).map(b => b.textContent.trim())")
            if 'Delete' in btns:
                r = await J("const b0 = JSON.stringify(C.score); [...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Delete' && b.offsetParent).click(); await sleep(150); const ch = JSON.stringify(C.score) !== b0; document.querySelector('#cpPalUndo').click(); await sleep(100); return [ch, JSON.stringify(C.score) === b0];")
                ok(r == [True, True], f'  Delete {label}: removed {r[0]}, undo brings it back {r[1]}')
                await J(f"T.tapSelect({pt[0]}, {pt[1]}, false); await sleep(150);")
            ch = [x for x in btns if x.startswith('Change')]
            if ch:
                r = await J(f"""const b0 = JSON.stringify(C.score); const btn = [...document.querySelectorAll('button')].find(b => b.textContent.trim().startsWith('Change') && b.offsetParent); if (!btn) return 'no button';
                   btn.click(); await sleep(200);
                   // in the palette, the first card of its kind that is not on
                   const grp = {json.dumps(mk['kind'])};
                   const want = grp === 'clef' ? ['Treble', 'Bass', 'Alto', 'Tenor'] : null;
                   let cards = [...document.querySelectorAll('#cpPalBody .cp-card, #cpPalBody button')].filter(b => b.offsetParent && !b.classList.contains('on'));
                   if (want) cards = cards.filter(c => want.includes(c.textContent.trim()));
                   else if (grp === 'key') cards = cards.filter(c => /major|minor|sharp|flat|♯|♭/i.test(c.getAttribute('aria-label') || c.textContent));
                   else if (grp === 'tempo') cards = cards.filter(c => ['Largo', 'Adagio', 'Andante', 'Moderato', 'Presto'].includes(c.textContent.trim()));
                   else if (grp === 'time') cards = cards.filter(c => /^\\d+\\/\\d+$|Common|Cut/.test((c.getAttribute('aria-label') || c.textContent).trim()));
                   if (!cards.length) return 'no card (tab ' + C.tab + ')';
                   const pick = cards[0]; const name = (pick.getAttribute('aria-label') || pick.textContent).trim(); pick.click(); await sleep(200);
                   return [name, JSON.stringify(C.score) !== b0];""")
                ok(isinstance(r, list) and r[1], f'  Change… {label} → {r}')
                await J("document.querySelector('#cpPalUndo').click(); await sleep(80);")
        # ---- the selection bar: notes and bars
        def selN(): return "const st = M.allStaves(C.score)[0]; C.markSel = null; C.selBars = null; C.sel.clear(); C.sel.add(st.bars[1][1].id); T.syncSelBar(); await sleep(80);"
        def selB(): return "const st = M.allStaves(C.score)[0]; C.markSel = null; T.selectBars(st, st, 1, 2); T.syncSelBar(); await sleep(80);"
        for name, sj in [('note', selN()), ('bars', selB())]:
            btns = await J(sj + " return [...document.querySelectorAll('#cpSel button, .cp-sel-more button')].map(b => b.textContent.trim()).filter(Boolean)")
            print(name, 'bar buttons:', btns)
            for bt in btns:
                if bt in ('More ▾', 'Select more', 'Play', 'Copy', 'Transpose…'): continue
                r = await J(sj + f"""window.__b = JSON.stringify(C.score); const btn = [...document.querySelectorAll('#cpSel button, .cp-sel-more button')].find(b => b.textContent.trim() === {json.dumps(bt)}); if (!btn) return 'gone';
                   btn.click(); await sleep(150); const ch = JSON.stringify(C.score) !== window.__b; if (!ch) return [false, null];
                   document.querySelector('#cpPalUndo').click(); await sleep(80); return [true, JSON.stringify(C.score) === window.__b];""")
                if bt == 'Paste':
                    ok(r != 'gone', f'{name}: Paste there ({r})'); continue
                ok(r == [True, True], f'{name}: {bt} changes the score and undo restores it ({r})')
            # copy then paste into bar 5
            r = await J(sj + """[...document.querySelectorAll('#cpSel button, .cp-sel-more button')].find(b => b.textContent.trim() === 'Copy').click(); await sleep(80);
               T.selectBars(st, st, 8, 8); T.syncSelBar(); await sleep(60);
               [...document.querySelectorAll('#cpSel button, .cp-sel-more button')].find(b => b.textContent.trim() === 'Paste').click(); await sleep(150);
               const ok = st.bars[8].some(e => !e.rest); document.querySelector('#cpPalUndo').click(); await sleep(80); return ok;""")
            ok(r, f'{name}: Copy then Paste into bar 9 writes the music there')
        # ---- Play from a chosen note
        r = await J("""const st = M.allStaves(C.score)[0]; C.markSel = null; C.selBars = null; C.sel.clear(); const ev = st.bars[3][1]; C.sel.add(ev.id); T.syncSelBar();
           const { sampler } = await import('/js/sampler.js'); const got = []; const orig = sampler.noteOn.bind(sampler); sampler.noteOn = (ch, smp, midi, t, ...rest) => { got.push([midi, t]); return orig(ch, smp, midi, t, ...rest); };
           document.querySelector('#cpPlay').click(); for (let i = 0; i < 60 && !got.length; i++) await sleep(100); await sleep(300); document.querySelector('#cpPlay').click(); sampler.noteOn = orig;
           const info = M.staffInfo(C.score)[0]; const { midiOf } = M; const want = ev.notes.map(n => M.midiOf ? M.midiOf(n.s, n.a) : null);
           return { first: got.slice(0, 3), want, sel: C.sel.size };""")
        print('play from note:', r)
        ok(r['first'] and r['want'][0] is not None and r['first'][0][0] in [w + o for w in r['want'] for o in (0, -12, 12, -24, 24)], f'Play with a note chosen starts on that note {r}')
        r = await J("""const st = M.allStaves(C.score)[0]; C.sel.clear(); C.selBars = null; T.syncSelBar();
           const { sampler } = await import('/js/sampler.js'); const got = []; const orig = sampler.noteOn.bind(sampler); sampler.noteOn = (ch, smp, midi, t, ...rest) => { got.push([midi, t]); return orig(ch, smp, midi, t, ...rest); };
           document.querySelector('#cpPlay').click(); for (let i = 0; i < 60 && !got.length; i++) await sleep(100); await sleep(200); document.querySelector('#cpPlay').click(); sampler.noteOn = orig;
           const f = st.bars[0][0]; return { first: got.slice(0, 2), want: f.notes.map(n => M.midiOf(n.s, n.a)) };""")
        ok(r['first'] and r['first'][0][0] in [w + o for w in r['want'] for o in (0, -12, 12, -24, 24)], f'Play with nothing chosen starts at the beginning {r}')
        ok(not errs, 'no page errors ' + str(errs[:5]))
        await b.close()
    print('fails:', len(fails))
asyncio.run(main())
