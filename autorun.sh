#!/bin/bash

set -euo pipefail

cd "$(dirname "$0")"

python3 -m pip install requests

tmp_out="$(mktemp)"
trap 'rm -f "$tmp_out"' EXIT

if ! python3 scripts/youtube_m3ugrabber.py > "$tmp_out"; then
    echo "m3u grab failed, keeping the previous youtube.m3u" >&2
    exit 1
fi

mv "$tmp_out" youtube.m3u
chmod 644 youtube.m3u

echo m3u grabbed
