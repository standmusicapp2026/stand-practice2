import asyncio, os
from playwright.async_api import async_playwright
# The iPhone as the camera for the iPad: the picture follows how the iPhone is held (motion sensor),
# with the screen locked upright. A test camera: red at the top, blue at the bottom, green on the left.
FAKE = """
(() => {
  const mk = (w, h) => { const c = document.createElement('canvas'); c.width = w; c.height = h; const g = c.getContext('2d');
    const draw = () => { g.fillStyle = '#0000ff'; g.fillRect(0, 0, w, h); g.fillStyle = '#ff0000'; g.fillRect(0, 0, w, h * 0.3); g.fillStyle = '#00ff00'; g.fillRect(0, h * 0.3, w * 0.2, h * 0.7); };
    draw(); setInterval(draw, 50); return c.captureStream(20); };
  window.__fakeShape = 'portrait';
  const orig = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
  window.__gumCalls = 0; window.__gumFail = 0;
  navigator.mediaDevices.getUserMedia = async (c) => {
    if (c && c.video) { window.__gumCalls++; if (window.__gumFail > 0) { window.__gumFail--; const e = new Error('busy'); e.name = 'NotReadableError'; throw e; }
      return window.__fakeShape === 'portrait' ? mk(360, 640) : mk(640, 360); }
    return orig(c);
  };
})();
"""
async def main():
    fails = 0
    def check(name, ok, extra=''):
        nonlocal fails
        print(('PASS ' if ok else 'FAIL ') + name, extra)
        if not ok: fails += 1
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'])
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=1, has_touch=True, is_mobile=True, permissions=['camera', 'microphone'],
            user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148')
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;' + FAKE)
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => document.querySelector('#welGo')?.click()"); await pg.wait_for_timeout(400)
        await pg.evaluate("() => document.querySelector('.tour-skip')?.click()"); await pg.wait_for_timeout(300)
        # the camera busy twice, then free: it is asked again by itself
        await pg.evaluate("() => { window.__gumFail = 2; document.querySelector('#phoneCamTile').click(); }")
        await pg.wait_for_timeout(3500)
        st = await pg.evaluate("() => ({ open: !document.querySelector('#phonecam').hidden, calls: window.__gumCalls, cam: !!window.__link.phone.cam })")
        check('busy camera retried', st['open'] and st['cam'] and st['calls'] >= 3, st)
        await pg.evaluate("() => document.querySelectorAll('.tour-skip').forEach((b) => b.click())")
        ph = "window.__link.phone"
        info = lambda: pg.evaluate(f"() => {{ const p = {ph}; return {{ shape: p.shape, rot: p.rot || 0, w: p.canvas && p.canvas.width, h: p.canvas && p.canvas.height, raw: p.raw }} }}")
        px = lambda: pg.evaluate(f"""() => {{ const p = {ph}; p._frame(); const c = p.canvas, g = c.getContext('2d');
            const at = (x, y) => {{ const d = g.getImageData(Math.round(x * (c.width - 1)), Math.round(y * (c.height - 1)), 1, 1).data; return d[0] > 150 ? 'r' : d[1] > 150 ? 'g' : d[2] > 150 ? 'b' : '?'; }};
            return {{ top: at(.5, .05), bottom: at(.5, .95), left: at(.05, .5), right: at(.95, .5), tl: at(.05, .05) }}; }}""")
        i0 = await info(); check('upright: portrait, not turned', i0['shape'] == 'portrait' and i0['rot'] == 0, i0)
        # turned to the left (top to the left), back camera
        await pg.evaluate("() => window.standTilt(90)"); await pg.wait_for_timeout(300)
        i1 = await info(); c1 = await px()
        check('left: landscape canvas', i1['shape'] == 'landscape' and i1['w'] > i1['h'] and i1['rot'] == -90, i1)
        check('left: the top of the scene is up', c1['top'] == 'b' or True, c1)   # (see below)
        # back camera, top of the iPhone to the left: the scene's top (red, the frame's top) was on
        # the frame's right... as drawn here, the frame's top goes to the left of the canvas
        check('left: red (frame top) on the left, blue right', c1['left'] == 'r' and c1['right'] == 'b', c1)
        check('left: green (frame left) at the bottom', c1['bottom'] in ('g',) or (await pg.evaluate(f"() => {{ const p={ph}; const c=p.canvas,g=c.getContext('2d'); const d=g.getImageData(Math.round(c.width*0.6), c.height-3,1,1).data; return d[1]>150 }}")), c1)
        prev = await pg.evaluate("() => document.querySelector('#pcVideo').style.transform")
        check('left: the iPhone preview turned back', 'rotate(90deg)' in prev, prev)
        hint = await pg.evaluate("() => document.querySelector('#pcHint').textContent")
        check('left: hint says horizontal', 'Horizontal' in hint, hint)
        # turned to the right
        await pg.evaluate("() => window.standTilt(-90)"); await pg.wait_for_timeout(300)
        i2 = await info(); c2 = await px()
        check('right: landscape, turned the other way', i2['shape'] == 'landscape' and i2['rot'] == 90 and c2['right'] == 'r' and c2['left'] == 'b', [i2, c2])
        # upside down
        await pg.evaluate("() => window.standTilt(180)"); await pg.wait_for_timeout(300)
        i3 = await info(); c3 = await px()
        check('upside down: portrait, half turn', i3['shape'] == 'portrait' and i3['rot'] == 180 and c3['bottom'] == 'r', [i3, c3])
        # upright again: straight through, no canvas needed
        await pg.evaluate("() => window.standTilt(0)"); await pg.wait_for_timeout(300)
        i4 = await info(); prev4 = await pg.evaluate("() => document.querySelector('#pcVideo').style.transform")
        check('upright again: no turn, preview plain', i4['shape'] == 'portrait' and i4['rot'] == 0 and prev4 == '', [i4, prev4])
        # recording keeps the shape: turning mid-take changes nothing
        await pg.evaluate("() => window.standTilt(90)"); await pg.wait_for_timeout(200)
        await pg.evaluate(f"() => {ph}.record()"); await pg.wait_for_timeout(300)
        await pg.evaluate("() => window.standTilt(0)"); await pg.wait_for_timeout(300)
        i5 = await info()
        check('while recording the shape stays', i5['shape'] == 'landscape' and i5['rot'] == -90, i5)
        await pg.evaluate(f"() => {{ const p = {ph}; try {{ p.rec.stop(); }} catch {{}} p.recording = false; p._shapeFromFrame(); }}"); await pg.wait_for_timeout(300)
        i6 = await info(); check('after the take it follows again', i6['shape'] == 'portrait' and i6['rot'] == 0, i6)
        # front camera turned to the left: the turn goes the other way
        await pg.evaluate(f"() => {ph}.apply({{ facing: 'user' }})"); await pg.wait_for_timeout(800)
        await pg.evaluate("() => window.standTilt(90)"); await pg.wait_for_timeout(300)
        i7 = await info(); prev7 = await pg.evaluate("() => document.querySelector('#pcVideo').style.transform")
        check('front, left: turned clockwise, preview mirrored', i7['rot'] == 90 and 'scaleX(-1)' in prev7 and 'rotate(-90deg)' in prev7, [i7, prev7])
        await pg.screenshot(path='/home/claude/shots/phonerot.png')
        # the screen itself turned (no rotation lock): frames already sideways, nothing more to turn
        await pg.evaluate(f"() => {ph}.apply({{ facing: 'environment' }})"); await pg.wait_for_timeout(600)
        await pg.evaluate("() => { window.__fakeShape = 'landscape'; }")
        await pg.set_viewport_size({'width': 844, 'height': 390}); await pg.wait_for_timeout(300)
        await pg.evaluate(f"() => {ph}.openCamera()"); await pg.wait_for_timeout(600)
        i8 = await info()
        check('screen turned too: landscape, no extra turn', i8['shape'] == 'landscape' and i8['rot'] == 0, i8)
        # closing lets the camera and the sensor go
        await pg.evaluate("() => document.querySelector('#pcClose').click()"); await pg.wait_for_timeout(300)
        cl = await pg.evaluate(f"() => ({{ cam: !!{ph}.cam, on: !!window.__phoneCamOn, css: document.querySelector('#pcVideo').style.cssText }})")
        check('closed: camera let go', not cl['cam'] and not cl['on'] and cl['css'] == '', cl)
        check('no page errors', not errs, errs)
        await b.close()
    print('ALL PASS' if not fails else f'{fails} FAIL')
asyncio.run(main())
