#!/bin/bash
# bench1.sh SET PORT TAG [GLOB]: realbench on one set against the app served on PORT; results in
# $SP/TAG_SET.json and .txt (resumes where it stopped). Restarts the app servers if they are down
# (8765 = the build to beat, 8766 = the build being worked on; WT_BASE / WT_DEV their folders).
SP=${SP:-/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad}
SET=$1; PORT=$2; TAG=$3; G="${4:-{\}}"
WT_BASE=${WT_BASE:-$SP/base}; WT_DEV=${WT_DEV:-$SP/dev}
# (realbench starts the app's server itself when it is down, as its own child: a server started on
# its own here was stopped after a while)

cd /home/claude/omreval/tools
SP=$SP PORT=$PORT GLOB="$G" OUTJ=$SP/${TAG}_$SET.json python3 realbench.py $SET > $SP/${TAG}_$SET.txt 2>&1
tail -1 $SP/${TAG}_$SET.txt
