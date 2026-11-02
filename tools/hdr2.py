# Header reading of every staff of an image: clef, key, time and the clef/key traces.  hdr2.py FILE [staff]
import asyncio, json, sys, base64
from playwright.async_api import async_playwright
FILE = sys.argv[1]; ONLY = int(sys.argv[2]) if len(sys.argv) > 2 else None
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(800)
        import os
        if os.environ.get('G'): await pg.evaluate('(g) => { globalThis.G0 = JSON.parse(g); }', os.environ['G'])
        data = 'data:image/png;base64,' + base64.b64encode(open(FILE,'rb').read()).decode()
        r = await pg.evaluate("""async (src) => { const O = await import('/js/omr.js'); const img = new Image(); img.src = src; await img.decode();
          const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; c.getContext('2d').drawImage(img, 0, 0);
          if (globalThis.G0) Object.assign(globalThis, globalThis.G0); const A = await O.analyse(c, true); return A.staves.map((st) => { const s = st._; return { sp: s.sp, top: Math.round(s.top), clef: s.clef, key: s.key, time: s.time, zone: s.head.zone, trace: (s.head.trace || []).filter((t) => !t.inAccDbg && !t.a), signs: s.signs, st: s.signTrace }; }); }""", data)
        for i, s in enumerate(r):
            if ONLY is not None and i != ONLY: continue
            print(f"staff {i} top {s['top']} sp {s['sp']:.1f} clef {s['clef']} key {s['key']} time {s['time']}")
            if ONLY is not None:
                for z in s['zone'] or []: print('  zone', z)
                print('  signs', s['signs'])
                for t in (s['st'] or []):
                    if any(k in t for k in ('cand','clef','pre','near','bassGeo','loose','lead','keyMid','keyMidTrace')): print('  st', t)
                for t in s['trace']: (print("  trace", json.dumps({k:v for k,v in t.items() if k!="rows"})[:400]), [print("   ", r) for r in t.get("rows", [])])
        await b.close()
asyncio.run(main())
