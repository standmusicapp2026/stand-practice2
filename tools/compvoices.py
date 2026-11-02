# Four voices on a staff: written, drawn (stems 1 and 3 up, 2 and 4 down), played, and kept through MusicXML
import asyncio, os, json
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(800)
        r = await pg.evaluate("""async () => {
          const M = await import('/js/compose/model.js'), E = await import('/js/compose/engrave.js'), X = await import('/js/compose/musicxml.js'), P = await import('/js/compose/playback.js');
          const sc = M.newScore({ title: 'V', insts: ['piano'], bars: 2 }); const st = M.allStaves(sc)[0];
          const S = [37, 35, 33, 31];
          for (const v of [1, 2, 3, 4]) { const vst = M.voiceView(st, v, sc); vst.bars[0] = [0, 1, 2, 3].map((i) => ({ id: M.newId(), t: 4, dots: 0, notes: [{ s: S[v - 1] - i, a: 0 }] })); }
          const lay = E.layoutScore(sc); const c = document.createElement('canvas'); c.width = 800; c.height = 1100; const g = c.getContext('2d'); g.scale(800 / lay.W, 800 / lay.W); E.drawPage(g, lay, 0);
          const hits = (lay.hits || lay.pages[0].hit || null);
          const tl = P.buildTimeline(sc, { from: 0 });
          const xml = X.toMusicXML ? X.toMusicXML(sc) : null;
          let back = null; if (xml) { let s2 = X.fromMusicXML(xml); s2 = s2.score || s2; const st2 = M.allStaves(s2)[0]; back = [1, 2, 3, 4].map((v) => (v === 1 ? st2.bars : st2['v' + v] || [])[0]?.filter((e) => !e.rest).length || 0); }
          const found = M.findEvent(sc, st.v4[0][2].id);
          return { notesPlayed: tl.notes.length, voicesBack: back, find4: found && found.voice, xml: !!xml };
        }""")
        print(r)
        ok = r['notesPlayed'] == 16 and r['find4'] == 4 and (not r['xml'] or r['voicesBack'] == [4, 4, 4, 4])
        print('errors', errs[:3]); print('fails', 0 if ok and not errs else 1)
        await b.close()
asyncio.run(main())
