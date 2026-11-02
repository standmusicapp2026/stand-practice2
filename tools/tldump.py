# The notes the app plays for a MusicXML file (as its own export would), with times: JSON.
import asyncio, json, os, sys
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(800)
        if os.environ.get('G'): await pg.evaluate('(g) => Object.assign(globalThis, JSON.parse(g))', os.environ['G'])
        r = await pg.evaluate("""async (xml) => { const X = await import('/js/compose/musicxml.js'); const P = await import('/js/compose/playback.js');
          let sc = X.fromMusicXML(xml); sc = sc.score || sc; const tl = P.buildTimeline(sc, { from: 0, humanize: globalThis.__hum ?? true });
          return tl.notes.map(n => ({ t: +(n.t + 0.2).toFixed(4), dur: +n.dur.toFixed(4), midi: n.midi, vel: +n.vel.toFixed(3), part: n.part, m: n.m, pos: n.pos, connect: !!n.connect, legato: !!n.legato })); }""", open(sys.argv[1]).read())
        json.dump(r, open(sys.argv[2], 'w'))
        print(len(r), 'notes')
        await b.close()
asyncio.run(main())
