# The YouTube player's own buttons, against a stand-in for YouTube's player API that behaves as
# YouTube says it does (only the video's own speeds; any other is moved toward 1): the Speed button
# shows the speed that really plays, every press; a video with one speed stays at 100%; the A-B loop
# goes back to A; nothing is drawn over the video; each YouTube error says why, with a way out.
import asyncio, os, json, urllib.parse
from playwright.async_api import async_playwright
PORT = os.environ.get('PORT', '8765')
FAKE = r"""
window.__ytRates = window.__ytRates || [0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2];
window.YT = { Player: function (id, o) {
  const self = this; let rate = 1, t = 0, state = -1; window.__yt = self;
  const el = document.getElementById(id); const f = document.createElement('iframe'); f.id = id; f.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;border:0;background:#200'; el.replaceWith(f);
  self.getAvailablePlaybackRates = () => window.__ytRates.slice();
  // (YouTube: an unsupported value is rounded down to the nearest supported value in the direction of 1)
  self.setPlaybackRate = (r) => { const av = window.__ytRates; let got = 1;
    if (av.includes(r)) got = r; else if (r < 1) got = Math.min(...av.filter((x) => x >= r && x <= 1).concat([1])); else got = Math.max(...av.filter((x) => x <= r && x >= 1).concat([1]));
    if (got !== rate) { rate = got; setTimeout(() => o.events.onPlaybackRateChange && o.events.onPlaybackRateChange({ data: rate }), 30); } };
  self.getPlaybackRate = () => rate;
  self.getCurrentTime = () => t; self.getDuration = () => 300; self.seekTo = (s) => { t = s; window.__seeks = (window.__seeks || 0) + 1; };
  self.playVideo = () => { state = 1; o.events.onStateChange({ data: 1 }); }; self.pauseVideo = () => { state = 2; o.events.onStateChange({ data: 2 }); };
  self.getPlayerState = () => state; self.__setTime = (s) => { t = s; };
  setTimeout(() => { if (window.__ytError) o.events.onError({ data: window.__ytError }); else o.events.onReady({}); }, 50);
} };
setTimeout(() => window.onYouTubeIframeAPIReady && window.onYouTubeIframeAPIReady(), 10);
"""
async def page(b, rates=None, err=None):
    ctx = await b.new_context(viewport={'width': 480, 'height': 360})
    await ctx.route('https://www.youtube.com/iframe_api', lambda r: r.fulfill(status=200, content_type='text/javascript', body=FAKE))
    pg = await ctx.new_page()
    init = ''
    if rates: init += f'window.__ytRates = {json.dumps(rates)};'
    if err: init += f'window.__ytError = {err};'
    if init: await pg.add_init_script(init)
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    h = urllib.parse.quote(json.dumps({'kind': 'youtube', 'id': 'dQw4w9WgXcQ', 'start': 0, 'url': 'https://youtu.be/dQw4w9WgXcQ'}))
    await pg.goto(f'http://localhost:{PORT}/media.html#{h}'); await pg.wait_for_timeout(600)
    return ctx, pg, errs
async def main():
    fails = []
    def check(c, m):
        print(('ok   ' if c else 'FAIL ') + m)
        if not c: fails.append(m)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx, pg, errs = await page(b)
        seq = []
        for i in range(6):
            await pg.click('#bSpeed'); await pg.wait_for_timeout(150)
            seq.append((await pg.text_content('#bSpeed'), await pg.evaluate('Math.round(window.__yt.getPlaybackRate() * 100) + "%"')))
        check(all(a == b_ for a, b_ in seq), f'Speed: the button shows what plays, every press {seq}')
        check(len(set(a for a, _ in seq)) >= 3, f'Speed: at least three speeds to choose from ({sorted(set(a for a, _ in seq))})')
        check(all(a in ('50%', '75%', '100%', '125%') for a, _ in seq), 'Speed: only speeds this video has, none faster than 125%')
        # the loop
        await pg.evaluate('window.__yt.__setTime(10)'); await pg.click('#bA'); await pg.evaluate('window.__yt.__setTime(15)'); await pg.click('#bB')
        await pg.evaluate('window.__yt.__setTime(15.5)'); await pg.wait_for_timeout(400)
        t = await pg.evaluate('window.__yt.getCurrentTime()')
        check(abs(t - 10) < 0.01, f'A-B loop: past B it goes back to A ({t})')
        # nothing over the video
        over = await pg.evaluate("""() => { const f = document.querySelector('#stage iframe'); const r = f.getBoundingClientRect(); let bad = 0;
          for (let x = r.left + 4; x < r.right; x += 37) for (let y = r.top + 4; y < r.bottom; y += 29) { const e = document.elementFromPoint(x, y); if (e !== f) bad++; } return { bad, w: r.width, h: r.height }; }""")
        check(over['bad'] == 0, f"nothing drawn over the video ({over})")
        check(over['w'] >= 200 and over['h'] >= 200, f"the video is at least 200 × 200 ({over['w']} × {over['h']})")
        check(not errs, f'no errors {errs[:2]}')
        await ctx.close()
        # a video with one speed only
        ctx, pg, errs = await page(b, rates=[1])
        s = []
        for i in range(3):
            await pg.click('#bSpeed'); await pg.wait_for_timeout(120); s.append(await pg.text_content('#bSpeed'))
        check(s == ['100%'] * 3, f'one speed only: the button stays at 100% {s}')
        await ctx.close()
        # a video whose speeds are not ours: YouTube's own are offered
        ctx, pg, errs = await page(b, rates=[0.25, 1, 2])
        s = []
        for i in range(4):
            await pg.click('#bSpeed'); await pg.wait_for_timeout(120); s.append((await pg.text_content('#bSpeed'), await pg.evaluate('Math.round(window.__yt.getPlaybackRate() * 100) + "%"')))
        check(all(a == b_ for a, b_ in s) and '25%' in [a for a, _ in s], f'other speeds: YouTube\'s own, shown as they play {s}')
        await ctx.close()
        # errors
        for code, want in [(150, 'outside YouTube'), (153, 'did not accept'), (100, 'no longer on YouTube'), (5, 'cannot play here')]:
            ctx, pg, errs = await page(b, err=code)
            m = await pg.text_content('#msg'); out = await pg.evaluate("!!document.querySelector('#goOut')")
            check(want in (m or '') and out, f'error {code}: says why ({m!r}) with a way to open it in YouTube')
            await ctx.close()
        await b.close()
    print('\n' + ('ALL OK' if not fails else f'{len(fails)} FAILED'))
asyncio.run(main())
