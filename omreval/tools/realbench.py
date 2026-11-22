# realbench: Studio on real recordings, as a musician uses it. For each piece of a set: the recording
# imported into Recordings, Studio opened on it, the score's page(s) chosen in the picker (every page,
# "Whole page" on each), the line looked over (Done), Stand follows the playing by itself. Each bar's
# start is then compared with the truth: a bar is missed when it is off by more than a quarter of its
# length. When Capture read a different number of bars than the truth has, the bars are matched in
# order (the most bars that can be right) and the rest count as missed.
#   python3 realbench.py SET  (sets: /home/claude/omreval/<SET>/<SET>.json  { key: { page, wav, T } })
# env: PORT (8766), GLOB (JSON of globals set before the app loads), ONLY (comma list of key prefixes),
#      PART (tune|hold|all: md5(key) % 4 == 0 is "hold"), OUTJ (results JSON), FRESH (reload every N)
import asyncio, hashlib, json, os, sys, time
from playwright.async_api import async_playwright
SET = sys.argv[1]; D = f'/home/claude/omreval/{SET}'
META = json.load(open(f'{D}/{SET}.json'))
PORT = os.environ.get('PORT', '8766'); GLOB = os.environ.get('GLOB', '{}')
ONLY = [x for x in os.environ.get('ONLY', '').split(',') if x]
PART = os.environ.get('PART', 'all'); OUTJ = os.environ.get('OUTJ'); FRESH = int(os.environ.get('FRESH', '6'))
def part(k):
    h = int(hashlib.md5(k.encode()).hexdigest(), 16) % 4 == 0
    return PART == 'all' or (PART == 'hold') == h
keys = [k for k in META if part(k) and (not ONLY or any(k.startswith(o) for o in ONLY))]
def score(T, got):
    """(bars scored, missed, per-bar err, per-bar rel, why)"""
    nb = len(T) - 1
    ok = [i for i in range(nb) if T[i] is not None and T[i + 1] is not None]
    if len(got) == nb:
        err = [None if T[i] is None else got[i] - T[i] for i in range(nb)]
        rel = [None if i not in ok else abs(err[i]) / max(0.3, T[i + 1] - T[i]) for i in range(nb)]
        return len(ok), sum(rel[i] > 0.25 for i in ok), err, rel, None
    # (bars read differently: in order, as many right as can be)
    n, m = len(ok), len(got); H = [[0] * (m + 1) for _ in range(n + 1)]
    for a in range(n - 1, -1, -1):
        i = ok[a]; L = max(0.3, T[i + 1] - T[i])
        for b in range(m - 1, -1, -1):
            hit = 1 if abs(got[b] - T[i]) <= 0.25 * L else 0
            H[a][b] = max(H[a + 1][b], H[a][b + 1], H[a + 1][b + 1] + hit)
    return n, n - H[0][0], [], [], f'count {m} vs {nb}'
def vid(k, wav):
    """the recording as a video (Recordings takes videos): a still black picture and the sound"""
    os.makedirs('/home/claude/omreval/vid', exist_ok=True); out = f'/home/claude/omreval/vid/{SET}_{k}.webm'
    if not os.path.exists(out):
        import subprocess
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=black:s=64x64:r=5', '-i', wav, '-shortest', '-c:v', 'libvpx', '-b:v', '20k', '-c:a', 'libopus', '-b:a', '96k', out], check=True)
    return out
async def waitjs(pg, fn, timeout):
    """(an async check polled until it says yes: wait_for_function takes a promise for a yes)"""
    t0 = time.time()
    while time.time() - t0 < timeout / 1000:
        if await pg.evaluate(fn): return
        await asyncio.sleep(1)
    raise TimeoutError('waited too long: ' + fn[:80])
