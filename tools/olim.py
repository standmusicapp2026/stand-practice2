# Measure the app's reading on OLiMPiC scanned piano systems against their MusicXML.
# olim.py SPLIT N SEED OUT.json [only=sample,...]
# For each system both staves are read (as the app reads one staff of a system) and compared, onset by
# onset, with the ground truth of that staff:
#   pitch: the set of sounding pitches at each onset (chords complete, accidentals and key applied)
#   rhythm: the same with the duration (where all notes of the onset share one duration)
import asyncio, json, sys, random, base64, os, time
import xml.etree.ElementTree as ET
from playwright.async_api import async_playwright

ROOT = '/home/claude/ds/raw/olimpic-1.0-scanned'
SPLIT, N, SEED, OUT = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
ONLY = sys.argv[5].split(',') if len(sys.argv) > 5 else None
STEP = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
TYPE = {'whole': 1, 'half': 2, 'quarter': 4, 'eighth': 8, '16th': 16, '32nd': 32, '64th': 64, 'breve': 0.5}

def gt_of(path):
    """per staff: list of measures, each a list of (onset, sorted midi tuple, dur or None, rest)"""
    root = ET.parse(path).getroot()
    out = {1: [], 2: []}
    div = 1
    for meas in root.iter('measure'):
        cur = 0; last_on = 0
        ev = {1: {}, 2: {}}
        for el in meas:
            if el.tag == 'attributes':
                d = el.find('divisions')
                if d is not None: div = int(d.text)
            elif el.tag == 'backup': cur -= int(el.find('duration').text)
            elif el.tag == 'forward': cur += int(el.find('duration').text)
            elif el.tag == 'note':
                if el.find('grace') is not None: continue
                st = int(el.find('staff').text) if el.find('staff') is not None else 1
                dur = int(el.find('duration').text) if el.find('duration') is not None else 0
                on = last_on if el.find('chord') is not None else cur
                if el.find('chord') is None: last_on = cur; cur += dur
                ty = el.find('type'); t = TYPE.get(ty.text) if ty is not None else None
                dots = len(el.findall('dot'))
                e = ev[st].setdefault(on, {'p': set(), 'd': set(), 'rest': True})
                if el.find('rest') is not None:
                    e['d'].add((t, dots, 'r'))
                    continue
                pt = el.find('pitch'); s = pt.find('step').text; o = int(pt.find('octave').text); a = pt.find('alter'); a = int(float(a.text)) if a is not None else 0
                e['p'].add(12 * (o + 1) + STEP[s] + a); e['d'].add((t, dots, 'n')); e['rest'] = False
                if el.find('accidental') is not None: e.setdefault('acc', set()).add(12 * (o + 1) + STEP[s] + a)
        for st in (1, 2):
            m = []
            for on in sorted(ev[st]):
                e = ev[st][on]
                if e['rest'] and not e['p']:
                    ds = [d for d in e['d'] if d[2] == 'r']
                    m.append((on, None, (ds[0][0], ds[0][1]) if len(ds) == 1 else None, True))
                else:
                    ds = {(d[0], d[1]) for d in e['d'] if d[2] == 'n'}
                    m.append((on, tuple(sorted(e['p'])), ds.pop() if len(ds) == 1 else None, False, tuple(sorted(e.get('acc', ())))))
            out[st].append(m)
    k = root.find('.//key/fifths'); out['key'] = int(k.text) if k is not None else 0
    out['clefSeq'] = {1: [], 2: []}
    for c in root.iter('clef'):
        out['clefSeq'][int(c.get('number', '1'))].append(c.find('sign').text + c.find('line').text)
    cl = {}
    for c in root.iter('clef'):
        n = int(c.get('number', '1'))
        if n not in cl: cl[n] = c.find('sign').text + c.find('line').text
    out['clefs'] = cl
    return out

def lcs(A, B, eq):
    n, m = len(A), len(B)
    if not n or not m: return 0
    prev = [0] * (m + 1)
    for i in range(n - 1, -1, -1):
        cur = [0] * (m + 1)
        for j in range(m - 1, -1, -1):
            cur[j] = prev[j + 1] + 1 if eq(A[i], B[j]) else max(prev[j], cur[j + 1])
        prev = cur
    return prev[0]

