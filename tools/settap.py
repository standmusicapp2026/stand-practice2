# Every button and switch in Settings (home) and in a score's More, tapped for real (a finger at its
# place, not a script click: a tap swallowed by something on top shows only this way), as the app on
# the iPad and on the iPhone. Each must do something: a switch turns, a window or question opens, the
# page changes. Every question or window opened is then closed with a real tap on its Cancel/Close,
# and must close (and the panel under it must not have been closed by that tap).
import asyncio, os, re
from playwright.async_api import async_playwright
PORT = os.environ.get('PORT', '8765')
SKIP = re.compile(r'Delete everything|Erase|Reset all|Remove all', re.I)
NAT = '''window.__nat = []; window.standCaps = { native: true, face: true, tap: true, scan: true, video: true, pencil: true, audio: true, files: 3, busy: 1, recover: 1, memory: 1, peer: 4, notify: 1 };
  // (the app answers as the real one does: asked for the list of linked devices, it sends it)
  window.webkit = { messageHandlers: new Proxy({}, { get: (t, k) => t[k] || (t[k] = { postMessage(m) { window.__nat.push(String(k));
    if (k === 'standPeer' && m && m.op === 'pairList') setTimeout(() => window.standPairEvent && window.standPairEvent('list', { list: [{ d: 'dev1', kind: /iPhone/.test(navigator.userAgent) ? 'iPad' : 'iPhone', at: 1793000000000 }], me: 'x' }), 15); } }) }) };'''
