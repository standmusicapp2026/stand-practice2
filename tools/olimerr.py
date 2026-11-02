# What kind of errors: per staff, how much a whole-staff fix (octave, clef) would recover, and on
# the rest, onset by onset (aligned), what is wrong with the chord read.
import json, sys
from collections import Counter
r = json.load(open(sys.argv[1]))

def align(A, B, eq):
    n, m = len(A), len(B)
    L = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            L[i][j] = L[i + 1][j + 1] + 1 if eq(A[i], B[j]) else max(L[i + 1][j], L[i][j + 1])
    return L

def lcsn(A, B, eq): return align(A, B, eq)[0][0] if A and B else 0

whole = Counter(); kinds = Counter(); tot = 0
for x in r:
    for i, s in enumerate(x['staves']):
        G = [tuple(q) for q in s['gp']]; R = [tuple(q) for q in s['rp']]
        if not G: continue
        tot += len(G)
        base = s['pitch']
        best = ('none', base)
        for name, f in (('oct+12', lambda c: tuple(p + 12 for p in c)), ('oct-12', lambda c: tuple(p - 12 for p in c)),
                        ('oct+24', lambda c: tuple(p + 24 for p in c)), ('oct-24', lambda c: tuple(p - 24 for p in c))):
            v = lcsn(G, [f(c) for c in R], lambda a, b: a == b)
            if v > best[1] + max(2, len(G) * 0.2): best = (name, v)
        # (by pitch class only: key, clef or transposition)
        pc = lcsn(G, R, lambda a, b: len(a) == len(b))
        whole[best[0]] += best[1] - base
        if best[0] != 'none': continue
        # onset by onset: align on 'close' (same size or overlapping)
        L = align(G, R, lambda a, b: bool(set(a) & set(b)) or (len(a) == len(b) and all(abs(p - q) <= 2 for p, q in zip(a, b))))
        a = b = 0
        while a < len(G) and b < len(R):
            ga, rb = G[a], R[b]
            ok = bool(set(ga) & set(rb)) or (len(ga) == len(rb) and all(abs(p - q) <= 2 for p, q in zip(ga, rb)))
            if ok and L[a][b] == L[a + 1][b + 1] + 1:
                if ga == rb: kinds['right'] += 1
                elif set(rb) < set(ga): kinds['chord missing notes'] += 1
                elif set(rb) > set(ga): kinds['chord extra notes'] += 1
                elif len(ga) == len(rb) and all(abs(p - q) == 1 for p, q in zip(ga, rb) if p != q): kinds['semitone (accidental)'] += 1
                elif len(ga) == len(rb): kinds['wrong step'] += 1
                else: kinds['chord mixed'] += 1
                a += 1; b += 1
            elif L[a + 1][b] >= L[a][b + 1]: kinds['onset missed'] += 1; a += 1
            else: kinds['onset extra (read)'] += 1; b += 1
        kinds['onset missed'] += len(G) - a; kinds['onset extra (read)'] += len(R) - b
print('onsets', tot)
print('whole-staff fixes would recover:', dict(whole))
for k, v in kinds.most_common(): print(f'  {k:25s} {v}')
