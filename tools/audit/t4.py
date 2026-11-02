import asyncio, sys
sys.path.insert(0, '/home/claude/tools/audit')
from base import *
async def main():
    async with async_playwright() as p:
        b, pg, errs = await setup(p, pdf='/home/claude/fixtures/scan10.pdf', vw=1024, vh=1366)
        await pg.wait_for_timeout(1500)
        for delay in [0, 30, 80, 150, 300]:
            r = await J(pg, f"""document.querySelector('#grid .card:not(.folder)').click(); await sleep({delay});
              document.querySelector('#backBtn').click(); await sleep(2500);
              return [document.querySelector('#score').hidden, document.querySelector('#library').hidden, document.querySelectorAll('#stage canvas').length, document.body.classList.contains('at-home'), document.querySelector('#score').classList.contains('chrome-off')];""")
            print(delay, r)
        print(errs[:10])
        await b.close()
asyncio.run(main())
