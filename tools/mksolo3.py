# University of Iowa MIS (the older recordings: pp, mf and ff of every note, free for any use), split into
# single notes -> a solo cello with three strengths ("vc_solo3"): for each note and strength the string a
# player would use, its tuning measured (index "T", per recording), trimmed, mono.
import os, re, glob, json, sys, subprocess, numpy as np, soundfile as sf, librosa, warnings; warnings.filterwarnings('ignore')
SRC = '/home/claude/iowa/notes/cello'; D = '/home/claude/s24/Payload/Stand.app/www/vendor/sounds'; SET = 'vc_solo3'
OPEN = {'C': 36, 'G': 43, 'D': 50, 'A': 57}; LAY = {'pp': 'p', 'mf': 'm', 'ff': 'f'}
files = {}
for f in glob.glob(SRC + '/*.wav'):
    g = re.search(r'cello_arco_(pp|mf|ff)_sul([CGDA])_(\d+)\.wav', f)
    if g: files.setdefault((int(g.group(3)), g.group(1)), {})[g.group(2)] = f
tmp = '/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad/s3.wav'
out = f'{D}/{SET}'; os.makedirs(out, exist_ok=True)
I = json.load(open(D + '/index.json')); T = I.setdefault('T', {}); T[SET] = {}
ms = sorted({m for m, _ in files}); got = {}
for m in ms:
    for dyn, L in LAY.items():
        opts = files.get((m, dyn))
        if not opts: continue
        best = None
        for s, o in sorted(OPEN.items(), key=lambda q: -q[1]):
            if s in opts and o < m: best = s; break
        if best is None: best = min(opts, key=lambda s: OPEN[s])
        x, sr = sf.read(opts[best], always_2d=True); x = x.mean(1)
        a = np.abs(x); th = a.max() * 10 ** (-45 / 20)
        s0 = max(0, int(np.argmax(a > th)) - int(sr * 0.003)); x = x[s0:]
        seg = x[int(sr * 0.4): int(sr * 2.2)]
        f0 = librosa.yin(seg, fmin=librosa.midi_to_hz(m - 4), fmax=librosa.midi_to_hz(m + 4), sr=sr, frame_length=4096, hop_length=512)
        mm = librosa.hz_to_midi(f0); mm = mm[np.abs(mm - m) < 1.2]
        if len(mm) < 8: print('no pitch', m, dyn); continue
        cents = float(np.median((mm - m) * 100))
        if abs(cents) > 70: print('far', m, dyn, round(cents)); continue
        fd = int(sr * 0.06); x[-fd:] *= np.linspace(1, 0, fd)
        sf.write(tmp, x.astype(np.float32), sr, subtype='PCM_16')
        subprocess.run(['ffmpeg', '-v', 'quiet', '-y', '-i', tmp, '-ac', '1', '-codec:a', 'libmp3lame', '-b:a', '128k', f'{out}/{m}_{L}.mp3'], check=True)
        T[SET][f'{m}_{L}'] = round(-cents, 1); got.setdefault(m, set()).add(L)
full = [m for m in sorted(got) if got[m] == {'p', 'm', 'f'}]
print('notes with all three:', len(full), 'of', len(got), [m for m in sorted(got) if got[m] != {'p', 'm', 'f'}])
I['n'][SET] = sorted(got); I['L'][SET] = ['p', 'm', 'f']
I.setdefault('NL', {})[SET] = {L: sorted(m for m in got if L in got[m]) for L in ['p', 'm', 'f']}
print(I['NL'][SET])
json.dump(I, open(D + '/index.json', 'w'), separators=(',', ':'))