JS = """async ([src, staff]) => {
  const O = await import('/js/omr.js');
  const img = new Image(); img.src = src; await img.decode();
  const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; c.getContext('2d').drawImage(img, 0, 0);
  const t0 = performance.now();
  // (the piano's two staves are the last two of the system: a voice part above may be cut in)
  let r = await O.recogniseBest(c, { staff: 99 });
  if (r && staff === 0) { const n = r.systems === 1 ? r.staves : 2; r = await O.recogniseBest(c, { staff: Math.max(0, n - 2) }); }
  if (!r) return null;
  const BOT = { treble: 30, bass: 18, alto: 24, tenor: 22 };
  const SH = [3, 0, 4, 1, 5, 2, 6], FL = [6, 2, 5, 1, 4, 0, 3];      // letters (C=0) in sharp / flat order
  const SEMI = [0, 2, 4, 5, 7, 9, 11];
  let key = r.key || 0;
  const bars = r.bars.map((b, i) => {
    if (r.changes && r.changes[i] && r.changes[i].key !== undefined) key = r.changes[i].key;
    const kAlt = (letter) => key > 0 ? (SH.slice(0, key).includes(letter) ? 1 : 0) : key < 0 ? (FL.slice(0, -key).includes(letter) ? -1 : 0) : 0;
    return b.map((it) => {
      if (it.rest) return { rest: true, t: it.full ? 1 : it.t, dots: it.dots || 0, full: !!it.full };
      const cl = it.clef || r.clef;
      const midi = it.ps.map((p) => { const s = (BOT[cl] ?? 30) + p; const letter = ((s % 7) + 7) % 7, oct = Math.floor(s / 7); const a = it.acc && it.acc[p] !== undefined && it.acc[p] !== null ? it.acc[p] : kAlt(letter); return 12 * (oct + 1 + (it.ott || 0)) + SEMI[letter] + a; });
      return { cl: cl, wacc: Object.keys(it.acc || {}).filter((k) => it.acc[k] !== null && it.acc[k] !== undefined).length, t: it.t, dots: it.dots || 0, tup: !!it.tup, midi: [...new Set(midi)].sort((a, b) => a - b) };
    });
  });
  return { ms: Math.round(performance.now() - t0), clef: r.clef, key: r.key, time: r.time, bars, spo: r.analysis ? r.analysis.sp : 0 };
}"""

async def main():
    ids = [l.strip() for l in open(f'{ROOT}/samples.{SPLIT}.txt') if l.strip()]
    random.Random(SEED).shuffle(ids)
    ids = ids[:N] if not ONLY else [i for i in ids if any(i.endswith(o) for o in ONLY)]
    res = []
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(1000)
        for k, sid in enumerate(ids):
            src = 'data:image/png;base64,' + base64.b64encode(open(f'{ROOT}/{sid}.png', 'rb').read()).decode()
            gt = gt_of(f'{ROOT}/{sid}.musicxml')
            row = {'id': sid, 'staves': []}
            for st in (0, 1):
                try: r = await asyncio.wait_for(pg.evaluate(JS, [src, st]), 120)
                except Exception as e: r = None; row['err'] = str(e)[:200]
                g = gt[st + 1]
                G = [x for m in g for x in m if not x[3]]
                R = [it for bar in (r['bars'] if r else []) for it in bar if not it.get('rest')]
                gp = [x[1] for x in G]; rp = [tuple(it['midi']) for it in R]
                pitch = lcs(gp, rp, lambda a, b: a == b)
                gr = [(x[1], x[2]) for x in G]; rr = [(tuple(it['midi']), (it['t'], it['dots'])) for it in R]
                rhy = lcs(gr, rr, lambda a, b: a[0] == b[0] and (a[1] is None or a[1] == b[1]))
                # (the notes alone, each pitch, whatever it is sounded with)
                gn = [m for x in G for m in x[1]]; rn = [m for it in R for m in it['midi']]
                notes = lcs(gn, rn, lambda a, b: a == b)
                row['staves'].append({'gt': len(G), 'read': len(R), 'pitch': pitch, 'rhythm': rhy, 'gtNotes': len(gn), 'readNotes': len(rn), 'notes': notes,
                                      'gp': [list(x) for x in gp], 'rp': [list(x) for x in rp], 'gacc': [list(x[4]) for x in G], 'racc': [it.get('wacc', 0) for it in R], 'bars': len(r['bars']) if r else 0, 'gtBars': len(g), 'ms': r['ms'] if r else 0, 'key': r['key'] if r else None, 'gtKey': gt['key'],
                                      'spo': r.get('spo', 0) if r else 0, 'clef': r['clef'] if r else None, 'gtClef': gt['clefs'].get(st + 1), 'gtClefSeq': gt['clefSeq'][st + 1], 'rClefSeq': [c for k, c in enumerate([it['cl'] for it in R]) if k == 0 or c != R[k - 1]['cl']]})
            res.append(row)
            if (k + 1) % 10 == 0: print(k + 1, time.strftime('%H:%M:%S'), flush=True)
        await b.close()
    json.dump(res, open(OUT, 'w'))
    tot = lambda f: sum(s[f] for r in res for s in r['staves'])
    print(f"notes recall {tot('notes')/max(1,tot('gtNotes'))*100:.1f}% precision {tot('notes')/max(1,tot('readNotes'))*100:.1f}%  ", end='')
    print(f"systems {len(res)}  onsets {tot('gt')}  read {tot('read')}  pitch {tot('pitch')/max(1,tot('gt'))*100:.1f}%  rhythm {tot('rhythm')/max(1,tot('gt'))*100:.1f}%  "
          f"bars {sum(1 for r in res for s in r['staves'] if s['bars'] == s['gtBars'])}/{len(res)*2} staves right  key {sum(1 for r in res for s in r['staves'] if s['key'] == s['gtKey'])}  "
          f"clef {sum(1 for r in res for s in r['staves'] if (s['clef'], s['gtClef']) in (('treble','G2'),('bass','F4'),('alto','C3'),('tenor','C4')))}  time {tot('ms')/1000/max(1,len(res)):.1f}s/system")

asyncio.run(main())
