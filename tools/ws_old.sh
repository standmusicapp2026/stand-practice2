#!/bin/bash
PORT=${PORT:-8770}; export PORT
cd /home/claude/oldf/Payload/Stand.app/www
python3 -m http.server $PORT --bind 127.0.0.1 > /dev/null 2>&1 &
SRV=$!
trap "kill $SRV 2>/dev/null" EXIT
for i in $(seq 1 50); do curl -s -o /dev/null http://127.0.0.1:$PORT/index.html && break; sleep 0.1; done
cd /home/claude/tools
"$@"
