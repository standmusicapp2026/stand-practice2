# No internet (a concert hall, a plane): Stand starts, opens scores, writes, and the online search says
# plainly that there is no connection (no error, nothing stuck)
import asyncio, os
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width': 1180, 'height': 820}, has_touch=True)
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        base = 'http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'
        await pg.goto(base); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); setTimeout(() => document.querySelector('.tour-skip')?.click(), 300); }"); await pg.wait_for_timeout(700)
        await pg.set_input_files('#importInput', ['/home/claude/fixtures/vector8.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=60000)
        # everything outside Stand itself is cut off
        await pg.route('**/*', lambda r: r.abort() if not r.request.url.startswith(base.rsplit('/', 1)[0]) else r.continue_())
        await pg.evaluate("() => { document.querySelector('[data-goto=find]')?.click(); }"); await pg.wait_for_timeout(500)
        await pg.fill('#findInput', 'Elgar cello concerto'); await pg.press('#findInput', 'Enter')
        await pg.wait_for_timeout(15000)
        st = await pg.evaluate("() => [document.querySelector('#findStatus').hidden ? '' : document.querySelector('#findStatus').textContent, document.querySelector('#toast').hidden ? '' : document.querySelector('#toast').textContent, document.querySelectorAll('#findList .work, #findList li, #findList .wk').length]")
        print('search offline:', st)
        await pg.evaluate("() => document.querySelector('[data-goto=mine]')?.click()"); await pg.wait_for_timeout(400)
        await pg.evaluate("() => document.querySelector('#grid .card:not(.folder)').click()"); await pg.wait_for_timeout(2500)
        opened = await pg.evaluate("() => !document.querySelector('#score').hidden && [...document.querySelectorAll('#stage canvas.art')].some(c => c.width > 10)")
        said = (st[0] + ' ' + st[1]).lower()
        ok = opened and ('connect' in said or 'internet' in said or 'offline' in said or 'network' in said) and not errs
        print('opened', opened, 'errors', errs[:3])
        print('PASS' if ok else 'FAIL', 'offline: scores work, the online search says there is no connection')
        await b.close()
asyncio.run(main())
