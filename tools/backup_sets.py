import asyncio, base64, zipfile, io
from playwright.async_api import async_playwright
F='/home/claude/fixtures/'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width':1366,'height':1024})).new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); }")
        await pg.set_input_files('#importInput', [F+'vector8.pdf', F+'titles/c.pdf', F+'scan10.pdf']); await pg.wait_for_timeout(6000)
        r = await pg.evaluate("""async () => {
          const { db } = await import('/js/db.js'); const B = await import('/js/backup.js');
          const sc = await db.all('scores'); sc[1].folder = 'f1'; await db.put('scores', sc[1]);
          // an image score and a recording and some ink
          const c = document.createElement('canvas'); c.width=50; c.height=70; const jpg = await new Promise(r=>c.toBlob(r,'image/jpeg'));
          await db.put('files', { id: 'imgf', kind: 'images', data: [jpg, jpg] }); await db.put('scores', { id: 'imgs', fileId: 'imgf', title: 'My scan', composer: '', pages: 2, added: Date.now() });
          const pcm = new Float32Array(48000); for (let i=0;i<pcm.length;i++) pcm[i]=Math.sin(i/10)*0.5;
          await db.put('files', { id: 'audio:tk', data: pcm }); await db.put('takes', { id: 'tk', kind: 'audio', name: 'Bruch take', created: Date.now(), sr: 48000, dur: 1 });
          await db.put('ink', { key: sc[0].id + ':0', items: [{ t: 'pen', pts: [1,2,3] }] }).catch(async () => { const k = await db.keys('ink'); });
          const before = { scores: (await db.all('scores')).length, files: (await db.all('files')).length, takes: (await db.all('takes')).length, ink: (await db.all('ink')).length };
          const firstPdf = await db.get('files', sc[0].fileId);
          const vols = [...await B.makeBackupSet('library', '24 Oct 2026', [{ id: 'f1', name: 'Concertos' }]), ...await B.makeBackupSet('recordings', '24 Oct 2026', [], ['tk'])];
          const b64 = await Promise.all(vols.map(v => new Promise(res => { const r = new FileReader(); r.onload = () => res(String(r.result).split(',')[1]); r.readAsDataURL(v.blob); })));
          // wipe and restore
          for (const st of ['scores','files','takes','ink']) for (const k of await db.keys(st)) await db.del(st, k);
          const res = await B.restoreBackup(vols.map(v => new File([v.blob], v.name)));
          const after = { scores: (await db.all('scores')).length, files: (await db.all('files')).length, takes: (await db.all('takes')).length, ink: (await db.all('ink')).length };
          const pdf2 = await db.get('files', sc[0].fileId);
          const same = new Uint8Array(firstPdf.data).every((x,i)=> x === new Uint8Array(pdf2.data)[i]) && firstPdf.data.byteLength === pdf2.data.byteLength;
          const a2 = (await db.get('files','audio:tk')).data; const err = Math.max(...Array.from(a2.slice(0,2000)).map((x,i)=>Math.abs(x-pcm[i])));
          const imgs = (await db.get('files','imgf')).data;
          return { before, after, res, same, audioType: a2.constructor.name, audioErr: err, imgs: imgs.map(x=>x.size), names: vols.map(v=>v.name+' '+v.size), b64 };
        }""")
        for i, s in enumerate(r.pop('b64')):
            z = zipfile.ZipFile(io.BytesIO(base64.b64decode(s))); print('zip test', z.testzip()); 
            for n in z.namelist(): print('  ', n)
        print(r); print(errs); await b.close()
asyncio.run(main())
