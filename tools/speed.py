# How long the things that should be instant take (CPU slowed 4x, roughly an older iPad)
import asyncio, json, time, os
from playwright.async_api import async_playwright
FIX = '/home/claude/fixtures/'
PEN = open('/home/claude/tools/smoke.py').read().split("PEN = '''")[1].split("'''")[0]
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', '--autoplay-policy=no-user-gesture-required'])
        ctx = await b.new_context(viewport={'width': 1366, 'height': 1024}, has_touch=True)
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []
        pg.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
        pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'peerjs' not in m.text and 'ERR_' not in m.text else None)
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); setTimeout(()=>{ document.querySelector('.tour-skip')?.click(); }, 300); }"); await pg.wait_for_timeout(700)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
        await pg.set_input_files('#importInput', [FIX + 'vector8.pdf', FIX + 'scan10.pdf', FIX + 'imslp12.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 3", timeout=90000)
        await pg.wait_for_timeout(int(os.environ.get('SETTLE','6000')))
        cdp = await ctx.new_cdp_session(pg)
        await cdp.send('Emulation.setCPUThrottlingRate', {'rate': int(os.environ.get('CPU', '4'))})
        R = {}
        async def tm(name, act, cond, to=30000):
            t0 = time.time(); await J(act)
            await pg.wait_for_function(cond, timeout=to); R.setdefault(name, []).append(int((time.time() - t0) * 1000))
        art = "document.querySelector('#stage canvas.art') && [...document.querySelectorAll('#stage canvas.art')].every(c=>c.width>10)"
        for k in range(3):
            await tm('open score', f"document.querySelectorAll('#grid .card:not(.folder)')[{k}].click()", art)
            await pg.wait_for_timeout(1500)
            for i in range(4):
                lab = await J("return document.querySelector('#pageLabel').textContent")
                t0 = time.time(); await pg.keyboard.press('ArrowRight')
                await pg.wait_for_function(f"document.querySelector('#pageLabel').textContent !== {json.dumps(lab)} && " + art, timeout=30000)
                R.setdefault('turn (label+art)', []).append(int((time.time() - t0) * 1000))
                await pg.wait_for_timeout(700)
            # sharp page after turning: how long until the full render replaces the quick one
            await tm('ink on', "document.querySelector('#inkBtn').click()", "!document.querySelector('#inkbar').hidden")
            r = await J("const r=document.querySelector('#stage .pg').getBoundingClientRect(); return [r.left,r.top]")
            t0 = time.time(); await pg.evaluate(PEN, [[r[0]+100+i*8, r[1]+250+i*2] for i in range(15)]); R.setdefault('pen stroke (15 moves)', []).append(int((time.time()-t0)*1000))
            r2 = await J(f"const x0={r[0]+100}, y0={r[1]+350}; const t=document.elementFromPoint(x0,y0); const ev=(type,x,y)=>t.dispatchEvent(new PointerEvent(type,{{bubbles:true,cancelable:true,composed:true,pointerId:78,pointerType:'pen',isPrimary:true,clientX:x,clientY:y,pressure:0.5,buttons:type==='pointerup'?0:1}})); ev('pointerdown',x0,y0); const ts=[]; for(let i=1;i<40;i++){{ const a=performance.now(); ev('pointermove',x0+i*6,y0+Math.sin(i/3)*10); ts.push(performance.now()-a); await sleep(8); }} const a=performance.now(); ev('pointerup',x0+240,y0); const up=performance.now()-a; await sleep(100); ts.sort((p,q)=>p-q); return [ts[Math.floor(ts.length/2)].toFixed(1), ts[ts.length-1].toFixed(1), up.toFixed(1)]")
            R.setdefault('pen move handler ms (med,max,up)', []).append(r2)
            await tm('ink off', "document.querySelector('#inkDone').click()", "document.querySelector('#inkbar').hidden")
            await tm('back to library', "document.querySelector('#backBtn').click()", "!document.querySelector('#library').hidden")
            await pg.wait_for_timeout(600)
        for tile in ('metronome', 'tuner'):
            await tm('tool ' + tile, f"document.querySelector('.tile[data-tile=\"{tile}\"]').click()", "[...document.querySelectorAll('.panel, .sheet')].some(x=>!x.hidden && x.getBoundingClientRect().height>50)")
            await J("document.querySelector('.panel:not([hidden]) .close, .sheet:not([hidden]) .close, [data-close]')?.click(); await sleep(300);")
            await pg.keyboard.press('Escape'); await pg.wait_for_timeout(500)
        for k, v in R.items(): print(f'{k:28s} median {sorted(v)[len(v)//2]} ms  max {max(v)}  {v}')
        print('errors', errs[:8]); await b.close()
asyncio.run(main())
