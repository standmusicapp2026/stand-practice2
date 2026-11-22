# Original notebook covers for Stand, drawn from scratch (no photographs), so they are free to use.
# Same ids and the same places for the titles as the covers they replace (see js/covers.js).
import sys, math, os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageChops
from scipy.ndimage import gaussian_filter, map_coordinates

W, H = 1240, 1754
OUT = sys.argv[1] if len(sys.argv) > 1 else '/home/claude/covers_out'
os.makedirs(OUT + '/t', exist_ok=True)
rng = np.random.default_rng(7)

def hexrgb(h):
    h = h.lstrip('#'); return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], float) / 255

def noise(h, w, scale, seed, octaves=4, persistence=0.5):
    """smooth fractal noise in 0..1"""
    r = np.random.default_rng(seed)
    out = np.zeros((h, w)); amp = 1; tot = 0
    for o in range(octaves):
        s = max(1, int(scale / (2 ** o)))
        g = r.random((h // s + 3, w // s + 3))
        yy = np.linspace(0, h / s, h)[:, None] + 1; xx = np.linspace(0, w / s, w)[None, :] + 1
        out += amp * map_coordinates(g, [np.broadcast_to(yy, (h, w)), np.broadcast_to(xx, (h, w))], order=3, mode='reflect')
        tot += amp; amp *= persistence
    out /= tot
    return (out - out.min()) / (out.max() - out.min() + 1e-9)

def grain(h, w, seed, amt=0.03):
    r = np.random.default_rng(seed)
    return (gaussian_filter(r.standard_normal((h, w)), 0.7) * amt)

def paper(base, seed, fiber=0.035, blotch=0.04):
    b = hexrgb(base) if isinstance(base, str) else np.array(base)
    n = noise(H, W, 300, seed, 5) - 0.5
    f = grain(H, W, seed + 1, fiber)
    img = b[None, None, :] * (1 + n[..., None] * blotch) + f[..., None]
    return np.clip(img, 0, 1)

def save(img, name):
    a = (np.clip(img, 0, 1) * 255).astype(np.uint8)
    im = Image.fromarray(a, 'RGB')
    im.save(f'{OUT}/{name}.jpg', quality=86, optimize=True, progressive=True)
    im.resize((300, 424), Image.LANCZOS).save(f'{OUT}/t/{name}.jpg', quality=84, optimize=True)

def over(img, color, alpha):
    c = hexrgb(color) if isinstance(color, str) else np.asarray(color)
    if c.ndim == 1: c = c[None, None, :]
    a = alpha[..., None]
    return img * (1 - a) + c * a

def mult(img, color, alpha):
    c = hexrgb(color) if isinstance(color, str) else np.asarray(color)
    if c.ndim == 1: c = c[None, None, :]
    a = alpha[..., None]
    return img * (1 - a + a * c)

def mask_from(draw_fn, ss=2, blur=0.8):
    m = Image.new('L', (W * ss, H * ss), 0); d = ImageDraw.Draw(m); draw_fn(d, ss)
    m = m.resize((W, H), Image.LANCZOS)
    if blur: m = m.filter(ImageFilter.GaussianBlur(blur))
    return np.asarray(m, float) / 255

YY, XX = np.mgrid[0:H, 0:W].astype(float)

# ---------------------------------------------------------------- records
def record(name, vinyl, label, cx, cy, r, R, bg='#2c2d30', arm=True, seed=1, label_ink=None, plinth='brushed'):
    """a coloured record on a turntable seen from above; r = label radius, R = record radius (px)"""
    if plinth == 'brushed':
        n = noise(H, W, 40, seed, 3)
        img = hexrgb(bg)[None, None, :] * (0.92 + 0.12 * n[..., None]) + grain(H, W, seed, 0.015)[..., None]
        # brushed metal streaks
        streak = gaussian_filter(np.random.default_rng(seed).standard_normal((H, W)), (0.5, 40)) * 0.06
        img = img + streak[..., None]
    else:
        img = paper(bg, seed, 0.02, 0.05)
    d = np.hypot(XX - cx, YY - cy); ang = np.arctan2(YY - cy, XX - cx)
    # platter shadow and rim
    sh = np.clip(1 - (d - R) / 60, 0, 1) * (d > R)
    img = img * (1 - 0.45 * sh[..., None])
    disc = np.clip(R - d + 0.8, 0, 1)
    vc = hexrgb(vinyl)
    # grooves: fine rings with slight variation, a band structure (tracks)
    rings = 0.5 + 0.5 * np.sin(d * 2 * math.pi / 3.1 + noise(H, W, 200, seed + 3, 2) * 4)
    tracks = (np.sin((d - r) / (R - r) * math.pi * 9) > 0.93) * 0.18
    # sheen: light catches the grooves along two opposite directions
    sheen = (np.cos(2 * (ang - 0.7)) ** 8) * 0.55 + (np.cos(2 * (ang + 0.9)) ** 16) * 0.25
    sheen *= np.clip((d - r * 1.05) / 40, 0, 1)
    shade = 0.8 + 0.08 * rings - tracks + sheen
    vin = vc[None, None, :] * shade[..., None] + sheen[..., None] * 0.18
    # translucent coloured vinyl: deeper at the edge
    vin = vin * (0.82 + 0.18 * np.clip(1 - (d - r) / (R - r), 0, 1))[..., None]
    img = img * (1 - disc[..., None]) + vin * disc[..., None]
    # dead wax ring and label
    wax = (d > r) & (d < r * 1.08)
    img[wax] = img[wax] * 0.9 + vc * 0.05
    lab = np.clip(r - d + 0.8, 0, 1)
    lc = hexrgb(label)
    ln = noise(H, W, 120, seed + 9, 3)
    labimg = lc[None, None, :] * (0.95 + 0.07 * ln[..., None]) + grain(H, W, seed + 4, 0.012)[..., None]
    # thin printed rings on the label
    pr = ((np.abs(d - r * 0.92) < 1.6) | (np.abs(d - r * 0.88) < 0.8)) * 0.25
    ink = hexrgb(label_ink) if label_ink else lc * 0.6
    labimg = labimg * (1 - pr[..., None]) + ink * pr[..., None]
    img = img * (1 - lab[..., None]) + labimg * lab[..., None]
    # spindle
    sp = np.clip(r * 0.05 - d, 0, 1)
    img = img * (1 - sp[..., None]) + np.array([0.78, 0.78, 0.8]) * sp[..., None]
    if arm:
        img = tonearm(img, seed)
    return img

def tonearm(img, seed):
    # pivot top right, arm down to the record, a headshell at the end
    px_, py_ = W * 1.02, H * 0.08
    ex, ey = W * 0.62, H * 0.84
    def drawarm(dr, ss, off=(0, 0), col=255):
        o = (off[0] * ss, off[1] * ss)
        pts = [(px_ * ss + o[0], py_ * ss + o[1]), ((W * 0.86) * ss + o[0], (H * 0.55) * ss + o[1]), (ex * ss + o[0], ey * ss + o[1])]
        dr.line(pts, fill=col, width=int(16 * ss), joint='curve')
        # headshell
        hx, hy = ex * ss + o[0], ey * ss + o[1]
        a = math.atan2(ey - H * 0.55, ex - W * 0.86)
        ca, sa = math.cos(a), math.sin(a)
        L, Wd = 120 * ss, 46 * ss
        poly = [(hx + ca * L / 2 - sa * Wd / 2, hy + sa * L / 2 + ca * Wd / 2), (hx + ca * L / 2 + sa * Wd / 2, hy + sa * L / 2 - ca * Wd / 2),
                (hx - ca * 10 * ss + sa * Wd / 2, hy - sa * 10 * ss - ca * Wd / 2), (hx - ca * 10 * ss - sa * Wd / 2, hy - sa * 10 * ss + ca * Wd / 2)]
        dr.polygon(poly, fill=col)
        # pivot
        dr.ellipse([px_ * ss - 90 * ss + o[0], py_ * ss - 90 * ss + o[1], px_ * ss + 90 * ss + o[0], py_ * ss + 90 * ss + o[1]], fill=col)
    shadow = mask_from(lambda d, s: drawarm(d, s, (22, 26)), blur=14)
    img = img * (1 - 0.45 * shadow[..., None])
    m = mask_from(lambda d, s: drawarm(d, s), blur=0.6)
    # chrome: light along one side
    g = gaussian_filter(m, 5)
    gy, gx = np.gradient(g)
    lit = np.clip(0.75 + (gx * -1 + gy * -0.6) * 60, 0.35, 1.25)
    metal = np.stack([lit * 0.8, lit * 0.81, lit * 0.84], -1)
    return img * (1 - m[..., None]) + metal * m[..., None]

def records():
    REC = {'06': (-0.2016, 0.4601, 0.321), '16': (-0.1848, 0.4607, 0.3057), '17': (-0.0948, 0.461, 0.3098),
           '18': (-0.1642, 0.4581, 0.3211), '19': (-0.2447, 0.4573, 0.3639)}
    cols = {'06': ('#5a2340', '#e9dcc8'), '16': ('#5b3b28', '#efe4d0'), '17': ('#4f6c78', '#efe9dc'), '18': ('#2f5a3e', '#eee6d2'), '19': ('#7c1d22', '#f0e3cf')}
    for i, (k, (fx, fy, fr)) in enumerate(REC.items()):
        cx, cy, r = fx * W, fy * H, fr * W
        img = record(k, cols[k][0], cols[k][1], cx, cy, r, r * 3.15, seed=10 + i)
        save(img, k)
    # black record rising from the bottom, on cream
    fx, fy, fr = 0.4957, 1.0265, 0.2305
    img = record('07', '#151515', '#a8322b', fx * W, fy * H, fr * W, fr * W * 3.25, bg='#e8e0cc', arm=False, seed=30, label_ink='#f6ead8', plinth='paper')
    save(img, '07')

if __name__ == '__main__':
    which = sys.argv[2].split(',') if len(sys.argv) > 2 else ['records']
    for w in which: globals()[w]()
