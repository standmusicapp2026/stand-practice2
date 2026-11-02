# A clean page made to look like a phone photo: on a table, in perspective, lit unevenly,
# softer toward one side, with grain and jpeg.  mkphoto.py IN OUT SEED
import sys, numpy as np
from PIL import Image, ImageFilter
src, out, seed = sys.argv[1], sys.argv[2], int(sys.argv[3])
rng = np.random.default_rng(seed)
pg = Image.open(src).convert('L'); W, H = pg.size
CW, CH = int(W * 1.25), int(H * 1.18)
# where the page's corners land (a slanted, foreshortened quad)
j = lambda a: a * (0.5 + rng.random())
quad = [(CW*0.10 + j(40), CH*0.06 + j(30)), (CW*0.90 - j(60), CH*0.08 + j(40)), (CW*0.95 - j(30), CH*0.95 - j(30)), (CW*0.05 + j(30), CH*0.93 - j(20))]
def coeffs(dst, srcp):
    A = []; B = []
    for (x, y), (u, v) in zip(dst, srcp):
        A += [[x, y, 1, 0, 0, 0, -u*x, -u*y], [0, 0, 0, x, y, 1, -v*x, -v*y]]; B += [u, v]
    return np.linalg.solve(np.array(A, float), np.array(B, float))
c = coeffs(quad, [(0, 0), (W, 0), (W, H), (0, H)])
paper = pg.transform((CW, CH), Image.PERSPECTIVE, tuple(c), Image.BICUBIC, fillcolor=0)
mask = Image.new('L', (W, H), 255).transform((CW, CH), Image.PERSPECTIVE, tuple(c), Image.BILINEAR, fillcolor=0)
a = np.array(paper, float); m = np.array(mask, float) / 255
# blur growing toward the bottom
s1 = np.array(paper.filter(ImageFilter.GaussianBlur(0.8)), float)
s2 = np.array(paper.filter(ImageFilter.GaussianBlur(2.0 + rng.random())), float)
yy = np.linspace(0, 1, CH)[:, None]; t = np.clip((yy - 0.35) / 0.6, 0, 1)
a = s1 * (1 - t) + s2 * t
# light: a gradient and a soft shadow
xx = np.linspace(0, 1, CW)[None, :]
light = 0.97 - 0.18 * (1 - xx) * 0.6 - 0.14 * yy - 0.10 * np.exp(-((xx - rng.random())**2 + (yy - rng.random())**2) / 0.05)
a = a * light
table = 70 + 30 * rng.random()
a = a * m + table * (1 - m)
a += rng.normal(0, 4, a.shape)
Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).save(out, quality=82)
