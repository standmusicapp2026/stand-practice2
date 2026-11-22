import asyncio, base64, zipfile, io, os, shutil, json
from playwright.async_api import async_playwright
# Another Stand's library brought in: its Stand folder (the backup kept up to date, the copies of its
# scores, old backup zips), a backup zip, or a backup Files unzipped. Everything must come back as it
# was: folders, titles, markings, recordings, videos (not their cover pictures as scores), nothing twice.
F = '/home/claude/fixtures/'
W = '/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad/bringstand'
PORT = os.environ.get('PORT', '8765')
URL = 'http://localhost:' + PORT + '/index.html'

MAKE = """async () => {
  const { db } = await import('/js/db.js'); const B = await import('/js/backup.js');
  const sc = await db.all('scores');
  const folders = [{ id: 'f1', name: 'Concertos', created: 1 }, { id: 'f2', name: 'Partituras', created: 2 }, { id: 'f3', name: 'Empty folder', created: 3 }];
  await db.put('kv', { k: 'folders', v: folders });
  sc[1].folder = 'f1'; sc[1].title = 'Violin Concerto in E minor, Op. 64'; sc[1].composer = 'Felix Mendelssohn'; await db.put('scores', sc[1]);
  sc[0].folder = 'f2'; sc[0].title = 'Sonata Op. 3 (my edition)'; sc[0].composer = ''; await db.put('scores', sc[0]);
  const c = document.createElement('canvas'); c.width = 60; c.height = 80; const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, 60, 80); g.fillStyle = '#000'; g.fillRect(5, 20, 50, 2);
  const jpg = await new Promise((r) => c.toBlob(r, 'image/jpeg'));
  await db.put('files', { id: 'imgf', kind: 'images', data: [jpg, jpg, jpg] }); await db.put('scores', { id: 'imgs', fileId: 'imgf', title: 'Étude photographed', composer: '', pages: 3, added: Date.now(), folder: 'f1' });
  const pcm = new Float32Array(48000); for (let i = 0; i < pcm.length; i++) pcm[i] = Math.sin(i / 10) * 0.5;
  await db.put('files', { id: 'audio:tk', data: pcm }); await db.put('takes', { id: 'tk', kind: 'audio', name: 'Bruch take', created: Date.now(), sr: 48000, dur: 1, scoreId: sc[0].id });
  const mp4 = new Blob([new Uint8Array(5000).map((_, i) => i % 251)], { type: 'video/mp4' });
  await db.put('files', { id: 'video:vd', data: mp4 }); await db.put('takes', { id: 'vd', kind: 'video', name: 'Video 1', created: Date.now(), dur: 3, mime: 'video/mp4', thumb: jpg, scoreId: sc[1].id });
  await db.put('ink', { key: sc[1].id + ':0', items: [{ t: 'pen', pts: [1, 2, 3] }] });
  const summary = async () => { const s = await db.all('scores'); const f = (await db.get('kv', 'folders')).v; return { scores: s.map((x) => [x.title, x.composer || '', (f.find((y) => y.id === x.folder) || {}).name || '']).sort(), folders: f.map((x) => x.name).sort(), takes: (await db.all('takes')).map((t) => t.kind + ':' + t.name).sort(), ink: (await db.all('ink')).length }; };
  const want = await summary();
  const b64 = (blob) => new Promise((res) => { const r = new FileReader(); r.onload = () => res(String(r.result).split(',')[1]); r.readAsDataURL(blob); });
  const vols = await B.makeFolderBackup(true, '9 Nov 2026', folders);
  const zips = []; for (const v of vols) zips.push([v.name, await b64(v.blob)]);
  const mirror = [];
  const { lib } = await B.makeMirror(async (b) => { mirror.push([b.path, await b64(b.blob || b.make())]); });
  mirror.push(['Stand library.json', await b64(lib)]);
  // Stand's own copies of the PDF scores (Files › Stand › Scores)
  const copies = [];
  for (const s of await db.all('scores')) { const f = await db.get('files', s.fileId); if (!f || f.kind !== 'pdf') continue; const fo = folders.find((x) => x.id === s.folder);
    copies.push(['Scores/' + (fo ? fo.name + '/' : '') + (s.composer ? s.composer + ' - ' : '') + s.title + '.pdf', await b64(new Blob([f.data]))]); }
  return { want, zips, mirror, copies };
}"""

SUMMARY = """async () => { const { db } = await import('/js/db.js'); const s = await db.all('scores'); const fk = await db.get('kv', 'folders'); const f = fk ? fk.v : [];
  const v = await db.get('files', 'video:vd');
  return { scores: s.map((x) => [x.title, x.composer || '', (f.find((y) => y.id === x.folder) || {}).name || '']).sort(), folders: f.map((x) => x.name).sort(), takes: (await db.all('takes')).map((t) => t.kind + ':' + t.name).sort(), ink: (await db.all('ink')).length,
    video: v ? [v.data.type, v.data.size] : null, imgPages: ((await db.get('files', 'imgf')) || { data: [] }).data.length }; }"""

def write(root, rel, b64):
    p = os.path.join(root, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'wb').write(base64.b64decode(b64))

def listing(root):
    out = []
    for d, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(d, f); out.append({'rel': os.path.relpath(p, root), 'size': os.path.getsize(p)})
    return sorted(out, key=lambda x: x['rel'])

