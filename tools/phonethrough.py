import asyncio
from playwright.async_api import async_playwright
from PIL import Image
OUT = '/home/claude/shots/pt_'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'])
        ctx = await b.new_context(viewport={'width': 393, 'height': 852}, device_scale_factor=2, is_mobile=True, has_touch=True, user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)')
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'ERR_' not in m.text and 'peerjs' not in m.text else None)
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); setTimeout(()=>document.querySelector('.tour-skip')?.click(),300); }"); await pg.wait_for_timeout(800)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
        tiles = await J("return [...document.querySelectorAll('.tile')].filter(t=>t.offsetParent).map(t=>t.dataset.tile)")
        shots = ['home']; await pg.screenshot(path=OUT + 'home.png')
        for t in tiles:
            if not t: continue
            await J(f"document.querySelector('.tile[data-tile=\"{t}\"]').click(); await sleep(900);")
            await pg.screenshot(path=OUT + t + '.png'); shots.append(t)
            await J("document.querySelectorAll('.panel:not([hidden]) [data-close]').forEach(b=>b.click()); await sleep(300); document.querySelectorAll('.panel').forEach(x=>x.hidden=true);")
        await J("document.querySelector('#phScoresBar').click(); await sleep(800);"); await pg.screenshot(path=OUT + 'scores.png'); shots.append('scores')
        ims = [Image.open(OUT + s + '.png').resize((393, 852)) for s in shots]
        for k in range(0, len(ims), 7):
            part = ims[k:k + 7]
            sh = Image.new('RGB', (393 * len(part), 852), 'white')
            for i, im in enumerate(part): sh.paste(im, (i * 393, 0))
            sh.save(OUT + f'sheet{k // 7}.png')
        print(shots, errs[:6]); await b.close()
asyncio.run(main())
