# The monkey: for MIN minutes (default 20) Stand is used at random — taps on any button that is not
# destructive, taps and strokes on the page, pinches and swipes, the pedal keys, opening and closing
# scores, notebooks, Compose, panels — while every error is noted with the last 30 actions before it,
# and every minute: is the app still alive and responsive, and is memory growing?
# MIN=20 SEED=1 python3 monkey.py
import asyncio, os, time, json, random
from playwright.async_api import async_playwright
FIX = '/home/claude/fixtures/'
MIN = float(os.environ.get('MIN', '20')); SEED = int(os.environ.get('SEED', '1'))
MONKEY = r"""
window.__monkey = (() => {
  let seed = %SEED%;
  const rnd = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
  const pick = (a) => a[Math.floor(rnd() * a.length)];
  const log = []; const note = (s) => { log.push(s); if (log.length > 30) log.shift(); };
  // never: deleting, clearing, restoring, sharing, signing in, files, the system's own dialogs
  const BAD = /delete|remove|clear|restore|bring back|reset|erase all|start over|share|export|send|sign|choose file|import|add from|from files|scan|camera|record|film|video|back up|backup|pdf|print|feedback|report|tour|link|iphone|ipad|cloud|download|imslp|open in/i;
  const visible = (el) => { if (!el || el.disabled) return false; const r = el.getBoundingClientRect(); if (r.width < 4 || r.height < 4 || r.bottom < 0 || r.right < 0 || r.top > innerHeight || r.left > innerWidth) return false; const st = getComputedStyle(el); if (st.visibility === 'hidden' || st.pointerEvents === 'none') return false; let e = el; while (e) { if (e.hidden) return false; e = e.parentElement; } const top = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2); return !!top && (el === top || el.contains(top) || top.contains(el)); };
  const ptr = (t, type, x, y, id, kind, extra = {}) => t.dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true, pointerId: id, pointerType: kind, isPrimary: true, clientX: x, clientY: y, pressure: 0.5, width: kind === 'touch' ? 30 : 1, height: kind === 'touch' ? 30 : 1, buttons: type === 'pointerup' ? 0 : 1, ...extra }));
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const acts = {
    async button() {
      const bs = [...document.querySelectorAll('button, [role=button], .card, .chip, select, input[type=checkbox], input[type=range]')].filter((b) => visible(b) && !BAD.test((b.textContent || '') + ' ' + (b.getAttribute('aria-label') || '') + ' ' + (b.id || '') + ' ' + (b.title || '')) && !b.closest('#welcome'));
      if (!bs.length) return 'no buttons';
      const b = pick(bs);
      const name = (b.id ? '#' + b.id : '') + ' ' + (b.getAttribute('aria-label') || b.textContent || b.tagName).trim().slice(0, 30);
      if (b.tagName === 'SELECT') { const o = b.options; if (o.length) { b.selectedIndex = Math.floor(rnd() * o.length); b.dispatchEvent(new Event('change', { bubbles: true })); } return 'select ' + name; }
      if (b.type === 'range') { b.value = b.min + rnd() * (b.max - b.min); b.dispatchEvent(new Event('input', { bubbles: true })); b.dispatchEvent(new Event('change', { bubbles: true })); return 'slide ' + name; }
      b.click(); return 'click ' + name;
    },
    async stageTap() {
      const t = document.querySelector('#stage'); if (!t || !visible(t) && $hidden('#score')) return 'no stage';
      const r = t.getBoundingClientRect(), x = r.left + rnd() * r.width, y = r.top + rnd() * r.height;
      ptr(t, 'pointerdown', x, y, 21, 'touch'); await sleep(40); ptr(t, 'pointerup', x, y, 21, 'touch'); return 'tap stage ' + Math.round(x) + ',' + Math.round(y);
    },
    async pen() {
      const t = document.querySelector('#stage'); if (!t || document.querySelector('#score').hidden) return 'no stage';
      const r = t.getBoundingClientRect(); let x = r.left + rnd() * r.width, y = r.top + rnd() * r.height;
      ptr(t, 'pointerdown', x, y, 22, 'pen'); const n = 5 + Math.floor(rnd() * 25);
      for (let i = 0; i < n; i++) { x += (rnd() - 0.5) * 30; y += (rnd() - 0.5) * 30; ptr(t, 'pointermove', x, y, 22, 'pen'); if (i % 4 === 0) await sleep(8); }
      ptr(t, 'pointerup', x, y, 22, 'pen'); return 'pen stroke ' + n;
    },
    async swipe() {
      const t = document.querySelector('#stage'); if (!t || document.querySelector('#score').hidden) return 'no stage';
      const r = t.getBoundingClientRect(), x = r.left + r.width * (0.3 + rnd() * 0.4), y = r.top + r.height * (0.3 + rnd() * 0.4), dx = (rnd() < 0.5 ? -1 : 1) * (60 + rnd() * 300), dy = (rnd() - 0.5) * 200;
      ptr(t, 'pointerdown', x, y, 23, 'touch'); for (let i = 1; i <= 8; i++) { ptr(t, 'pointermove', x + dx * i / 8, y + dy * i / 8, 23, 'touch'); await sleep(12); } ptr(t, 'pointerup', x + dx, y + dy, 23, 'touch'); return 'swipe ' + Math.round(dx) + ',' + Math.round(dy);
    },
    async pinch() {
      const t = document.querySelector('#stage'); if (!t || document.querySelector('#score').hidden) return 'no stage';
      const r = t.getBoundingClientRect(), cx = r.left + r.width * (0.2 + rnd() * 0.6), cy = r.top + r.height * (0.2 + rnd() * 0.6), sp = (rnd() - 0.4) * 200, dx = (rnd() - 0.5) * 300, dy = (rnd() - 0.5) * 300;
      ptr(t, 'pointerdown', cx - 50, cy, 24, 'touch'); ptr(t, 'pointerdown', cx + 50, cy, 25, 'touch', { isPrimary: false });
      for (let i = 1; i <= 10; i++) { const f = i / 10; ptr(t, 'pointermove', cx - 50 - sp * f + dx * f, cy + dy * f, 24, 'touch'); ptr(t, 'pointermove', cx + 50 + sp * f + dx * f, cy + dy * f, 25, 'touch', { isPrimary: false }); await sleep(16); }
      ptr(t, 'pointerup', cx - 50 - sp + dx, cy + dy, 24, 'touch'); ptr(t, 'pointerup', cx + 50 + sp + dx, cy + dy, 25, 'touch', { isPrimary: false }); return 'pinch ' + Math.round(sp) + ' move ' + Math.round(dx) + ',' + Math.round(dy);
    },
    async keys() { const k = pick(['ArrowRight', 'ArrowLeft', 'PageDown', 'PageUp', 'ArrowDown', ' ', 'Escape']); (document.activeElement || document.body).dispatchEvent(new KeyboardEvent('keydown', { key: k, code: k, bubbles: true })); return 'key ' + k; },
    async home() { const b = document.querySelector('#backBtn'); if (b && visible(b)) { b.click(); return 'back'; } const c = document.querySelector('#cpBack, #compose [aria-label="Back"]'); if (c && visible(c)) { c.click(); return 'compose back'; } return 'no back'; },
    async score() { const cs = [...document.querySelectorAll('#grid .card:not(.folder)')].filter(visible); if (!cs.length) return 'no cards'; const c = pick(cs); c.click(); return 'open ' + (c.querySelector('.ttl') || {}).textContent; },
    async escape() { const c = [...document.querySelectorAll('[data-close]')].filter(visible); if (c.length) { pick(c).click(); return 'close panel'; } return 'nothing to close'; },
    async typeText() { const f = [...document.querySelectorAll('input[type=text], input:not([type]), textarea, [contenteditable=true]')].filter(visible); if (!f.length) return 'no field'; const e = pick(f); e.focus(); if ('value' in e && e.tagName !== 'DIV') { e.value = (e.value || '') + pick(['a', 'Bach ', '1', 'é', '♩']); e.dispatchEvent(new Event('input', { bubbles: true })); } else { e.textContent += 'x'; e.dispatchEvent(new Event('input', { bubbles: true })); } if (rnd() < 0.3) e.blur(); return 'type in ' + (e.id || e.tagName); },
  };
  const $hidden = (q) => { const e = document.querySelector(q); return !e || e.hidden; };
  const weights = [['button', 40], ['stageTap', 12], ['pen', 14], ['swipe', 6], ['pinch', 6], ['keys', 8], ['home', 3], ['score', 4], ['escape', 6], ['typeText', 3]];
  const total = weights.reduce((a, [, w]) => a + w, 0);
  return {
    log,
    async step() {
      let r = rnd() * total, name = 'button';
      for (const [n, w] of weights) { r -= w; if (r <= 0) { name = n; break; } }
      try { const s = await acts[name](); note(s); return s; } catch (e) { note(name + ' threw ' + e.message); return name + ' threw'; }
    },
    alive() { const lib = !document.querySelector('#library').hidden, sc = !document.querySelector('#score').hidden, cp = !document.querySelector('#compose').hidden, st = document.querySelector('#studio'); return { lib, sc, cp, studio: !!(st && !st.hidden), panel: [...document.querySelectorAll('aside.panel:not([hidden])')].map((a) => a.id) }; },
  };
})();
"""
async def main():
    async with async_playwright() as p:
        br = os.environ.get('BR', 'chromium')
        b = await getattr(p, br).launch(**({'args': ['--enable-precise-memory-info', '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', '--autoplay-policy=no-user-gesture-required']} if br == 'chromium' else {}))
        PH = os.environ.get('PHONE') == '1'
        ctx = await b.new_context(viewport={'width': 390, 'height': 844} if PH else {'width': 1366, 'height': 1024}, has_touch=True, **({'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148', 'device_scale_factor': 3} if PH else {}))
        pg = await ctx.new_page()
        await pg.add_init_script('window.__noTour = true;')
        await pg.add_init_script("window.alert = () => {}; window.confirm = () => true; window.prompt = () => null;")
        errs = []
        def onerr(e):
            errs.append({'t': round(time.time() - T0), 'err': str(e)[:300]})
        pg.on('pageerror', onerr)
        crashlog = []
        async def oncrash(_):
            crashlog.append(round(time.time() - T0)); print('PAGE CRASHED at', round(time.time() - T0), 's', flush=True)
        pg.on('crash', lambda p_: asyncio.ensure_future(oncrash(p_)))
        pg.on('dialog', lambda d: asyncio.ensure_future(d.dismiss()))
        base = 'http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'
        await pg.goto(base); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); setTimeout(() => document.querySelector('.tour-skip')?.click(), 300); }"); await pg.wait_for_timeout(700)
        if not PH:
          await pg.set_input_files('#importInput', [FIX + 'vector8.pdf', FIX + 'scan10.pdf', FIX + 'imslp12.pdf'])
          await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 3", timeout=120000)
          await pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); document.querySelector('#newNotebookBtn')?.click(); await sleep(1200); document.querySelector('#nbCreate')?.click(); await sleep(2000); document.querySelector('#backBtn')?.click(); await sleep(800); const E = await import('/js/compose/editor.js'); await E.createComposition({ title: 'Monkey', insts: ['cello', 'piano'], time: [3, 4], bars: 8 }); await sleep(1500); document.querySelector('#cpBack')?.click(); await sleep(800); }")
        await pg.add_init_script(MONKEY.replace('%SEED%', str(SEED)))
        await pg.evaluate(MONKEY.replace('%SEED%', str(SEED)))
        cdp = await ctx.new_cdp_session(pg) if br == 'chromium' else None
        if cdp: await cdp.send('Performance.enable')
        global T0; T0 = time.time()
        steps = 0; samples = []; stuck = []; lastErrN = 0; reports = []
        nextSample = 0
        while time.time() - T0 < MIN * 60:
            try:
                s = await asyncio.wait_for(pg.evaluate("() => window.__monkey.step()"), 20)
            except asyncio.TimeoutError:
                stuck.append({'t': round(time.time() - T0), 'log': await pg.evaluate("() => window.__monkey.log.slice(-10)")}); s = 'TIMEOUT'
            except Exception as e:
                if 'Execution context was destroyed' in str(e) or 'navigat' in str(e):
                    await pg.wait_for_timeout(2000); await pg.evaluate(MONKEY.replace('%SEED%', str(SEED + steps))); continue
                raise
            steps += 1
            with open('/tmp/claude-0/monkey_last_%s.txt' % SEED, 'a') as lf: lf.write(str(round(time.time() - T0)) + ' ' + str(s) + '\n')
            await pg.wait_for_timeout(random.Random(SEED + steps).randint(30, 250))
            if len(errs) > lastErrN:
                log = await pg.evaluate("() => window.__monkey.log.slice()")
                for e in errs[lastErrN:]: e['before'] = log[-12:]
                lastErrN = len(errs)
            if time.time() - T0 >= nextSample:
                nextSample += 60
                a = await pg.evaluate("() => window.__monkey.alive()")
                m = {}
                if cdp:
                    await cdp.send('HeapProfiler.collectGarbage')
                    mm = {x['name']: x['value'] for x in (await cdp.send('Performance.getMetrics'))['metrics']}
                    m = {'heapMB': round(mm['JSHeapUsedSize'] / 1e6), 'nodes': int(mm['Nodes']), 'listeners': int(mm['JSEventListeners'])}
                px = await pg.evaluate("() => { let n = 0, c = 0; for (const x of document.querySelectorAll('canvas')) { n += x.width * x.height; c++; } return [c, Math.round(n / 1e6)]; }")
                t0 = time.time(); await pg.evaluate("() => new Promise((r) => requestAnimationFrame(() => r()))"); lag = round((time.time() - t0) * 1000)
                samp = {'min': round((time.time() - T0) / 60), 'steps': steps, **m, 'canvases': px[0], 'canvasMpx': px[1], 'frameMs': lag, 'where': a}
                samples.append(samp); print(json.dumps(samp), flush=True)
        # the end: back home, and the library still works
        await pg.evaluate("() => { for (let i = 0; i < 5; i++) document.querySelector('[data-close]:not([hidden])')?.click(); document.querySelector('#backBtn')?.click(); }")
        await pg.wait_for_timeout(2000)
        noted = await pg.evaluate("() => (window.__standErrors || []).map((x) => x.line)")
        uniq = {}
        for e in errs:
            k = e['err'].split('\n')[0][:120]
            if 'RenderingCancelledException' in k: continue
            uniq.setdefault(k, e)
        print('steps', steps, 'errors', len(errs), 'distinct', len(uniq), 'stuck', len(stuck))
        for k, e in uniq.items(): print('ERROR at', e['t'], 's:', k, '\n   after:', ' | '.join(e.get('before', [])[-8:]))
        for s_ in stuck: print('STUCK at', s_['t'], s_['log'])
        print('noted by Stand:', noted[:10])
        grow = samples[-1].get('heapMB', 0) - samples[min(2, len(samples) - 1)].get('heapMB', 0) if samples else 0
        lgrow = samples[-1].get('listeners', 0) - samples[min(2, len(samples) - 1)].get('listeners', 0) if samples else 0
        print('heap growth after warm-up', grow, 'MB; listener growth', lgrow)
        ok = not uniq and not stuck and grow < 60 and lgrow < 3000
        print('PASS' if ok else 'FAIL', f'monkey {MIN} min, seed {SEED}')
        await b.close()
asyncio.run(main())
