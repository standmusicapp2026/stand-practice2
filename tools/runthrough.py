# A walk through every panel on a score, for a look at how they sit together; a contact sheet
import asyncio, json, sys
from playwright.async_api import async_playwright
from PIL import Image
OUT = '/home/claude/shots/rt_'
PANELS = ['metronome', 'tuner', 'pomodoro', 'scales', 'record', 'takes', 'reps', 'passages', 'study', 'goal', 'app', 'backup', 'listen', 'pages', 'exportpdf', 'settings', 'compose']
async def main():
    dark = 'dark' in sys.argv
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'])
        ctx = await b.new_context(viewport={'width': 1366, 'height': 1024}, has_touch=True, color_scheme='dark' if dark else 'light')
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'ERR_' not in m.text and 'peerjs' not in m.text else None)
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); setTimeout(()=>document.querySelector('.tour-skip')?.click(),300); }"); await pg.wait_for_timeout(700)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
        await pg.set_input_files('#importInput', ['/home/claude/fixtures/vector8.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=60000)
        await pg.screenshot(path=OUT + 'library.png')
        await J("document.querySelector('#grid .card:not(.folder)').click(); await sleep(2500);")
        shots = ['library']
        for name in PANELS:
            ok = await J(f"""const b = document.querySelector('#score [data-panel="{name}"]') || document.querySelector('[data-panel="{name}"]');
              if (b && b.offsetParent) {{ b.click(); }} else {{ const p = document.querySelector('#panel-{name}'); if (!p) return false; p.hidden = false; }}
              await sleep(700); return !document.querySelector('#panel-{name}').hidden""")
            await pg.screenshot(path=OUT + name + '.png'); shots.append(name)
            await J(f"const p=document.querySelector('#panel-{name}'); p.querySelector('[data-close]')?.click(); await sleep(300); p.hidden = true; document.querySelectorAll('.panel').forEach(x=>x.hidden=true);")
            await pg.keyboard.press('Escape')
        await J("document.querySelector('#inkBtn').click(); await sleep(500);")
        for tool in ['pen', 'stamp', 'eraser', 'print']:
            await J(f"document.querySelector('.ink-tool[data-tool=\"{tool}\"]').click(); await sleep(200); document.querySelector('.ink-tool[data-tool=\"{tool}\"]').click(); await sleep(400);")
            await pg.screenshot(path=OUT + 'ink_' + tool + '.png'); shots.append('ink_' + tool)
            await J("document.querySelectorAll('.ink-pop').forEach(x=>x.hidden=true);")
        await J("document.querySelector('#layerBtn').click(); await sleep(300);"); await pg.screenshot(path=OUT + 'ink_layers.png'); shots.append('ink_layers')
        # contact sheet
        ims = [Image.open(OUT + s + '.png').resize((683, 512)) for s in shots]
        cols = 4; rows = (len(ims) + cols - 1) // cols
        for k in range(0, len(ims), 8):
            part = ims[k:k + 8]; r = (len(part) + 3) // 4
            sheet = Image.new('RGB', (683 * 4, 512 * r), 'white')
            for i, im in enumerate(part): sheet.paste(im, ((i % 4) * 683, (i // 4) * 512))
            sheet.save(OUT + ('dark_' if dark else '') + f'sheet{k // 8}.png')
        print(shots); print('errors', errs[:8]); await b.close()
asyncio.run(main())
