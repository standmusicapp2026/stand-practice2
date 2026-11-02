import asyncio, base64, json
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-gl=swiftshader', '--enable-unsafe-swiftshader']); pg = await (await b.new_context()).new_page()
        logs = []; pg.on('console', lambda m: logs.append(m.text[:300])); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.add_init_script('window.__img = "data:image/jpeg;base64,' + base64.b64encode(open('/home/claude/fixtures/grade_face.jpg','rb').read()).decode() + '"'); await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(800)
        r = await pg.evaluate("""async () => {
          const G = await import('/js/grade.js');
          const img = new Image(); img.src = window.__img; await img.decode();
          // a poor phone video frame: dark, blue, flat, noisy
          const c = document.createElement('canvas'); c.width = 720; c.height = Math.round(720 * img.height / img.width);
          const g = c.getContext('2d'); g.filter = 'brightness(0.45) contrast(0.7) saturate(0.7)'; g.drawImage(img, 0, 0, c.width, c.height); g.filter = 'none';
          const d = g.getImageData(0, 0, c.width, c.height);
          let s = 7; const R = () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; };
          for (let i = 0; i < d.data.length; i += 4) { const n = (R() - 0.5) * 34; d.data[i] += n - 4; d.data[i + 1] += n; d.data[i + 2] += n + 14; }
          g.putImageData(d, 0, 0);
          const auto = G.autoLook([c]);
          const gr = new G.Grader();
          const out = gr.render(c, c.width, c.height, { preset: 'natural', adj: {}, auto, autoOn: true, autoAmt: 1 });
          const both = document.createElement('canvas'); both.width = c.width * 2; both.height = c.height; const bg = both.getContext('2d'); bg.drawImage(c, 0, 0); if (out) bg.drawImage(out, c.width, 0);
          const gl = gr.gl; const err = gl ? gl.getError() : 'nogl';
          return { ok: gr.ok, err, auto, png: both.toDataURL('image/jpeg', 0.85) };
        }""")
        open('/home/claude/shots/grade.jpg', 'wb').write(base64.b64decode(r.pop('png').split(',')[1]))
        print(json.dumps(r)); print(errs, [l for l in logs if 'rror' in l or 'ERROR' in l][:5]); await b.close()
asyncio.run(main())
