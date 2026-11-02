# VSCO 2 CE solo violin (CC0), arco with vibrato, soft and loud -> the app's solo violin ("vl_solo").
# Each recording: trimmed at its start, its tuning measured (index "T"), 7 s kept (the rest loops), mono.
import os, re, glob, json, subprocess, numpy as np, soundfile as sf, librosa, warnings; warnings.filterwarnings('ignore')
NOTE = {'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5, 'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11}
SRC = '/home/claude/sgossner/vsco-2-ce/Strings/Solo Violin/Arco Vib'; D = '/home/claude/s24/Payload/Stand.app/www/vendor/sounds'
out = D + '/vl_solo'; os.makedirs(out, exist_ok=True)
tmp = '/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad/v.wav'
I = json.load(open(D + '/index.json')); T = I.setdefault('T', {}); T['vl_solo'] = {}
got = set()
for f in sorted(glob.glob(SRC + '/*.wav')):
    g = re.search(r'_([A-G]#?)(\d)_(p|f)\.wav$', f); nm, o, lay = g.group(1), int(g.group(2)), g.group(3)
    m = 12 * (o + 1) + NOTE[nm]
    x, sr = sf.read(f, always_2d=True); x = x.mean(1)
    a = np.abs(x); th = a.max() * 10 ** (-45 / 20)
    s0 = max(0, int(np.argmax(a > th)) - int(sr * 0.003)); x = x[s0:s0 + int(sr * 7.0)]
    y = librosa.resample(x, orig_sr=sr, target_sr=22050); seg = y[int(22050 * 0.5): int(22050 * 3.0)]
    f0 = librosa.yin(seg, fmin=librosa.midi_to_hz(m - 4), fmax=librosa.midi_to_hz(m + 4), sr=22050, frame_length=4096, hop_length=256)
    mm = librosa.hz_to_midi(f0); mm = mm[np.abs(mm - m) < 1.2]
    cents = float(np.median((mm - m) * 100)) if len(mm) > 10 else 0.0
    fd = int(sr * 0.08); x[-fd:] *= np.linspace(1, 0, fd)
    sf.write(tmp, x.astype(np.float32), sr, subtype='PCM_16')
    subprocess.run(['ffmpeg', '-v', 'quiet', '-y', '-i', tmp, '-ac', '1', '-codec:a', 'libmp3lame', '-b:a', '128k', f'{out}/{m}_{lay}.mp3'], check=True)
    T['vl_solo'][f'{m}_{lay}'] = round(-cents, 1)
    if lay == 'f': T['vl_solo'][str(m)] = round(-cents, 1)
    got.add(m); print(m, lay, round(cents, 1))
I['n']['vl_solo'] = sorted(got); I['L']['vl_solo'] = ['p', 'f']
json.dump(I, open(D + '/index.json', 'w'), separators=(',', ':'))
