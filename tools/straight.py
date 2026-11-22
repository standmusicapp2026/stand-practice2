# (straight) The long line in Studio from a crooked scan: the lines of the clarinet part, turned by 1.5°
# and bent a little (as a scan of a page not lying flat), become one level line: the staff at the
# same height from one end to the other, the lines joined without a step, and the slurs over the
# notes kept whole (not cut where the picture was cut).
import asyncio, base64, json, os
from playwright.async_api import async_playwright
D = '/home/claude/dragon'
SP = '/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await (await b.new_context(viewport={'width': 1366, 'height': 1024})).new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.add_init_script("window.__noTour = true; window.__noTempo = true;")
        await pg.goto('http://localhost:8765/index.html'); await pg.wait_for_timeout(1200)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); }")
        await pg.set_input_files('#takeImportFile', f'{D}/4M30 clarinetes.webm')
        for _ in range(90):
            if await pg.evaluate("async () => { const { db } = await import('/js/db.js'); const t = await db.all('takes'); return t.length > 0 && !!t[0].pcm; }"): break
            await pg.wait_for_timeout(1000)
        tid = await pg.evaluate("async () => { const { db } = await import('/js/db.js'); return (await db.all('takes'))[0].id; }")
        await pg.evaluate("async (id) => { const S = await import('/js/studio.js'); await S.openStudio(id); }", tid)
        ls = sorted(json.load(open(f'{D}/app1.json'))[48]['lines'], key=lambda L: L['y0'])
        y0, y1 = ls[0]['y0'], ls[5]['y1']
        data = base64.b64encode(open(f'{D}/out/How to Train Your Dragon 2 - Clarinet 1.pdf', 'rb').read()).decode()
        r = await pg.evaluate("""async ([b64, y0, y1]) => {
          const { openDocument } = await import('/js/score.js'); const bin = atob(b64), u = new Uint8Array(bin.length); for (let k = 0; k < bin.length; k++) u[k] = bin.charCodeAt(k);
          const doc = await openDocument({ kind: 'pdf', data: u.buffer }); const [pw, ph] = doc.sizes[48]; const W = 2400, H = Math.round(W * ph / pw);
          const c = document.createElement('canvas'); await doc.render(48, c, W, H);
          // the scan: turned 1.5° and bowed (each column moved down a little more towards the middle)
          const r = document.createElement('canvas'); r.width = W; r.height = Math.round((y1 - y0 + 0.04) * H);
          const g = r.getContext('2d'); g.fillStyle = '#f4f1ea'; g.fillRect(0, 0, r.width, r.height);
          const t = document.createElement('canvas'); t.width = W; t.height = r.height; const tg = t.getContext('2d'); tg.fillStyle = '#fff'; tg.fillRect(0, 0, W, t.height);
          tg.translate(W / 2, t.height / 2); tg.rotate(1.5 * Math.PI / 180); tg.translate(-W / 2, -t.height / 2); tg.drawImage(c, 0, Math.round((y0 - 0.02) * H), W, t.height, 0, 0, W, t.height);
          for (let x = 0; x < W; x += 2) { const bow = Math.sin((x / W) * Math.PI) * 9; g.drawImage(t, x, 0, 2, t.height, x, bow, 2, t.height); }
          g.globalCompositeOperation = 'multiply'; g.fillStyle = '#f4f1ea'; g.fillRect(0, 0, r.width, r.height);
          const S = await import('/js/studio.js'); const o = await S._addScoreFrom(r);
          const st = S._studio.strips.get(o.id).canvas, L = o.layout, sp = L.sp;
          const d = st.getContext('2d').getImageData(0, 0, st.width, st.height).data, Wd = st.width;
          const dark = (x, y) => d[(y * Wd + x) * 4] < 200;
          // the top staff line's row at many places along the line (the row nearest the staff's top)
          const rows = [];
          for (const s of L.segs) {
            for (let f = 0.08; f < 0.95; f += 0.07) {
              const x = Math.round(s.sx + s.w * f), want = Math.round(s.dy + s.staff);
              let best = -1; for (let y = want - 8; y <= want + 8; y++) if (y >= 0 && y < st.height && dark(x, y)) { const rw = [-25, -12, 12, 25].filter((k) => dark(x + k, y)).length; if (rw >= 3) { best = y; break; } }
              if (best >= 0) rows.push(best);
            }
          }
          // a slur over the notes of the first line: ink above the staff, by more than a space
          let slur = 0; const s0 = L.segs[0];
          for (let x = s0.sx; x < s0.sx + s0.w; x += 2) for (let y = 0; y < s0.dy + s0.staff - sp * 1.2; y++) if (dark(x, y)) slur++;
          return { sp, segs: L.segs.length, rows, slur, h: st.height, data: st.toDataURL('image/png').split(',')[1] };
        }""", [data, y0, y1])
        open(f'{SP}/straight.png', 'wb').write(base64.b64decode(r.pop('data')))
        rows = r['rows']; spread = max(rows) - min(rows) if rows else 99
        print(json.dumps({**r, 'rows': rows[:12], 'n': len(rows), 'spread': spread}))
        ok = len(rows) > 40 and spread <= 3 and r['slur'] > 200
        print('PASS' if ok and not errs else 'FAIL', 'a crooked scan made one level line, slurs kept', errs[:2])
        await b.close()
asyncio.run(main())
