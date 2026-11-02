# The app's own reading of a score (its timeline: times, dynamics, slurs, swells), for one part
import asyncio, json, os, sys
from playwright.async_api import async_playwright
JS = r"""
async ([xml, keep]) => {
  const X = await import('/js/compose/musicxml.js'); const P = await import('/js/compose/playback.js');
  let sc = X.fromMusicXML(xml); sc = sc.score || sc;
  const tl = P.buildTimeline(sc, {});
  const pid = sc.parts[keep].id;
  return tl.notes.filter((n) => n.part === pid).map((n) => ({ t: n.t, dur: n.dur, midi: n.midi, vel: n.vel, connect: !!n.connect, legato: !!n.legato, art: n.art || null, env: n.env || null, vib: n.vib || 0 }));
}
"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1000)
        r = await pg.evaluate(JS, [open(sys.argv[1]).read(), int(sys.argv[3]) if len(sys.argv) > 3 else 0])
        json.dump(r, open(sys.argv[2], 'w')); print(len(r), 'notes'); await b.close()
asyncio.run(main())
