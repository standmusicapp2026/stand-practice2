# The QA robot: uses Stand as a person would (taps, the Pencil, two fingers), on an iPad-sized screen,
# through whole journeys and then at random; after every step: how long it took, slow work, dropped
# frames, errors, memory, and anything odd on screen. Writes a report (JSON + screenshots).
#   python3 qa.py [--seed N] [--random N] [--only name,name] [--portrait] [--phone]
import asyncio, json, os, sys, time, random, base64
from playwright.async_api import async_playwright
ARGS = sys.argv[1:]
def arg(name, default=None):
    return ARGS[ARGS.index(name) + 1] if name in ARGS else default
SEED = int(arg('--seed', '1')); RANDOM_STEPS = int(arg('--random', '120')); ONLY = arg('--only'); OUT = arg('--out', '/home/claude/qa_out')
PORT = os.environ.get('PORT', '8765'); BASE = f'http://localhost:{PORT}/index.html'
FIX = '/home/claude/fixtures'
os.makedirs(OUT, exist_ok=True)
VIEW = {'width': 820, 'height': 1180} if '--portrait' in ARGS else {'width': 390, 'height': 844} if '--phone' in ARGS else {'width': 1180, 'height': 820}
UA = ('Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148' if '--phone' in ARGS
      else 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15')
steps = []   # every step and what was seen
R = random.Random(SEED)

class Robot:
    def __init__(self, pg, cdp): self.pg = pg; self.cdp = cdp; self.n = 0; self.scenario = ''
    async def step(self, name, fn, budget=1500):
        pg = self.pg; self.n += 1
        await pg.evaluate('(n) => { window.__qa.step = n; }', f'{self.scenario}:{name}')
        e0 = await pg.evaluate('() => [window.__qa.errors.length, window.__qa.long.length, window.__qa.frames.length]')
        t0 = time.time(); ok = True; why = ''
        try:
            await pg.evaluate('() => { window.__qa.actT = performance.now(); window.__qa.firstChange = null; }')
            await fn()
            settle = await pg.evaluate('() => window.__qa.settle()')
            first = await pg.evaluate('() => window.__qa.firstChange')
        except Exception as ex:
            ok = False; why = str(ex).split('\n')[0][:200]; first = None
        ms = round((time.time() - t0) * 1000)
        info = await pg.evaluate('(e0) => { const Q = window.__qa; return { errors: Q.errors.slice(e0[0]), long: Q.long.slice(e0[1]).map((q) => q.d), frames: Q.frames.slice(e0[2]).map((q) => q.d), mem: Q.mem(), issues: Q.check() }; }', e0)
        rec = {'n': self.n, 'scenario': self.scenario, 'step': name, 'ok': ok, 'why': why, 'ms': ms, 'firstChange': first, 'longMs': sum(info['long']), 'longest': max(info['long'] or [0]), 'maxFrameGap': max(info['frames'] or [0]),
               'errors': info['errors'], 'issues': info['issues'], 'mem': info['mem']}
        # (slow: the screen took long to answer the touch, or the page's work stopped it for a moment)
        bad = (not ok) or info['errors'] or info['issues'] or rec['longest'] > 300 or (first is not None and first > budget)
        if bad:
            path = f'{OUT}/s{self.n:04d}.png'; await pg.screenshot(path=path); rec['shot'] = os.path.basename(path)
        steps.append(rec)
        flag = '!!' if (not ok or info['errors']) else ' ~' if bad else '  '
        print(f"{flag} {self.n:4d} {self.scenario[:10]:10s} {name[:44]:44s} {ms:5d}ms first {first if first is not None else '-':>5} long {rec['longest']:4d} gap {rec['maxFrameGap']:4d} mem {rec['mem']}" + (f"  ERR {info['errors'][0]['msg'][:90]}" if info['errors'] else '') + (f"  ISSUE {info['issues'][0]}" if info['issues'] else '') + (f'  FAIL {why}' if not ok else ''), flush=True)
        return ok
    # ---- ways of touching
    async def center(self, sel):
        b = await self.pg.locator(sel).first.bounding_box()
        if not b: raise Exception('not on screen: ' + sel)
        return b['x'] + b['width'] / 2, b['y'] + b['height'] / 2
    async def tap(self, sel):
        x, y = await self.center(sel); await self.pg.touchscreen.tap(x, y)
    async def tapxy(self, x, y): await self.pg.touchscreen.tap(x, y)
    async def visible(self, sel):
        try: return await self.pg.locator(sel).first.is_visible()
        except Exception: return False
    async def pen(self, pts, pressure=0.5):
        # the Apple Pencil: real pen events through the browser's input (pointerType pen)
        x0, y0 = pts[0]
        await self.cdp.send('Input.dispatchMouseEvent', {'type': 'mousePressed', 'x': x0, 'y': y0, 'button': 'left', 'buttons': 1, 'clickCount': 1, 'pointerType': 'pen', 'force': pressure})
        for (x, y) in pts[1:]:
            await self.cdp.send('Input.dispatchMouseEvent', {'type': 'mouseMoved', 'x': x, 'y': y, 'button': 'left', 'buttons': 1, 'pointerType': 'pen', 'force': pressure})
        xe, ye = pts[-1]
        await self.cdp.send('Input.dispatchMouseEvent', {'type': 'mouseReleased', 'x': xe, 'y': ye, 'button': 'left', 'buttons': 0, 'clickCount': 1, 'pointerType': 'pen'})
    async def swipe(self, x0, y0, x1, y1, n=8):
        await self.cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x0, 'y': y0}]})
        for i in range(1, n + 1):
            await self.cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x0 + (x1 - x0) * i / n, 'y': y0 + (y1 - y0) * i / n}]})
            await asyncio.sleep(0.012)
        await self.cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
    async def pinch(self, cx, cy, d0, d1, n=8):
        pts = lambda d: [{'x': cx - d / 2, 'y': cy, 'id': 1}, {'x': cx + d / 2, 'y': cy, 'id': 2}]
        await self.cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': pts(d0)})
        for i in range(1, n + 1):
            await self.cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': pts(d0 + (d1 - d0) * i / n)}); await asyncio.sleep(0.016)
        await self.cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})

