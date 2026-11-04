# The first link made easy: an iPad and an iPhone, never linked, both open nearby. Each is told the
# other is there and offers to link it; Link on both shows the code; typed, they are linked. Once
# dismissed, a device is not offered again. A new iPhone also explains linking at its first start.
import asyncio, os, json, sys
sys.path.insert(0, '/home/claude/tools')
import pairtest as PT
from playwright.async_api import async_playwright
res = []
def ok(c, m): res.append(bool(c)); print('PASS' if c else 'FAIL', m, flush=True)
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ipad, phone = PT.Dev('ipad', 'iPad'), PT.Dev('phone', 'iPhone')
        net = PT.Net([ipad, phone]); net.nearby = True
        errs = []
        async def boot(dev, intro_seen=False):
            dev.reset(); dev.announced = set()
            ua = PT.IPAD_UA if dev.kind == 'iPad' else PT.IPHONE_UA
            vp = {'width': 1180, 'height': 820} if dev.kind == 'iPad' else {'width': 390, 'height': 844}
            if not hasattr(dev, 'ctx'):
                dev.ctx = await b.new_context(viewport=vp, user_agent=ua, has_touch=True, is_mobile=dev.kind != 'iPad')
                await dev.ctx.expose_binding('__peerOut', lambda src, s, d=dev: asyncio.ensure_future(net.from_page(d, json.loads(s))))
                await dev.ctx.add_init_script(PT.BRIDGE)
                if intro_seen: await dev.ctx.add_init_script("try { localStorage.setItem('standLinkIntro', '1'); } catch {}")
            pg = await dev.ctx.new_page(); dev.pg = pg
            pg.on('pageerror', lambda e, n=dev.name: errs.append(n + ': ' + str(e)))
            await pg.goto(f'http://localhost:{PT.PORT}/index.html'); await pg.wait_for_timeout(800)
            await pg.evaluate("() => { document.querySelector('#welGo')?.click(); setTimeout(() => document.querySelector('.tour-skip')?.click(), 300); }")
        # the iPhone, never linked, first start: the explanation
        await boot(phone)
        await phone.pg.wait_for_timeout(4500)
        intro = await phone.pg.evaluate("() => document.querySelector('.ask .ask-title')?.textContent || ''")
        ok('Use Stand with your iPad' in intro, 'a new iPhone explains linking at its first start: ' + intro)
        await phone.pg.evaluate("() => [...document.querySelectorAll('.ask .btn')].find((x) => /Not now/.test(x.textContent))?.click()"); await phone.pg.wait_for_timeout(500)
        # the iPad opens nearby: both are told, both offer to link
        await boot(ipad)
        await ipad.pg.wait_for_timeout(3500)
        t1 = await ipad.pg.evaluate("() => document.querySelector('.ask .ask-title')?.textContent || ''")
        t2 = await phone.pg.evaluate("() => document.querySelector('.ask .ask-title')?.textContent || ''")
        ok(t1 == 'An iPhone with Stand is nearby' and t2 == 'An iPad with Stand is nearby', f'both offer to link the other: "{t1}" / "{t2}"')
        ok(not net.conn, 'nothing connects before Link is tapped')
        await ipad.pg.evaluate("() => [...document.querySelectorAll('.ask .btn')].find((x) => /^Link$/.test(x.textContent))?.click()")
        await phone.pg.evaluate("() => [...document.querySelectorAll('.ask .btn')].find((x) => /^Link$/.test(x.textContent))?.click()")
        await phone.pg.wait_for_function("() => { const i = document.querySelector('.pair .pair-input'); return i && !i.hidden; }", timeout=10000)
        await ipad.pg.wait_for_function("() => { const c = document.querySelector('.pair .pair-code'); return c && !c.hidden && c.textContent.trim().length > 0; }", timeout=10000)
        code = await ipad.pg.evaluate("() => document.querySelector('.pair .pair-code').textContent.replace(/\\s/g, '')")
        await phone.pg.fill('.pair .pair-input', code); await phone.pg.wait_for_timeout(1200)
        ok(phone.id in ipad.linked and ipad.id in phone.linked, 'Link on both, the code typed: linked')
        await ipad.pg.wait_for_timeout(4500)
        # started again: no offer for a linked device; a dismissed device is not offered again
        await ipad.pg.close(); ipad.on = False
        for o in net.devs:
            if net.key(ipad, o) in net.conn: await net.drop(ipad, o)
        await boot(ipad); await ipad.pg.wait_for_timeout(3500)
        t3 = await ipad.pg.evaluate("() => document.querySelector('.ask .ask-title')?.textContent || ''")
        ok(t3 == '' and net.key(ipad, phone) in net.conn, 'started again: no offer, the two connect by themselves')
        stranger = PT.Dev('stranger', 'iPhone'); net.devs.append(stranger)
        await boot(stranger, intro_seen=True); await stranger.pg.wait_for_timeout(3500)
        t4 = await ipad.pg.evaluate("() => document.querySelector('.ask .ask-title')?.textContent || ''")
        ok(t4 == 'An iPhone with Stand is nearby', 'another iPhone nearby: offered once')
        await ipad.pg.evaluate("() => [...document.querySelectorAll('.ask .btn')].find((x) => /Not now/.test(x.textContent))?.click()"); await ipad.pg.wait_for_timeout(400)
        await ipad.pg.close(); ipad.on = False
        for o in net.devs:
            if net.key(ipad, o) in net.conn: await net.drop(ipad, o)
        await boot(ipad); await ipad.pg.wait_for_timeout(3500)
        t5 = await ipad.pg.evaluate("() => document.querySelector('.ask .ask-title')?.textContent || ''")
        ok(t5 == '' and net.key(ipad, stranger) not in net.conn, 'dismissed: not offered again, and never connected')
        print('errors', errs[:3]); ok(not errs, 'no page errors')
        print('PASS' if all(res) else 'FAIL', 'the first link made easy')
        await b.close()
asyncio.run(main())
