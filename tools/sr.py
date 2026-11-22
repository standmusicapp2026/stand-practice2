# Real-ESRGAN (realesr-general-x4v3, SRVGGNetCompact) run with numpy only: 4x enlargement.
import sys, zipfile, pickle, numpy as np
from PIL import Image

def load_pth(path):
    z = zipfile.ZipFile(path)
    root = z.namelist()[0].split('/')[0]
    DT = {'FloatStorage': np.float32, 'HalfStorage': np.float16, 'DoubleStorage': np.float64, 'LongStorage': np.int64, 'IntStorage': np.int32}
    class U(pickle.Unpickler):
        def find_class(self, mod, name):
            if name == '_rebuild_tensor_v2':
                def rb(storage, offset, size, stride, *a):
                    arr = np.lib.stride_tricks.as_strided(storage[offset:], shape=size, strides=[s * storage.itemsize for s in stride]) if size else storage[offset:offset + 1].reshape(())
                    return np.array(arr)
                return rb
            if name == '_rebuild_parameter':
                return lambda data, *a: data
            if name.endswith('Storage'):
                return name
            if mod == 'collections' and name == 'OrderedDict':
                import collections; return collections.OrderedDict
            return super().find_class(mod, name)
        def persistent_load(self, pid):
            _, stype, key, loc, numel = pid
            data = z.read(f'{root}/data/{key}')
            return np.frombuffer(data, dtype=DT[stype if isinstance(stype, str) else stype.__name__])
    return U(z.open(f'{root}/data.pkl')).load()

def conv3(x, w, b):
    # x: (H, W, Cin), w: (Cout, Cin, 3, 3)
    H, W_, C = x.shape
    p = np.pad(x, ((1, 1), (1, 1), (0, 0)), mode='edge')
    out = np.zeros((H * W_, w.shape[0]), np.float32)
    for dy in range(3):
        for dx in range(3):
            out += p[dy:dy + H, dx:dx + W_].reshape(-1, C) @ w[:, :, dy, dx].T
    out += b
    return out.reshape(H, W_, -1)

def prelu(x, a):
    return np.where(x >= 0, x, x * a)

def upscale(img, sd):
    x = (np.asarray(img.convert('RGB')).astype(np.float32) / 255.0)
    keys = sorted({int(k.split('.')[1]) for k in sd if k.startswith('body.')})
    h = x
    for k in keys:
        if f'body.{k}.bias' in sd:
            h = conv3(h, sd[f'body.{k}.weight'].astype(np.float32), sd[f'body.{k}.bias'].astype(np.float32))
        else:
            h = prelu(h, sd[f'body.{k}.weight'].astype(np.float32).reshape(1, 1, -1))
    H, W_, C = h.shape
    r = 4
    # pixel shuffle: (H, W, 3*r*r) -> (H*r, W*r, 3); channel index = c*r*r + i*r + j
    h = h.reshape(H, W_, 3, r, r).transpose(0, 3, 1, 4, 2).reshape(H * r, W_ * r, 3)
    base = np.repeat(np.repeat(x, r, 0), r, 1)
    out = np.clip(h + base, 0, 1)
    return Image.fromarray((out * 255 + 0.5).astype(np.uint8))

if __name__ == '__main__':
    sd = load_pth('/home/claude/newcovers/realesr-general-x4v3.pth')
    if 'params' in sd: sd = sd['params']
    elif 'params_ema' in sd: sd = sd['params_ema']
    for src in sys.argv[1:]:
        out = src.replace('.png', '_x4.png')
        upscale(Image.open(src), sd).save(out)
        print(out)
