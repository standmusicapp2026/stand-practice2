import asyncio, json, os
from playwright.async_api import async_playwright
JS = r"""
async () => {
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const E = await import('/js/compose/editor.js'); const M = await import('/js/compose/model.js');
  await E.createComposition({ title: 'Test', insts: ['cello'], time: [4, 4], bars: 8 });
  await sleep(1200);
  const C = window.__compose, T = window.__composeTest;
  const cello = M.staffInfo(C.score)[0];
  const tg = (m, t, p) => ({ staff: { st: cello.st, inst: cello.inst }, meas: { m }, t, p });
  C.tool.dur = 4; for (let m = 2; m < 5; m++) for (let t = 0; t < 4; t++) T.commitWrite(tg(m, t * 480, 2 + t));
  C.score.spans = [{ id: 'sl1', kind: 'slur', st: cello.st.id, v: 1, a: { m: 2, pos: 0 }, b: { m: 3, pos: 0 } }];
  window.__composeRelayout(); await sleep(500);
  const out = {};
  const pi = C.hits.findIndex(h => h && h.spans && h.spans.length); const h = C.hits[pi].spans[0];
  const r = C.pages[pi].pg.getBoundingClientRect(), k = C.pages[pi].k;
  const box = document.querySelector('#cpPages');
  Object.defineProperty(Touch.prototype, 'touchType', { configurable: true, get() { return this.identifier === 1 ? 'stylus' : 'direct'; } });
  // a pen touch on the page: stopped (it never scrolls)
  const tch = new Touch({ identifier: 1, target: box, clientX: r.left + 50, clientY: r.top + 50, touchType: 'stylus' });
  const te = new TouchEvent('touchstart', { bubbles: true, cancelable: true, touches: [tch], changedTouches: [tch] }); box.dispatchEvent(te);
  out.penTouchStopped = te.defaultPrevented;
  const tf = new Touch({ identifier: 2, target: box, clientX: r.left + 50, clientY: r.top + 50, touchType: 'direct' });
  const te2 = new TouchEvent('touchstart', { bubbles: true, cancelable: true, touches: [tf], changedTouches: [tf] }); box.dispatchEvent(te2);
  out.fingerTouchFree = !te2.defaultPrevented;
  // choose the slur, then in Write mode the pen grabs it a little away from the line and drags up
  C.mode = 'write'; C.markSel = { id: 'sl1', kind: 'span', name: 'slur' };
  const cx = r.left + ((h.x0 + h.x1) / 2) * k, cy = r.top + ((h.y0 + h.y1) / 2 + 0.9) * k;
  const pe = (type, x, y) => { const e = new PointerEvent(type, { bubbles: true, cancelable: true, pointerId: 5, pointerType: 'pen', clientX: x, clientY: y, buttons: type === 'pointerup' ? 0 : 1 }); box.dispatchEvent(e); };
  pe('pointerdown', cx, cy); for (let i = 1; i <= 6; i++) { pe('pointermove', cx, cy - i * 6); await sleep(20); } pe('pointerup', cx, cy - 36); await sleep(300);
  out.writeModeHd = C.score.spans[0].hd;
  out.notesStill = C.score.parts[0].staves[0].bars[2].filter(e => !e.rest).length;
  // Select mode: same
  C.mode = 'select'; C.markSel = { id: 'sl1', kind: 'span', name: 'slur' };
  pe('pointerdown', cx, cy); for (let i = 1; i <= 6; i++) { pe('pointermove', cx, cy + i * 4); await sleep(20); } pe('pointerup', cx, cy + 24); await sleep(300);
  out.selectModeHd = C.score.spans[0].hd;
  return out;
}
"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width':1366,'height':1024}, has_touch=True)).new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); }"); await pg.wait_for_timeout(500)
        print(json.dumps(await pg.evaluate(JS)))
        print(errs); await b.close()
asyncio.run(main())
