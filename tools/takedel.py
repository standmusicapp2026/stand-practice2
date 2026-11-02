# Delete a recording: the list of the others shows again and they open
import asyncio, os
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width': 1366, 'height': 1024})).new_page()
        await pg.add_init_script('window.__noTour = true;'); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); }")
        r = await pg.evaluate("""async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); const { db } = await import('/js/db.js');
          for (const id of ['tk1','tk2']) { const pcm = new Float32Array(48000).map((_, i) => Math.sin(i / 20) * 0.3);
            await db.put('files', { id: 'audio:' + id, data: pcm }); await db.put('takes', { id, kind: 'audio', name: 'Take ' + id, created: Date.now(), sr: 48000, dur: 1, peaks: new Float32Array(200).fill(0.3), peak: 0.3 }); }
          document.querySelector('.tile[data-panel=takes]').click(); await sleep(800);
          const items = () => [...document.querySelectorAll('#panel-takes li.take')].filter((x) => x.offsetParent);
          const n0 = items().length; items()[0].click(); await sleep(800);
          const open1 = !document.querySelector('#player').hidden;
          document.querySelector('#delTake').click(); await sleep(100); document.querySelector('#delYes').click(); await sleep(800);
          const n1 = items().length; if (n1) items()[0].click(); await sleep(800);
          return { n0, open1, afterDelete: n1, opensAgain: !document.querySelector('#player').hidden }; }""")
        print(r, errs[:3]); await b.close()
asyncio.run(main())
