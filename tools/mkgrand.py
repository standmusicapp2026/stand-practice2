# Salamander Grand Piano V3 (Yamaha C5, Alexander Holm, CC-BY 3.0) -> the app's grand piano:
# every minor third from A0, three strengths (p = v5, m = v10, f = v15), stereo, made mono and trimmed to a
# natural length (long in the bass, short in the treble) with a gentle fade.
import os, subprocess, json, numpy as np, soundfile as sf
S = '/home/claude/salamander/SalamanderGrandPianoV3_44.1khz16bit/44.1khz16bit'
D = '/home/claude/s24/Payload/Stand.app/www/vendor/sounds/grand'
NAMES = {'C': 0, 'D#': 3, 'F#': 6, 'A': 9}
LAY = {'p': 5, 'm': 10, 'f': 15}
out = []
for f in sorted(os.listdir(S)):
    if not f.endswith('v1.wav'): continue
    nm = f[:-6]
    n = nm[:-1]; o = int(nm[-1]); m = 12 * (o + 1) + NAMES[n]
    for L, v in LAY.items():
        x, sr = sf.read(f'{S}/{nm}v{v}.wav', always_2d=True)
        a = np.abs(x).max(1); th = a.max() * 10 ** (-50 / 20)
        s0 = max(0, int(np.argmax(a > th)) - int(sr * 0.002))
        keep = 2.5 + (108 - m) / 87 * 6.5
        x = x[s0:s0 + int(sr * keep)]
        fd = int(sr * min(0.8, keep * 0.15)); x[-fd:] *= np.linspace(1, 0, fd)[:, None] ** 2
        tmp = f'/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad/g.wav'
        sf.write(tmp, x, sr, subtype='PCM_16')
        subprocess.run(['ffmpeg', '-v', 'quiet', '-y', '-i', tmp, '-codec:a', 'libmp3lame', '-ac', '1', '-b:a', '112k', f'{D}/{m}_{L}.mp3'], check=True)
    out.append(m)
print(sorted(out), len(out))
I = json.load(open(D + '/../index.json'))
I['n']['grand'] = sorted(out); I['L']['grand'] = ['p', 'm', 'f']; I['g']['grand'] = I['g']['piano']
json.dump(I, open(D + '/../index.json', 'w'), separators=(',', ':'))
