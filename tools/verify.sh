#!/bin/bash
# bench + real pages + test lines against the saved baselines
S=/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad
cd /home/claude/tools
python3 bench.py Bravura,Leland,Petaluma,MScore 1,2,3,4 clean,scan 2>&1 | grep MEAN
bash realall.sh $S/real_cur.txt; echo "real diff:"; diff $S/real_base.txt $S/real_cur.txt
bash lines.sh $S/lines_cur.txt; echo "lines diff:"; diff $S/lines_base.txt $S/lines_cur.txt
