# Read a real scan (or a crop of it) and print what was read, bar by bar, with pitch names.
import asyncio, json, sys, base64
from playwright.async_api import async_playwright
FILE = sys.argv[1]; CROP = [int(v) for v in sys.argv[2].split(',')] if len(sys.argv) > 2 and sys.argv[2] != '-' else None
STAFF = int(sys.argv[3]) if len(sys.argv) > 3 else 0
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1000)
        mime = 'image/jpeg' if FILE.endswith('.jpg') else 'image/png'
        data = 'data:' + mime + ';base64,' + base64.b64encode(open(FILE,'rb').read()).decode()
        r = await pg.evaluate("""async ([src, crop, staff]) => {
          const O = await import('/js/omr.js');
          const img = new Image(); img.src = src; await img.decode();
          const [x, y, w, h] = crop || [0, 0, img.width, img.height];
          const c = document.createElement('canvas'); c.width = w; c.height = h; c.getContext('2d').drawImage(img, -x, -y);
          const r = await O.recognise(c, { staff });
          if (!r) return null;
          const BOT = { treble: 30, bass: 18, alto: 24, tenor: 22 };
          const L = 'CDEFGAB';
          const nm = (p, cl) => { const s = (BOT[cl || r.clef] ?? 30) + p; return L[((s % 7) + 7) % 7] + Math.floor(s / 7); };
          const fmt = (it) => {
            const d = it.t + '.'.repeat(it.dots || 0) + (it.tup ? 't' : '');
            if (it.rest) return 'r' + d;
            return (it.clef && it.clef !== r.clef ? '[' + it.clef + ']' : '') + it.ps.map((p, k) => nm(p, it.clef) + (it.acc && it.acc[p] !== undefined && it.acc[p] !== null ? ['bb','b','n','#','x'][it.acc[p] + 2] : '')).join('+') + '/' + d
              + (it.ties && it.ties.length ? '~' : '') + (it.slurStart ? '(' : '') + (it.slurEnd ? ')' : '') + (it.art && it.art.length ? '[' + it.art.join(',') + ']' : '')
              + (it.dyn ? '{' + it.dyn + '}' : '') + (it.fing ? '<' + it.fing + '>' : '') + (it.txt ? '"' + it.txt + '"' : '') + (it.grace ? '{g' + nm(it.grace.p) + '}' : '');
          };
          return { clef: r.clef, key: r.key, time: r.time, fit: r.fitRead, systems: r.systems, staves: r.staves, bars: r.bars.map((b, i) => (r.changes && Object.keys(r.changes[i] || {}).length ? JSON.stringify(r.changes[i]) + ' ' : '') + b.map(fmt).join(' ')), extra: r.marks || null };
        }""", [data, CROP, STAFF])
        if not r: print('nothing read', errs); return
        print('clef', r['clef'], 'key', r['key'], 'time', r['time'], 'fit', round(r['fit'], 2), 'systems', r['systems'], 'staves', r['staves'])
        for i, bb in enumerate(r['bars']): print(f'{i+1:3d} | {bb}')
        if errs: print(errs)
        await b.close()
asyncio.run(main())
