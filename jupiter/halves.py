# Split staff strips into two halves (and stack several staves) for reading by eye.
import sys
from PIL import Image
d, names, out = sys.argv[1], sys.argv[2].split(','), sys.argv[3]
for h in (0, 1):
    ims = [Image.open(f'{d}/{n}.png') for n in names]
    W = ims[0].width; cut = [(0, int(W * 0.53)), (int(W * 0.47), W)][h]
    parts = [i.crop((cut[0], 0, cut[1], i.height)) for i in ims]
    c = Image.new('L', (parts[0].width, sum(p.height for p in parts)), 255); y = 0
    for p in parts: c.paste(p, (0, y)); y += p.height
    c.save(f'{out}_{h + 1}.png'); print(out, h + 1, c.size)