# ---------------- journeys ----------------
async def j_library(r):
    r.scenario = 'library'
    pg = r.pg
    await r.step('import three scores', lambda: pg.set_input_files('#importInput', [f'{FIX}/vector8.pdf', f'{FIX}/scan10.pdf', f'{FIX}/imslp12.pdf']), budget=20000)
    await r.step('wait for the three cards', lambda: pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 3", timeout=90000), budget=90000)
    await r.step('search', lambda: pg.fill('#searchInput', 'bach'))
    await r.step('clear search', lambda: pg.fill('#searchInput', ''))
    await r.step('select (hold) then drag a score', lambda: hold_drag(r))
    if await r.visible('#libEdit'): await r.step('done selecting', lambda: r.tap('#libEdit'))

async def hold_drag(r):
    x, y = await r.center('#grid .card:not(.folder)')
    await r.cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y}]})
    await asyncio.sleep(0.75)
    for i in range(1, 9):
        await r.cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x + i * 12, 'y': y + i * 8}]}); await asyncio.sleep(0.02)
    await r.cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})

async def j_reading(r, which=0):
    r.scenario = f'read{which}'
    pg = r.pg; W, H = VIEW['width'], VIEW['height']
    await r.step('open a score', lambda: r.tap(f'#grid .card:not(.folder) >> nth={which}'), budget=2500)
    for i in range(10): await r.step(f'tap right to turn ({i + 1})', lambda: r.tapxy(W * 0.93, H * 0.5), budget=800)
    for i in range(4): await r.step(f'swipe back ({i + 1})', lambda: r.swipe(W * 0.7, H * 0.5, W * 0.2, H * 0.52) if False else r.swipe(W * 0.2, H * 0.5, W * 0.75, H * 0.5), budget=800)
    await r.step('pinch to zoom in', lambda: r.pinch(W / 2, H / 2, 150, 420), budget=1200)
    await r.step('pinch to zoom out', lambda: r.pinch(W / 2, H / 2, 420, 140), budget=1200)
    await r.step('the Pencil opens markings', lambda: r.pen([(W * 0.45, H * 0.4)]), budget=1200)
    for i in range(3):
        await r.step(f'write a stroke ({i + 1})', lambda: r.pen([(W * 0.3 + k * 6, H * 0.35 + i * 40 + (k % 5) * 3) for k in range(40)]), budget=900)
    if await r.visible('#inkBtn'): await r.step('close markings', lambda: r.tap('#inkBtn'))
    await r.step('pages panel', lambda: open_pages(r), budget=2500)
    await r.step('close pages panel', lambda: pg.keyboard.press('Escape') if False else close_panel(r))
    await r.step('back to library', lambda: back_home(r), budget=1500)

