import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width':1180,'height':820}, device_scale_factor=2)).new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1200)
        await pg.evaluate("() => document.querySelector('#welGo')?.click()"); await pg.wait_for_timeout(300)
        await pg.set_input_files('#importInput', ['/home/claude/fixtures/vector8.pdf']); await pg.wait_for_timeout(3000)
        await pg.evaluate("""async () => { const { db } = await import('/js/db.js'); const pcm = new Float32Array(48000); await db.put('files', { id: 'audio:tk', data: pcm }); await db.put('takes', { id: 'tk', kind: 'audio', name: 'Take', created: Date.now(), sr: 48000, dur: 1 });
          window.__shared = []; }""")
        await pg.evaluate("() => { document.querySelector('.tour-skip')?.click(); document.querySelector('[data-panel=\"backup\"]').click(); }"); await pg.wait_for_timeout(800)
        await pg.evaluate("() => { const c = document.querySelector('#bkTakes'); c.checked = true; c.dispatchEvent(new Event('change')); }"); await pg.wait_for_timeout(200)
        # stop downloads: replace anchor click
        await pg.evaluate("() => { HTMLAnchorElement.prototype.click = function () { window.__shared.push(this.download); }; }")
        await pg.evaluate("() => document.querySelector('#bkMake').click()"); await pg.wait_for_timeout(3000)
        await pg.screenshot(path='/home/claude/shots/bk_panel.png')
        print(await pg.evaluate("() => [...document.querySelectorAll('#bkList li')].map(l => l.textContent)"), await pg.evaluate("() => window.__shared"), errs)
        await b.close()
asyncio.run(main())
