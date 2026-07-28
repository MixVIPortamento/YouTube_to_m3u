
<h1 align="center"> YouTube_to_m3u </h1>

[![M3U generator for YouTube](https://github.com/MixVIPortamento/YouTube_to_m3u/actions/workflows/m3u_Generator.yml/badge.svg)](https://github.com/MixVIPortamento/YouTube_to_m3u/actions/workflows/m3u_Generator.yml)

`https://raw.githubusercontent.com/MixVIPortamento/YouTube_to_m3u/main/youtube.m3u`

Updated m3u links of YouTube live channels, **auto-updated every 3 hours**.


### Add more channels
Edit `youtube_channel_info.txt` to add your favourite YouTube livestreams

Create a pull request or connect: https://discord.gg/dmgYmAEdee

### Usage
Paste this URL: `https://raw.githubusercontent.com/MixVIPortamento/YouTube_to_m3u/main/youtube.m3u` to any player which supports M3U playlists

Links carry a ~6 hour `expire` token, so always re-read the playlist rather than caching URLs.

### Run the tool on your local machine
``` bash
git clone https://github.com/MixVIPortamento/YouTube_to_m3u.git
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

### Keeping it working

YouTube changes its player regularly, so the generator is built to fail loudly rather than
quietly publish placeholders:

* `autorun.sh` reinstalls `requirements.txt` on every run, so **yt-dlp is always upgraded** to the
  version that knows about YouTube's latest changes — this is what keeps the script working
  across years without code edits.
* Every run prints `# resolved <n>/<total> channels` to stderr (also shown in the Action's run
  summary), and exits non-zero when **nothing** resolved. The Action then fails instead of
  committing an all-placeholder playlist, and GitHub emails you.
* A failing run almost always means the `YOUTUBE_COOKIES` export has expired — re-export it and
  update the secret. A residential `YTDLP_PROXY` avoids that maintenance.
* Channels drift too: entries whose video is private/removed can never resolve and should be
  deleted from `youtube_channel_info.txt`. Prefer channel URLs (`.../@handle/live`) over fixed
  `watch?v=<id>` links, since a channel URL follows whatever stream is live now.

### Tests

``` bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest tests -q --cov=scripts
```

### Support

🙂 https://www.buymeacoffee.com/benmoose39
