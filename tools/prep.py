# Pick the tiles for the covers, crop each to the cover's shape (1240 x 1754, about 0.707) and
# enlarge them 4x with Real-ESRGAN (x4plus). Output: up/<id>.png
import os, sys, json
from PIL import Image
from sr import load_pth, rrdb_upscale

A = 1240 / 1754
# id: (tile, where to crop along the long side 0 = start, 0.5 = middle, 1 = end), category, label
SEL = {
    # records (the six turntables)
    'r1': ('s3_r1c1', None, 'records', 'Black record'),
    'r2': ('s3_r1c2', None, 'records', 'Red record'),
    'r3': ('s3_r2c1', None, 'records', 'Blue record'),
    'r4': ('s3_r2c2', None, 'records', 'Green record'),
    'r5': ('s3_r3c1', None, 'records', 'Brown record'),
    'r6': ('s3_r3c2', None, 'records', 'Silver record'),
    # flowers
    'f1': ('s2_r4c1', 0.5, 'flowers', 'Blue petals'),
    'f2': ('s2_r4c2', 0.5, 'flowers', 'Red petals'),
    'f3': ('s2_r4c3', 0.5, 'flowers', 'Poppies'),
    'f4': ('s2_r4c4', 0.5, 'flowers', 'Anthurium'),
    'f5': ('s2_r5c4', 0.5, 'flowers', 'Anemones'),
    # paint
    'p1': ('s2_r3c3', 0.5, 'paint', 'Blue ribbons'),
    'p2': ('s2_r4c5', 0.5, 'paint', 'Red brush'),
    'p3': ('s2_r5c1', 0.5, 'paint', 'Green brush'),
    'p4': ('s1_r5c4', 0.8, 'paint', 'Ink wave'),
    'p5': ('s2_r3c5', 0.5, 'paint', 'Blue marble'),
    'p6': ('s2_r5c3', 0.6, 'paint', 'Mountains'),
    # textures
    't1': ('s2_r1c1', 0.6, 'textures', 'Red and sage waves'),
    't2': ('s2_r3c4', 0.5, 'textures', 'Navy and sand'),
    't3': ('s2_r3c1', 0.5, 'textures', 'Indigo squares'),
    't4': ('s2_r3c2', 0.5, 'textures', 'Faded squares'),
    't5': ('s1_r2c4', 0.5, 'textures', 'Blue cross'),
    't6': ('s1_r3c3', 0.5, 'textures', 'Weathered blue'),
    # paper
    'a1': ('s1_r1c2', 0.0, 'paper', 'Torn paper'),
    'a2': ('s1_r4c3', 0.45, 'paper', 'Torn across'),
    'a3': ('s2_r5c2', 0.5, 'paper', 'Torn diagonal'),
    # music
    'm1': ('s2_r1c3', 0.5, 'music', 'Plectrums'),
    'm2': ('s2_r1c4', 0.7, 'music', 'Painted score'),
    'm3': ('s2_r1c5', 0.5, 'music', 'Cassette'),
}

def crop(t, where, disk):
    w, h = t.size
    t = t.crop((3, 3, w - 3, h - 3)); w, h = t.size
    if disk:
        # keep the label on the left and the tone arm: a portrait strip from the left side
        cw = round(h * A); x0 = 30
        return t.crop((x0, 0, x0 + cw, h))
    if w / h > A:
        cw = round(h * A); x0 = round((w - cw) * where); return t.crop((x0, 0, x0 + cw, h))
    ch = round(w / A); y0 = round((h - ch) * where); return t.crop((0, y0, w, y0 + ch))

if __name__ == '__main__':
    os.makedirs('crops', exist_ok=True); os.makedirs('up', exist_ok=True)
    json.dump({k: {'tile': v[0], 'cat': v[2], 'label': v[3]} for k, v in SEL.items()}, open('sel.json', 'w'), indent=1)
    only = sys.argv[1:] or list(SEL)
    sd = load_pth('RealESRGAN_x4plus.pth')['params_ema']
    for k in only:
        tile, where, cat, label = SEL[k]
        c = crop(Image.open(f'tiles/{tile}.png').convert('RGB'), where, cat == 'records')
        c.save(f'crops/{k}.png')
        if os.path.exists(f'up/{k}.png'): continue
        rrdb_upscale(c, sd).save(f'up/{k}.png')
        print(k, c.size, flush=True)
