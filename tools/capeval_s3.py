# Capture against the truth: a real engraved score (Mutopia: LilyPond PDF with its MIDI). Each page
# is read as Capture reads it (all its lines); the notes read are lined up with the MIDI's notes:
# how many are right (pitch, in order), how many missing, how many extra.
import asyncio, json, sys, os, base64, subprocess, glob
from playwright.async_api import async_playwright
sys.path.insert(0, '/home/claude/tools'); from midinotes import read as midi_read
PDF, MIDS = sys.argv[1], sys.argv[2].split(',')
PAGES = [int(x) for x in sys.argv[3].split(',')] if len(sys.argv) > 3 else None
DPI = int(os.environ.get('DPI', '150'))
truth = []
for m in MIDS:
    ns = midi_read(m); groups = []
    for t, p in ns:
        if groups and groups[-1][0] == t: groups[-1][1].add(p)
        else: groups.append([t, {p}])
    truth += [g[1] for g in groups]
def align(read, tru, meta=None):
    # semi-global: the read page is matched in full against any stretch of the truth
    n, m = len(read), len(tru); INF = 10**9
    D = [[0] * (m + 1)] + [[INF] * (m + 1) for _ in range(n)]
    for i in range(1, n + 1):
        D[i][0] = i
        for j in range(1, m + 1):
            r, t = read[i - 1], tru[j - 1]
            hit = 0 if (r & t) else (0.5 if any(abs(a - b) in (1, 12) for a in r for b in t) else 1)
            D[i][j] = min(D[i-1][j-1] + hit, D[i-1][j] + 1, D[i][j-1] + 1)
    j = min(range(m + 1), key=lambda q: D[n][q]); end = j
    i = n; ok = semi = sub = ins = dele = 0; errs = []
    while i > 0 and j > 0:
        r, t = read[i - 1], tru[j - 1]
        hit = 0 if (r & t) else (0.5 if any(abs(a - b) in (1, 12) for a in r for b in t) else 1)
        if D[i][j] == D[i-1][j-1] + hit:
            if hit == 0: ok += 1
            elif hit == 0.5: semi += 1; errs.append(('off', meta[i-1] if meta else None, sorted(r), sorted(t)))
            else: sub += 1; errs.append(('wrong', meta[i-1] if meta else None, sorted(r), sorted(t)))
            i -= 1; j -= 1
        elif D[i][j] == D[i-1][j] + 1: ins += 1; errs.append(('extra', meta[i-1] if meta else None, sorted(r), None)); i -= 1
        else: dele += 1; errs.append(('missing', None, None, sorted(t))); j -= 1
    ins += i
    if os.environ.get('V'):
        for e in reversed(errs): print('   ', e[0], 'bar', e[1]['bar'] if e[1] else '-', 'read', e[2], 'truth', e[3], ('ps %s acc %s clef %s key %s' % (e[1]['ps'], e[1]['acc'], e[1]['clef'], e[1]['key'])) if e[1] else '')
    return {'ok': ok, 'off1': semi, 'wrong': sub, 'extra': ins, 'missing': dele, 'span': end - j}
async def main():
    npages = int(subprocess.run(['pdfinfo', PDF], capture_output=True, text=True).stdout.split('Pages:')[1].split()[0])
    pages = PAGES or list(range(1, npages + 1))
    tmp = '/tmp/claude-0/capeval'; os.makedirs(tmp, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.add_init_script('globalThis.__noShapes3 = ' + ('true' if os.environ.get('NOS3') == '1' else 'false') + ';'); await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(1000)
        if os.environ.get('G'): await pg.evaluate('(g) => Object.assign(globalThis, JSON.parse(g))', os.environ['G'])
        tot = {'ok': 0, 'off1': 0, 'wrong': 0, 'extra': 0, 'missing': 0, 'span': 0}
        for n in pages:
            subprocess.run(['pdftoppm', '-r', str(DPI), '-f', str(n), '-l', str(n), '-png', '-singlefile', PDF, f'{tmp}/p'], check=True)
            data = 'data:image/png;base64,' + base64.b64encode(open(f'{tmp}/p.png', 'rb').read()).decode()
            r = await pg.evaluate("""async (src) => {
              const O = await import('/js/omr.js'); const M = await import('/js/compose/model.js');
              const img = new Image(); img.src = src; await img.decode();
              const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height); g.drawImage(img, 0, 0);
              const r = await O.recogniseBest(c, { lines: 'all' });
              if (!r) return [];
              const BOT = { treble: 30, bass: 18, alto: 24, tenor: 22 };
              const out = []; let key = r.key || 0, clef = r.clef || 'treble';
              r.bars.forEach((bar, bi) => {
                const ch = (r.changes && r.changes[bi]) || {};
                if (ch.key !== undefined) key = ch.key; if (ch.clef) clef = ch.clef;
                const accs = new Map();
                for (const it of bar) {
                  if (it.clef) clef = it.clef;
                  if (it.rest || !it.ps || !it.ps.length || it.grace) continue;
                  const set = [];
                  for (const q of it.ps) {
                    const s = (BOT[it.clef || clef] ?? 30) + q;
                    let a = it.acc && it.acc[q] !== undefined && it.acc[q] !== null ? it.acc[q] : accs.has(s) ? accs.get(s) : M.keyAlter(key, s);
                    if (it.acc && it.acc[q] !== undefined && it.acc[q] !== null) accs.set(s, it.acc[q]);
                    set.push(M.midiOf(s, a));
                  }
                  out.push({ set, bar: bi + 1, ps: it.ps, acc: it.acc || null, clef: it.clef || clef, key });
                }
              });
              return out;
            }""", data)
            read = [set(x['set']) for x in r]; meta = r
            a = align(read, truth, meta) if read else {'ok': 0, 'off1': 0, 'wrong': 0, 'extra': 0, 'missing': 0, 'span': 0}
            for k in tot: tot[k] += a[k]
            acc = a['ok'] / max(1, a['ok'] + a['off1'] + a['wrong'] + a['extra'] + a['missing'])
            print(f'page {n}: read {len(read)} notes, right {a["ok"]}, a step off {a["off1"]}, wrong {a["wrong"]}, extra {a["extra"]}, missing {a["missing"]}  -> {acc*100:.1f}%', flush=True)
        acc = tot['ok'] / max(1, tot['ok'] + tot['off1'] + tot['wrong'] + tot['extra'] + tot['missing'])
        print('TOTAL', json.dumps(tot), f'{acc*100:.1f}%'); print(errs[:3]); await b.close()
asyncio.run(main())
