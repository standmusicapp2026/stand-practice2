# The loudness of every recorded note (the steady part, after the attack): so the engine can play
# each note, and the soft and loud recordings, at an even loudness (dynamics come from the music)
import os, json, subprocess, numpy as np, sys
D = '/home/claude/s24/Payload/Stand.app/www/vendor/sounds'
idx = json.load(open(D + '/index.json'))
R = {}
def rms_of(path):
    raw = subprocess.run(['ffmpeg', '-v', 'quiet', '-i', path, '-ac', '1', '-ar', '22050', '-f', 'f32le', '-'], capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.float32)
    if len(x) < 2000: return None
    sr = 22050
    # the loudest 0.4 s window among the first 1.5 s (a note's body; plucked notes: their start)
    seg = x[:int(sr * 1.5)]
    w = int(sr * 0.4); best = 0
    for s in range(0, max(1, len(seg) - w), int(sr * 0.05)):
        r = float(np.sqrt(np.mean(seg[s:s + w] ** 2))); best = max(best, r)
    return best
for sid in sorted(os.listdir(D)):
    p = os.path.join(D, sid)
    if not os.path.isdir(p): continue
    out = {}
    for f in sorted(os.listdir(p)):
        if not f.endswith('.mp3'): continue
        r = rms_of(os.path.join(p, f))
        if r: out[f[:-4]] = round(r, 5)
    if out: R[sid] = out
idx['R'] = R
json.dump(idx, open(D + '/index.json', 'w'), separators=(',', ':'))
print(len(R), 'sets'); 
for k in ['vc_sus', 'vl_sus', 'cello', 'piano']: print(k, R.get(k))