async def one(pg, k, m):
    J = lambda js, a=None: pg.evaluate("async (a) => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }", a)
    await J("const { db } = await import('/js/db.js'); for (const t of await db.all('takes')) await db.del('takes', t.id);")
    await pg.set_input_files('#takeImportFile', vid(k, m['wav'] if m['wav'].startswith('/') else f'{D}/{m["wav"]}'))
    await waitjs(pg, "async () => { const { db } = await import('/js/db.js'); const t = await db.all('takes'); return t.length > 0 && t[0].pcm; }", 600000)
    tid = await J("const { db } = await import('/js/db.js'); const t = await db.all('takes'); return t[0].id;")
    await J("const S = await import('/js/studio.js'); await S.openStudio(a); await sleep(1500); document.querySelector('.tour-skip')?.click();", tid)
    await waitjs(pg, "async () => { const S = await import('/js/studio.js'); return !!(S._studio.pcm); }", 300000)
    Tend = max(t for t in m['T'] if t is not None)
    await J("const S = await import('/js/studio.js'); const ST = S._studio; ST.P.trim.b = Math.min(ST.dur || 1e9, a + 3); S._studio.P.overlays = S._studio.P.overlays.filter((o) => o.kind !== 'score'); window.__ad = S._addScore();", Tend)
    # (the picker: the PDF, every page whole)
    await pg.wait_for_selector('#pkLib input[type=file]', state='attached', timeout=30000)
    await pg.set_input_files('#pkLib input[type=file]', f'{D}/{m["page"]}')
    for _ in range(40):
        await pg.wait_for_function("() => !document.querySelector('#pkAll').hidden", timeout=180000, polling=300)
        # (Whole page, a few times over: the first tap can come before the page's lines are all in)
        for _ in range(3): await pg.wait_for_timeout(800); await pg.evaluate("() => document.querySelector('#pkAll').click()")
        try: await pg.wait_for_function("() => { if (!document.querySelector('#pkDone').disabled) return true; document.querySelector('#pkAll').click(); return false; }", timeout=60000, polling=1000)
        except Exception:
            await pg.screenshot(path='/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad/pk.png'); raise
        if await pg.evaluate("() => document.querySelector('#pkNext').disabled"): break
        pno = await pg.evaluate("() => document.querySelector('#pkPageNo').textContent")
        await pg.click('#pkNext')
        await pg.wait_for_function("(p) => document.querySelector('#pkPageNo').textContent !== p", arg=pno, timeout=60000)
        await pg.wait_for_timeout(4000)
    await pg.click('#pkDone')
    # (the line looked over: Done)
    await pg.wait_for_function("() => { const b = document.querySelector('#stEraser'); return b && !b.hidden && [...b.querySelectorAll('button')].some((x) => x.textContent.trim() === 'Done'); }", timeout=600000, polling=500)
    await J("[...document.querySelectorAll('#stEraser button')].find((x) => x.textContent.trim() === 'Done').click();")
    await waitjs(pg, "async () => { const S = await import('/js/studio.js'); const o = S._studio.P.overlays.find((q) => q.kind === 'score'); return o && o.syncInfo && o.synced !== 'even'; }", 1200000)
    return await J("const S = await import('/js/studio.js'); const o = S._studio.P.overlays.find((q) => q.kind === 'score'); return { times: o.times, how: o.syncInfo && o.syncInfo.how, feat: o.syncInfo && o.syncInfo.feat || null };")
async def main():
    R = json.load(open(OUTJ)) if OUTJ and os.path.exists(OUTJ) else []
    done = {r['key'] for r in R}
    async with async_playwright() as p:
        b = pg = None; used = 0
        async def fresh():
            nonlocal b, pg, used
            if b:
                try: await b.close()
                except Exception: pass
            b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width': 1366, 'height': 1024})
            pg = await ctx.new_page(); used = 0
            await pg.add_init_script("window.__noTour = true; window.__noTempo = true; Object.assign(globalThis, " + GLOB + ");")
            await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1500)
            await pg.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); }")
        for k in keys:
            if k in done: continue
            m = META[k]
            for attempt in range(2):
                try:
                    if pg is None or used >= FRESH: await fresh()
                    t0 = time.time(); r = await one(pg, k, m); used += 1
                    break
                except Exception as e:
                    print(k, 'error', str(e)[:200], flush=True); r = None; pg = None
            if r is None: R.append({'key': k, 'bars': sum(1 for i in range(len(m['T']) - 1) if m['T'][i] is not None and m['T'][i + 1] is not None), 'miss': None, 'why': 'error'}); continue
            nb, miss, err, rel, why = score(m['T'], r['times'])
            R.append({'key': k, 'bars': nb, 'miss': miss, 'err': err, 'rel': rel, 'why': why, 'how': r['how'], 'conf': r['feat'], 'secs': round(time.time() - t0)})
            print(f"{k:34s} {miss:3d}/{nb:3d} missed  {why or ''}  {round(time.time() - t0)}s", flush=True)
            if OUTJ: json.dump(R, open(OUTJ, 'w'))
        if b: await b.close()
    R = [r for r in R if r['miss'] is not None]
    tb = sum(r['bars'] for r in R); tm = sum(r['miss'] for r in R); bad = [r for r in R if r['why']]
    print(f"TOTAL {SET} {PART}: {len(R)} pieces  {tb} bars  missed {tm} ({tm / max(1, tb) * 100:.1f}%)  [pieces with Capture's bar count wrong: {sum(r['bars'] for r in bad)} bars, {sum(r['miss'] for r in bad)} of them missed]")
asyncio.run(main())
