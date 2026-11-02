# Render a MusicXML file with the Compose engine (the app's own audio export) -> WAV.
# usage: render.py in.musicxml out.wav [partIndexes e.g. 0 or 0,1] ; env G='{"__x":1}' sets globals first
import asyncio, json, os, sys, base64
from playwright.async_api import async_playwright
JS = r"""
async ([xml, keep, style]) => {
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const X = await import('/js/compose/musicxml.js'); const P = await import('/js/compose/playback.js');
  let sc = X.fromMusicXML(xml); sc = sc.score || sc;
  if (keep) sc.parts = sc.parts.filter((p, i) => keep.includes(i));
  if (style) sc.sound = { ...(sc.sound || {}), style };
  const blob = await P.renderAudio(sc);
  const buf = new Uint8Array(await blob.arrayBuffer()); let s = ''; for (let i = 0; i < buf.length; i += 0x8000) s += String.fromCharCode(...buf.subarray(i, i + 0x8000));
  return btoa(s);
}
"""
async def main():
    src, out = sys.argv[1], sys.argv[2]
    keep = [int(x) for x in sys.argv[3].split(',')] if len(sys.argv) > 3 and sys.argv[3] != '-' else None
    style = sys.argv[4] if len(sys.argv) > 4 else None
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required']); pg = await (await b.new_context()).new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1200)
        if os.environ.get('G'): await pg.evaluate('(g) => Object.assign(globalThis, JSON.parse(g))', os.environ['G'])
        r = await pg.evaluate(JS, [open(src).read(), keep, style])
        open(out, 'wb').write(base64.b64decode(r))
        if errs: print('ERR', errs[:3])
        await b.close()
asyncio.run(main())
