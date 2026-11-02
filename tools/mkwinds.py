# University of Iowa MIS (2012, "used for any projects, without restrictions"): real winds and brass,
# ff, one note every minor third, trimmed and made mono for the app (sets w_<sid>).
import os, re, glob, json, subprocess, numpy as np, soundfile as sf, librosa
NOTE = {'C':0,'Db':1,'D':2,'Eb':3,'E':4,'F':5,'Gb':6,'G':7,'Ab':8,'A':9,'Bb':10,'B':11}
SRC = '/home/claude/iowa/w12'; D = '/home/claude/s24/Payload/Stand.app/www/vendor/sounds'
MAP = {'Flute': 'flute', 'Oboe': 'oboe', 'BbClarinet': 'clarinet', 'Bassoon': 'bassoon', 'Horn': 'horn', 'BbTrumpet': 'trumpet'}
I = json.load(open(D + '/index.json'))
tmp = '/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad/w.wav'
for p, sid in MAP.items():
    files = {}
    for f in glob.glob(f'{SRC}/{p}/*.aif'):
        nm = re.search(r'\.([A-G]b?\d)\.stereo', f).group(1); files[12 * (int(nm[-1]) + 1) + NOTE[nm[:-1]]] = f
    ms = sorted(files); pick = ms[::3]
    if ms[-1] - pick[-1] >= 2: pick.append(ms[-1])
    out = f'{D}/w_{sid}'; os.makedirs(out, exist_ok=True)
    got = []
    for m in pick:
        x, sr = sf.read(files[m], always_2d=True); x = x.mean(1)
        a = np.abs(x); th = a.max() * 10 ** (-45 / 20)
        s0 = max(0, int(np.argmax(a > th)) - int(sr * 0.003))
        e0 = len(a) - int(np.argmax(a[::-1] > th))
        x = x[s0:min(e0, s0 + int(sr * 4.5))]
        if len(x) < sr * 1.4: print('short', p, m, len(x) / sr); 
        fd = int(sr * 0.08); x[-fd:] *= np.linspace(1, 0, fd)
        y = librosa.resample(x, orig_sr=sr, target_sr=44100)
        sf.write(tmp, y.astype(np.float32), 44100, subtype='PCM_16')
        subprocess.run(['ffmpeg', '-v', 'quiet', '-y', '-i', tmp, '-ac', '1', '-codec:a', 'libmp3lame', '-b:a', '128k', f'{out}/{m}.mp3'], check=True)
        got.append(m)
    I['n']['w_' + sid] = got
    print(sid, got)
json.dump(I, open(D + '/index.json', 'w'), separators=(',', ':'))
