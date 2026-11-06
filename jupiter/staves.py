# Find the staves (groups of 5 lines) on a page image: prints [top, bottom, spacing] for each.
import sys
from PIL import Image
import numpy as np
def staves(path, x0f=0.12, x1f=0.98):
    im = np.array(Image.open(path).convert('L')); H, W = im.shape
    band = im[:, int(W * x0f):int(W * x1f)] < 140
    rows = band.mean(axis=1)
    lines = [y for y in range(H) if rows[y] > 0.45]
    # merge adjacent rows into lines
    L = []
    for y in lines:
        if L and y - L[-1][-1] <= 2: L[-1].append(y)
        else: L.append([y])
    L = [sum(l) / len(l) for l in L]
    out = []; i = 0
    while i + 4 < len(L):
        g = L[i:i + 5]; d = [g[k + 1] - g[k] for k in range(4)]
        if max(d) - min(d) <= 3 and 6 < d[0] < 60: out.append((g[0], g[4], sum(d) / 4)); i += 5
        else: i += 1
    return out
if __name__ == '__main__':
    for s in staves(sys.argv[1]): print('%.0f %.0f %.1f' % s)
