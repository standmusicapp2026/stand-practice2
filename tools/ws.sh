#!/bin/bash
# run a command with the test server up for its duration
cd /home/claude/s24/Payload/Stand.app/www
python3 -m http.server 8765 --bind 127.0.0.1 > /dev/null 2>&1 &
SRV=$!
trap "kill $SRV 2>/dev/null" EXIT
for i in $(seq 1 50); do curl -s -o /dev/null http://127.0.0.1:8765/index.html && break; sleep 0.1; done
cd /home/claude/tools
"$@"
