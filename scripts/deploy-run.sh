#!/bin/bash

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <host> <cmd> [additional options]"
  exit 1
fi

DIR="$(dirname "$0")"
cd "$DIR/.."

SSH_HOST="$1"
CMD="$2"
shift 2

set -xeo pipefail
make install DESTDIR=$PWD/tmp/screen-apps
scp -r tmp/screen-apps/. scripts/run-*.sh "$SSH_HOST":/tmp/screen-apps
ssh -t "$SSH_HOST" "/tmp/screen-apps/$CMD" "$@"
