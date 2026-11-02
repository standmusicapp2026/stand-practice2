# Every screen size Stand runs on (iPad mini to iPad Pro 13", upright and sideways; small and big
# iPhones): the main screens and every panel are opened, and checked for things cut off by the edge
# of the screen, the page scrolling sideways, buttons too small to tap, and buttons covering each
# other. Screenshots in /tmp/claude-0/layouts/.
import asyncio, os, json
from playwright.async_api import async_playwright
FIX = '/home/claude/fixtures/'
OUT = '/tmp/claude-0/layouts'; os.makedirs(OUT, exist_ok=True)
SIZES = [('ipad-mini-up', 744, 1133, False), ('ipad-mini-side', 1133, 744, False), ('ipad-11-up', 820, 1180, False), ('ipad-13-side', 1376, 1032, False),
         ('iphone-se', 375, 667, True), ('iphone-pro-max', 430, 932, True)]
CHECK = r"""
() => {
  const W = innerWidth, H = innerHeight, out = [];
  const vis = (el) => { const r = el.getBoundingClientRect(); if (r.width < 2 || r.height < 2) return null; let e = el; while (e) { if (e.hidden || getComputedStyle(e).display === 'none' || getComputedStyle(e).visibility === 'hidden') return null; e = e.parentElement; } return r; };
  if (document.documentElement.scrollWidth > W + 2) out.push('page scrolls sideways: ' + document.documentElement.scrollWidth + ' > ' + W);
  const btns = [...document.querySelectorAll('button, [role=button], select, input:not([type=hidden]), a[href]')];
  const shown = [];
  for (const b of btns) {
    const r = vis(b); if (!r) continue;
    // inside something that scrolls sideways on purpose (a row of chips): not cut off
    let sc = b.parentElement, scrolls = false; while (sc && sc !== document.body) { const cs = getComputedStyle(sc); if (/(auto|scroll)/.test(cs.overflowX) || /(auto|scroll)/.test(cs.overflowY)) { scrolls = true; break; } sc = sc.parentElement; }
    const name = (b.id ? '#' + b.id + ' ' : '') + (b.getAttribute('aria-label') || b.textContent || b.tagName).trim().replace(/\s+/g, ' ').slice(0, 30);
    if (!scrolls && (r.right > W + 1 || r.left < -1 || r.bottom > H + 1 && getComputedStyle(b).position === 'fixed')) out.push('cut off: ' + name + ' [' + Math.round(r.left) + '..' + Math.round(r.right) + ']');
    if (!scrolls && r.top < H && r.bottom > 0 && r.right > 0 && r.left < W) {
      if (Math.min(r.width, r.height) < 26 && b.tagName !== 'INPUT' && b.tagName !== 'A' && !b.closest('.pthumb') ) out.push('small to tap: ' + name + ' ' + Math.round(r.width) + 'x' + Math.round(r.height));
      shown.push([b, r, name]);
    }
  }
  // buttons covering each other (the one on top hides most of the other)
  for (let i = 0; i < shown.length; i++) for (let j = i + 1; j < shown.length; j++) {
    const [a, ra, na] = shown[i], [b, rb, nb] = shown[j];
    if (a.contains(b) || b.contains(a)) continue;
    const ix = Math.max(0, Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left)), iy = Math.max(0, Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top));
    const small = Math.min(ra.width * ra.height, rb.width * rb.height);
    if (ix * iy > small * 0.4) out.push('overlap: ' + na + ' / ' + nb);
  }
  return [...new Set(out)];
}
"""
async def main():
    async with async_playwright() as p:
        br = os.environ.get('BR', 'chromium')
        b = await getattr(p, br).launch()
        total = {}
        for name, w, h, phone in SIZES:
            ua = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148' if phone else None
            ctx = await b.new_context(viewport={'width': w, 'height': h}, has_touch=True, **({'user_agent': ua} if ua else {}), device_scale_factor=2)
            pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
            errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(1500)
            await pg.evaluate("() => { document.querySelector('#welGo')?.click(); setTimeout(() => document.querySelector('.tour-skip')?.click(), 300); }"); await pg.wait_for_timeout(800)
            found = {}
            async def look(tag):
                await pg.wait_for_timeout(500)
                r = await pg.evaluate(CHECK)
                await pg.screenshot(path=f'{OUT}/{name}-{tag}.png')
                if r: found[tag] = r
            await look('home')
            panels = await pg.evaluate("() => [...new Set([...document.querySelectorAll('[data-panel]')].map(b => b.dataset.panel))]")
            for pn in panels:
                if pn in ('record',): continue
                ok = await pg.evaluate("(pn) => { const b = [...document.querySelectorAll('[data-panel=\"' + pn + '\"]')].find(x => x.offsetParent); if (!b) return false; b.click(); return true; }", pn)
                if not ok: continue
                await look('home-panel-' + pn)
                await pg.evaluate("() => { for (const c of document.querySelectorAll('aside.panel:not([hidden]) [data-close]')) c.click(); }"); await pg.wait_for_timeout(300)
            if not phone:
                await pg.set_input_files('#importInput', [FIX + 'vector8.pdf'])
                await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=60000)
                await pg.evaluate("() => document.querySelector('#grid .card:not(.folder)').click()"); await pg.wait_for_timeout(2500)
                await pg.evaluate("() => document.querySelector('.tour-skip')?.click()"); await pg.wait_for_timeout(300)
                await look('score')
                await pg.evaluate("() => document.querySelector('#inkBtn')?.click()"); await look('score-writing')
                await pg.evaluate("() => document.querySelector('#inkBtn')?.click()"); await pg.wait_for_timeout(300)
                spanels = await pg.evaluate("() => [...new Set([...document.querySelectorAll('#score [data-panel]')].filter(b => b.offsetParent).map(b => b.dataset.panel))]")
                for pn in spanels:
                    if pn in ('record',): continue
                    await pg.evaluate("(pn) => document.querySelector('#score [data-panel=\"' + pn + '\"]').click()", pn)
                    await look('score-panel-' + pn)
                    await pg.evaluate("() => { for (const c of document.querySelectorAll('aside.panel:not([hidden]) [data-close]')) c.click(); }"); await pg.wait_for_timeout(300)
            if errs: found['errors'] = errs[:3]
            total[name] = found
            print(name, sum(len(v) for v in found.values()), 'findings', flush=True)
            for k, v in found.items(): print('  ', k, v[:8])
            await ctx.close()
        json.dump(total, open(OUT + '/findings.json', 'w'), indent=1)
        await b.close()
asyncio.run(main())
