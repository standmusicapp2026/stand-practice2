# Original vs what the app rebuilt: read the picture, paste into a new piano (or one-staff) score, engrave
import asyncio, base64, json, sys, random
from playwright.async_api import async_playwright
from PIL import Image, ImageDraw, ImageFont
import io
ROOT = '/home/claude/ds/raw/olimpic-1.0-scanned'
JS = """async ([src, piano]) => {
  const O = await import('/js/omr.js'); const E = await import('/js/compose/editor.js'); const EN = await import('/js/compose/engrave.js'); const M = await import('/js/compose/model.js');
  const img = new Image(); img.src = src; await img.decode();
  const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; c.getContext('2d').drawImage(img, 0, 0);
  let res = [];
  if (piano) {
    const r0 = await O.recogniseBest(c, { staff: 99 }); const n = r0 ? (r0.systems === 1 ? r0.staves : 2) : 2;
    res = [await O.recogniseBest(c, { staff: Math.max(0, n - 2) }), await O.recogniseBest(c, { staff: Math.max(0, n - 1) })];
  } else res = [await O.recogniseBest(c, { lines: 'all' })];
  await E.createComposition({ insts: [piano ? 'piano' : 'violin'], time: (res[0] && res[0].time) || [4, 4], bars: 4, key: 0 }); await new Promise(r => setTimeout(r, 400));
  const C = window.__compose; const sts = C.score.parts[0].staves;
  res.forEach((r, i) => { if (!r || !r.notes.length) return; C.capture = { ...r, clef: r.clef || 'treble', clef0: r.clef || 'treble', key: r.key || 0 }; const cap = document.querySelector('#capTo'); if (cap) cap.value = ''; window.__composeTest.pasteCapture(sts[i], 0); });
  C.score.title = ''; C.score.layout.staffMm = 7;
  const lay = EN.layoutScore(C.score, {}); const pg = lay.pages[0];
  const s0 = pg.systems[0], sN = pg.systems[pg.systems.length - 1]; const px = 14;
  const top = s0.top - 8, bot = sN.top + sN.height + 8;
  const cv = document.createElement('canvas'); cv.width = Math.round(lay.W * px); cv.height = Math.round((bot - top) * px);
  const g = cv.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, cv.width, cv.height); g.scale(px, px); g.translate(0, -top); EN.drawPage(g, lay, 0);
  return cv.toDataURL('image/png');
}"""
async def main():
    items = json.loads(sys.argv[1])
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width': 1366, 'height': 1024})).new_page()
        await pg.add_init_script('window.__noTour = true;')
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1200)
        await pg.evaluate("() => document.querySelector('#welGo')?.click()")
        for k, (path, piano, label, crop) in enumerate(items):
            im = Image.open(path).convert('RGB')
            if crop: im = im.crop(tuple(crop))
            buf = io.BytesIO(); im.save(buf, 'PNG')
            src = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
            try: out = await pg.evaluate(JS, [src, piano])
            except Exception as e: print('ERR', path, str(e)[:200]); continue
            rb = Image.open(io.BytesIO(base64.b64decode(out.split(',')[1]))).convert('RGB')
            W = 1600
            a = im.resize((W, int(im.height * W / im.width))); r = rb.resize((W, int(rb.height * W / rb.width)))
            pad = 60
            canvas = Image.new('RGB', (W, a.height + r.height + pad * 2 + 20), 'white')
            d = ImageDraw.Draw(canvas)
            try: f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 30)
            except Exception: f = None
            d.text((10, 12), 'ORIGINAL — ' + label, fill=(150, 0, 0), font=f)
            canvas.paste(a, (0, pad))
            d.line((0, pad + a.height + 10, W, pad + a.height + 10), fill=(180, 180, 180), width=3)
            d.text((10, pad + a.height + 22), 'O QUE A APP LEU (reconstruído no compositor)', fill=(0, 90, 160), font=f)
            canvas.paste(r, (0, a.height + pad * 2 + 20))
            fn = f'/home/claude/examples/exemplo_{k + 1}.png'; canvas.save(fn); print(fn)
        await b.close()
asyncio.run(main())