async def run(p, phone, panel):
    b = await getattr(p, os.environ.get('BR', 'chromium')).launch()
    kw = dict(viewport={'width': 393, 'height': 852}, is_mobile=True, has_touch=True, user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)') if phone else dict(viewport={'width': 1180, 'height': 820}, has_touch=True)
    ctx = await b.new_context(**kw); pg = await ctx.new_page()
    await pg.add_init_script('window.__noTour = true; try { localStorage.setItem("standLinkIntro", "1"); } catch {}')
    if os.environ.get('NATIVE', '1') == '1': await pg.add_init_script(NAT)
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('dialog', lambda d: asyncio.ensure_future(d.dismiss()))
    await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1500)
    await pg.evaluate("() => { document.querySelector('#welGo')?.click(); setTimeout(() => document.querySelector('.tour-skip')?.click(), 300); }"); await pg.wait_for_timeout(900)
    J = lambda js, a=None: pg.evaluate("async (a) => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }", a)
    if panel == 'settings':
        await pg.set_input_files('#importInput', ['/home/claude/fixtures/imslp12.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=60000)
        await J("document.querySelector('#grid .card:not(.folder)').click(); await sleep(2500); document.querySelector('.tour-skip')?.click(); await sleep(300);")
    async def tap(x, y):
        # a finger (touch events, as on the iPad and iPhone), or the mouse with MOUSE=1
        if os.environ.get('MOUSE'): await pg.mouse.click(x, y)
        else: await pg.touchscreen.tap(x, y)
        await pg.wait_for_timeout(120)
    async def open_panel():
        if await J("return !document.querySelector('#panel-' + a).hidden", panel): return True
        # (opening it is not what is tested here: a script click)
        await J("const bs = [...document.querySelectorAll('[data-panel=\"' + a + '\"]')]; (bs.find((x) => x.offsetParent) || bs[0]).click(); await sleep(300);", panel)
        await pg.wait_for_timeout(450)
        return await J("return !document.querySelector('#panel-' + a).hidden", panel)
    print('panel opens:', await open_panel())
    # open every <details> so that what is inside can be tapped
    n = await J("""const P = document.querySelector('#panel-' + a); P.querySelectorAll('details').forEach((d) => d.open = true); await sleep(200);
      const set = new Set(P.querySelectorAll('button, label.btn')); P.querySelectorAll('input[type=checkbox]').forEach((c) => { const w = c.closest('.switch') || c.closest('label'); if (w) set.add(w); }); const all = [...set]; all.forEach((e, i) => e.dataset.tap = i); return all.length;""", panel)
    bad = []; seen = 0
    for i in range(n):
        if not await open_panel(): bad.append(('panel', 'did not open again before #' + str(i), '')); break
        await J("document.querySelectorAll('#panel-' + a + ' details').forEach((d) => d.open = true);", panel)
        info = await J("""const e = document.querySelector('[data-tap="' + a + '"]'); if (!e || e.closest('[hidden]') || !e.offsetParent) return null;
          const inp = e.querySelector('input[type=checkbox]'); if (inp && inp.disabled) return null; if (e.disabled) return null;
          e.scrollIntoView({ block: 'center' }); await sleep(150); const r = e.getBoundingClientRect(); if (r.width < 4 || r.height < 4) return null;
          const lab = (e.closest('.set-row, label')?.querySelector('b')?.textContent || e.textContent || e.getAttribute('aria-label') || '').trim().replace(/\\s+/g, ' ').slice(0, 46);
          const top = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
          return { x: r.x + r.width / 2, y: r.y + r.height / 2, lab, id: e.id || (inp && inp.id) || '', sw: !!inp, was: inp ? inp.checked : null, cover: top && !e.contains(top) && !top.contains(e) ? (top.id || String(top.className)).slice(0, 40) : null, panelIn: !!e.dataset.panel || !!e.closest('[data-panel]') };""", i)
        if not info: continue
        if SKIP.search(info['lab']): print('  skip ', info['lab']); continue
        seen += 1
        await J("window.__mut = 0; window.__mo && window.__mo.disconnect(); window.__mo = new MutationObserver((l) => { window.__mut += l.length; }); window.__mo.observe(document.body, { subtree: true, childList: true, attributes: true, characterData: true });")
        backs0 = await J("return document.querySelectorAll('.ask-back, .ptool').length")
        await tap(info['x'], info['y']); await pg.wait_for_timeout(1300)
        st = await J("""const e = document.querySelector('[data-tap="' + a + '"]'); const inp = e && e.querySelector('input[type=checkbox]');
          return { mut: window.__mut, now: inp ? inp.checked : null, backs: document.querySelectorAll('.ask-back, .ptool').length, panel: !document.querySelector('#panel-' + window.__PN).hidden };""", i) if False else await J("""const e = document.querySelector('[data-tap="' + a[0] + '"]'); const inp = e && e.querySelector('input[type=checkbox]');
          return { mut: window.__mut, now: inp ? inp.checked : null, backs: document.querySelectorAll('.ask-back, .ptool').length, panel: !document.querySelector('#panel-' + a[1]).hidden };""", [i, panel])
        note = ''
        if info['cover']: note += f" covered by {info['cover']}"
        if info['sw'] and st['now'] == info['was']: note += ' SWITCH DID NOT TURN'
        if not info['sw'] and st['mut'] == 0: note += ' NOTHING HAPPENED'
        # a question or window opened: close it with a real tap; it must go, and the tap must not close more
        closed_ok = None
        if st['backs'] > backs0:
            for k in range(1):   # (one tap: it must close at the first)
                c = await J("""const bs = [...document.querySelectorAll('.ask-back button, .ptool button')].filter((b) => b.offsetParent && /^(Cancel|Close|Not now|Later|Done|Back)$/.test(b.textContent.trim()));
                  const b = bs[bs.length - 1]; if (!b) return null; const r = b.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2, b.textContent.trim()];""")
                if not c: break
                await tap(c[0], c[1]); await pg.wait_for_timeout(700)
                if await J("return document.querySelectorAll('.ask-back, .ptool').length") <= backs0: break
            left = await J("return document.querySelectorAll('.ask-back, .ptool').length")
            closed_ok = left <= backs0
            if closed_ok and not await J("return !document.querySelector('#panel-' + a).hidden", panel): note += ' THE TAP ON ITS CANCEL ALSO CLOSED THE PANEL'
            if not closed_ok:
                note += ' ITS WINDOW DID NOT CLOSE WITH A TAP'
                await J("document.querySelectorAll('.ask-back, .ptool').forEach((x) => x.remove());")
        # a switch put back as it was (with a real tap too)
        if info['sw'] and st['now'] != info['was']:
            await open_panel(); await J("document.querySelectorAll('#panel-' + a + ' details').forEach((d) => d.open = true);", panel)
            r = await J("const e = document.querySelector('[data-tap=\"' + a + '\"]'); e.scrollIntoView({ block: 'center' }); await sleep(120); const r = e.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2];", i)
            await tap(*r); await pg.wait_for_timeout(500)
            if await J("return document.querySelector('[data-tap=\"' + a + '\"] input[type=checkbox]').checked", i) != info['was']: note += ' SWITCH DID NOT TURN BACK'
            await J("document.querySelectorAll('.ask-back').forEach((x) => { const c = [...x.querySelectorAll('button')].find((b) => /Cancel|Not now/.test(b.textContent)); c && c.click(); });")
        print(('  BAD  ' if note else '  ok   ') + f"{info['id'] or '-':16s} {info['lab']:46s}" + (' (window closed by a tap)' if closed_ok else '') + note, flush=True)
        if note: bad.append((info['id'], info['lab'], note.strip()))
        # back to where we were
        await J("for (const x of document.querySelectorAll('.panel:not([hidden])')) if (x.id !== 'panel-' + a) x.querySelector('[data-close]')?.click(); await sleep(150);" + ("" if panel == 'settings' else " if (!document.querySelector('#score').hidden) document.querySelector('#backBtn')?.click(); for (const s of ['#compose', '#studio']) { const x = document.querySelector(s); if (x && !x.hidden) x.querySelector('[data-close], .back, #cpBack, #stBack')?.click(); } await sleep(200); document.querySelector('.tour-skip')?.click();"), panel)
    print('tapped', seen, 'errors', errs[:5])
    await b.close()
    return bad + ([('errors', str(errs[:3]), '')] if errs else [])
async def main():
    async with async_playwright() as p:
        allbad = []
        for panel in os.environ.get('PANELS', 'app settings').split():
            for phone in (False, True):
                print('=====', panel, 'iPhone' if phone else 'iPad')
                allbad += [(panel, 'iPhone' if phone else 'iPad') + x for x in await run(p, phone, panel)]
        print('SUMMARY', len(allbad), 'problems'); [print('  ', x) for x in allbad]
        print('PASS' if not allbad else 'FAIL', 'every Settings button and switch works with a real tap')
asyncio.run(main())
