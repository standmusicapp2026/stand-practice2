# From the 4x enlargement to the cover: exact size 1240 x 1754, a little of the original's soft
# texture mixed back in (the enlarger can make surfaces waxy), a fine paper grain, a gentle
# sharpening and a thumbnail. Output: out/<id>.jpg and out/t/<id>.jpg
import os, sys, json
import numpy as np
from PIL import Image, ImageFilter

W, H = 1240, 1754
os.makedirs('out/t', exist_ok=True)
sel = json.load(open('sel.json'))
rng = np.random.default_rng(3)

def finish(k):
    up = Image.open(f'up/{k}.png').convert('RGB').resize((W, H), Image.LANCZOS)
    soft = Image.open(f'crops/{k}.png').convert('RGB').resize((W, H), Image.BICUBIC)
    a = np.asarray(up).astype(np.float32); b = np.asarray(soft).astype(np.float32)
    # records are photographs of shiny vinyl: less texture back, the rest are paper and paint
    mix = 0.08 if sel[k]['cat'] == 'records' else 0.16
    img = a * (1 - mix) + b * mix
    # fine grain, a little stronger in the light parts (as on paper)
    g = rng.standard_normal((H, W)).astype(np.float32)
    g = np.asarray(Image.fromarray(((g * 40) + 128).clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))).astype(np.float32) - 128
    lum = img.mean(2, keepdims=True) / 255
    img = img + g[..., None] * (0.05 + 0.07 * lum) * (0.5 if sel[k]['cat'] == 'records' else 1)
    out = Image.fromarray(img.clip(0, 255).astype(np.uint8))
    out = out.filter(ImageFilter.UnsharpMask(radius=1.6, percent=45, threshold=2))
    out.save(f'out/{k}.jpg', quality=88, optimize=True, progressive=True)
    out.resize((300, 424), Image.LANCZOS).save(f'out/t/{k}.jpg', quality=85, optimize=True)

for k in (sys.argv[1:] or [k for k in sel if os.path.exists(f'up/{k}.png')]):
    finish(k); print(k)
