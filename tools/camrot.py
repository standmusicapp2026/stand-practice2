import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream'])
        ctx = await b.new_context(viewport={'width':390,'height':844}, device_scale_factor=2, has_touch=True, is_mobile=True, permissions=['camera','microphone'],
            user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148')
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => document.querySelector('#welGo')?.click()"); await pg.wait_for_timeout(400)
        # a count-in of 2 bars so there is time to turn
        await pg.evaluate("async () => { const m = await import('/js/main.js').catch(()=>null); }")
        shape = lambda: pg.evaluate("() => { const v=document.querySelector('#camVideo'); const c=document.querySelector('#cam'); const r=c.getBoundingClientRect(); return [v.videoWidth, v.videoHeight, c.hidden, Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height), innerWidth, innerHeight] }")
        await pg.evaluate("() => { window.__startRec && 0; }")
        ok = await pg.evaluate("() => { const b=document.querySelector('[data-rec=\"video\"], #recVideo, .tile[data-tile=\"video\"]'); if (b) { b.click(); return b.id||b.className; } return null }")
        print('button', ok); await pg.wait_for_timeout(int(__import__('os').environ.get('W','2500')))
        print('portrait', await shape())
        await pg.set_viewport_size({'width':844,'height':390}); await pg.wait_for_timeout(1500)
        print('turned', await shape())
        await pg.screenshot(path='/home/claude/shots/camrot.png')
        print(errs); await b.close()
asyncio.run(main())
