# Cut each staff of a page into its own strip (with room for ledger lines) for Capture to read.
# python3 strips.py page.png outdir names [first_staff] [x_splice]
import sys, os
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__)); from staves import staves
page, out, names = sys.argv[1], sys.argv[2], sys.argv[3].split(',')
first = int(sys.argv[4]) if len(sys.argv) > 4 else 0
splice = float(sys.argv[5]) if len(sys.argv) > 5 else 0
im = Image.open(page).convert('L'); W, H = im.size
S = staves(page)[first:first + len(names)]
os.makedirs(out, exist_ok=True)
for (top, bot, sp), nm in zip(S, names):
    a, b = int(top - sp * 3.2), int(bot + sp * 3.2)
    x0 = int(W * 0.115)
    if splice:
        # the clef and key from the start of the line, then the music from the double bar
        left = im.crop((x0, a, x0 + int(W * 0.055), b)); right = im.crop((int(W * splice), a, int(W * 0.985), b))
        c = Image.new('L', (left.width + right.width + 20, b - a), 255); c.paste(left, (0, 0)); c.paste(right, (left.width + 20, 0))
    else:
        c = im.crop((x0, a, int(W * 0.985), b))
    # white margin all round (Capture looks for a page)
    pad = Image.new('L', (c.width + 120, c.height + 160), 255); pad.paste(c, (60, 80))
    pad.save(f'{out}/{nm}.png')
print(len(S), 'strips')
