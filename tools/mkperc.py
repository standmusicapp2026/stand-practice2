# Versilian Community Sample Library (CC0): tuned percussion at several strengths -> the app's sets
# "p_<name>" with per-layer note lists (index NL) and each recording's tuning measured (index T).
import os, re, glob, json, subprocess, sys, numpy as np, soundfile as sf, librosa, warnings; warnings.filterwarnings('ignore')
V = '/home/claude/sgossner/vcsl'; D = '/home/claude/s24/Payload/Stand.app/www/vendor/sounds'
NOTE = {'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3, 'E': 4, 'F': 5, 'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8, 'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11}
def midi(n): m = re.match(r'([A-G][#b]?)(-?\d)', n); return 12 * (int(m.group(2)) + 1) + NOTE[m.group(1)]
CFG = {
  'p_marimba': (V + '/Idiophones/Struck Idiophones/Marimba/**/Marimba_hit_Outrigger_*.wav', r'_([A-G]#?\d)_(soft|med|loud)_01', {'soft': 'p', 'med': 'm', 'loud': 'f'}, 3.0),
  'p_xylo': (V + '/Idiophones/Struck Idiophones/Xylophone/**/Xylo_Medium_*.wav', r'_([A-G]#?\d)_(pp|ff)_01', {'pp': 'p', 'ff': 'f'}, 1.6),
  'p_glock': (V + '/Idiophones/Struck Idiophones/Glockenspiel/**/glock_*.wav', r'glock_(soft|medium|loud)_([A-G]#?\d)_', {'soft': 'p', 'medium': 'm', 'loud': 'f'}, 4.0),
  'p_vibes': (V + '/Idiophones/Struck Idiophones/Vibraphone/**/Vibes_*.wav', r'Vibes_(soft|hard)_([A-G]#?\d)_(v\d)', None, 6.0),
  'p_chimes': (V + '/Idiophones/Struck Idiophones/Tubular Bells 1/**/chimes_*.wav', r'chimes_([A-G]#?\d)_(pp|p|f|ff|fff)_', {'pp': 'p', 'p': 'p', 'f': 'f', 'ff': 'f', 'fff': 'f'}, 6.0),
}
tmp = '/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad/pc.wav'
I = json.load(open(D + '/index.json')); I.setdefault('NL', {}); I.setdefault('T', {})
def measure(x, sr, m):
    seg = x[int(sr * 0.05): int(sr * 1.0)]
    f0 = librosa.yin(seg, fmin=librosa.midi_to_hz(m - 3), fmax=librosa.midi_to_hz(m + 3), sr=sr, frame_length=4096 if m < 60 else 2048, hop_length=256)
    mm = librosa.hz_to_midi(f0); mm = mm[np.abs(mm - m) < 0.8]
    return float(np.median((mm - m) * 100)) if len(mm) > 5 else 0.0
for set_, (pat, rx, lay, keep) in CFG.items():
    out = f'{D}/{set_}'; os.makedirs(out, exist_ok=True); T = {}; NL = {}
    chosen = {}
    for f in sorted(glob.glob(pat, recursive=True)):
        g = re.search(rx, os.path.basename(f))
        if not g: continue
        if set_ == 'p_glock': L = lay[g.group(1)]; m = midi(g.group(2))
        elif set_ == 'p_vibes':
            hard, nm, v = g.group(1), g.group(2), g.group(3); m = midi(nm)
            L = 'p' if (hard == 'soft' and v == 'v1') else 'm' if (hard == 'soft' and v == 'v2') else 'f' if (hard == 'hard' and v == 'v3') else None
            if not L: continue
        else: m = midi(g.group(1)); L = lay[g.group(2)]
        if (m, L) in chosen: continue
        chosen[(m, L)] = f
    for (m, L), f in sorted(chosen.items()):
        x, sr = sf.read(f, always_2d=True); x = x.mean(1)
        a = np.abs(x); th = a.max() * 10 ** (-50 / 20); s0 = max(0, int(np.argmax(a > th)) - int(sr * 0.002)); x = x[s0:s0 + int(sr * keep)]
        cents = measure(x, sr, m)
        fd = int(len(x) * 0.25); x[-fd:] *= np.linspace(1, 0, fd) ** 2
        sf.write(tmp, x.astype(np.float32), sr, subtype='PCM_16')
        subprocess.run(['ffmpeg', '-v', 'quiet', '-y', '-i', tmp, '-ac', '1', '-ar', '44100', '-codec:a', 'libmp3lame', '-b:a', '128k', f'{out}/{m}_{L}.mp3'], check=True)
        T[f'{m}_{L}'] = round(-cents, 1); NL.setdefault(L, []).append(m)
    Ls = [l for l in ['p', 'm', 'f'] if l in NL]
    I['n'][set_] = sorted({m for (m, _) in chosen}); I['L'][set_] = Ls; I['NL'][set_] = {l: sorted(NL[l]) for l in Ls}; I['T'][set_] = T
    print(set_, Ls, {l: len(NL[l]) for l in Ls}, 'tuning', sorted(T.values())[:2], sorted(T.values())[-2:])
json.dump(I, open(D + '/index.json', 'w'), separators=(',', ':'))
