# the same page with and without the LilyPond shapes (set before the reader loads)
import asyncio, sys, os, subprocess
for flag in ['0', '1']:
    env = dict(os.environ, NOS3=flag)
    print('noShapes3' if flag == '1' else 'with Shapes3')
    subprocess.run(['python3', '/home/claude/tools/capeval_s3.py'] + sys.argv[1:], env=env)
