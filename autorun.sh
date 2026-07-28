#!/bin/bash
set -uo pipefail

cd "$(dirname "$0")"

python3 -m pip install --quiet --upgrade -r requirements.txt

# Optional: export YOUTUBE_COOKIES=/path/to/cookies.txt (Netscape format) and/or
# YTDLP_PROXY=http://host:port if YouTube blocks anonymous requests from your IP.
# The playlist is written to a temp file first so a failed run leaves the
# previous youtube.m3u in place instead of truncating it.
tmp_out="$(mktemp)"
trap 'rm -f "$tmp_out"' EXIT

status=0
(cd scripts/ && python3 youtube_m3ugrabber.py) > "$tmp_out" || status=$?

if [ "$status" -ne 0 ]; then
    echo "m3u grab failed (exit $status), keeping the previous youtube.m3u" >&2
    exit "$status"
fi

mv "$tmp_out" youtube.m3u
chmod 644 youtube.m3u

echo m3u grabbed
