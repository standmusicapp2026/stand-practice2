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
    sheen = (np.cos(2 * (ang - 0.7)) ** 8) * 0.38 + (np.cos(2 * (ang + 0.9)) ** 16) * 0.18
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
        dr.line(pts, fill=col, width=int(22 * ss), joint='curve')
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
    cols = {'06': ('#4e1f38', '#e9dcc8'), '16': ('#4f3424', '#d9b98c'), '17': ('#3f5864', '#efe9dc'), '18': ('#284d36', '#e8d9b0'), '19': ('#6e1a1f', '#f0e3cf')}
    for i, (k, (fx, fy, fr)) in enumerate(REC.items()):
        cx, cy, r = fx * W, fy * H, fr * W
        img = record(k, cols[k][0], cols[k][1], cx, cy, r, r * 3.15, seed=10 + i)
        save(img, k)
    # black record rising from the bottom, on cream
    fx, fy, fr = 0.4957, 1.0265, 0.2305
    img = record('07', '#151515', '#a8322b', fx * W, fy * H, fr * W, fr * W * 3.25, bg='#e8e0cc', arm=False, seed=30, label_ink='#f6ead8', plinth='paper')
    save(img, '07')


# ---------------------------------------------------------------- paint
def bezier(pts, n=240):
    pts = np.array(pts, float)
    # Catmull-Rom through the points
    P = np.vstack([pts[0], pts, pts[-1]])
    out = []
    seg = len(pts) - 1
    for i in range(seg):
        p0, p1, p2, p3 = P[i], P[i + 1], P[i + 2], P[i + 3]
        for t in np.linspace(0, 1, n // seg, endpoint=False):
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(pts[-1])
    return np.array(out)

def stroke(img, pts, width, color, seed, bristles=180, dry=0.35, taper=0.25, light=(-0.6, -0.8), relief=1.0, opacity=1.0):
    """a loaded brush pulled along pts: bristle streaks, dry-brush gaps at the end, a little relief"""
    r = np.random.default_rng(seed)
    ss = 2
    path = bezier(pts) * ss
    d = np.diff(path, axis=0); L = np.hypot(d[:, 0], d[:, 1]); s = np.concatenate([[0], np.cumsum(L)]); t = s / s[-1]
    tang = np.vstack([d, d[-1:]]); tang /= np.hypot(tang[:, 0], tang[:, 1])[:, None] + 1e-9
    nrm = np.stack([-tang[:, 1], tang[:, 0]], 1)
    cov = Image.new('L', (W * ss, H * ss), 0); hgt = Image.new('L', (W * ss, H * ss), 0)
    dc, dh = ImageDraw.Draw(cov), ImageDraw.Draw(hgt)
    # the stroke is a little narrower at the start and end
    wprof = np.clip(np.minimum(t / taper, 1) * 0.35 + 0.65, 0, 1) * np.clip(np.minimum((1 - t) / taper, 1) * 0.3 + 0.7, 0, 1)
    for b in range(bristles):
        o = (b / (bristles - 1) - 0.5) * 2
        o += r.normal(0, 0.012)
        load = r.uniform(0.55, 1.0)
        tend = 1 - r.random() ** 2 * dry * (1.6 if abs(o) > 0.8 else 1)
        tstart = r.random() ** 3 * 0.05
        wob = gaussian_filter(r.standard_normal(len(t)), 25) * 0.04
        gaps = gaussian_filter(r.random(len(t)), 3)
        off = (o * width * ss / 2) * wprof + wob * width * ss
        P = path + nrm * off[:, None]
        val = int(120 + 135 * load)
        bw = max(1, int(width * ss / bristles * 2.6 * r.uniform(0.7, 1.3)))
        # dry brush: towards the end, gaps open where the bristle runs out of paint
        keep = (t >= tstart) & (t <= tend) & (gaps > np.clip((t - (1 - dry * 1.5)) * 2.2, 0, 1) * 0.62 + 0.0 * load)
        segs = np.split(np.arange(len(t)), np.where(np.diff(keep.astype(int)) != 0)[0] + 1)
        for sg in segs:
            if len(sg) < 2 or not keep[sg[0]]: continue
            q = [tuple(x) for x in P[sg]]
            dc.line(q, fill=255, width=bw)
            dh.line(q, fill=val, width=bw)
    cov = np.asarray(cov.resize((W, H), Image.LANCZOS), float) / 255
    hg = np.asarray(hgt.resize((W, H), Image.LANCZOS), float) / 255
    hg = gaussian_filter(hg, 0.8)
    gy, gx = np.gradient(gaussian_filter(hg, 1.2))
    shade = 1 + (gx * light[0] + gy * light[1]) * 9 * relief
    col = hexrgb(color) if isinstance(color, str) else np.asarray(color)
    tone = (0.86 + 0.18 * hg)[..., None] * col[None, None, :] * shade[..., None]
    a = np.clip(cov * 1.15, 0, 1) * opacity
    return img * (1 - a[..., None]) + np.clip(tone, 0, 1) * a[..., None]

def brush_covers():
    # 25 green, 26 red: one generous stroke sweeping across, the title in light letters over it at the bottom
    for k, col, seed in (('25', '#2f5a2b', 50), ('26', '#a8261f', 51)):
        img = paper('#efe9dc', seed, 0.02, 0.04)
        pts = [(-0.15 * W, 0.98 * H), (0.25 * W, 0.62 * H), (0.7 * W, 0.5 * H), (1.12 * W, 0.42 * H)]
        img = stroke(img, pts, 0.62 * W, col, seed, bristles=220, dry=0.3)
        pts2 = [(-0.1 * W, 1.08 * H), (0.4 * W, 0.92 * H), (1.1 * W, 0.8 * H)]
        img = stroke(img, pts2, 0.5 * W, col, seed + 7, bristles=200, dry=0.25)
        save(img, k)
    # 12 navy strokes: strokes to the right and below, the top-left clear for the title
    img = paper('#ece6d8', 60, 0.02, 0.04)
    for i, (pts, w) in enumerate([
        ([(0.55 * W, 0.25 * H), (0.75 * W, 0.45 * H), (1.1 * W, 0.6 * H)], 0.35 * W),
        ([(0.1 * W, 1.05 * H), (0.35 * W, 0.7 * H), (0.62 * W, 0.42 * H)], 0.3 * W),
        ([(0.3 * W, 1.05 * H), (0.7 * W, 0.8 * H), (1.08 * W, 0.78 * H)], 0.28 * W),
    ]):
        img = stroke(img, pts, w, '#1b2a55', 61 + i, bristles=170, dry=0.45)
    save(img, '12')
    # 09 Japandi: a calm beige with two ink-blue sweeps on the right
    img = paper('#e4dccb', 70, 0.02, 0.06)
    img = stroke(img, [(0.62 * W, -0.05 * H), (0.7 * W, 0.4 * H), (0.6 * W, 1.05 * H)], 0.22 * W, '#1d2b4a', 71, dry=0.5)
    img = stroke(img, [(0.95 * W, 0.15 * H), (0.82 * W, 0.6 * H), (0.98 * W, 1.02 * H)], 0.14 * W, '#a0835c', 72, dry=0.55, opacity=0.9)
    save(img, '09')
    # 23 ink wave: a deep blue wave along the bottom, white spray, light above
    img = paper('#f0ece2', 80, 0.02, 0.04)
    for i in range(7):
        y = 0.72 + i * 0.045
        pts = [(-0.1 * W, (y + 0.06) * H), (0.25 * W, (y - 0.05) * H), (0.55 * W, (y + 0.04) * H), (0.85 * W, (y - 0.06) * H), (1.1 * W, (y + 0.02) * H)]
        img = stroke(img, pts, (0.06 + 0.02 * i) * W, ['#16234a', '#1f3566', '#2b4a86', '#14213f'][i % 4], 81 + i, bristles=120, dry=0.5, relief=0.6)
    for i in range(3):
        y = 0.74 + i * 0.07
        img = stroke(img, [(-0.1 * W, (y + 0.03) * H), (0.3 * W, (y - 0.03) * H), (0.6 * W, (y + 0.02) * H), (1.1 * W, (y - 0.02) * H)], 0.025 * W, '#eef0f2', 90 + i, bristles=60, dry=0.7, relief=0.3)
    save(img, '23')
    # 11 boho: blue-grey layers, darker at the top left (the title is light there)
    img = paper('#5f6e85', 100, 0.02, 0.1)
    for i, (c, pts, w) in enumerate([
        ('#2c3a55', [(-0.1 * W, 0.12 * H), (0.5 * W, 0.18 * H), (1.1 * W, 0.1 * H)], 0.5 * W),
        ('#9fb0c4', [(-0.1 * W, 0.55 * H), (0.5 * W, 0.6 * H), (1.1 * W, 0.5 * H)], 0.28 * W),
        ('#d8cfbf', [(0.2 * W, 0.8 * H), (0.6 * W, 0.75 * H), (1.1 * W, 0.85 * H)], 0.2 * W),
        ('#36465f', [(-0.1 * W, 0.95 * H), (0.5 * W, 0.9 * H), (1.1 * W, 1.0 * H)], 0.25 * W),
        ('#7d8fa8', [(0.6 * W, 0.35 * H), (0.9 * W, 0.4 * H), (1.1 * W, 0.32 * H)], 0.18 * W)]):
        img = stroke(img, pts, w, c, 101 + i, bristles=200, dry=0.4, relief=0.7)
    save(img, '11')
    # 10 ribbons, 13 textured, 14 blue squares (a cream card carries the title on these)
    img = paper('#e9e3d6', 110, 0.02, 0.05)
    for i in range(6):
        a = i / 5
        pts = [(-0.1 * W, (0.05 + a * 0.9) * H), (0.4 * W, (0.15 + a * 0.75) * H), (0.75 * W, (a * 0.95) * H), (1.1 * W, (0.1 + a * 0.8) * H)]
        img = stroke(img, pts, 0.16 * W, ['#16244a', '#2c4a7c', '#c9d2df', '#1c2f5c', '#5b77a3', '#0f1a36'][i], 111 + i, bristles=160, dry=0.35)
    save(img, '10')
    img = paper('#26364f', 120, 0.03, 0.14)
    for i in range(14):
        rr = np.random.default_rng(121 + i)
        x0, y0 = rr.uniform(-0.1, 1.0), rr.uniform(0, 1)
        pts = [(x0 * W, y0 * H), ((x0 + rr.uniform(0.15, 0.4)) * W, (y0 + rr.uniform(-0.05, 0.05)) * H)]
        img = stroke(img, pts, rr.uniform(0.08, 0.2) * W, ['#d9d2c3', '#3f5a80', '#7f93ad', '#18243a', '#b7a98f'][i % 5], 130 + i, bristles=120, dry=0.6, opacity=rr.uniform(0.6, 0.95))
    save(img, '13')
    img = paper('#d8d3c7', 140, 0.02, 0.05)
    for i in range(18):
        rr = np.random.default_rng(141 + i)
        x0, y0, w = rr.uniform(-0.05, 0.85), rr.uniform(-0.05, 0.95), rr.uniform(0.12, 0.3)
        pts = [(x0 * W, (y0 + w * 0.35) * H * 0.7 / 0.7), ((x0 + w) * W, (y0 + w * 0.35) * H)]
        img = stroke(img, pts, w * W * 0.9, ['#1d3461', '#365a8c', '#8aa2c0', '#c8d3e0', '#253b66'][i % 5], 150 + i, bristles=140, dry=0.25, opacity=rr.uniform(0.7, 1))
    save(img, '14')
    # 08 navy: a deep textured navy
    img = paper('#1b2442', 160, 0.03, 0.16)
    img = stroke(img, [(-0.1 * W, 0.3 * H), (0.5 * W, 0.35 * H), (1.1 * W, 0.28 * H)], 0.9 * W, '#202b4e', 161, bristles=260, dry=0.2, relief=0.8, opacity=0.8)
    save(img, '08')


# ---------------------------------------------------------------- flowers
def petal_mask(cx, cy, ang, length, width, seed, ruffle=0.06):
    """a soft petal from (cx,cy) outwards along ang: (mask 0..1, distance-from-edge 0..1, along 0..1)"""
    r = np.random.default_rng(seed)
    ca, sa = math.cos(ang), math.sin(ang)
    u = ((XX - cx) * ca + (YY - cy) * sa) / length            # along the petal 0..1
    v = (-(XX - cx) * sa + (YY - cy) * ca) / (width / 2)      # across -1..1 at the widest
    prof = np.sin(np.clip(u, 0, 1) * math.pi) ** 0.7 * (0.55 + 0.45 * np.clip(u, 0, 1))
    wav = 1 + ruffle * np.sin(u * 14 + r.uniform(0, 6)) + ruffle * 0.6 * np.sin(np.arctan2(v, u + 0.1) * 9)
    edge = prof * wav - np.abs(v)
    inside = np.clip(edge * width / 4, 0, 1) * (u > 0) * (u < 1.05)
    depth = np.clip(edge / (prof + 1e-3), 0, 1)
    return inside, depth, np.clip(u, 0, 1), v

def xray_flower(img, cx, cy, n, length, width, color, seed, rot=0, alpha=0.5, veins=True, paint=False):
    col = hexrgb(color)
    for i in range(n):
        a = rot + i * 2 * math.pi / n + np.random.default_rng(seed + i).uniform(-0.15, 0.15)
        m, dep, u, v = petal_mask(cx, cy, a, length * np.random.default_rng(seed + 50 + i).uniform(0.85, 1.1), width, seed + i)
        # translucent: deeper colour at the rim, light in the middle, darker near the base
        dens = (0.35 + 0.65 * (1 - dep) ** 2.2) * (0.7 + 0.5 * (1 - u))
        a_ = np.clip(m * dens * alpha, 0, 1)
        img = over(img, col, a_) if paint else mult(img, col, a_)
        if veins:
            vv = np.zeros_like(m)
            for k in range(-4, 5):
                vv = np.maximum(vv, np.exp(-((v - k * 0.18 * (u ** 0.6)) ** 2) / 0.0008) * (u < 0.92))
            img = mult(img, col * 0.8, np.clip(vv * m * 0.35, 0, 1))
    # the heart: stamens
    r = np.random.default_rng(seed + 99)
    hm = mask_from(lambda d, s: [d.line([(cx * s, cy * s), ((cx + math.cos(t) * l) * s, (cy + math.sin(t) * l) * s)], fill=255, width=int(3 * s)) or
                                  d.ellipse([((cx + math.cos(t) * l) - 7) * s, ((cy + math.sin(t) * l) - 7) * s, ((cx + math.cos(t) * l) + 7) * s, ((cy + math.sin(t) * l) + 7) * s], fill=255)
                                  for t, l in zip(r.uniform(0, 2 * math.pi, 12), r.uniform(length * 0.15, length * 0.32, 12))], blur=0.8)
    return mult(img, col * 0.55, hm * 0.85)

def flowers():
    # 20 pink petals on the right, the title on the left
    img = paper('#f7f3ee', 200, 0.012, 0.02)
    img = xray_flower(img, 0.86 * W, 0.3 * H, 5, 0.42 * W, 0.34 * W, '#d9476a', 201, rot=0.4, alpha=0.55)
    img = xray_flower(img, 0.95 * W, 0.82 * H, 5, 0.36 * W, 0.3 * W, '#e0708a', 210, rot=1.1, alpha=0.5)
    save(img, '20')
    # 27 blue petals, the title at the bottom centre
    img = paper('#f5f6f7', 220, 0.012, 0.02)
    img = xray_flower(img, 0.45 * W, 0.28 * H, 4, 0.36 * W, 0.36 * W, '#2c56b8', 221, rot=0.3, alpha=0.6)
    img = xray_flower(img, 0.8 * W, 0.62 * H, 4, 0.28 * W, 0.28 * W, '#3a66c4', 230, rot=0.9, alpha=0.55)
    img = xray_flower(img, 0.12 * W, 0.66 * H, 4, 0.22 * W, 0.22 * W, '#4a72c8', 240, rot=0.1, alpha=0.5)
    save(img, '27')
    # 28 teal leaves (anthurium-like hearts), title bottom left
    img = paper('#f4f6f5', 250, 0.012, 0.02)
    for i, (cx, cy, a, L) in enumerate([(0.75, 0.15, 2.3, 0.5), (0.95, 0.45, 2.6, 0.45), (0.62, 0.55, 1.2, 0.42), (1.0, 0.85, 3.6, 0.4)]):
        m, dep, u, v = petal_mask(cx * W, cy * H, a, L * W, L * W * 0.95, 251 + i, ruffle=0.02)
        dens = (0.25 + 0.75 * (1 - dep) ** 3)
        img = mult(img, hexrgb('#3f8a8f'), np.clip(m * dens * 0.6, 0, 1))
        vv = np.zeros_like(m)
        for k in range(-5, 6):
            vv = np.maximum(vv, np.exp(-((v - k * 0.16 * np.sqrt(u)) ** 2) / 0.0006))
        img = mult(img, hexrgb('#2d6b70'), np.clip(vv * m * 0.4, 0, 1))
        # stem
        sm = mask_from(lambda d, s, cx=cx, cy=cy, a=a: d.line([(cx * W * s, cy * H * s), ((cx * W - math.cos(a) * 0.5 * W) * s, (cy * H - math.sin(a) * 0.5 * W) * s + 300 * s)], fill=255, width=int(7 * s)), blur=1)
        img = mult(img, hexrgb('#3f7f72'), sm * 0.6)
    save(img, '28')
    # 29 poppies: a blue wash, darker at the top (light title), small red poppies below
    n = noise(H, W, 260, 290, 5)
    g = np.clip(YY / H, 0, 1)
    top, bot = hexrgb('#2f5277'), hexrgb('#9bb6cc')
    img = top * (1 - g[..., None]) + bot * g[..., None]
    img = img * (0.9 + 0.2 * n[..., None]) + grain(H, W, 291, 0.012)[..., None]
    r = np.random.default_rng(292)
    for i in range(9):
        x, y = r.uniform(0.12, 0.9) * W, r.uniform(0.6, 0.86) * H
        stem = mask_from(lambda d, s, x=x, y=y: d.line([(x * s, y * s), ((x + r.uniform(-30, 30)) * s, H * 1.02 * s)], fill=255, width=int(4 * s)), blur=0.8)
        img = mult(img, hexrgb('#2a3f36'), stem * 0.75)
        img = xray_flower(img, x, y, 5, r.uniform(45, 75), r.uniform(50, 70), '#d8321f', 300 + i, alpha=1.0, veins=False, paint=True)
    save(img, '29')
    # 15 night flowers: pale petals on deep navy (a card carries the title)
    img = paper('#141d33', 330, 0.02, 0.1)
    for i in range(16):
        x, y = r.uniform(-0.1, 1.1) * W, r.uniform(-0.05, 1.05) * H
        L = r.uniform(0.15, 0.3) * W
        m_all = np.zeros((H, W))
        for k in range(5):
            m, dep, u, v = petal_mask(x, y, k * 1.257 + r.uniform(0, 1), L, L * 0.8, 340 + i * 5 + k, ruffle=0.08)
            m_all = np.maximum(m_all, m * (0.35 + 0.65 * (1 - dep) ** 1.5))
        img = over(img, ['#c9d4e6', '#8ea3c4', '#5f7aa5'][i % 3], np.clip(m_all * 0.75, 0, 1))
    save(img, '15')


# ---------------------------------------------------------------- paper
def edge_line(n, seed, amp, fine):
    r = np.random.default_rng(seed)
    a = gaussian_filter(r.standard_normal(n), 60) ; a = a / (np.abs(a).max() + 1e-9) * amp
    b = gaussian_filter(r.standard_normal(n), 3); b = b / (np.abs(b).max() + 1e-9) * fine
    return a + b

def torn(base, under, holefn, seed, fiber='#fbfaf6', shadow=0.5):
    """base paper with a torn opening (holefn(off) -> bool mask, larger off = bigger) showing `under`"""
    hole = holefn(0).astype(float)
    fibre_w = holefn(1).astype(float)          # the opening grown by the white paper core
    fn = gaussian_filter(np.random.default_rng(seed).random((H, W)), 1.2)
    core = np.clip(fibre_w - hole, 0, 1) * (fn > 0.42)
    hole = gaussian_filter(hole, 0.7)
    core = gaussian_filter(core.astype(float), 0.6)
    # the top sheet casts a soft shadow into the opening
    top = 1 - gaussian_filter(holefn(-0.6).astype(float), 1)
    sh = gaussian_filter(top, 14) * hole * shadow
    img = base * (1 - hole[..., None]) + under * hole[..., None]
    img = img * (1 - sh[..., None])
    img = over(img, fiber, np.clip(core * 0.95, 0, 1))
    return img

def paper_covers():
    # 01 lined paper: ruled lines under the handwritten title (title at y .165H, lines .085W apart)
    img = paper('#f3ecd9', 400, 0.02, 0.05)
    step = 0.085 * W; y0 = 0.165 * H + 8
    ys = [y0 + k * step for k in range(-2, 20) if 0 < y0 + k * step < H - 10]
    lm = mask_from(lambda d, s: [d.line([(0, y * s), (W * s, y * s)], fill=255, width=int(2.2 * s)) for y in ys], blur=0.5)
    img = mult(img, hexrgb('#7aa6c9'), lm * 0.7)
    mm = mask_from(lambda d, s: [d.line([(x * s, 0), (x * s, H * s)], fill=255, width=int(2.2 * s)) for x in (0.13 * W, 0.135 * W)], blur=0.5)
    img = mult(img, hexrgb('#d65a5a'), mm * 0.7)
    # punched holes on the left
    for y in (0.2, 0.5, 0.8):
        hm = np.clip(26 - np.hypot(XX - 0.05 * W, YY - y * H), 0, 1)
        sh = np.clip(30 - np.hypot(XX - 0.05 * W - 3, YY - y * H - 4), 0, 1) - hm
        img = img * (1 - 0.25 * np.clip(sh, 0, 1)[..., None])
        img = over(img, '#e7e3dc', hm)
    save(img, '01')
    # 02 torn opening down the middle, white paper beneath
    xl = edge_line(H, 410, 30, 6); xr = edge_line(H, 411, 30, 6); yt = edge_line(W, 412, 20, 5)
    def hole2(off):
        g = off * 14
        return (XX > 0.37 * W + xl[:, None] - g) & (XX < 0.61 * W + xr[:, None] + g) & (YY > 0.13 * H + yt[None, :] - g) & (YY < 1.2 * H)
    base = paper('#d9d8d3', 413, 0.02, 0.05); under = paper('#f8f7f3', 414, 0.01, 0.02)
    save(torn(base, under, hole2, 415), '02')
    # 24 torn across: cream over burgundy
    yt = edge_line(W, 420, 26, 7); yb = edge_line(W, 421, 26, 7)
    def hole24(off):
        g = off * 16
        return (YY > 0.43 * H + yt[None, :] - g) & (YY < 0.555 * H + yb[None, :] + g)
    base = paper('#efe7d6', 422, 0.02, 0.05); under = paper('#5d1823', 423, 0.03, 0.12)
    save(torn(base, under, hole24, 424, shadow=0.6), '24')

# ---------------------------------------------------------------- music
def music_covers():
    # 05 cassette, standing upright: a label strip to write on at x .12–.23, a dark band at .072
    img = paper('#33302d', 500, 0.02, 0.08)
    def rect(x0, y0, x1, y1, col, a=1.0, rad=0):
        nonlocal img
        m = mask_from(lambda d, s: d.rounded_rectangle([x0 * W * s, y0 * H * s, x1 * W * s, y1 * H * s], radius=rad * W * s, fill=255), blur=0.6)
        img = over(img, col, m * a)
    rect(0.035, 0.03, 0.965, 0.97, '#2a2826', rad=0.04)
    rect(0.045, 0.045, 0.105, 0.955, '#1d1c1b')                 # dark band (subtitle)
    rect(0.115, 0.06, 0.235, 0.94, '#ede5d2', rad=0.01)          # label strip
    for k in range(1, 6):
        x = 0.115 + k * 0.02
        m = mask_from(lambda d, s, x=x: d.line([(x * W * s, 0.08 * H * s), (x * W * s, 0.92 * H * s)], fill=255, width=int(1.6 * s)), blur=0.4)
        img = mult(img, hexrgb('#b9b2a1'), m)
    rect(0.3, 0.2, 0.75, 0.8, '#4a4743', rad=0.03)               # window frame
    rect(0.36, 0.27, 0.69, 0.73, '#141312', rad=0.02)             # window
    for cy in (0.37, 0.63):                                     # reels
        cx = 0.525 * W
        d = np.hypot(XX - cx, YY - cy * H)
        tape = np.clip(0.13 * W - d, 0, 1)
        img = over(img, '#3a2a20', tape * 0.95)
        hub = np.clip(0.055 * W - d, 0, 1)
        img = over(img, '#e9e4da', hub)
        ang = np.arctan2(YY - cy * H, XX - cx)
        teeth = (np.cos(ang * 6) > 0.4) * np.clip(0.04 * W - d, 0, 1) * (d > 0.022 * W)
        img = over(img, '#2a2826', teeth * 0.9)
        img = over(img, '#2a2826', np.clip(0.02 * W - d, 0, 1))
    for y in (0.1, 0.9):                                         # screws
        for x in (0.82, 0.3):
            d = np.hypot(XX - x * W, YY - y * H)
            img = over(img, '#8d8a85', np.clip(16 - d, 0, 1))
            img = over(img, '#3d3b38', np.clip(3 - np.abs((XX - x * W) - (YY - y * H)) , 0, 1) * (d < 13))
    rect(0.8, 0.3, 0.9, 0.7, '#3f3c38', rad=0.01)                # head opening area
    save(img, '05')
    # 03 plectrums on dark felt, the title at the top
    img = paper('#1c1b1d', 510, 0.03, 0.08)
    for i, (y, col) in enumerate([(0.31, '#e0b84a'), (0.5, '#8fa9a4'), (0.69, '#e9e6df'), (0.88, '#d4563b')]):
        cx, cy, R = 0.5 * W, y * H, 0.12 * W
        def pickmask(off=(0, 0), blur=0.7):
            # a rounded triangle, wide at the top, pointing down
            ss = 2
            m = Image.new('L', (W * ss, H * ss), 0); d = ImageDraw.Draw(m)
            A = (cx - R * 0.78 + off[0], cy - R * 0.62 + off[1]); B = (cx + R * 0.78 + off[0], cy - R * 0.62 + off[1]); C = (cx + off[0], cy + R * 0.85 + off[1])
            d.polygon([(p[0] * ss, p[1] * ss) for p in (A, B, C)], fill=255)
            # the top edge bulges a little
            d.ellipse([(cx - R * 0.8 + off[0]) * ss, (cy - R * 0.85 + off[1]) * ss, (cx + R * 0.8 + off[0]) * ss, (cy - R * 0.35 + off[1]) * ss], fill=255)
            m = m.resize((W, H), Image.LANCZOS)
            a = gaussian_filter(np.asarray(m, float) / 255, R * 0.14)
            a = np.clip((a - 0.5) * 6 + 0.5, 0, 1)
            return gaussian_filter(a, blur)
        sm = pickmask((10, 14), 10)
        img = img * (1 - 0.6 * sm[..., None])
        m = pickmask()
        sheen = np.clip(1 - np.hypot(XX - cx + R * 0.4, YY - cy + R * 0.5) / (R * 1.4), 0, 1) * 0.22
        c = hexrgb(col)
        body = c[None, None, :] * (0.92 + 0.1 * noise(H, W, 30, 520 + i, 2)[..., None]) + sheen[..., None]
        img = img * (1 - m[..., None]) + np.clip(body, 0, 1) * m[..., None]
    save(img, '03')
    # 04 a page of music with watercolour washes; a card at the bottom carries the title
    img = paper('#f1ead9', 530, 0.02, 0.05)
    r = np.random.default_rng(531)
    for i, (x, y, rad, col) in enumerate([(0.25, 0.25, 0.3, '#2b5fa8'), (0.75, 0.4, 0.26, '#d8a32c'), (0.4, 0.6, 0.22, '#c0392b'), (0.8, 0.12, 0.18, '#2d7a6a')]):
        n = noise(H, W, 120, 540 + i, 4)
        d = np.hypot(XX - x * W, YY - y * H) / (rad * W)
        m = np.clip((1 - d) * 1.6 + (n - 0.5) * 1.4, 0, 1)
        edge = np.clip(1 - np.abs(m - 0.15) * 8, 0, 1) * 0.35
        img = mult(img, hexrgb(col), np.clip(m * 0.45 + edge, 0, 1))
    staff_y = [0.08 + k * 0.095 for k in range(9)]
    def staves(d, s):
        for y0 in staff_y:
            for j in range(5):
                y = (y0 + j * 0.008) * H
                d.line([(0.07 * W * s, y * s), (0.93 * W * s, y * s)], fill=255, width=int(2 * s))
            # bar lines and notes
            for bx in np.linspace(0.07, 0.93, 5):
                d.line([(bx * W * s, y0 * H * s), (bx * W * s, (y0 + 0.032) * H * s)], fill=255, width=int(2 * s))
            for nx in np.linspace(0.1, 0.9, 16):
                if r.random() < 0.15: continue
                ny = y0 + r.integers(-2, 10) * 0.004
                cx, cy = nx * W, ny * H
                d.ellipse([(cx - 11) * s, (cy - 8) * s, (cx + 11) * s, (cy + 8) * s], fill=255)
                up = ny > y0 + 0.016
                d.line([((cx + (10 if up else -10)) * s, cy * s), ((cx + (10 if up else -10)) * s, (cy + (-70 if up else 70)) * s)], fill=255, width=int(3 * s))
    m = mask_from(staves, blur=0.5)
    img = mult(img, hexrgb('#262321'), m * 0.85)
    save(img, '04')
    # 21 spruce and an f-hole: the top of a string instrument, close up
    gx = XX + gaussian_filter(np.random.default_rng(550).standard_normal((H, W)), 30) * 40
    grain_ = 0.5 + 0.5 * np.sin(gx / W * 2 * math.pi * 60 + noise(H, W, 400, 551, 3) * 10)
    fine = grain(H, W, 552, 0.03)
    base = hexrgb('#b8742f')
    img = base[None, None, :] * (0.86 + 0.12 * grain_[..., None] ** 4) + fine[..., None]
    img = img * (0.75 + 0.3 * np.clip(1 - np.abs(XX / W - 0.55) * 1.3, 0, 1))[..., None]
    img = img * (0.85 + 0.25 * noise(H, W, 500, 553, 2)[..., None])
    def fhole(d, s):
        cx = 0.6 * W
        L, R_ = [], []
        for t in np.linspace(0, 1, 90):
            y = (0.2 + t * 0.56) * H
            x = cx + math.sin(t * math.pi - math.pi / 2) * 0.05 * W
            w = 9 + 14 * math.sin(t * math.pi) ** 0.5
            if 0.46 < t < 0.54: w *= 0.5
            L.append(((x - w) * s, y * s)); R_.append(((x + w) * s, y * s))
        d.polygon(L + R_[::-1], fill=255)
        for (x, y) in ((cx - 0.05 * W, 0.2 * H), (cx + 0.05 * W, 0.76 * H)):
            d.ellipse([(x - 30) * s, (y - 30) * s, (x + 30) * s, (y + 30) * s], fill=255)
        my = 0.48 * H
        d.polygon([((cx - 40) * s, (my - 4) * s), ((cx + 40) * s, (my + 10) * s), ((cx + 40) * s, (my + 14) * s), ((cx - 40) * s, (my)*s)], fill=255)
    m = mask_from(fhole, blur=0.8)
    edge = np.clip(gaussian_filter(m, 4) - m, 0, 1)
    img = img * (1 - edge[..., None] * 0.6)
    img = over(img, '#120a05', m)
    # purfling near the edge
    pm = mask_from(lambda d, s: d.rounded_rectangle([0.06 * W * s, -0.2 * H * s, 1.4 * W * s, 1.2 * H * s], radius=0.4 * W * s, outline=255, width=int(7 * s)), blur=0.6)
    img = mult(img, hexrgb('#2a160a'), pm * 0.8)
    save(img, '21')

if __name__ == '__main__':
    which = sys.argv[2].split(',') if len(sys.argv) > 2 else ['records']
    for w in which: globals()[w]()
