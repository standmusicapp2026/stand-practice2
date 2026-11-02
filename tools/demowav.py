import asyncio, json, os, base64
from playwright.async_api import async_playwright
JS = r"""
async (xml) => {
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const E = await import('/js/compose/editor.js'); const X = await import('/js/compose/musicxml.js'); const P = await import('/js/compose/playback.js');
  await E.createComposition({ title: 'x', insts: ['cello', 'piano'], time: [4, 4], bars: 4 });
  await sleep(800);
  const C = window.__compose;
  const sc = X.fromMusicXML(xml); C.score = sc.score || sc; window.__composeRelayout(); await sleep(1500);
  const blob = await P.renderAudio(C.score);
  const buf = new Uint8Array(await blob.arrayBuffer()); let s = ''; for (let i = 0; i < buf.length; i += 0x8000) s += String.fromCharCode(...buf.subarray(i, i + 0x8000));
  const pdf = new Uint8Array(await (await window.__composeTest.makePdf()).arrayBuffer()); let s2 = ''; for (let i = 0; i < pdf.length; i += 0x8000) s2 += String.fromCharCode(...pdf.subarray(i, i + 0x8000));
  return { wav: btoa(s), pdf: btoa(s2), title: C.score.title, parts: C.score.parts.map(p => p.inst) };
}
"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required']); pg = await (await b.new_context(viewport={'width':1366,'height':1024})).new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); }"); await pg.wait_for_timeout(500)
        r = await pg.evaluate(JS, open('/home/claude/demo/piece.musicxml').read())
        open('/home/claude/demo/Cancao.wav','wb').write(base64.b64decode(r['wav'])); open('/home/claude/demo/Cancao.pdf','wb').write(base64.b64decode(r['pdf']))
        await pg.screenshot(path='/home/claude/demo/screen.png')
        print(r['title'], r['parts'], errs); await b.close()
asyncio.run(main())
