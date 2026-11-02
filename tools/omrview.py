# Draw what the reader found over a real scan: heads (green black / blue hollow), stems, rests,
# barlines, accidentals, marks. Output: shots/omrview.png
import asyncio, json, sys, base64
from playwright.async_api import async_playwright
FILE = sys.argv[1]; CROP = [int(v) for v in sys.argv[2].split(',')] if len(sys.argv) > 2 and sys.argv[2] != '-' else None
OUT = sys.argv[3] if len(sys.argv) > 3 else '/home/claude/shots/omrview.png'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1000)
        mime = 'image/jpeg' if FILE.endswith('.jpg') else 'image/png'
        data = 'data:' + mime + ';base64,' + base64.b64encode(open(FILE,'rb').read()).decode()
        r = await pg.evaluate("""async ([src, crop]) => {
          const O = await import('/js/omr.js');
          const img = new Image(); img.src = src; await img.decode();
          const [x, y, w, h] = crop || [0, 0, img.width, img.height];
          const c = document.createElement('canvas'); c.width = w; c.height = h; c.getContext('2d').drawImage(img, -x, -y);
          const A = await O.analyse(c, false);
          const g = c.getContext('2d'); g.lineWidth = 2; g.font = '14px sans-serif';
          for (const s of A.staves) {
            g.strokeStyle = 'rgba(255,0,0,.35)'; g.strokeRect(s.x0, s.top, s.x1 - s.x0, s.bottom - s.top);
            for (const b of s.bars) { g.strokeStyle = 'magenta'; g.beginPath(); g.moveTo(b.x, s.top - 10); g.lineTo(b.x, s.bottom + 10); g.stroke(); }
            for (const hd of s.heads) {
              g.strokeStyle = hd.kind === 'black' ? 'lime' : hd.kind === 'half' ? 'blue' : 'orange';
              g.strokeRect(hd.x, hd.y - s.sp * 0.5, hd.w, s.sp);
              if (hd.stem) { g.strokeStyle = 'cyan'; g.beginPath(); g.moveTo(hd.stem.x, hd.y); g.lineTo(hd.stem.x, hd.stem.end); g.stroke(); }
              g.fillStyle = 'red'; const lab = (hd.beams ? 'b' + hd.beams : '') + (hd.dots ? '.' : '') + (hd.acc !== undefined && hd.acc !== null ? ['bb','b','n','#','x'][hd.acc + 2] : '') + (hd.art.length ? '[' + hd.art.join(',') + ']' : '');
              if (lab) g.fillText(lab, hd.x, hd.y + s.sp * 2.4 + (hd.p % 2) * 12);
            }
            for (const r of s.rests) { g.fillStyle = 'rgba(255,140,0,.9)'; g.fillText('r' + r.t, r.x, s.top - 6); g.strokeStyle = 'orange'; g.strokeRect(r.x, s.top, r.w, s.bottom - s.top); }
            g.fillStyle = 'purple'; g.fillText((s.clef || '?') + ' k' + s.key + ' ' + (s.time ? s.time.join('/') : ''), s.x0, s.top - 22);
          }
          return { png: c.toDataURL('image/png'), n: A.staves.length };
        }""", [data, CROP])
        open(OUT,'wb').write(base64.b64decode(r['png'].split(',')[1])); print('staves', r['n'], errs)
        await b.close()
asyncio.run(main())