async def show_chrome(r):
    if not await r.visible('#backBtn'): await r.tapxy(VIEW['width'] / 2, 40)
async def open_pages(r):
    await show_chrome(r)
    await r.tap('[data-panel="settings"]'); await asyncio.sleep(0.4); await r.tap('#pagesBtn')
async def back_home(r):
    await show_chrome(r); await asyncio.sleep(0.3); await r.tap('#backBtn')
async def close_panel(r):
    for sel in ['aside.panel:not([hidden]) [data-close]']:
        if await r.visible(sel): await r.tap(sel); return

async def j_tools(r):
    r.scenario = 'tools'
    pg = r.pg
    for name in ['metronome', 'tuner', 'scales', 'takes', 'reps', 'pomodoro', 'goal', 'backup', 'app']:
        sel = f'[data-panel="{name}"]'
        if not await r.visible(sel): continue
        await r.step(f'open {name}', lambda: r.tap(sel), budget=1500)
        if name == 'metronome' and await r.visible('#metroToggle'):
            await r.step('metronome start', lambda: r.tap('#metroToggle'))
            await asyncio.sleep(1.5)
            await r.step('metronome stop', lambda: r.tap('#metroToggle'))
        if name == 'tuner' and await r.visible('#droneToggle'):
            await r.step('drone on', lambda: r.tap('#droneToggle'))
            await asyncio.sleep(1)
            await r.step('drone off', lambda: r.tap('#droneToggle'))
        await r.step(f'close {name}', lambda: close_panel(r))

async def j_compose(r):
    r.scenario = 'compose'
    pg = r.pg; W, H = VIEW['width'], VIEW['height']
    if not await r.visible('[data-panel="compose"]'): return
    await r.step('open compose', lambda: r.tap('[data-panel="compose"]'), budget=1500)
    if await r.visible('#cnCreate'):
        await r.step('create a score', lambda: r.tap('#cnCreate'), budget=3000)
    else:
        await r.step('new score', lambda: pg.evaluate("async () => { const E = await import('/js/compose/editor.js'); await E.createComposition({ title: 'QA', insts: ['cello', 'piano'], time: [4, 4], bars: 16 }); }"), budget=3000)
    # write notes with the Pencil, staff by staff
    box = await pg.locator('#cpPages .cp-page').first.bounding_box()
    if box:
        for i in range(16):
            x = box['x'] + box['width'] * (0.18 + 0.045 * i); y = box['y'] + box['height'] * (0.17 + (i % 5) * 0.004)
            await r.step(f'write a note ({i + 1})', lambda: r.pen([(x, y)]), budget=700)
    for btn in ['#cpUndo', '#cpRedo', '#cpPlay']:
        if await r.visible(btn): await r.step(f'tap {btn}', lambda: r.tap(btn), budget=2500)
    await asyncio.sleep(2)
    if await r.visible('#cpPlay'): await r.step('stop playing', lambda: r.tap('#cpPlay'))
    for name in ['cplayout', 'cpmix', 'cpinst', 'cpexport', 'cpcapture']:
        sel = f'[data-panel="{name}"]'
        if await r.visible(sel):
            await r.step(f'open {name}', lambda: r.tap(sel), budget=1500)
            await r.step(f'close {name}', lambda: close_panel(r))
    # every button of the palette, twice (each answers at once?)
    btns = await pg.evaluate("() => [...document.querySelectorAll('#cpPal button')].filter((b) => { const r = b.getBoundingClientRect(); return r.width > 8 && r.height > 8 && r.top > 0 && r.bottom < innerHeight; }).map((b) => { const r = b.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2, (b.getAttribute('aria-label') || b.textContent || b.className).trim().slice(0, 24)]; })")
    for rep in range(2):
        for (x, y, label) in btns:
            if 'Fold' in label or 'fold' in label: continue
            await r.step(f'palette: {label}', lambda: r.tapxy(x, y), budget=300)
    await r.step('scroll the score', lambda: r.swipe(W * 0.5, H * 0.75, W * 0.5, H * 0.3))
    await r.step('pinch the score', lambda: r.pinch(W / 2, H / 2, 160, 360))
    await r.step('back to library', lambda: r.tap('#cpBack'), budget=2500)

