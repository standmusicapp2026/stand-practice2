# The app's own MIDI export of a MusicXML score
import asyncio, os, sys, base64
from playwright.async_api import async_playwright
JS = r"""
async (xml) => {
  const X = await import('/js/compose/musicxml.js'); const M = await import('/js/compose/midi.js');
  let sc = X.fromMusicXML(xml); sc = sc.score || sc;
  let out = M.toMidi(sc); if (out instanceof Blob) out = new Uint8Array(await out.arrayBuffer());
  let s = ''; for (const b of out) s += String.fromCharCode(b); return btoa(s);
}
"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1000)
        open(sys.argv[2], 'wb').write(base64.b64decode(await pg.evaluate(JS, open(sys.argv[1]).read()))); await b.close()
asyncio.run(main())
