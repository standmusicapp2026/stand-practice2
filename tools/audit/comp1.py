import asyncio, json, os
from playwright.async_api import async_playwright
JS = """async () => {
  const M = await import('/js/compose/model.js'); const P = await import('/js/compose/playback.js');
  const S = M.newScore({ title: 't', insts: ['violin'], time: [3, 4], key: 2, bars: 4 });
  S.measures[0].tempo = { bpm: 80, beat: 4 };
  M.addBars(S, 1, 0);
  const r1 = [JSON.stringify(S.measures[0]), JSON.stringify(S.measures[1]), M.timeAt(S, 0).join('/'), M.keyAt(S, 0)];
  const S2 = M.newScore({ title: 't', insts: ['violin'], time: [4, 4], key: 0, bars: 4 });
  S2.measures[1].bar = 'repeat'; S2.measures[3].bar = 'repeat';
  const tl = P.buildTimeline ? P.buildTimeline(S2, {}) : null;
  return { bars: r1, order: tl && tl.order };
}"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ['PORT'] + '/index.html'); await pg.wait_for_timeout(1000)
        print(await pg.evaluate(JS)); print(errs); await b.close()
asyncio.run(main())
