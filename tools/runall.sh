#!/bin/bash
SP=/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad
cd /home/claude/tools
for t in smoke layers addpages zoomtest touchturn turnstress phfolders phscores libtest statetest tourtest turnmany compedit comppaste cappaste libdrag layui phscores backup_rt backup_sets routetest scaletest selbar selscroll studiotest tptest timing perf stour eyecaltest bkui marksel pplink studiophone search doubttest scaleui midclef softness tunersens notestest libout followwhen inkres phonethrough audiotest winksim runspeed speed biglib stfolder palm slurpen nativeext comp compfeat compsound compwav stfolder2 captpages holddrag spacing dynsmooth blackthumb runspeed2 nbfinger metrobg foldermove mirrorbk compthumb compzoom zoomink compclef compallbtn compmarks orchstress livesound compvoices winkspeed gradetest perscore perscore2 inkaway rename rename_cp plantest ocrtitle imp pianopick preview playfile pages reccount keyreal; do
  [ -f $t.py ] || continue
  s=$(date +%s); timeout 400 python3 $t.py > $SP/t/$t.txt 2>&1; c=$?
  echo "$t exit=$c $(( $(date +%s)-s ))s $(grep -c FAIL $SP/t/$t.txt) fails $(grep -ci 'pageerror\|Traceback' $SP/t/$t.txt) errs" >> $SP/t/_summary.txt
done
echo DONE >> $SP/t/_summary.txt
