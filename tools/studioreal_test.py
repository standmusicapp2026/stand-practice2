# Real performances through Studio's automatic following (videos and scores in /home/claude/realvid):
# a soloist slow (violin), fast (guitar, transposed), and a cellist with piano must stay lined up.
import subprocess, json, os
R = '/home/claude/realvid/'
cases = [('slow_sarabande.webm', 'crop_sarabande.png', None, None, 0.65, 'soloist, slow'),
         ('fast_prelude.webm', 'crop_prelude.png', None, None, 0.80, 'soloist, fast'),
         ('piano_elegie.webm', 'crop_elegie.png', '0', '205', 0.65, 'with piano')]
ok = True
for v, c, a, b, need, what in cases:
    args = ['python3', '/home/claude/tools/studioreal.py', R + v, R + c, '/tmp/claude-0/x.mp4', 'paper', 'scroll', '9:16'] + ([a, b, R + v, 'pre'] if a else [])
    out = subprocess.run(args, capture_output=True, text=True, env={**os.environ, 'SYNCONLY': '1'}, timeout=900).stdout
    d = json.loads(out.split('STUDIO ', 1)[1].splitlines()[0]) if 'STUDIO ' in out else {}
    g = (d.get('info') or {}).get('good', 0); t = d.get('times') or []
    mono = all(y >= x for x, y in zip(t, t[1:])); spread = (t[-1] - t[0]) if t else 0
    good = g >= need and mono and spread > 60
    ok &= good
    print('PASS' if good else 'FAIL', f'{what}: {g:.0%} of the notes, bars from {t[0] if t else 0}s to {t[-1] if t else 0}s, {d.get("info", {}).get("how")}', flush=True)
print('PASS' if ok else 'FAIL', 'Studio follows real performances')
