import asyncio, sys
sys.path.insert(0, '/home/claude/tools/audit')
from base import *
async def main():
    async with async_playwright() as p:
        b, pg, errs = await setup(p, pdf='/home/claude/fixtures/scan10.pdf', vw=1024, vh=1366)
        sid = await J(pg, "return document.querySelector('#grid .card:not(.folder)').dataset.sid")
        await J(pg, f"window.__run.startRun('set', 'Test', [{{sid: '{sid}', a: 1, b: 3}}, {{sid: '{sid}', a: 5, b: 6}}]); await sleep(3000);")
        print('label', await J(pg, "return document.querySelector('#pageLabel').textContent"))
        errs.clear()
        await J(pg, "document.querySelector('#backBtn').click(); await sleep(3000);")
        print('errors after back during set:', errs[:10])
        await b.close()
asyncio.run(main())
