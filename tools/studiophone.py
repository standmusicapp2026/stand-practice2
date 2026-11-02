import asyncio, sys
from playwright.async_api import async_playwright
CLIP = sys.argv[1] if len(sys.argv) > 1 else '/home/claude/fixtures/portrait.webm'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        for name, vp in [('port', {'width':390,'height':844}), ('land', {'width':844,'height':390})]:
            ctx = await b.new_context(viewport=vp, device_scale_factor=2, has_touch=True, is_mobile=True,
                user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148')
            pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
            errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1200)
            J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
            await J("document.querySelector('#welGo')?.click(); await sleep(300); document.querySelector('.tour-skip')?.click(); await sleep(200); document.querySelector('.tile[data-tile=\"takes\"]').click(); await sleep(500);")
            await pg.set_input_files('#takeImportFile', CLIP); await pg.wait_for_timeout(5000)
            await J("document.querySelector('#takeList li')?.click(); await sleep(1200);")
            await pg.screenshot(path=f'/home/claude/shots/st_{name}_take.png')
            await J("document.querySelector('#studioBtn').click(); await sleep(2500);")
            await pg.screenshot(path=f'/home/claude/shots/st_{name}.png')
            info = await J("const s=document.querySelector('#studio'); const c=document.querySelector('#stCanvas').getBoundingClientRect(); const st=document.querySelector('#stStage').getBoundingClientRect(); return {scrollH: s.scrollHeight, clientH: s.clientHeight, canvas:[c.left,c.top,c.width,c.height].map(Math.round), stage:[st.left,st.top,st.width,st.height].map(Math.round), ov: getComputedStyle(s).overflowY}")
            print(name, info, errs)
            await J("document.querySelector('#studio').scrollTop = 2000; await sleep(300);")
            await pg.screenshot(path=f'/home/claude/shots/st_{name}_scrolled.png')
            await ctx.close()
        await b.close()
asyncio.run(main())
