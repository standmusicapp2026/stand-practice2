# how soft the edges are: the median width of the paper-to-ink rise, at a staff space of ~20 px
import sys, numpy as np
from PIL import Image
for f in sys.argv[1:]:
    im = np.array(Image.open(f).convert('L')).astype(float)
    # scale so a staff space is about 20 px: estimate from row runs is long; use the page height
    k = 3300 / im.shape[0]
    im = np.array(Image.fromarray(im.astype(np.uint8)).resize((int(im.shape[1]*k), int(im.shape[0]*k)), Image.BILINEAR)).astype(float)
    p = np.percentile(im, 95); im = np.clip(im * 255 / max(30, p), 0, 255)
    ws = []
    for x in range(5, im.shape[1] - 5, 7):
        c = im[:, x]; y = 1
        while y < len(c) - 12:
            if c[y-1] > 215 and c[y] <= 215:
                e = y
                while e < y + 12 and c[e] > 90: e += 1
                if e < y + 12 and c[e] <= 90: ws.append(e - y); y = e
            y += 1
    ws = np.array(ws); print(f.split('/')[-1], len(ws), 'median', np.median(ws) if len(ws) else None, 'p75', np.percentile(ws, 75) if len(ws) else None)
