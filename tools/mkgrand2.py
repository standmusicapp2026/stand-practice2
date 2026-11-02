# Salamander Grand Piano V3 (Yamaha C5, Alexander Holm, CC-BY 3.0): six strengths, stereo, the natural
# length (long in the bass), for the app's concert grand ("grand2"). Each strength keeps its own
# recorded loudness (a real piano is louder as well as brighter when played harder).
import os, subprocess, json, numpy as np, soundfile as sf
S = '/home/claude/salamander/SalamanderGrandPianoV3_44.1khz16bit/44.1khz16bit'
D = '/home/claude/s24/Payload/Stand.app/www/vendor/sounds/grand2'
os.makedirs(D, exist_ok=True)
NAMES = {'C': 0, 'D#': 3, 'F#': 6, 'A': 9}
LAY = {'1': 4, '2': 7, '3': 9, '4': 11, '5': 13, '6': 15}          # Salamander layers used
VEL = {'1': 40, '2': 53, '3': 68, '4': 84, '5': 100, '6': 116}       # their MIDI velocity (middle)
tmp = '/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad/g2.wav'
out = []
for f in sorted(os.listdir(S)):
    if not f.endswith('v1.wav') or f.startswith('harm'): continue
    nm = f[:-6]; n = nm[:-1]; o = int(nm[-1]); m = 12 * (o + 1) + NAMES[n]
    for L, v in LAY.items():
        x, sr = sf.read(f'{S}/{nm}v{v}.wav', always_2d=True)
        a = np.abs(x).max(1); th = a.max() * 10 ** (-50 / 20)
        s0 = max(0, int(np.argmax(a > th)) - int(sr * 0.002))
        keep = 3.0 + (108 - m) / 87 * 9.0
        x = x[s0:s0 + int(sr * keep)]
        fd = int(sr * min(1.0, keep * 0.2)); x[-fd:] *= (np.linspace(1, 0, fd) ** 2)[:, None]
        sf.write(tmp, x, sr, subtype='PCM_16')
        subprocess.run(['ffmpeg', '-v', 'quiet', '-y', '-i', tmp, '-codec:a', 'libmp3lame', '-b:a', '160k', f'{D}/{m}_{L}.mp3'], check=True)
    out.append(m)
I = json.load(open(D + '/../index.json'))
I['n']['grand2'] = sorted(out); I['L']['grand2'] = list(LAY); I.setdefault('LV', {})['grand2'] = [VEL[k] / 127 for k in LAY]
json.dump(I, open(D + '/../index.json', 'w'), separators=(',', ':'))
print(len(out))
