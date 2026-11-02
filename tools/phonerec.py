import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width':390,'height':844}, device_scale_factor=2, has_touch=True, is_mobile=True,
            user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148')
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("""async () => { const { db } = await import('/js/db.js');
          const sr=48000, n=sr*3, d=new Float32Array(n); for (let i=0;i<n;i++) d[i]=Math.sin(i/20)*0.3*Math.sin(i/9000);
          const peaks=[]; for(let i=0;i<400;i++) peaks.push(Math.abs(Math.sin(i/7))*0.5);
          for (let k=0;k<6;k++) { const id='t'+k; await db.put('files',{id:'audio:'+id,data:d}); await db.put('takes',{id,kind:'audio',name:'Recording with a quite long name number '+k+' Bruch Kol Nidrei Adagio',created:Date.now()-k*86400000,sr,dur:3,peaks,peak:0.3,fav:k==1}); }
        }""")
        await pg.evaluate("() => document.querySelector('.tile[data-tile=\"takes\"]').click()"); await pg.wait_for_timeout(900)
        def over():
            return pg.evaluate("""() => { const W=innerWidth; const out=[]; for (const e of document.querySelectorAll('#panel-takes *')) { const r=e.getBoundingClientRect(); if (r.width && (r.right>W+0.5 || r.left< -0.5)) out.push(e.tagName+'#'+e.id+'.'+[...e.classList].join('.')+' '+Math.round(r.left)+'..'+Math.round(r.right)); }
              const sc=[...document.querySelectorAll('#panel-takes, #panel-takes *')].filter(e=>e.scrollWidth>e.clientWidth+1 && getComputedStyle(e).overflowX!='hidden').map(e=>e.tagName+'#'+e.id+'.'+e.className+' '+e.scrollWidth+'/'+e.clientWidth);
              return {out:out.slice(0,15), sc, doc: document.documentElement.scrollWidth}; }""")
        print('list', await over())
        await pg.screenshot(path='/home/claude/shots/phonerec.png')
        await pg.evaluate("() => document.querySelector('#takeList li, #takeList .take')?.click()"); await pg.wait_for_timeout(1200)
        print('open', await over())
        await pg.screenshot(path='/home/claude/shots/phonerec2.png')
        print(errs); await b.close()
asyncio.run(main())
