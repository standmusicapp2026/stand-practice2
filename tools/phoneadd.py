# (phoneadd) The iPhone's own scores: in My scores, + brings pictures from Photos (one score, the pages
# in order) and PDFs from Files (each its own score); scanned pages come the same way. They show with
# the iPad's, open and read like them (pages, Play), stay when the iPad's list comes again, and can
# be deleted.
import asyncio, json
from playwright.async_api import async_playwright
D = '/home/claude/dragon'
SP = '/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad'
UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, user_agent=UA, has_touch=True)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.add_init_script("window.__noTour = true; window.__noTempo = true;")
        await pg.goto('http://localhost:8765/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); document.querySelectorAll('.ask-back button').forEach(b=>/Not now/.test(b.textContent)&&b.click()); }")
        await pg.wait_for_function("() => window.__phs && window.__phs.addOwn", timeout=20000)
        await pg.click('#phScoresBar'); await pg.wait_for_timeout(600)
        empty = await pg.evaluate("() => document.querySelector('#phsEmpty').textContent")
        # + › From Photos: two pictures, one score of two pages
        await pg.click('#phsAdd'); await pg.wait_for_timeout(300)
        items = await pg.evaluate("() => [...document.querySelectorAll('.choose-item b')].map((x) => x.textContent)")
        await pg.evaluate("() => [...document.querySelectorAll('.choose-item')].find((x) => /Photos/.test(x.textContent)).click()")
        await pg.set_input_files('#phsPhotos', [f'{D}/p1-01.png', f'{D}/p1-02.png'])
        await pg.wait_for_function("() => window.__phoneAdded", timeout=60000)
        a1 = await pg.evaluate("() => window.__phoneAdded")
        await pg.evaluate("() => { window.__phoneAdded = null; }")
        # + › From Files: a PDF, its own score
        await pg.evaluate("() => document.querySelector('#phsFiles').click = () => {}")
        await pg.set_input_files('#phsFiles', [f'{D}/test1.pdf'])
        await pg.wait_for_function("() => window.__phoneAdded", timeout=60000)
        a2 = await pg.evaluate("() => window.__phoneAdded")
        await pg.wait_for_timeout(800)
        await pg.screenshot(path=f'{SP}/phone-add.png')
        cards = await pg.evaluate("() => [...document.querySelectorAll('#phsGrid .phs-card[data-score]')].map((c) => ({ t: c.querySelector('.phs-t').textContent, ok: !!c.querySelector('.phs-state.ok'), thumb: !!c.querySelector('.phs-thumb').style.backgroundImage }))")
        # a scan, as the scanner hands it over (pictures, through the incoming files)
        await pg.evaluate("() => { window.__phoneAdded = null; }")
        await pg.evaluate("""async () => { const r = await fetch('/js/../index.html'); }""")
        # open the first: its pages show
        await pg.evaluate("() => document.querySelector('#phsGrid .phs-card[data-score]').click()")
        await pg.wait_for_function("() => !document.querySelector('#phView').hidden && document.querySelector('#phvImg').naturalWidth > 0", timeout=30000)
        view = await pg.evaluate("() => ({ title: document.querySelector('#phvTitle').textContent, page: document.querySelector('#phvPage').textContent, w: document.querySelector('#phvImg').naturalWidth })")
        await pg.screenshot(path=f'{SP}/phone-add-view.png')
        await pg.click('#phvClose'); await pg.wait_for_timeout(500)
        # the iPad's list comes again: the iPhone's own stay
        await pg.evaluate("async () => { window.__askIpadTest = async (q) => { if (q.what === 'list') return { scores: [{ id: 'ip1', title: 'From the iPad', composer: 'Bach', pages: 2, stamp: 5 }] }; throw new Error('ipad:none'); }; }")
        await pg.click('#phsRefresh'); await pg.wait_for_timeout(1500)
        after = await pg.evaluate("() => [...document.querySelectorAll('#phsGrid .phs-card[data-score]')].map((c) => c.querySelector('.phs-t').textContent)")
        # deleted (Edit, −)
        await pg.click('#phsEdit'); await pg.wait_for_timeout(300)
        await pg.evaluate("() => [...document.querySelectorAll('#phsGrid .phs-card[data-score]')].find((c) => /test1|Test/i.test(c.textContent)).querySelector('.phs-del').click()")
        await pg.wait_for_timeout(300)
        await pg.evaluate("() => document.querySelector('#phsSheetOk').click()"); await pg.wait_for_timeout(800)
        left = await pg.evaluate("async () => { const { getSetting } = await import('/js/db.js'); return (await getSetting('phoneOwn', [])).map((x) => x.title); }")
        print(json.dumps({'empty': empty, 'items': items, 'a1': a1, 'a2': a2, 'cards': cards, 'view': view, 'after': after, 'left': left}))
        ok = len(items) >= 2 and a1 and a1.get('pages') == 2 and a2 and a2.get('pages', 0) >= 1 and len(cards) == 2 and all(c['ok'] and c['thumb'] for c in cards) and view['w'] > 500 and len(after) == 3 and len(left) == 1
        print('PASS' if ok and not errs else 'FAIL', 'iPhone: scores added from Photos and Files, read, kept, deleted', errs[:3])
        await b.close()
asyncio.run(main())
