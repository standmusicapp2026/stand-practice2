# Errors are noted (once each), a problem report is made with them and the library's size, and the
# "Stand could not start" notice never shows when Stand starts well
import asyncio, os
from playwright.async_api import async_playwright
FIX = '/home/claude/fixtures/'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width': 1366, 'height': 1024}, has_touch=True, accept_downloads=True)
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); setTimeout(() => document.querySelector('.tour-skip')?.click(), 300); }"); await pg.wait_for_timeout(700)
        await pg.set_input_files('#importInput', [FIX + 'vector8.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=60000)
        await pg.evaluate("() => { setTimeout(() => { throw new Error('test boom'); }, 0); setTimeout(() => { throw new Error('test boom'); }, 5); Promise.reject(new Error('test reject')); }")
        await pg.wait_for_timeout(300)
        noted = await pg.evaluate("() => window.__standErrors.map(x => x.line)")
        print('noted', noted)
        await pg.evaluate("() => document.querySelector('[data-panel=app]').click()"); await pg.wait_for_timeout(500)
        async with pg.expect_download() as dl:
            await pg.evaluate("() => document.querySelector('#sendReport').click()")
        d = await dl.value; path = await d.path(); text = open(path).read()
        print(text[:900])
        await pg.wait_for_timeout(20500)
        notice = await pg.evaluate("() => document.body.innerText.includes('Stand could not start')")
        ok = (sum('test boom' in x for x in noted) == 1 and any('test reject' in x for x in noted) and 'Library: 1 scores' in text and 'test boom' in text
              and 'Stand problem report' in text and not notice)
        print('PASS' if ok else 'FAIL', 'errors noted once, report made, no false start notice'); print([e for e in errs if 'test ' not in e][:3])
        await b.close()
asyncio.run(main())
