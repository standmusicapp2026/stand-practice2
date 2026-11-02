# Capture on real LilyPond editions (Mutopia) against their MIDI: every page, then the totals
M=/home/claude/real/muto; cd /home/claude/tools
run() { python3 capeval.py $M/$1 $2 $3 2>&1 | grep -E "^TOTAL|^page|^    " | sed "s#^#$1 #"; }
run bwv1008-a4.pdf $M/bwv1008-mids/bwv1008.mid,$(ls $M/bwv1008-mids/bwv1008-[1-6].mid | tr '\n' ',' | sed 's/,$//') $1
run cellosuite3-a4.pdf $M/cellosuite3-mids/cellosuite3.mid,$(ls $M/cellosuite3-mids/cellosuite3-[1-6].mid | tr '\n' ',' | sed 's/,$//') $1
run bwv1010-a4.pdf $M/bwv1010-mids/bwv1010.mid,$(ls $M/bwv1010-mids/bwv1010-[1-6].mid | tr '\n' ',' | sed 's/,$//') $1
run bwv-1012-1-a4.pdf $M/bwv-1012-1.mid $1
run bwv-1012-3-a4.pdf $M/bwv-1012-3.mid $1
