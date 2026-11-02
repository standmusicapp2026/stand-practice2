import asyncio, json, os, sys
from playwright.async_api import async_playwright
JS = r"""
async ([xml, g]) => {
  Object.assign(globalThis, g);
  const X = await import('/js/compose/musicxml.js'); const P = await import('/js/compose/playback.js');
  let sc = X.fromMusicXML(xml); sc = sc.score || sc;
  const tl = P.buildTimeline(sc, {});
  const v = tl.notes.map(n => n.vel); v.sort((a,b)=>a-b);
  const q = (p) => v[Math.floor(p * (v.length - 1))];
  return { n: v.length, style: (sc.sound||{}).style, p10: q(0.1), p50: q(0.5), p90: q(0.9), first: tl.notes.slice(0, 24).map(n => +n.vel.toFixed(2)) };
}
"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1000)
        for g in sys.argv[2:]:
            print(g, json.dumps(await pg.evaluate(JS, [open(sys.argv[1]).read(), json.loads(g)])))
        await b.close()
asyncio.run(main())
