#!/bin/bash

# Exit codes: 0 playlist regenerated, 1 the grabber failed, 2 no stream could be
# resolved at all (YouTube unreachable or rate limiting). The previous
# youtube.m3u is left in place for anything other than 0.

set -uo pipefail

cd "$(dirname "$0")"

python3 -m pip install requests

tmp_out="$(mktemp)"
trap 'rm -f "$tmp_out"' EXIT

status=0
python3 scripts/youtube_m3ugrabber.py > "$tmp_out" || status=$?

if [ "$status" -ne 0 ]; then
    echo "m3u grab failed (exit $status), keeping the previous youtube.m3u" >&2
    exit "$status"
fi

mv "$tmp_out" youtube.m3u
chmod 644 youtube.m3u

echo m3u grabbed
