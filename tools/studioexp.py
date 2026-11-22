# (studioexp) Studio's export in the app, with iOS's part played by the test: every picture is drawn
# exactly (none dropped, none twice), at the video's own frame rate and full size, the original video
# and Studio's sound are handed over in pieces, and the finished film is kept in Recordings.
import asyncio, base64, json, os, sys
from playwright.async_api import async_playwright
D = '/home/claude/dragon'
MOCK = r"""
(() => {
  const st = window.__mock = { frames: 0, sizes: [], src: 0, wav: 0, ops: [], last: null, prev: null, same: 0, diffs: [], fps: 0 };
  const send = (ev) => setTimeout(() => window.standVideoOutEvent && window.standVideoOutEvent(ev), 5);
  window.standCaps = Object.assign(window.standCaps || {}, { videoOut: 1 });
  window.webkit = window.webkit || {}; window.webkit.messageHandlers = window.webkit.messageHandlers || {};
  window.webkit.messageHandlers.standDone = { postMessage() {} };
  window.webkit.messageHandlers.standVideoOut = { postMessage(m) {
    st.ops.push(m.op + (m.part ? ':' + m.part : ''));
    if (m.op === 'begin') { st.w = m.w; st.h = m.h; st.fps = m.fps; send({ id: m.id, type: 'ready', w: m.w, h: m.h, fps: m.fps }); }
    else if (m.op === 'set') { st.fps = m.fps; send({ id: m.id, type: 'ready', fps: m.fps }); }
    else if (m.op === 'src' || m.op === 'wav') {
      if (m.part === 'chunk') st[m.op] += atob(m.data).length;
      if (m.op === 'src' && m.part === 'end') send({ id: m.id, type: 'src', fps: +(window.__srcFps || 30), w: 720, h: 1280, hasAudio: true });
      else send({ id: m.id, type: 'chunk' });
    }
    else if (m.op === 'frame') {
      if (m.i !== st.frames) st.order = (st.order || 0) + 1;
      st.frames++;
      // (the top of the picture is the video: two pictures in a row exactly alike = a frame shown twice)
      const img = new Image(); img.onload = () => {
        const c = document.createElement('canvas'); c.width = 64; c.height = 48; const g = c.getContext('2d');
        g.drawImage(img, 0, 0, img.width, img.height * 0.4, 0, 0, 64, 48); const px = g.getImageData(0, 0, 64, 48).data;
        if (!st.size) st.size = [img.width, img.height];
        if (st.prev) { let d = 0; for (let k = 0; k < px.length; k += 4) d += Math.abs(px[k] - st.prev[k]); d /= px.length / 4; st.diffs.push(+d.toFixed(2)); if (d < 0.01) st.same++; }
        st.prev = px;
        send({ id: m.id, type: 'ack', i: m.i });
      };
      img.src = 'data:image/jpeg;base64,' + m.data;
    }
    else if (m.op === 'end') { st.end = m; fetch('/__exp_test.mp4').catch(() => null); send({ id: m.id, type: 'done', path: window.__donePath }); }
    else if (m.op === 'cancel') st.cancelled = (st.cancelled || 0) + 1;
  } };
})();
"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1366, 'height': 1024})
        pg = await ctx.new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.add_init_script("window.__noTour = true; window.__noTempo = true;")
        await pg.goto('http://localhost:8765/index.html'); await pg.wait_for_timeout(1200)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); }")
        await pg.set_input_files('#takeImportFile', f'{D}/4M30 clarinetes.webm')
        for _ in range(120):
            if await pg.evaluate("async () => { const { db } = await import('/js/db.js'); const t = await db.all('takes'); return t.length > 0 && !!t[0].pcm; }"): break
            await pg.wait_for_timeout(1000)
        tid = await pg.evaluate("async () => { const { db } = await import('/js/db.js'); return (await db.all('takes'))[0].id; }")
        await pg.evaluate("async (id) => { const S = await import('/js/studio.js'); await S.openStudio(id); }", tid)
        await pg.wait_for_timeout(2000)
        # a short part (2 s) with a picture over it, then the export
        res = {}
        for room in ('studio', 'dry'):
            await pg.evaluate(MOCK)
            # (a finished film to hand back: a few seconds of the video itself)
            await pg.evaluate("async () => { const { db } = await import('/js/db.js'); const t = (await db.all('takes'))[0]; const f = await db.get('files', 'video:' + t.id); window.__donePath = URL.createObjectURL(f.data.slice(0, 400000, 'video/mp4')); }")
            r = await pg.evaluate("""async (room) => { const S = await import('/js/studio.js'); const P = S._studio.P; P.trim = { a: 10, b: 12 }; P.sound.room = room;
              const before = (await (await import('/js/db.js')).db.all('takes')).length;
              const t0 = performance.now(); const ok = await S._exportNative({ share: false }); const ms = performance.now() - t0;
              await new Promise((r) => setTimeout(r, 400));
              const after = (await (await import('/js/db.js')).db.all('takes')).length;
              const m = window.__mock; return { ok, ms: Math.round(ms), frames: m.frames, order: m.order || 0, size: m.size, fps: m.fps, same: m.same, src: m.src, wav: m.wav, end: m.end, kept: after - before, ops: [...new Set(m.ops)], res: window.__studioExport, diffs: m.diffs.slice(0, 12) }; }""", room)
            res[room] = r
            print(room, json.dumps(r))
        await pg.screenshot(path='/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad/exp.png')
        ok = True
        for room, r in res.items():
            want_audio = 'wav' if room == 'studio' else 'src'
            good = r['ok'] and r['frames'] == 60 and r['order'] == 0 and r['same'] == 0 and r['size'] == [1080, 1920] and r['src'] > 1e6 and r['end']['audio'] == want_audio and r['kept'] == 1
            if want_audio == 'wav': good = good and r['wav'] > 2 * 48000 * 2 * 2 * 0.9
            print(room, 'ok' if good else 'BAD')
            ok = ok and good
        print('PASS' if ok and not errs else 'FAIL', 'studio export in the app: every picture, original video and sound handed over', errs[:3])
        await b.close()
asyncio.run(main())
