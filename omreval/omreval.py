# Capture quality on real engraved scores (Mutopia cello suites) against their MIDI: every page read
# as Capture reads it (recogniseBest), turned into pitches (clef, key, accidentals) and lengths, and
# lined up with the MIDI of the suite (the best matching stretch). Prints, per page: how many of the
# notes read are right (pitch), how many of the score's notes were found, how many lengths are right.
#   python3 omreval.py PAGES.json [port]    PAGES.json: [[png, [mid, ...]], ...]
import asyncio, base64, json, os, sys
import mido
from playwright.async_api import async_playwright
CASES = json.load(open(sys.argv[1])); PORT = sys.argv[2] if len(sys.argv) > 2 else '8765'
def gt_of(mids):
    seq = []
    for f in mids:
        m = mido.MidiFile(f); tpb = m.ticks_per_beat; ev = []
        for t in m.tracks:
            now = 0; on = {}
            for msg in t:
                now += msg.time
                if msg.type == 'note_on' and msg.velocity > 0: on[msg.note] = now
                elif msg.type in ('note_off', 'note_on') and msg.note in on: s = on.pop(msg.note); ev.append((s, now - s, msg.note))
        ev.sort(); i = 0
        while i < len(ev):
            j = i; grp = []
            while j < len(ev) and ev[j][0] - ev[i][0] <= tpb // 48: grp.append(ev[j]); j += 1
            nxt = ev[j][0] if j < len(ev) else ev[i][0] + max(g[1] for g in grp)
            seq.append((sorted({g[2] for g in grp}), round((nxt - ev[i][0]) * 480 / tpb)))
            i = j
    return seq
def align(read, gt):
    # local alignment: a read note matches a score note when they share a pitch
    n, m = len(read), len(gt)
    H = [[0] * (m + 1) for _ in range(n + 1)]; P = [[0] * (m + 1) for _ in range(n + 1)]
    best = (0, 0, 0)
    for i in range(1, n + 1):
        ri = set(read[i - 1][0])
        for j in range(1, m + 1):
            gj = set(gt[j - 1][0])
            s = 2 if ri & gj else -1
            c = [0, H[i - 1][j - 1] + s, H[i - 1][j] - 1, H[i][j - 1] - 1]
            k = max(range(4), key=lambda q: c[q]); H[i][j] = c[k]; P[i][j] = k
            if c[k] > best[0]: best = (c[k], i, j)
    _, i, j = best; pairs = []; ie, je = i, j
    while i > 0 and j > 0 and H[i][j] > 0:
        k = P[i][j]
        if k == 1: pairs.append((i - 1, j - 1)); i -= 1; j -= 1
        elif k == 2: i -= 1
        elif k == 3: j -= 1
        else: break
    return pairs, (i, ie), (j, je)
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1200)
        tot = dict(read=0, right=0, gt=0, found=0, dur=0, durok=0)
        gtc = {}
        for png, mids in CASES:
            data = ('data:image/jpeg;base64,' if png.endswith('.jpg') else 'data:image/png;base64,') + base64.b64encode(open(png, 'rb').read()).decode()
            r = await pg.evaluate("""async (src) => {
              const O = await import('/js/omr.js'); const M = await import('/js/compose/model.js');
              const img = new Image(); img.src = src; await img.decode();
              const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; c.getContext('2d').drawImage(img, 0, 0);
              const t0 = performance.now(); const r = await O.recogniseBest(c, {}); const ms = performance.now() - t0;
              if (!r) return { seq: [], ms };
              let clef = r.clef || 'treble', key = r.key || 0; const seq = [];
              r.bars.forEach((bar, i) => {
                const ch = r.changes[i] || {}; if (ch.clef) clef = ch.clef; if (ch.key !== undefined) key = ch.key;
                for (const it of bar) {
                  const len = Math.round(1920 / it.t * (2 - Math.pow(0.5, it.dots || 0)) * (it.tup ? it.tup.m / it.tup.n : 1));
                  if (it.rest) { if (seq.length) seq[seq.length - 1][2] += it.full ? 0 : len; continue; }
                  const cl = M.CLEFS[it.clef || clef] || M.CLEFS[clef];
                  const ms2 = it.ps.map((p) => { const s = cl.bottom + p; const a = it.acc && it.acc[p] !== undefined ? it.acc[p] : M.keyAlter(key, s); return M.midiOf(s, a) + (it.ott ? (Math.abs(it.ott) < 3 ? it.ott * 12 : it.ott) : 0); });
                  seq.push([ms2, len, 0]);
                }
              });
              return { seq, ms, clef: r.clef, key: r.key, time: r.time, fit: r.fitRead, bars: r.bars.length, systems: r.systems };
            }""", data)
            read = [(x[0], x[1]) for x in r['seq']]
            if not read: print(os.path.basename(png), 'NOTHING READ'); continue
            # (several ground truths possible: [[mid, ...], [mid, ...]]: the one that fits best)
            sets = mids if mids and isinstance(mids[0], list) else [mids]
            bestA = None
            for ms_ in sets:
                key = '|'.join(ms_)
                if key not in gtc: gtc[key] = gt_of(ms_)
                gt0 = gtc[key]; A_ = align(read, gt0)
                if not bestA or len(A_[0]) > len(bestA[0][0]): bestA = (A_, gt0)
            (pairs, (ra, rb), (ga, gb)), gt = bestA
            right = len(pairs); span = gb - ga
            durok = sum(1 for i, j in pairs if read[i][1] == gt[j][1])
            if os.environ.get('PCONF'):
                from collections import Counter
                inn = set(i for i, _ in pairs); gj = set(j for _, j in pairs)
                # read notes in the stretch that were not matched: what they were against the score note at the same place
                bad = Counter(); prev = None
                for (i, j), (i2, j2) in zip(pairs, pairs[1:]):
                    if i2 - i == 2 and j2 - j == 2:
                        r_ = read[i + 1][0]; g_ = gt[j + 1][0]
                        bad[(min(r_) - min(g_)) if r_ and g_ else None] += 1
                print('   pitch misreads (read - score, semitones):', bad.most_common(8))
            if os.environ.get('CONF'):
                from collections import Counter
                cf = Counter((gt[j][1], read[i][1]) for i, j in pairs if read[i][1] != gt[j][1])
                print('   length errors (score -> read):', cf.most_common(6))
            tot['read'] += len(read); tot['right'] += right; tot['gt'] += span; tot['dur'] += right; tot['durok'] += durok
            print(f"{os.path.basename(png):22s} read {len(read):4d} right {right / max(1, len(read)) * 100:5.1f}%  found {right / max(1, span) * 100:5.1f}% of {span}  lengths {durok / max(1, right) * 100:5.1f}%  clef {r.get('clef')} key {r.get('key')} time {r.get('time')} fit {r.get('fit', 0):.2f} {r['ms'] / 1000:.1f}s", flush=True)
        print(f"TOTAL pitch right {tot['right'] / max(1, tot['read']) * 100:.1f}%  found {tot['right'] / max(1, tot['gt']) * 100:.1f}%  lengths {tot['durok'] / max(1, tot['dur']) * 100:.1f}%")
        await b.close()
asyncio.run(main())
