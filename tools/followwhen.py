import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'])
        ctx = await b.new_context(viewport={'width': 1366, 'height': 1024}, has_touch=True)
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); setTimeout(()=>document.querySelector('.tour-skip')?.click(),300); }"); await pg.wait_for_timeout(700)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
        await pg.set_input_files('#importInput', ['/home/claude/fixtures/vector8.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=60000)
        await J("document.querySelector('#grid .card:not(.folder)').click(); await sleep(2500);")
        r = await J("""const b=document.querySelector('[data-panel=listen]'); if (b && b.offsetParent) b.click(); else document.querySelector('#panel-listen').hidden=false; await sleep(600);
          const on=document.querySelector('#followOn'); const vis0 = !document.querySelector('#followBody').hidden;
          if (!on.checked) { on.click(); await sleep(800); }
          const r=document.querySelector('#followAt');
          const out={vis0, vis1: !document.querySelector('#followBody').hidden, v: r.value, hint: document.querySelector('#followWhenHint').textContent, mark: document.querySelector('#followAtMark').style.left};
          r.value = 100; r.dispatchEvent(new Event('input')); await sleep(400);
          out.after = r.value; out.hint2=document.querySelector('#followWhenHint').textContent; out.mark2=document.querySelector('#followAtMark').style.left; return out;""")
        print(r)
        await J("document.querySelectorAll('.panel').forEach(p=>p.hidden=true); const e=document.querySelector('#followAt'); e.closest('.panel').hidden=false; e.scrollIntoView({block:'center'}); await sleep(400)"); await pg.locator('#followBody').screenshot(path='/home/claude/shots/followwhen.png')
        await pg.wait_for_timeout(800); await pg.reload(); await pg.wait_for_timeout(2500)
        r2 = await J("const b=document.querySelector('#grid .card:not(.folder)'); b && b.click(); await sleep(2500); const x=document.querySelector('[data-panel=listen]'); if (x && x.offsetParent) x.click(); else document.querySelector('#panel-listen').hidden=false; await sleep(600); return document.querySelector('#followAt').value")
        print('after reload', r2, 'errors', errs); await b.close()
asyncio.run(main())