async def fresh(p, root):
    b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width': 1366, 'height': 1024})
    async def serve(route):
        rel = route.request.url.split('/__picked/', 1)[1]
        from urllib.parse import unquote
        path = os.path.join(root, unquote(rel))
        if os.path.isfile(path): await route.fulfill(status=200, body=open(path, 'rb').read())
        else: await route.fulfill(status=404, body='')
    await ctx.route('**/__picked/**', serve)
    pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.goto(URL); await pg.wait_for_timeout(1500)
    await pg.evaluate("() => document.querySelector('#welGo')?.click()"); await pg.wait_for_timeout(300)
    return b, pg, errs

async def main():
    fails = 0
    def check(n, ok, x=''):
        nonlocal fails; print(('PASS ' if ok else 'FAIL ') + n, '' if ok else x); fails += 0 if ok else 1
    shutil.rmtree(W, ignore_errors=True); os.makedirs(W)
    async with async_playwright() as p:
        b, pg, errs = await fresh(p, W)
        await pg.set_input_files('#importInput', [F + 'vector8.pdf', F + 'titles/c.pdf', F + 'scan10.pdf']); await pg.wait_for_timeout(6000)
        made = await pg.evaluate(MAKE)
        want = made['want']; print('want', json.dumps(want))
        await b.close()
        # 1. the old app's Stand folder: Backup (kept up to date), Scores (copies), Backups (an old zip)
        D1 = W + '/old'
        for rel, d in made['mirror']: write(D1, 'Stand/Backup/' + rel, d)
        for rel, d in made['copies']: write(D1, 'Stand/' + rel, d)
        for name, d in made['zips']: write(D1, 'Stand/Backups/' + name, d)
        write(D1, 'Stand/Backup/Read me.txt', base64.b64encode(b'x').decode())
        # 2. a backup zip that Files unzipped (tapped), next to a loose PDF of another score
        D2 = W + '/unzipped'
        for name, d in made['zips']:
            z = zipfile.ZipFile(io.BytesIO(base64.b64decode(d)))
            for n in z.namelist(): write(D2, name[:-4] + '/' + n, base64.b64encode(z.read(n)).decode())
        shutil.copy(F + 'titles/c.pdf', D2 + '/Bach - Cello Suite No. 2.pdf')
        # 3. a folder holding only backup zips
        D3 = W + '/zips'
        for name, d in made['zips']: write(D3, name, d)
        KINDS = {'pdf', 'jpg', 'jpeg', 'png', 'heic', 'heif', 'tif', 'tiff', 'zip', '4sb', '4sc', 'standbackup', 'json', 'mov', 'mp4', 'm4v', 'webm', 'wav', 'm4a', 'bin', 'f32', 'i16', 'u8'}
        for label, root, extra in [('Stand folder of the old app', D1, 0), ('unzipped backup + a loose PDF', D2, 1), ('backup zips in a folder', D3, 0)]:
            files = [f for f in listing(root) if f['rel'].rsplit('.', 1)[-1].lower() in KINDS]
            b, pg, errs = await fresh(p, root)
            await pg.evaluate("(m) => { window.standFolder(m); }", {'name': os.path.basename(root), 'files': files})
            # (Stand starts again once it is all in)
            for _ in range(60):
                await pg.wait_for_timeout(1000)
                try:
                    t = await pg.evaluate("() => document.querySelector('#toast') && !document.querySelector('#toast').hidden ? document.querySelector('#toast').textContent : ''")
                except Exception: t = ''
                if 'Starting again' in t: print('  toast:', t); break
            await pg.wait_for_timeout(4500)
            got = await pg.evaluate(SUMMARY)
            check(label + ': the same scores, titles, composers and folders', got['scores'][:len(want['scores'])] == want['scores'] if not extra else [x for x in got['scores'] if 'Cello Suite No. 2' not in x[0]] == want['scores'], json.dumps(got['scores'], ensure_ascii=False))
            if extra: check(label + ': the loose PDF came in too, titled from its name', any(x[0] == 'Cello Suite No. 2' and 'Bach' in x[1] for x in got['scores']), got['scores'])
            check(label + ': nothing twice, no cover pictures as scores', len(got['scores']) == len(want['scores']) + extra, len(got['scores']))
            check(label + ': every folder, the empty one too', set(want['folders']) <= set(got['folders']), got['folders'])
            check(label + ': recordings and the video as a video', got['takes'] == want['takes'] and got['video'] and got['video'][0] == 'video/mp4' and got['video'][1] == 5000, [got['takes'], got['video']])
            check(label + ': markings and the photographed pages', got['ink'] == want['ink'] and got['imgPages'] == 3, [got['ink'], got['imgPages']])
            check(label + ': no page errors', not errs, errs)
            await b.close()
        # 4. the backup zip opened in Stand ("Open in Stand", or Bring › archive)
        b, pg, errs = await fresh(p, W)
        name, d = made['zips'][0]
        await pg.evaluate("async ([n, d]) => { const bin = Uint8Array.from(atob(d), (c) => c.charCodeAt(0)); window.__bring.bringArchive(new File([bin], n)); }", [name, d])
        await pg.wait_for_timeout(9000)
        got = await pg.evaluate(SUMMARY)
        check('backup zip opened: all back', got['scores'] == want['scores'] and got['takes'] == want['takes'], json.dumps(got, ensure_ascii=False))
        check('backup zip opened: no page errors', not errs, errs)
        await b.close()
    print('ALL PASS' if not fails else f'{fails} FAIL')
asyncio.run(main())
