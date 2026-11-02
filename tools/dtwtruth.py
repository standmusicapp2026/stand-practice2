# When each note of the read score is played in a recording (offline alignment, for judging turns)
import json, sys, subprocess, numpy as np
audio, readjson = sys.argv[1], sys.argv[2]
pages = json.loads(open(readjson).readline())
# by bars: each bar's notes together (arpeggios ring on: the bar's harmony is what is heard)
seq = []; starts = []; boff = 0
for p in pages:
    starts.append(len(seq)); nb = max(e['bar'] for e in p['seq']) + 1
    bars = [[] for _ in range(nb)]
    for e in p['seq']: bars[e['bar']] += e['pcs']
    seq += bars
sr = 22050
x = np.frombuffer(subprocess.run(['ffmpeg', '-v', 'quiet', '-i', audio, '-ac', '1', '-ar', str(sr), '-f', 'f32le', '-'], capture_output=True).stdout, dtype=np.float32)
N, H = 4096, 1024
win = np.hanning(N); frames = []
freqs = np.fft.rfftfreq(N, 1 / sr)
valid = (freqs > 60) & (freqs < 2000)
pc = np.zeros(len(freqs), dtype=int); pc[valid] = (np.round(12 * np.log2(freqs[valid] / 440)) + 69).astype(int) % 12
for s in range(0, len(x) - N, H):
    m = np.abs(np.fft.rfft(x[s:s + N] * win)); m = np.log1p(m * 100)
    c = np.zeros(12); np.add.at(c, pc[valid], m[valid]); frames.append(c / (np.linalg.norm(c) + 1e-9))
F = np.array(frames); T = len(F)
tpl = np.zeros((len(seq), 12))
for i, ps in enumerate(seq):
    for q in ps: tpl[i, q] += 1; tpl[i, (q + 7) % 12] += 0.15
    tpl[i] /= np.linalg.norm(tpl[i]) + 1e-9
MIN = int(1.0 * sr / H)
tpl = np.repeat(tpl, MIN, axis=0)
F = F - 0.85 * F.mean(0, keepdims=True)   # (what rings all the time — open strings, the room — taken out)
Fc = F - F.mean(1, keepdims=True); Fc /= np.linalg.norm(Fc, axis=1, keepdims=True) + 1e-9
Tc = tpl - tpl.mean(1, keepdims=True); Tc /= np.linalg.norm(Tc, axis=1, keepdims=True) + 1e-9
cost = 1 - Fc @ Tc.T   # T x n (each bar as MIN states in a row: at least a second long)
n = tpl.shape[0]; D = np.full((T + 1, n + 1), np.inf); D[0, 0] = 0
B = np.zeros((T + 1, n + 1), dtype=np.int8)
for t in range(1, T + 1):
    c = cost[t - 1]
    stay = D[t - 1, 1:]; adv = D[t - 1, :-1]
    best = np.minimum(stay, adv); B[t, 1:] = (adv < stay)
    D[t, 1:] = best + c
# a little silence allowed at the start and end: free start/end in time
t_end = np.argmin(D[:, n][int(T * 0.8):]) + int(T * 0.8)
path_t = {}
t, j = t_end, n
while t > 0 and j > 0:
    path_t[j - 1] = t - 1
    if B[t, j]: j -= 1
    t -= 1
tm = lambda b: round(path_t.get(b * MIN, 0) * H / sr, 2)
print(json.dumps({'pageStartBars': starts, 'barStarts': [tm(b) for b in range(len(seq))], 'dur': round(len(x) / sr, 1)}))
if '-v' in sys.argv:
    nb = len(seq); Tb = Tc[::MIN]
    sim = Fc @ Tb.T
    for t0 in range(0, T, int(5 * sr / H)):
        seg = sim[t0:t0 + int(5 * sr / H)].mean(0)
        print(round(t0 * H / sr), 'best bars', list(np.argsort(-seg)[:3]), round(float(seg.max()), 2))
