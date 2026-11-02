# all LilyPond test pages: capture accuracy, one line each, then the total
cd /home/claude
tot=0
for f in /home/claude/lyb/t*.pdf; do b=${f%.pdf}; python3 tools/capeval.py $f $b.midi 2>&1 | grep '^page'; done
