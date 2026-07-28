#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

python3 -m pip install --quiet --upgrade -r requirements.txt

# Optional: export YOUTUBE_COOKIES=/path/to/cookies.txt (Netscape format) and/or
# YTDLP_PROXY=http://host:port if YouTube blocks anonymous requests from your IP.
(cd scripts/ && python3 youtube_m3ugrabber.py) > youtube.m3u

echo m3u grabbed
