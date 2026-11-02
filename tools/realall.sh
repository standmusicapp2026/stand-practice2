#!/bin/bash
# run realomr over the real examples, output to $1
OUT=$1; : > $OUT
for f in BachInvention5.jpg D0392410-1.256.png allegretto.png batuque.png carmen.png chula.png cucaracha.png hove.png zizi.png; do
  echo "== $f" >> $OUT
  timeout 300 python3 /home/claude/tools/realomr.py /home/claude/omrdata/av/data/examples/$f - >> $OUT 2>&1
done
