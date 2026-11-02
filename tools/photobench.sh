# Capture on phone-photo versions of real engraved pages (Mutopia, against their MIDI): photobench.sh WWW PORT OUT
M=/home/claude/real/muto; cd /home/claude/tools
export PHOTO=${PHOTO:-1} DPI=${DPI:-200}
run() { WWW=$1 PORT=$2 bash ws2.sh python3 capeval.py $M/$3 $4 $5 2>&1 | grep -E "^TOTAL|^page" | sed "s#^#$3 #"; }
{
run $1 $2 bwv1008-a4.pdf $M/bwv1008-mids/bwv1008.mid,$(ls $M/bwv1008-mids/bwv1008-[1-6].mid | tr '\n' ',' | sed 's/,$//') 1,2,3
run $1 $2 cellosuite3-a4.pdf $M/cellosuite3-mids/cellosuite3.mid,$(ls $M/cellosuite3-mids/cellosuite3-[1-6].mid | tr '\n' ',' | sed 's/,$//') 1,2
run $1 $2 bwv1010-a4.pdf $M/bwv1010-mids/bwv1010.mid,$(ls $M/bwv1010-mids/bwv1010-[1-6].mid | tr '\n' ',' | sed 's/,$//') 1,2
run $1 $2 bwv-1012-1-a4.pdf $M/bwv-1012-1.mid 1,2
} > $3
grep TOTAL $3
