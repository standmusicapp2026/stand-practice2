#!/bin/bash
# fit of every test line (Ravel, Peters, sax p1, sax p2), one line each
OUT=$1; : > $OUT
run() { r=$(timeout 300 python3 /home/claude/tools/realomr.py $1 $2 2>&1); echo "== $1 $2 $(echo "$r" | grep -o 'fit [0-9.]*')" >> $OUT; echo "$r" | grep "^ " >> $OUT; }
for c in 43,615,2300,317 40,935,2306,319 39,1254,2307,313 39,1568,2306,310 39,1878,2306,313 40,2232,2306,316 42,2533,2302,317 49,2855,2289,309; do run /home/claude/tc/raw-003.jpg $c; done
for c in 45,359,2326,322 44,573,2321,312 62,908,2288,218; do run /home/claude/tc/raw-000.jpg $c; done
for c in 146,598,1955,300 147,1012,1953,295 147,1421,1953,292 144,1845,1957,297 146,2295,1956,299 150,2710,1221,292; do run /home/claude/tc/raw-001.jpg $c; done
for c in 159,217,2059,308 155,516,2066,314 152,819,2070,316 152,1096,2068,311 152,1363,2067,310 153,1651,2066,310 149,2014,2072,316 150,2319,2072,316 154,2592,2066,316 158,2865,2060,308; do run /home/claude/tc/raw-002.jpg $c; done
