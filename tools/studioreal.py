# A real performance video through Studio, as a musician would use it: the video imported into
# Recordings, opened in Studio, the lines of the score given, Stand follows the playing by itself.
# Then the finished video is made frame by frame from what Studio draws (its own export drawing),
# with the original sound. Prints how well the playing matched the score.
#   python3 studioreal.py VIDEO.webm CROP.png OUT.mp4 [look] [mode] [format] [a] [b] [audio_src]
import asyncio, base64, json, os, subprocess, sys
from playwright.async_api import async_playwright
VID, CROP, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
LOOK = sys.argv[4] if len(sys.argv) > 4 else 'paper'
MODE = sys.argv[5] if len(sys.argv) > 5 else 'scroll'
FMT = sys.argv[6] if len(sys.argv) > 6 else '9:16'
A = float(sys.argv[7]) if len(sys.argv) > 7 else None
B = float(sys.argv[8]) if len(sys.argv) > 8 else None
AUD = sys.argv[9] if len(sys.argv) > 9 else VID
PRE = len(sys.argv) > 10 and sys.argv[10] == 'pre'   # (the part chosen before following: the score is only that part of the playing)
FPS = 25
OW, OH = {'9:16': (720, 1280), '4:5': (864, 1080), '1:1': (900, 900), '16:9': (1280, 720)}[FMT]
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required', '--use-gl=swiftshader', '--enable-unsafe-swiftshader'])
        ctx = await b.new_context(viewport={'width': 1180, 'height': 820}, has_touch=True)
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append('console ' + m.type + ': ' + m.text[:300]) if m.type in ('error', 'warning') else None)
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(1500)
        J = lambda js, a=None: pg.evaluate("async (a) => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }", a)
        await J("document.querySelector('#welGo')?.click(); await sleep(400); document.querySelector('.tour-skip')?.click(); await sleep(200); document.querySelector('.tile[data-tile=\"takes\"]')?.click(); await sleep(600);")
        await pg.set_input_files('#takeImportFile', VID)
        ok = await J("const { db } = await import('/js/db.js'); for (let i = 0; i < 600; i++) { const t = await db.all('takes'); if (t.length && t[0].pcm) return true; await sleep(1000); } return false;")
        print('imported', ok, flush=True)
        await J("document.querySelector('.tour-skip')?.click(); await sleep(300); document.querySelector('#takeList li')?.click(); await sleep(1200); document.querySelector('#studioBtn').click(); await sleep(2500); document.querySelector('.tour-skip')?.click();")
        ok = await J("const S = await import('/js/studio.js'); for (let i = 0; i < 300; i++) { const ST = S._studio; if (ST.P && ST.pcm && ST.media && ST.media.readyState >= 2) return true; await sleep(1000); } return false;")
        print('studio open', ok, flush=True)
        crop = base64.b64encode(open(CROP, 'rb').read()).decode()
        info = await J("""const S = await import('/js/studio.js'); const ST = S._studio;
          ST.P.format = a.fmt; if (a.pre) { if (a.A !== null) ST.P.trim.a = a.A; if (a.B !== null) ST.P.trim.b = a.B; }
          const img = new Image(); img.src = 'data:image/png;base64,' + a.crop; await img.decode();
          const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height); g.drawImage(img, 0, 0);
          const o = await S._addScoreFrom(c);
          const wide = a.fmt === '16:9';
          Object.assign(o, { look: a.look, mode: a.mode, perView: wide ? 4 : 2, size: wide ? 0.9 : 0.96, pos: { x: 0.5, y: wide ? 0.8 : 0.78 } });
          const t0 = performance.now(); await S._autoSync(o); const toast = document.querySelector('#toast')?.textContent + ' | harmony ' + JSON.stringify(window.__studioHarmony || null); if (a.A !== null) ST.P.trim.a = a.A; if (a.B !== null) ST.P.trim.b = a.B;
          return { bars: o.layout.bars.length, notes: o.layout.notes.length, synced: o.synced, info: o.syncInfo || null, secs: Math.round((performance.now() - t0) / 1000), dur: ST.dur, trim: ST.P.trim, times: (o.times || []).map((x) => +x.toFixed(1)), toast };""",
          {'crop': crop, 'look': LOOK, 'mode': MODE, 'fmt': FMT, 'A': A, 'B': B, 'pre': PRE})
        print('STUDIO', json.dumps(info), flush=True)
        if os.environ.get('SYNCONLY'): await b.close(); return
        a, bb = info['trim']['a'], info['trim']['b']
        ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'image2pipe', '-framerate', str(FPS), '-i', '-', '-ss', str(a), '-t', str(bb - a), '-i', AUD,
                               '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-shortest', '-movflags', '+faststart', OUT], stdin=subprocess.PIPE)
        n = int((bb - a) * FPS); k = 0
        while k < n:
            batch = await J("""const S = await import('/js/studio.js'); const m = S._studio.media; const out = [];
              window.__big = window.__big || document.createElement('canvas'); window.__small = window.__small || document.createElement('canvas');
              const sm = window.__small; sm.width = a.W; sm.height = a.H; const sg = sm.getContext('2d');
              for (let i = a.k; i < Math.min(a.n, a.k + 25); i++) {
                const t = a.a + i / a.fps;
                await new Promise((r) => { const done = () => { m.removeEventListener('seeked', done); r(); }; m.addEventListener('seeked', done); m.currentTime = t; setTimeout(done, 1500); });
                S._drawAt(window.__big, t); sg.drawImage(window.__big, 0, 0, a.W, a.H);
                out.push(sm.toDataURL('image/jpeg', 0.86).split(',')[1]);
              }
              return out;""", {'a': a, 'k': k, 'n': n, 'fps': FPS, 'W': OW, 'H': OH})
            for im in batch: ff.stdin.write(base64.b64decode(im))
            k += len(batch)
            if k % 500 < 25: print(f'  frame {k}/{n}', flush=True)
        ff.stdin.close(); ff.wait()
        print('errors', errs[:3]); print('DONE', OUT, os.path.getsize(OUT) if os.path.exists(OUT) else 0)
        await b.close()
asyncio.run(main())
