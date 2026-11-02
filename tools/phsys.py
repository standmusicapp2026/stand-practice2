# per-system note agreement from the last phototest json dump
import json, sys
r = json.load(open(sys.argv[1]))
def lcs(A, B):
    n, m = len(A), len(B); L = [[0]*(m+1) for _ in range(n+1)]
    for i in range(n-1, -1, -1):
        for j in range(m-1, -1, -1):
            L[i][j] = L[i+1][j+1] + 1 if A[i] == B[j] else max(L[i+1][j], L[i][j+1])
    return L[0][0]
for s in sorted(set(r['sysC'])):
    A = ' | '.join(b for b, k in zip(r['photo'], r['sysP']) if k == s).split()
    B = ' | '.join(b for b, k in zip(r['clean'], r['sysC']) if k == s).split()
    print(s, 'bars', r['sysP'].count(s), r['sysC'].count(s), 'tokens', len(A), len(B), 'same %.0f%%' % (100 * lcs(A, B) / max(1, len(B))))
