# (suite) Studio: follow again and tap from a bar, on the orchestra video
import os, subprocess, sys
r = subprocess.run([sys.executable, '/home/claude/tools/studiofrom.py', '/home/claude/realvid/orch_elgar.webm', '/home/claude/realvid/crop_elgar.png', '/tmp/x.mp4', 'warm', 'lines', '16:9'], env={**os.environ, 'SYNCONLY': '1'}, capture_output=True, text=True, timeout=880)
print(r.stdout[-1500:]); print(r.stderr[-800:])