# ---------------- at random ----------------
SKIP = ('#importInput', 'input[type=file]', '[data-danger]', '#bkInput', '#libDelete', '.danger')
async def random_walk(r, n):
    r.scenario = 'random'
    pg = r.pg
    for i in range(n):
        cands = await pg.evaluate("""() => {
          const vis = (el) => { const r = el.getBoundingClientRect(); if (r.width < 8 || r.height < 8 || r.bottom < 0 || r.top > innerHeight || r.right < 0 || r.left > innerWidth) return false; const s = getComputedStyle(el); if (s.visibility === 'hidden' || s.display === 'none' || s.pointerEvents === 'none') return false;
            const x = Math.min(innerWidth - 2, Math.max(1, r.left + r.width / 2)), y = Math.min(innerHeight - 2, Math.max(1, r.top + r.height / 2)); const top = document.elementFromPoint(x, y); return top && (top === el || el.contains(top)); };
          return [...document.querySelectorAll('button, [role=button], select, input[type=range], input[type=checkbox], .card, label.check')].filter(vis)
            .filter((el) => !/delete|remove|erase all|clear|reset|restore/i.test(el.textContent + ' ' + (el.getAttribute('aria-label') || '') + ' ' + el.id))
            .map((el) => { const r = el.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2, what: (el.id ? '#' + el.id : el.className.toString().slice(0, 30)) + ' ' + (el.textContent || el.getAttribute('aria-label') || '').trim().slice(0, 24), tag: el.tagName, type: el.type || '' }; });
        }""")
        if not cands:
            await r.step('nothing to tap: back', lambda: pg.keyboard.press('Escape')); continue
        c = R.choice(cands)
        if c['tag'] == 'SELECT':
            await r.step(f"choose in {c['what']}", lambda: pg.evaluate("([x, y]) => { const e = document.elementFromPoint(x, y); const s = e && e.closest('select'); if (s && s.options.length) { s.selectedIndex = Math.floor(Math.random() * s.options.length); s.dispatchEvent(new Event('change', { bubbles: true })); } }", [c['x'], c['y']]))
        elif c['type'] == 'range':
            await r.step(f"slide {c['what']}", lambda: r.swipe(c['x'] - 30, c['y'], c['x'] + R.randint(-60, 60), c['y'], 5))
        else:
            await r.step(f"tap {c['what']}", lambda: r.tapxy(c['x'], c['y']))
        # (now and then the system back: Escape, and a page turn)
        if R.random() < 0.08: await r.step('turn a page', lambda: r.tapxy(VIEW['width'] * 0.93, VIEW['height'] * 0.5))

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', '--autoplay-policy=no-user-gesture-required', '--enable-precise-memory-info'])
        ctx = await b.new_context(viewport=VIEW, has_touch=True, device_scale_factor=2, user_agent=UA, permissions=['microphone', 'camera'])
        pg = await ctx.new_page()
        await pg.add_init_script('window.__noTour = true;')
        await pg.add_init_script(open('/home/claude/tools/qa/probe.js').read())
        pg.on('dialog', lambda d: asyncio.ensure_future(d.dismiss()))
        pg.on('filechooser', lambda fc: None)
        cdp = await ctx.new_cdp_session(pg)
        r = Robot(pg, cdp)
        await pg.goto(BASE); await pg.wait_for_timeout(1500)
        r.scenario = 'start'
        if await r.visible('#welGo'): await r.step('welcome', lambda: r.tap('#welGo'))
        J = {'library': j_library, 'read0': lambda r: j_reading(r, 0), 'read1': lambda r: j_reading(r, 1), 'read2': lambda r: j_reading(r, 2), 'tools': j_tools, 'compose': j_compose}
        for name, fn in J.items():
            if ONLY and name not in ONLY.split(','): continue
            try: await fn(r)
            except Exception as ex: print('JOURNEY FAILED', name, ex)
        if RANDOM_STEPS: await random_walk(r, RANDOM_STEPS)
        json.dump({'view': VIEW, 'seed': SEED, 'steps': steps}, open(f'{OUT}/report.json', 'w'), indent=1)
        errs = [s for s in steps if s['errors'] or not s['ok']]; slow = [s for s in steps if s['longest'] > 300 or s['maxFrameGap'] > 400]; odd = [s for s in steps if s['issues']]
        print(f'\nSTEPS {len(steps)}  errors/failed {len(errs)}  slow {len(slow)}  odd screens {len(odd)}  mem end {steps[-1]["mem"] if steps else None} MB')
        await b.close()
asyncio.run(main())
