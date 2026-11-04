# Every layout put into a notebook, one after another, as you do it: each makes a page of its own
# (sideways when it is), with what it should have on it, and nothing goes wrong.
import asyncio, os
from playwright.async_api import async_playwright
S = '/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad/lay'
res = []
def ok(c, m): res.append(bool(c)); print('PASS' if c else 'FAIL', m, flush=True)
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width': 1366, 'height': 1024}, has_touch=True); pg = await ctx.new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(1200)
        await pg.evaluate("() => { const w = document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); setTimeout(() => document.querySelector('.tour-skip')?.click(), 300); }"); await pg.wait_for_timeout(700)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
        await J("""document.querySelector('#newNotebookBtn').click(); await sleep(1500);
          document.querySelector('#nbHasCover').checked = false; document.querySelector('#nbHasCover').dispatchEvent(new Event('change'));
          document.querySelector('#nbPapers button[data-v="plain"]').click(); await sleep(300);
          document.querySelector('#nbCreate').click(); await sleep(2500); document.querySelector('.tour-skip')?.click();""")
        cats = await J("return [...document.querySelectorAll('.lay-cats button')].map((b) => b.textContent)")
        if not cats:
            await J("document.querySelector('#inkInsert').click(); await sleep(300); document.querySelector('#insTabs [data-v=\"layouts\"]').click(); await sleep(800);")
            cats = await J("return [...document.querySelectorAll('.lay-cats button')].map((b) => b.textContent)")
        print('categories', cats)
        start = await J("const t = document.querySelector('#pageLabel').textContent; const m = /(\\d+)\\s*$/.exec(t.trim()); return m ? +m[1] : -1;")
        total = 0; bad = []
        for cat in cats:
            names = await J(f"[...document.querySelectorAll('.lay-cats button')].find((b) => b.textContent === '{cat}').click(); await sleep(250); return [...document.querySelectorAll('#insLayouts .ins-layout')].filter((b) => !b.hidden).map((b) => b.textContent)")
            print(cat, len(names), names)
            for i, name in enumerate(names):
                before = await J("const t = document.querySelector('#pageLabel').textContent; const m = /(\\d+)\\s*$/.exec(t.trim()); return m ? +m[1] : -1;")
                r = await J(f"""const bs = [...document.querySelectorAll('#insLayouts .ins-layout')].filter((b) => !b.hidden);
                  if (!bs[{i}]) return 'missing';
                  // (the Insert panel may have closed after the last one: open it again on the same category)
                  if (!bs[{i}].offsetParent) {{ document.querySelector('#inkInsert').click(); await sleep(300); document.querySelector('#insTabs [data-v="layouts"]').click(); await sleep(400); [...document.querySelectorAll('.lay-cats button')].find((b) => b.textContent === '{cat}').click(); await sleep(200); }}
                  [...document.querySelectorAll('#insLayouts .ins-layout')].filter((b) => !b.hidden)[{i}].click(); await sleep(1200);
                  const t = document.querySelector('#pageLabel').textContent; const m = /(\\d+)\\s*$/.exec(t.trim()); return m ? +m[1] : -1;""")
                total += 1
                if r != before + 1: bad.append(f'{name}: pages {before} -> {r}')
        ok(not bad, f'all {total} layouts make a page of their own' + (': ' + '; '.join(bad[:5]) if bad else ''))
        n = await J("const t = document.querySelector('#pageLabel').textContent; const m = /(\\d+)\\s*$/.exec(t.trim()); return m ? +m[1] : -1;")
        ok(n == start + total, f'the notebook has {n} pages ({start} + {total})')
        await pg.screenshot(path=S + '/insert_last.png')
        print(errs[:3]); ok(not errs, 'no page errors')
        print('PASS' if all(res) else 'FAIL', 'every layout goes into a notebook')
        await b.close()
asyncio.run(main())
