# Studio's Tap ball: beside the play button, round, saying Tap, on the screen on every iPad and iPhone
# both ways round, nothing over it and it over nothing. One touch and you tap along at once: from bar 1
# when the bars were never set, else from the bar playing now (the bars before it kept). While tapping
# it is gone (the big ball is what you tap), and back when you stop.
import asyncio, os, sys, base64
from playwright.async_api import async_playwright
PORT = os.environ.get('PORT', '8765'); SHOT = os.environ.get('SHOT'); SP = os.environ.get('SP', '/tmp')
fails = []
def check(c, m):
    print(('ok   ' if c else 'FAIL ') + m)
    if not c: fails.append(m)
async def run(b, name, vp, mob):
    ctx = await b.new_context(viewport=vp, device_scale_factor=2, has_touch=True, is_mobile=mob); pg = await ctx.new_page()
    await pg.add_init_script('window.__noTour = true;')
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1200)
    J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); const S = await import('/js/studio.js'); const ST = S._studio; " + js + " }")
    await J("document.querySelector('#welGo')?.click(); await sleep(300); document.querySelector('.tour-skip')?.click(); await sleep(200); document.querySelector('.tile[data-tile=\"takes\"]').click(); await sleep(500);")
    await pg.set_input_files('#takeImportFile', '/home/claude/fixtures/clip.webm'); await pg.wait_for_timeout(4000)
    await J("document.querySelector('#takeList li')?.click(); await sleep(1200); document.querySelector('#studioBtn').click(); await sleep(2500); document.querySelector('.tour-skip')?.click();")
    no = await J("return document.querySelector('#stTapGo').hidden")
    check(no, f'{name}: no score yet: no Tap ball')
    img = base64.b64encode(open('/home/claude/tc/raw-002.jpg', 'rb').read()).decode()
    await pg.evaluate("""async (src) => { const S = await import('/js/studio.js'); const img = new Image(); img.src = 'data:image/jpeg;base64,' + src; await img.decode();
      const c = document.createElement('canvas'); c.width = 2080; c.height = 620; c.getContext('2d').drawImage(img, -150, -500); await S._addScoreFrom(c); }""", img)
    await pg.wait_for_timeout(900)
    UI = """const g = document.querySelector('#stTapGo'), r = g.getBoundingClientRect(), p = document.querySelector('#stPlay').getBoundingClientRect();
      const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      const others = [...document.querySelectorAll('#stTransport .st-clock, #stTransport .st-tzoom button')].map((x) => x.getBoundingClientRect()).filter((q) => q.width);
      const over = others.some((q) => q.left < r.right - 1 && q.right > r.left + 1 && q.top < r.bottom - 1 && q.bottom > r.top + 1);
      return { shown: !g.hidden && r.width > 0 && getComputedStyle(g).visibility !== 'hidden', w: r.width, h: r.height, text: g.textContent.trim(),
        inView: r.top >= 0 && r.bottom <= innerHeight && r.left >= 0 && r.right <= innerWidth, hit: !!hit && !!hit.closest('#stTapGo'), over,
        beside: r.left > p.right + 2 && Math.abs((r.top + r.height / 2) - (p.top + p.height / 2)) < 3, round: parseFloat(getComputedStyle(g).borderTopLeftRadius) >= r.width / 2 - 1 };"""
    u = await J(UI)
    check(u['shown'] and u['text'] == 'Tap', f'{name}: a score: the Tap ball shows, saying Tap {u}')
    check(u['round'] and u['w'] >= 36 and abs(u['w'] - u['h']) < 1, f'{name}: round, big enough to touch ({u["w"]:.0f} px)')
    check(u['inView'] and u['hit'] and not u['over'], f'{name}: on the screen, nothing over it, over nothing {u}')
    check(u['beside'], f'{name}: beside the play button')
    if SHOT: await pg.screenshot(path=f'{SP}/tapgo_{name}.png')
    # never set: from bar 1
    r = await J("""const o = ST.P.overlays.find((x) => x.kind === 'score'); o.synced = 'even'; document.querySelector('#stTapGo').click(); await sleep(250);
      return { tapping: !!ST.tapping, from: ST.tapping && ST.tapping.from, gone: getComputedStyle(document.querySelector('#stTapGo')).visibility === 'hidden', label: document.querySelector('#stTapBar').textContent };""")
    check(r['tapping'] and r['from'] == 0 and r['label'] == 'Bar 1', f'{name}: one touch: tapping at once, from bar 1 {r}')
    check(r['gone'], f'{name}: while tapping the Tap ball is gone (the big ball is what you tap)')
    if SHOT: await pg.screenshot(path=f'{SP}/tapgo_{name}_tapping.png')
    await J("document.querySelector('#stTapStop').click(); await sleep(400);")
    back = await J("return getComputedStyle(document.querySelector('#stTapGo')).visibility !== 'hidden' && !ST.tapping")
    check(back, f'{name}: stopped: the Tap ball is back')
    # set: from the bar playing now
    r = await J("""const o = ST.P.overlays.find((x) => x.kind === 'score'); const n = o.layout.bars.length; const a = ST.P.trim.a;
      o.times = Array.from({ length: n + 1 }, (_, k) => a + 0.3 + k * 0.4); o.synced = 'auto'; const keep = o.times.slice(0, 3);
      ST.media.currentTime = o.times[3] + 0.1; await sleep(400); document.querySelector('#stTapGo').click(); await sleep(250);
      const T = ST.tapping; return { n, from: T && T.from, kept: T && JSON.stringify(T.times.slice(0, 3)) === JSON.stringify(keep), label: document.querySelector('#stTapBar').textContent };""")
    check(r['from'] == 3 and r['kept'] and r['label'] == 'Bar 4', f'{name}: the bars set: tapping from the bar playing now, the bars before kept {r}')
    await J("document.querySelector('#stTapStop').click(); await sleep(300);")
    check(not errs, f'{name}: no page errors {errs[:2]}')
    await ctx.close()
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        for d in [('ipad-land', {'width': 1180, 'height': 820}, False), ('ipad-portrait', {'width': 820, 'height': 1180}, False), ('ipad-mini', {'width': 744, 'height': 1133}, False),
                  ('ipad-mini-land', {'width': 1133, 'height': 744}, False), ('ipad-pro13', {'width': 1376, 'height': 1032}, False), ('ipad-pro13-portrait', {'width': 1032, 'height': 1376}, False),
                  ('ipad-pro11', {'width': 1210, 'height': 834}, False), ('iphone', {'width': 393, 'height': 852}, True), ('iphone-land', {'width': 852, 'height': 393}, True),
                  ('iphone-se', {'width': 375, 'height': 667}, True), ('iphone-se-land', {'width': 667, 'height': 375}, True), ('iphone-max', {'width': 440, 'height': 956}, True)]:
            await run(b, *d)
        await b.close()
    print('FAILS', len(fails)); sys.exit(1 if fails else 0)
asyncio.run(main())
