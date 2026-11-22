# Studio on the iPhone held upright: every tool, every part of it, every button and slider pressed;
# Done brings the tools back; nothing overflows sideways; no errors.
import asyncio, base64, os, sys
from playwright.async_api import async_playwright
PORT = os.environ.get('PORT', '8765')
UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1'
SKIP = r'/Remove|Add an image|Add the score|Add a second|Edit what is shown|Tap along from|From the start|From bar|Export|Auto|Looking/'
async def main():
    fails = []
    def check(c, m):
        print(('ok   ' if c else 'FAIL ') + m)
        if not c: fails.append(m)
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        for (w, h) in [(375, 667), (390, 844), (430, 932)]:
            ctx = await b.new_context(viewport={'width': w, 'height': h}, has_touch=True, user_agent=UA)
            pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
            errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1200)
            J = lambda js, a=None: pg.evaluate("async (a) => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }", a)
            await J("document.querySelector('#welGo')?.click(); await sleep(300); document.querySelector('.tour-skip')?.click(); await sleep(200); document.querySelector('.tile[data-tile=\"takes\"]')?.click(); await sleep(500);")
            await pg.set_input_files('#takeImportFile', '/home/claude/fixtures/face_clip.webm'); await pg.wait_for_timeout(5000)
            await J("document.querySelector('#takeList li')?.click(); await sleep(1200); document.querySelector('#studioBtn').click(); await sleep(2500);")
            img = base64.b64encode(open('/home/claude/tc/raw-002.jpg', 'rb').read()).decode()
            await J("""const S = await import('/js/studio.js'); const img = new Image(); img.src = 'data:image/jpeg;base64,' + a; await img.decode();
              const c = document.createElement('canvas'); c.width = 2080; c.height = 620; c.getContext('2d').drawImage(img, -150, -500);
              await S._addScoreFrom(c); await sleep(1500); document.querySelector('#stSheetDone')?.click(); await sleep(300);""", img)
            for tab in ['score', 'timing', 'image', 'frame', 'look']:
                r = await J("""const tb = document.querySelector('#stTabs [data-tab="' + a + '"]'); const vis = tb.getBoundingClientRect().height > 0; tb.click(); await sleep(500);
                  const st = document.querySelector('#studio'), pan = document.querySelector('#stSide').getBoundingClientRect(), stg = document.querySelector('#stStage').getBoundingClientRect();
                  return { vis, open: st.classList.contains('sheet-open'), tabsHidden: document.querySelector('#stTabs').getBoundingClientRect().height === 0, panH: Math.round(pan.height), stageH: Math.round(stg.height), done: !!document.querySelector('#stSheetDone'), parts: [...document.querySelectorAll('.st-subpick button')].map(x => x.textContent) };""", tab)
                check(r['vis'] and r['open'] and r['tabsHidden'] and r['done'] and r['panH'] > 150 and r['stageH'] > 140, f'{w}x{h} {tab}: opens as a sheet with Done, picture still there {r}')
                parts = r['parts'] or [None]
                for part in parts:
                    q = await J("""const SK = """ + SKIP + """; if (a) { const sp = [...document.querySelectorAll('.st-subpick button')].find(x => x.textContent === a); sp.click(); await sleep(300); }
                      let n = 0, wide = 0;
                      for (let round = 0; round < 2; round++) {
                        const btns = [...document.querySelectorAll('#stSide button, #stSide input[type=checkbox]')].filter(x => !x.closest('.st-subpick') && x.id !== 'stSheetDone' && !SK.test(x.textContent) && !x.disabled && x.getBoundingClientRect().height > 0);
                        for (const x of btns) { if (!x.isConnected) continue; x.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true })); x.dispatchEvent(new PointerEvent('pointerup', { bubbles: true })); x.click(); n++; await sleep(60); }
                      }
                      for (const i of [...document.querySelectorAll('#stSide input[type=range]')]) { i.value = (+i.min + +i.max) / 2; i.dispatchEvent(new Event('input', { bubbles: true })); n++; await sleep(40); }
                      for (const x of document.querySelectorAll('#stSide *')) { const r = x.getBoundingClientRect(); if (r.width && r.right > innerWidth + 1) wide++; }
                      return { n, wide, sw: document.documentElement.scrollWidth, open: document.querySelector('#studio').classList.contains('sheet-open') };""", part)
                    check(q['n'] > 0 and q['wide'] == 0 and q['sw'] <= w and q['open'], f'{w}x{h} {tab}/{part}: every control pressed, nothing off the side {q}')
                r = await J("document.querySelector('#stSheetDone').click(); await sleep(400); return { open: document.querySelector('#studio').classList.contains('sheet-open'), tabs: document.querySelector('#stTabs').getBoundingClientRect().height > 0, tl: document.querySelector('.st-timeline').getBoundingClientRect().height > 0 };")
                check(not r['open'] and r['tabs'] and r['tl'], f'{w}x{h} {tab}: Done brings back the tools and the timeline {r}')
            # a bar tapped on the timeline opens Timing at Bar times; tapped again stays open
            r = await J("""const c = document.querySelector('#stScoreRoll .st-bar, #stScoreRoll > *'); const rr = c.getBoundingClientRect();
              const S = await import('/js/studio.js'); S._studio.selBar = null;
              const at = (x, y) => { for (const t of ['pointerdown', 'pointerup']) document.elementFromPoint(x, y).dispatchEvent(new PointerEvent(t, { bubbles: true, clientX: x, clientY: y, pointerId: 7, isPrimary: true, pointerType: 'touch' })); };
              at(rr.left + rr.width / 2, rr.top + rr.height / 2); await sleep(700); const one = { tab: S._studio.tab, part: S._studio.sub && S._studio.sub.timing };
              const c2 = document.querySelector('#stScoreRoll .st-bar, #stScoreRoll > *').getBoundingClientRect(); at(c2.left + c2.width / 2, c2.top + c2.height / 2); await sleep(700);
              return { one, two: S._studio.tab, card: !!document.querySelector('#stBarTime') };""")
            check(r['one']['tab'] == 'timing' and r['one']['part'] == 'bar' and r['two'] == 'timing' and r['card'], f'{w}x{h}: a bar tapped opens its time, tapped again stays {r}')
            await pg.screenshot(path=f'/home/claude/shots/stphoneall_{w}.png')
            check(not errs, f'{w}x{h}: no page errors {errs[:3]}')
            await ctx.close()
        await b.close()
    print(f'{len(fails)} fails'); sys.exit(1 if fails else 0)
asyncio.run(main())
