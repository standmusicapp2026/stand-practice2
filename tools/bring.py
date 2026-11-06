# Bring your scores from another app: a forScore-like archive (.4sb, a deflated zip with folders,
# a __MACOSX copy and a picture) comes in with its folders; choosing it again brings nothing twice.
# The empty library's "Hear an orchestra" opens the Holst example and plays it (once: no copies).
# "My instrument": nothing chosen at the start, every family listed, a new one (tuba) works.
import asyncio, os, sys, zipfile, io
from playwright.async_api import async_playwright
PORT = os.environ.get('PORT', '8765'); WWW = '/home/claude/s24/Payload/Stand.app/www'
def make_zip(path):
    pdf = open(WWW + '/examples/bach-cello-suite-3.pdf', 'rb').read()
    from PIL import Image; b = io.BytesIO(); Image.new('RGB', (600, 800), 'white').save(b, 'JPEG'); jpg = b.getvalue()
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('Documents/Etudes/Popper - Etude 1.pdf', pdf)
        z.writestr('Documents/Pieces/Saint-Saens - The Swan.pdf', pdf)
        z.writestr('Documents/Loose page.jpg', jpg)
        z.writestr('__MACOSX/Documents/._Loose page.jpg', b'junk')
        z.writestr('Documents/settings.plist', b'<plist/>')
async def main():
    zp = '/tmp/claude-0/brtest.4sb'; os.makedirs('/tmp/claude-0', exist_ok=True); make_zip(zp)
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        pg = await (await b.new_context(viewport={'width': 1180, 'height': 820})).new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1500)
        J = lambda js, a=None: pg.evaluate("async (a) => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }", a)
        wel = await J("const s = document.querySelector('#welInst'); return { value: s.value, groups: [...s.querySelectorAll('optgroup')].map((g) => g.label), n: s.options.length, hasTuba: !![...s.options].find((o) => o.value === 'tuba') };")
        print('welcome', wel)
        await J("const s = document.querySelector('#welInst'); s.value = 'tuba'; s.dispatchEvent(new Event('change')); document.querySelector('#welGo').click(); await sleep(400); document.querySelector('.tour-skip')?.click(); await sleep(300);")
        inst = await J("return { app: document.querySelector('#appInst').value, tuner: document.querySelector('#tunerInst').value };")
        print('instrument', inst)
        # tuner opens with a tuba
        await J("const bs=[...document.querySelectorAll('[data-panel=\"tuner\"]')]; (bs.find((x)=>x.offsetParent)||bs[0]).click(); await sleep(800); document.querySelector('[data-close]')?.click();")
        # bring the archive
        await J("document.querySelector('#bringBtn').click(); await sleep(300);")
        shown = await J("return !document.querySelector('#panel-bring').hidden;")
        await pg.set_input_files('#brArchiveInput', zp)
        for _ in range(60):
            await pg.wait_for_timeout(1000)
            busy = await J("return document.querySelector('#toast') && !document.querySelector('#toast').hidden ? document.querySelector('#toast').textContent : '';")
            if 'brought in' in busy or 'already' in busy or 'could not' in busy: break
        lib = await J("""const { db, getSetting } = await import('/js/db.js'); const sc = await db.all('scores'); const fol = await getSetting('folders', []);
          return { n: sc.length, titles: sc.map((s) => s.title + ' @' + ((fol.find((f) => f.id === s.folder) || {}).name || '-')), folders: fol.map((f) => f.name), toast: document.querySelector('#toast').textContent };""")
        print('first', lib)
        await pg.set_input_files('#brArchiveInput', zp)
        for _ in range(30):
            await pg.wait_for_timeout(1000)
            t = await J("return document.querySelector('#toast').textContent;")
            if 'already' in t or 'Nothing' in t: break
        again = await J("""const { db } = await import('/js/db.js'); return { n: (await db.all('scores')).length, toast: document.querySelector('#toast').textContent };""")
        print('again', again)
        ok1 = wel['value'] == '' and wel['hasTuba'] and len(wel['groups']) >= 6 and inst == {'app': 'tuba', 'tuner': 'tuba'} and shown
        ok2 = lib['n'] == 3 and sorted(lib['folders']) == ['Etudes', 'Pieces'] and again['n'] == 3 and 'already here' in again['toast']
        await b.close()
        # a fresh start: hear an orchestra from the empty library, twice (one copy only)
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        pg = await (await b.new_context(viewport={'width': 1180, 'height': 820})).new_page()
        await pg.add_init_script('window.__noTour = true;'); pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1500)
        J = lambda js, a=None: pg.evaluate("async (a) => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }", a)
        await J("document.querySelector('#welGo').click(); await sleep(400); document.querySelector('.tour-skip')?.click(); await sleep(300); document.querySelector('#hearOrchBtn').click(); await sleep(6000);")
        h = await J("return { open: !document.querySelector('#compose').hidden, play: document.querySelector('#cpPlay').textContent.trim() };")
        print('hear', h)
        await J("document.querySelector('#cpPlay').click(); await sleep(300); document.querySelector('#cpBack, #compose [data-close], #cpClose')?.click(); await sleep(800);")
        n = await J("const { db } = await import('/js/db.js'); return (await db.all('scores')).filter((s) => s.kind === 'comp').length;")
        print('comps', n)
        ok3 = h['open'] and h['play'] in ('Stop', 'Loading')
        print('errors', errs[:4])
        print('PASS' if ok1 and ok2 and ok3 and not errs else 'FAIL', 'bring scores from another app; hear an orchestra; my instrument from the full list')
        await b.close()
asyncio.run(main())
