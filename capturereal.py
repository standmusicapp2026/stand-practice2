# (suite) Capture on real music against its MIDI: a clean engraving, a phone photo and an 1879
# engraving scan. Fails if pitches or lengths read get worse than they are now.
import subprocess, sys, re
r = subprocess.run([sys.executable, '/home/claude/omreval/tools/omreval.py', '/home/claude/omreval/suite5.json'], capture_output=True, text=True, timeout=880)
print(r.stdout[-2500:]); print(r.stderr[-500:])
m = re.search(r'TOTAL pitch right ([\d.]+)%  found ([\d.]+)%  lengths ([\d.]+)%', r.stdout)
ok = m and float(m.group(1)) >= 94 and float(m.group(2)) >= 95 and float(m.group(3)) >= 90
print('PASS' if ok else 'FAIL', 'Capture reads real music (pitch >= 94%, found >= 95%, lengths >= 90%)')
