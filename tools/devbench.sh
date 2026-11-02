# snapshot the dev copy and run the Mutopia bench on it: devbench.sh NAME PORT
rm -rf /tmp/claude-0/snap_$1; cp -R /tmp/claude-0/wdev /tmp/claude-0/snap_$1
WWW=/tmp/claude-0/snap_$1 PORT=$2 bash /home/claude/tools/ws2.sh bash /home/claude/tools/mutobench.sh > /tmp/claude-0/muto_$1.txt 2>&1
