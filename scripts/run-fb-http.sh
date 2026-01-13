#!/bin/bash

DIR=$(dirname "$0")
BINDIR="$DIR/usr/local/bin"
HTMLDIR="$DIR/usr/local/share/fb-http/html"

cleanup() {
    kill $PIDS 2>/dev/null
    exit 1
}

trap cleanup INT TERM EXIT
umask 0022

"$BINDIR/fb-http.py" \
    --html-dir "$HTMLDIR" \
    --fb /dev/fb0 \
    --touch /dev/input/event0 \
    --port 8092 \
    --bind 0.0.0.0 &
PIDS="$!"

wait -n
echo "fb-http process has exited"
