#!/bin/bash
# peak total memory of the browser's processes while a command runs
peak=0; "$@" & P=$!
while kill -0 $P 2>/dev/null; do t=$(ps -eo rss,comm | awk '/chrom|headless_shell/{s+=$1} END{print s+0}'); [ "$t" -gt "$peak" ] && peak=$t; sleep 0.1; done
echo "PEAK_MB $((peak/1024))"
