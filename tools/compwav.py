import asyncio, json, os
from playwright.async_api import async_playwright
JS = r"""
async () => {
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const E = await import('/js/compose/editor.js'); const M = await import('/js/compose/model.js'); const P = await import('/js/compose/playback.js');
  await E.createComposition({ title: 'Test', insts: ['cello', 'piano'], time: [4, 4], bars: 4 });
  await sleep(1000);
  const C = window.__compose, T = window.__composeTest;
  const st = M.staffInfo(C.score)[0];
  C.tool.dur = 4; for (let m = 0; m < 4; m++) for (let t = 0; t < 4; t++) T.commitWrite({ staff: { st: st.st, inst: st.inst }, meas: { m }, t: t * 480, p: t });
  const t0 = performance.now();
  const blob = await P.renderAudio(C.score);
  const v = new DataView(await blob.arrayBuffer());
  const sr = v.getUint32(24, true), bits = v.getUint16(34, true), ch = v.getUint16(22, true), n = v.getUint32(40, true) / (ch * bits / 8);
  let peak = 0; for (let i = 44; i + 2 < v.byteLength; i += 3) { let x = v.getUint8(i) | (v.getUint8(i+1) << 8) | (v.getInt8(i+2) << 16); peak = Math.max(peak, Math.abs(x)); }
  const pdf = await T.makePdf(); const head = new TextDecoder().decode(new Uint8Array(await pdf.slice(0, 5).arrayBuffer()));
  return { sr, bits, ch, secs: +(n / sr).toFixed(2), peakDb: +(20 * Math.log10(peak / 8388607)).toFixed(2), ms: Math.round(performance.now() - t0), mb: +(blob.size / 1e6).toFixed(2), pdf: head, pdfKB: Math.round(pdf.size / 1024) };
}
"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width':1366,'height':1024})).new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); }"); await pg.wait_for_timeout(500)
        print(json.dumps(await pg.evaluate(JS)))
        print(errs); await b.close()
asyncio.run(main())
