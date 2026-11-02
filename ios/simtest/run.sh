#!/bin/bash
# Runs Stand's self-test on several iPad and iPhone simulators, one after another.
# For each: a fresh simulator, the app installed, microphone and camera allowed, the app started with
# -standSelfTest; the events log is followed: each "SHOT name" gives a screenshot, memory is sampled
# every second; at "SELFTEST DONE" (or after 6 minutes) the simulator is shut down and deleted.
# Usage: run.sh path/to/Stand.app out_dir
set -u
APP="$1"; OUT="$2"; BID=com.paulo.stand
mkdir -p "$OUT"
SUMMARY="$OUT/summary.txt"; : > "$SUMMARY"

# the newest iOS runtime, and the oldest one that is at least 16.4 (if the machine has several)
RUNTIMES=$(xcrun simctl list runtimes -j | python3 -c '
import json, sys
r = [x for x in json.load(sys.stdin)["runtimes"] if x.get("isAvailable") and x["name"].startswith("iOS")]
def v(x): return tuple(int(p) for p in x["version"].split("."))
r = [x for x in r if v(x) >= (16, 4)]
r.sort(key=v)
pick = [r[-1]] + ([r[0]] if len(r) > 1 else [])
print("\n".join(x["identifier"] + "|" + x["version"] for x in pick))
')
echo "runtimes: $RUNTIMES" | tee -a "$SUMMARY"

# the devices wanted (the first of each group that this machine has)
WANT=(
  "iPad mini (6th generation)|iPad mini (A17 Pro)|iPad mini"
  "iPad (10th generation)|iPad (A16)|iPad (9th generation)"
  "iPad Pro 13-inch (M4)|iPad Pro (12.9-inch) (6th generation)|iPad Pro (12.9-inch)"
  "iPhone SE (3rd generation)|iPhone 16e|iPhone SE"
  "iPhone 16 Pro Max|iPhone 15 Pro Max|iPhone 14 Pro Max"
)
TYPES=$(xcrun simctl list devicetypes -j)
typeid() { echo "$TYPES" | python3 -c "
import json, sys
names = sys.argv[1].split('|'); t = {x['name']: x['identifier'] for x in json.load(sys.stdin)['devicetypes']}
for n in names:
    if n in t: print(t[n] + '|' + n); break
" "$1"; }

i=0
while IFS= read -r RT; do
  [ -z "$RT" ] && continue
  RID="${RT%%|*}"; RV="${RT##*|}"; i=$((i+1))
  for W in "${WANT[@]}"; do
    # on the older runtime only one iPad and one iPhone (time is counted)
    if [ $i -gt 1 ] && [[ "$W" != iPad\ \(10th* && "$W" != iPhone\ SE* ]]; then continue; fi
    T=$(typeid "$W"); [ -z "$T" ] && { echo "no device type for $W" | tee -a "$SUMMARY"; continue; }
    TID="${T%%|*}"; TNAME="${T##*|}"
    TAG=$(echo "$TNAME-iOS$RV" | tr ' ()' '_--' | tr -s '_-')
    D="$OUT/$TAG"; mkdir -p "$D"
    echo "=== $TNAME, iOS $RV" | tee -a "$SUMMARY"
    UDID=$(xcrun simctl create "st-$TAG" "$TID" "$RID") || { echo "  could not create" | tee -a "$SUMMARY"; continue; }
    xcrun simctl boot "$UDID"; xcrun simctl bootstatus "$UDID" -b > /dev/null 2>&1
    xcrun simctl install "$UDID" "$APP" || { echo "  install failed" | tee -a "$SUMMARY"; xcrun simctl delete "$UDID"; continue; }
    for s in microphone camera photos; do xcrun simctl privacy "$UDID" grant $s $BID > /dev/null 2>&1; done
    START=$(date +%s)
    xcrun simctl launch "$UDID" $BID -standSelfTest > /dev/null
    sleep 3
    CONT=$(xcrun simctl get_app_container "$UDID" $BID data 2>/dev/null)
    LOG="$CONT/Documents/Diagnostics/events.log"
    SEEN=0; echo "t,rss_app_mb,rss_web_mb" > "$D/memory.csv"
    while true; do
      NOW=$(( $(date +%s) - START ))
      if [ -f "$LOG" ]; then
        N=$(wc -l < "$LOG")
        if [ "$N" -gt "$SEEN" ]; then
          tail -n +$((SEEN+1)) "$LOG" | head -n $((N-SEEN)) > "$D/new.txt"; SEEN=$N
          while IFS= read -r L; do
            case "$L" in
              *"page: SHOT "*) NAME="${L##*SHOT }"; xcrun simctl io "$UDID" screenshot "$D/$NAME.png" > /dev/null 2>&1 ;;
            esac
          done < "$D/new.txt"
          grep -q "SELFTEST DONE" "$LOG" && break
        fi
      fi
      # memory of the app and of its web content (the processes run on this Mac)
      APPPID=$(pgrep -f "$UDID.*Stand.app/Stand" | head -1)
      A=$( [ -n "$APPPID" ] && ps -o rss= -p "$APPPID" | awk '{print int($1/1024)}' || echo 0)
      WEB=$(ps -axo rss=,command= | grep -i "simruntime" | grep -i "WebContent" | grep -v grep | awk '{s+=$1} END {print int(s/1024)}')
      echo "$NOW,${A:-0},${WEB:-0}" >> "$D/memory.csv"
      [ $NOW -gt 360 ] && { echo "  TIMEOUT (no DONE after 6 minutes)" | tee -a "$SUMMARY"; xcrun simctl io "$UDID" screenshot "$D/timeout.png" > /dev/null 2>&1; break; }
      [ -z "$APPPID" ] && [ $NOW -gt 20 ] && { echo "  the app is not running any more (crashed?)" | tee -a "$SUMMARY"; xcrun simctl io "$UDID" screenshot "$D/gone.png" > /dev/null 2>&1; break; }
      sleep 1
    done
    [ -f "$LOG" ] && cp "$LOG" "$D/events.log"
    cp "$CONT"/Documents/Diagnostics/*.json "$D/" 2>/dev/null
    grep "SELFTEST" "$D/events.log" 2>/dev/null | sed 's/^[^ ]*  page: /  /' | tee -a "$SUMMARY" > /dev/null
    PEAK=$(awk -F, 'NR>1 && $3>m {m=$3} END {print m+0}' "$D/memory.csv"); PA=$(awk -F, 'NR>1 && $2>m {m=$2} END {print m+0}' "$D/memory.csv")
    echo "  peak memory: app $PA MB, web content $PEAK MB" | tee -a "$SUMMARY"
    ls ~/Library/Logs/DiagnosticReports/ 2>/dev/null | grep -i stand | while read f; do cp ~/Library/Logs/DiagnosticReports/"$f" "$D/"; echo "  crash report: $f" | tee -a "$SUMMARY"; done
    xcrun simctl shutdown "$UDID" > /dev/null 2>&1; xcrun simctl delete "$UDID" > /dev/null 2>&1
  done
done <<< "$RUNTIMES"
echo; echo "fails: $(grep -c 'SELFTEST FAIL' "$SUMMARY"), errors: $(grep -c 'SELFTEST error' "$SUMMARY"), timeouts/crashes: $(grep -c 'TIMEOUT\|not running' "$SUMMARY")" | tee -a "$SUMMARY"
