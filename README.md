
<h1 align="center"> YouTube_to_m3u </h1>

[![M3U generator for YouTube](https://github.com/benmoose39/YouTube_to_m3u/actions/workflows/m3u_Generator.yml/badge.svg)](https://github.com/benmoose39/YouTube_to_m3u/actions/workflows/m3u_Generator.yml)

`https://raw.githubusercontent.com/benmoose39/YouTube_to_m3u/main/youtube.m3u`

Updated m3u links of YouTube live channels, **auto-updated every 3 hours**.


### Add more channels
Edit `youtube_channel_info.txt` to add your favourite YouTube livestreams

Create a pull request or connect: https://discord.gg/dmgYmAEdee

### Usage
Paste this URL: `https://raw.githubusercontent.com/benmoose39/YouTube_to_m3u/main/youtube.m3u` to any player which supports M3U playlists

### Run the tool on your local machine
``` bash
git clone https://github.com/benmoose39/YouTube_to_m3u.git
cd YouTube_to_m3u
chmod +x autorun.sh
./autorun.sh
```

Do not forget to add a cron job set for every 4 hours(or 5) if you plan to run the script locally.

### Requirements

* Python 3 with `requirements.txt` installed (`requests`, `yt-dlp`)
* A JavaScript runtime — [deno](https://deno.land) — because YouTube's player requires solving
  a JS challenge before it exposes stream formats:

``` bash
curl -fsSL https://deno.land/install.sh | sh
```

### YouTube bot checks

YouTube answers most datacenter/CI requests with `Sign in to confirm you're not a bot`, so
anonymous runs fall back to the `moose_na.m3u` placeholder instead of a stream. Two optional
knobs work around it, used by both `scripts/youtube_m3ugrabber.py` and the GitHub Action:

| Variable / repo secret | Purpose |
| --- | --- |
| `YOUTUBE_COOKIES` | Path to a Netscape-format `cookies.txt` export (locally), or the file contents (as a repo secret) |
| `YTDLP_PROXY` | Proxy URL used for YouTube requests, e.g. `http://user:pass@host:port` |

``` bash
export YOUTUBE_COOKIES=~/cookies.txt   # exported from a signed-in browser
./autorun.sh
```

Use a throwaway Google account for cookies — YouTube may flag accounts used for automation.

### Tests

``` bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest tests -q --cov=scripts
```

### Support

🙂 https://www.buymeacoffee.com/benmoose39
