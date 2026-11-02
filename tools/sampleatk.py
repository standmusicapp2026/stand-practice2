# Per recording of the real strings, its onset curve: the level (dB, relative to the held sound)
# at fixed times after the sound starts, and when it starts. index.json "A" = {set: {"<m>_<layer>": [start, [dB...]]}}
import json, os, numpy as np, librosa, warnings; warnings.filterwarnings('ignore')
D = '/home/claude/s24/Payload/Stand.app/www/vendor/sounds'
TS = [0.005, 0.015, 0.03, 0.05, 0.08, 0.12, 0.17, 0.24, 0.32, 0.42, 0.55]
I = json.load(open(f'{D}/index.json'))
A = {}
for s in ['vl_sus', 'va_sus', 'vc_sus', 'cb_sus', 'vc_solo', 'vc_solo3', 'vl_solo'] + (['va_solo'] if os.path.isdir(D + '/va_solo') else []):
    A[s] = {}
    for f in sorted(os.listdir(f'{D}/{s}')):
        if not f.endswith('.mp3'): continue
        y, sr = librosa.load(f'{D}/{s}/{f}', sr=22050)
        hop = 55
        r = librosa.feature.rms(y=y, frame_length=441, hop_length=hop, center=True)[0]; db = 20 * np.log10(r + 1e-7)
        fps = sr / hop; n = len(db)
        sus = np.median(db[int(min(n - 2, 1.0 * fps)):int(min(n - 1, 2.0 * fps))])
        on = int(np.argmax(db > sus - 30))
        lv = [round(float(np.clip(db[min(n - 1, on + int(t * fps))] - sus, -40, 12)), 1) for t in TS]
        A[s][f[:-4]] = [round(on / fps, 3), lv]
    print(s, list(A[s].items())[:3])
I['A'] = A; I['AT'] = TS
json.dump(I, open(f'{D}/index.json', 'w'), separators=(',', ':'))
