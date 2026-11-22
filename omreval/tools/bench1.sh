#!/bin/bash
# bench1.sh SET PORT TAG [GLOB]: realbench on one set against the app served on PORT; results in
# $SP/TAG_SET.json and .txt (resumes where it stopped). Restarts the app servers if they are down
# (8765 = the build to beat, 8766 = the build being worked on; WT_BASE / WT_DEV their folders).
SP=${SP:-/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad}
WT_BASE=${WT_BASE:-$SP/base}; WT_DEV=${WT_DEV:-$SP/dev}
for pd in "8765 $WT_BASE" "8766 $WT_DEV"; do set -- $pd
  curl -s -o /dev/null localhost:$1/index.html || (cd $2 && setsid nohup python3 -m http.server $1 >/dev/null 2>&1 &)
done; sleep 1

cd /home/claude/omreval/tools
PORT=$2 GLOB="${4:-{\}}" OUTJ=$SP/$3_$1.json python3 realbench.py $1 > $SP/$3_$1.txt 2>&1
tail -1 $SP/$3_$1.txt
