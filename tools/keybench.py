# The drone's "It listens", measured: tonal melodies played with the app's cello sound (phrases that
# move mostly by step, lean on the tonic and the fifth, end on long notes, minor with its leading
# note), with real changes of key; and music that must not move it.
# For each piece: how long until the drone is on the new key, how many wrong moves, and the share of
# the time the drone is on the right key.
#   SENS=0.6 (the slider), ONLY=<part of a name>, G='{"__kfX": 1}' (settings to try)
import asyncio, json, os, random, sys
from playwright.async_api import async_playwright
NAMES = ['C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B']
MAJ = [0, 2, 4, 5, 7, 9, 11]; MIN = [0, 2, 3, 5, 7, 8, 10]   # natural minor; 7th raised at cadences
def melody(R, pc, minor, secs, beat=0.42, low=45):
    # a register for the key (cello: tonic between A2 and G#3)
    tonic = low + ((pc - low) % 12)
    sc = MIN if minor else MAJ
    deg = lambda d: tonic + 12 * (d // 7) + sc[d % 7]
    out, t, d = [], 0.0, 0
    weights = {0: 3, 2: 2, 4: 2.5}    # tonic, third, fifth
    while t < secs:
        n = R.choice([6, 8, 8, 10])
        for i in range(n):
            if i == n - 1:
                # the end of a phrase: tonic (or fifth), long; in minor led to by the raised 7th
                d = R.choice([0, 0, 0, 7, 4]) if i else 0
                if minor and d in (0, 7) and R.random() < 0.7:
                    lead = deg(d - 1) + 1; out.append((lead, t, beat * 0.95)); t += beat
                out.append((deg(d), t, beat * 2.8)); t += beat * 3
            else:
                step = R.choice([-1, 1, -1, 1, -2, 2, 0, 3, -3, 4, -4])
                cand = max(-3, min(10, d + step))
                if R.random() < 0.35:
                    cand = R.choices(list(weights), list(weights.values()))[0] + 7 * R.choice([0, 0, 1])
                d = cand
                du = R.choice([1, 1, 1, 0.5, 0.5, 2])
                m = deg(d)
                # minor: the 6th and 7th raised going up now and then (melodic minor)
                if minor and d % 7 in (5, 6) and step > 0 and R.random() < 0.5: m += 1
                out.append((m, t, beat * du * 0.95)); t += beat * du
    return out, t
def piece(seed, parts, beat=0.42):
    R = random.Random(seed); notes, t0, bounds = [], 0.5, []
    for pc, minor, secs in parts:
        mel, dur = melody(R, pc, minor, secs, beat)
        notes += [[m, t0 + t, d, 0.7] for m, t, d in mel]
        bounds.append((t0, t0 + dur, pc, minor)); t0 += dur
    return notes, bounds
def chrom_passing(seed, pc, secs):
    # a major melody with chromatic passing and neighbour notes (as real pieces have): must not move
    R = random.Random(seed); mel, dur = melody(R, pc, False, secs)
    out = []
    for i, (m, t, d) in enumerate(mel):
        if i % 5 == 3 and d < 0.5: out.append([m + R.choice([1, -1]), t, d * 0.5, 0.7]); out.append([m, t + d * 0.5, d * 0.5, 0.7])
        else: out.append([m, t, d, 0.7])
    return out, [(0.5, 0.5 + dur, pc, False)]
def seq(pitches, beat=0.35, start=0.3):
    out, t = [], start
    for p in pitches:
        m, d = p if isinstance(p, tuple) else (p, 1)
        out.append([m, t, beat * d * 0.97, 0.7]); t += beat * d
    return out
def scale(root, octs=2):
    up = [root + 12 * o + s for o in range(octs) for s in MAJ] + [root + 12 * octs]
    return up + up[-2::-1]
# (name, drone's key at the start [pc, minor], notes and the true keys)
def scen():
    S = []
    # the drone on another key at the start: it should find the key you play
    for i, (start, pc, mi) in enumerate([((0, 0), 9, False), ((7, 0), 5, True), ((2, 0), 3, False), ((0, 0), 4, True)]):
        n, b = piece(100 + i, [(pc, mi, 40)]); S.append((f'find {NAMES[pc]}{"m" if mi else ""} (drone on {NAMES[start[0]]})', start, n, b))
    # real changes of key, 35 s each side
    for i, (a, b2) in enumerate([((2, False), (9, False)),   # D → A (to the dominant)
                                 ((0, False), (5, False)),   # C → F (to the subdominant)
                                 ((7, False), (4, True)),    # G → E minor (relative minor)
                                 ((9, True), (0, False)),    # A minor → C (relative major)
                                 ((2, True), (2, False)),    # D minor → D major (parallel)
                                 ((0, False), (3, False)),   # C → Eb (far)
                                 ((10, False), (7, True))]): # Bb → G minor
        n, b = piece(200 + i, [(a[0], a[1], 35), (b2[0], b2[1], 35)])
        S.append((f'{NAMES[a[0]]}{"m" if a[1] else ""} -> {NAMES[b2[0]]}{"m" if b2[1] else ""}', [a[0], int(a[1])], n, b))
    # must not move
    n, b = chrom_passing(300, 7, 45); S.append(('stay: G with chromatic notes', [7, 0], n, b))
    n = seq((scale(43) * 3), 0.3); S.append(('stay: G scales', [7, 0], n, [(0, 99, 7, False)]))
    n = seq(([36 + i for i in range(25)] + [60 - i for i in range(25)]) * 2, 0.25); S.append(('stay: chromatic scale (C)', [0, 0], n, [(0, 99, 0, False)]))
    n = seq([(36, 6), (43, 6), (50, 6), (57, 6), (36, 3), (43, 3), (50, 3), (57, 3)] * 2, 0.5); S.append(('stay: open strings (C)', [0, 0], n, [(0, 99, 0, False)]))
    n, b = piece(400, [(2, True, 45)]); S.append(('stay: D minor melody', [2, 1], n, b))
    return S
def judge(events, start, bounds, secs):
    # the drone's key over time against the true key
    ch = [(0.0, start[0], bool(start[1]))] + [(e[0], int(e[1].rstrip('m')), e[1].endswith('m')) for e in events]
    def drone_at(t):
        k = ch[0]
        for c in ch:
            if c[0] <= t: k = c
        return k[1], k[2]
    def true_at(t):
        for a, b, pc, mi in bounds:
            if a <= t < b: return pc, mi
        return bounds[-1][2], bounds[-1][3]
    ok = tot = 0; t = 1.0
    while t < secs:
        tot += 1; ok += drone_at(t) == true_at(t); t += 0.25
    # time to reach each true key (from its start), or the whole part if never
    lat = []
    prev = (start[0], bool(start[1]))
    for a, b, pc, mi in bounds:
        if (pc, mi) == prev: continue
        hit = next((c[0] for c in ch if c[0] >= a - 0.5 and (c[1], c[2]) == (pc, mi)), None)
        lat.append(round((hit - a) if hit is not None and hit < b else (b - a), 1)); prev = (pc, mi)
    wrong = sum(1 for e in ch[1:] if (e[1], e[2]) != true_at(e[0] + 0.01))
    return ok / max(1, tot), lat, wrong
async def main():
    sens = float(os.environ.get('SENS', '0.6'))
    only = os.environ.get('ONLY')
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(800)
        if os.environ.get('G'): await pg.evaluate('(g) => Object.assign(globalThis, JSON.parse(g))', os.environ['G'])
        await pg.add_script_tag(content=open('/home/claude/tools/keyreal.js').read())
        accs, lats, wrongs = [], [], 0
        for name, start, notes, bounds in scen():
            if only and only not in name: continue
            secs = max(x[1] + x[2] for x in notes) + 1.5
            r = await pg.evaluate("(o) => window.__keyReal(o)", {'notes': notes, 'secs': secs, 'key': start, 'sens': sens})
            acc, lat, wrong = judge(r['events'], start, [(a, min(bb, secs), pc, mi) for a, bb, pc, mi in bounds], secs)
            accs.append(acc); lats += lat; wrongs += wrong
            for sn in (r.get('snaps') or []) if os.environ.get('SNAP') else []: print('    ', sn)
            print(f'{name:34s} on key {acc*100:5.1f}%  time to new key {lat}  wrong moves {wrong}  {[e[:2] for e in r["events"]]}', flush=True)
        print(f'SUMMARY on key {sum(accs)/len(accs)*100:.1f}%  mean time to new key {sum(lats)/max(1,len(lats)):.1f} s  (max {max(lats or [0])})  wrong moves {wrongs}')
        print(errs[:3]); await b.close()
asyncio.run(main())
