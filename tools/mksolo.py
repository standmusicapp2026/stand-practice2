# University of Iowa MIS 2012 solo strings (arco ff, every note on every string; free for any use)
# -> the app's solo cello / viola: for each note the string a player would use, its exact tuning
# measured (index "T": cents to correct), trimmed, mono.
import os, re, glob, json, sys, subprocess, numpy as np, soundfile as sf, librosa, warnings; warnings.filterwarnings('ignore')
NOTE = {'C':0,'Db':1,'D':2,'Eb':3,'E':4,'F':5,'Gb':6,'G':7,'Ab':8,'A':9,'Bb':10,'B':11}
inst, setname = sys.argv[1], sys.argv[2]
OPEN = {'Cello': {'C': 36, 'G': 43, 'D': 50, 'A': 57}, 'Viola': {'C': 48, 'G': 55, 'D': 62, 'A': 69}}[inst]
SRC = f'/home/claude/iowa/s12/{inst}'; D = '/home/claude/s24/Payload/Stand.app/www/vendor/sounds'
files = {}
for f in glob.glob(SRC + '/*.aif'):
    g = re.search(r'\.sul([CGDA])\.([A-G]b?\d)\.stereo', f)
    if not g: continue
    s, nm = g.group(1), g.group(2); m = 12 * (int(nm[-1]) + 1) + NOTE[nm[:-1]]
    files.setdefault(m, {})[s] = f
def choose(m):
    opts = files[m]
    # the highest string whose open note is below the note (a stopped note, with vibrato); the
    # lowest note of each string only on its own string when nothing else can play it
    best = None
    for s, o in sorted(OPEN.items(), key=lambda q: -q[1]):
        if s in opts and o < m: best = s; break
    if best is None: best = min(opts, key=lambda s: OPEN[s])
    return opts[best], best
tmp = '/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad/s.wav'
out = f'{D}/{setname}'; os.makedirs(out, exist_ok=True)
I = json.load(open(D + '/index.json')); T = I.setdefault('T', {}); T[setname] = {}
got = []
for m in sorted(files):
    f, s = choose(m)
    x, sr = sf.read(f, always_2d=True); x = x.mean(1)
    a = np.abs(x); th = a.max() * 10 ** (-45 / 20)
    s0 = max(0, int(np.argmax(a > th)) - int(sr * 0.003)); e0 = len(a) - int(np.argmax(a[::-1] > th))
    x = x[s0:e0]
    y = librosa.resample(x, orig_sr=sr, target_sr=22050)
    seg = y[int(22050 * 0.4): int(22050 * 2.2)]
    f0 = librosa.yin(seg, fmin=librosa.midi_to_hz(m - 4), fmax=librosa.midi_to_hz(m + 4), sr=22050, frame_length=4096, hop_length=256)
    mm = librosa.hz_to_midi(f0); mm = mm[np.abs(mm - m) < 1.2]
    if len(mm) < 10: print('no pitch', m, s); continue
    cents = float(np.median((mm - m) * 100))
    if abs(cents) > 60: print('far off', m, s, cents); continue
    fd = int(sr * 0.06); x[-fd:] *= np.linspace(1, 0, fd)
    y = librosa.resample(x, orig_sr=sr, target_sr=44100)
    sf.write(tmp, y.astype(np.float32), 44100, subtype='PCM_16')
    subprocess.run(['ffmpeg', '-v', 'quiet', '-y', '-i', tmp, '-ac', '1', '-codec:a', 'libmp3lame', '-b:a', '128k', f'{out}/{m}_f.mp3'], check=True)
    T[setname][str(m)] = round(-cents, 1); got.append(m)
    print(m, s, round(cents, 1), round(len(x) / sr, 2))
I['n'][setname] = got; I['L'][setname] = ['f']
json.dump(I, open(D + '/index.json', 'w'), separators=(',', ':'))
print(setname, len(got), got)
