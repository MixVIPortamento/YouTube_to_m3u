#! /usr/bin/python3

import glob
import json
import os
import re
import subprocess
import sys
import time
from urllib.parse import urlparse

import requests

try:
    import yt_dlp
except ImportError:  # pragma: no cover - yt_dlp is declared in requirements
    yt_dlp = None

banner = r'''
#########################################################################
#      ____            _           _   __  __                           #
#     |  _ \ _ __ ___ (_) ___  ___| |_|  \/  | ___   ___  ___  ___      #
#     | |_) | '__/ _ \| |/ _ \/ __| __| |\/| |/ _ \ / _ \/ __|/ _ \     #
#     |  __/| | | (_) | |  __/ (__| |_| |  | | (_) | (_) \__ \  __/     #
#     |_|   |_|  \___// |\___|\___|\__|_|  |_|\___/ \___/|___/\___|     #
#                   |__/                                                #
#                                  >> https://github.com/benmoose39     #
#########################################################################
'''

NOT_AVAILABLE_LINK = ('https://raw.githubusercontent.com/MixVIPortamento/YouTube_to_m3u'
                      '/main/assets/moose_na.m3u')
CHANNEL_INFO_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 '..', 'youtube_channel_info.txt')

# YouTube blocks plain scraping from most datacenter IPs ("Sign in to confirm
# you're not a bot"). Export cookies from a browser and point YOUTUBE_COOKIES
# at the file (Netscape format) to authenticate; YTDLP_PROXY routes requests
# through a proxy.
COOKIES_ENV = 'YOUTUBE_COOKIES'
PROXY_ENV = 'YTDLP_PROXY'

# youtube_channel_info.txt is editable by anyone opening a pull request, so its
# urls are untrusted input: only fetch https urls on a YouTube host.
ALLOWED_HOSTS = frozenset({
    'youtube.com',
    'www.youtube.com',
    'm.youtube.com',
    'youtu.be',
})

# Resolving a hundred channels back-to-back trips YouTube's rate limiting, which
# surfaces as a bot check even on a signed-in session. Space the requests out and
# retry those failures once the limiter has had a moment to relax.
THROTTLE_MARKERS = ("confirm you're not a bot", 'confirm you\u2019re not a bot',
                    'too many requests', 'http error 429')
THROTTLE_RETRY_DELAYS = (5, 20)

BROWSER_HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'),
    'Accept-Language': 'en-US,en;q=0.9',
}

HLS_MANIFEST_RE = re.compile(r'"hlsManifestUrl"\s*:\s*"(?P<url>[^"]+\.m3u8[^"]*)"')
PLAYABILITY_RE = re.compile(r'"playabilityStatus"\s*:\s*\{"status"\s*:\s*"(?P<status>\w+)"')

windows = 'win' in sys.platform


class QuietLogger:
    """Swallow yt-dlp's own logging; grab() reports failures itself."""

    def debug(self, msg):
        pass

    info = warning = error = debug


def ytdlp_options():
    options = {
        'quiet': True,
        'no_warnings': True,
        'logger': QuietLogger(),
        'skip_download': True,
        'noplaylist': True,
        'socket_timeout': 20,
        'sleep_interval_requests': 1,
        # YouTube's player requires solving a JS challenge to expose formats;
        # needs a JS runtime (deno) plus yt-dlp's remote solver script.
        'remote_components': ['ejs:github'],
    }
    cookies = os.environ.get(COOKIES_ENV)
    if cookies:
        options['cookiefile'] = cookies
    proxy = os.environ.get(PROXY_ENV)
    if proxy:
        options['proxy'] = proxy
    return options


def is_throttled(exc):
    """True when yt-dlp failed because YouTube is rate limiting us, not the video."""
    message = str(exc).lower()
    return any(marker in message for marker in THROTTLE_MARKERS)


def extract_info(url):
    """Run yt-dlp against url, retrying while YouTube's rate limiter rejects us."""
    for delay in THROTTLE_RETRY_DELAYS + (None,):
        try:
            with yt_dlp.YoutubeDL(ytdlp_options()) as ydl:
                return ydl.extract_info(url, download=False)
        except Exception as exc:
            if delay is None or not is_throttled(exc):
                raise
            print(f'# {url} -> rate limited, retrying in {delay}s', file=sys.stderr)
            time.sleep(delay)


def hls_from_ytdlp(url):
    """Resolve the live HLS manifest with yt-dlp, or None if unavailable."""
    if yt_dlp is None:
        return None
    try:
        info = extract_info(url)
    except Exception as exc:
        print(f'# {url} -> yt-dlp failed: {exc}', file=sys.stderr)
        return None
    if info is None:
        return None
    manifest = info.get('manifest_url')
    if manifest and '.m3u8' in manifest:
        return manifest
    for fmt in info.get('formats') or []:
        candidate = fmt.get('manifest_url') or fmt.get('url') or ''
        if '.m3u8' in candidate:
            return candidate
    return None


def fetch(url):
    response = requests.get(url, timeout=15, headers=BROWSER_HEADERS)
    response.raise_for_status()
    return response.text


def is_allowed_url(url):
    """True for https urls pointing at a YouTube host."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme == 'https' and parsed.hostname in ALLOWED_HOSTS


def fetch_with_curl(url, temp_file='temp.txt'):
    """Fetch url with curl; returns an empty body when curl fails."""
    try:
        result = subprocess.run(
            ['curl', '-sSL', '--max-time', '20',
             '-A', BROWSER_HEADERS['User-Agent'], url],
            capture_output=True, text=True)
    except OSError as exc:
        print(f'# {url} -> could not run curl: {exc}', file=sys.stderr)
        return ''
    if result.returncode != 0:
        print(f'# {url} -> curl exited {result.returncode}: {result.stderr.strip()}',
              file=sys.stderr)
        return ''
    try:
        with open(temp_file, 'w') as f:
            f.write(result.stdout)
    except OSError as exc:
        print(f'# could not write {temp_file}: {exc}', file=sys.stderr)
    return result.stdout


def extract_m3u8_link(response):
    """Return the first https .m3u8 link found in response, or None."""
    match = HLS_MANIFEST_RE.search(response)
    if match:
        return json.loads(f'"{match.group("url")}"')
    if '.m3u8' not in response:
        return None
    end = response.find('.m3u8') + 5
    tuner = 100
    while True:
        start = max(end - tuner, 0)
        window = response[start: end]
        if 'https://' in window:
            return window[window.find('https://'): window.find('.m3u8') + 5]
        if start == 0:
            return None
        tuner += 5


def hls_from_html(url):
    """Scrape the watch/live page for an HLS manifest, or None."""
    response = fetch(url)
    link = extract_m3u8_link(response)
    if link:
        return link
    status = PLAYABILITY_RE.search(response)
    if status and status.group('status') != 'OK':
        print(f'# {url} -> playabilityStatus {status.group("status")}', file=sys.stderr)
    if windows:
        return None
    return extract_m3u8_link(fetch_with_curl(url))


def grab(url):
    """Print the live .m3u8 link for a channel url; True when one was found."""
    if not is_allowed_url(url):
        print(f'# {url} -> refusing to fetch a non-YouTube url', file=sys.stderr)
        print(NOT_AVAILABLE_LINK)
        return False
    link = hls_from_ytdlp(url)
    if not link:
        try:
            link = hls_from_html(url)
        except requests.RequestException as exc:
            print(f'# {url} -> request failed: {exc}', file=sys.stderr)
            link = None
    print(link or NOT_AVAILABLE_LINK)
    return bool(link)


def sanitise_field(value):
    """Drop quotes and newlines so an entry cannot forge extra m3u directives."""
    return re.sub(r'[\r\n"]', '', value).strip()


def parse_channel_line(line):
    """Parse a `name | group | logo | tvg-id` line into an #EXTINF line, or None."""
    parts = [sanitise_field(part) for part in line.split('|')]
    if len(parts) < 4:
        print(f'# skipping malformed channel line, expected '
              f'"name | group | logo | tvg-id": {line}', file=sys.stderr)
        return None
    ch_name, grp_title, tvg_logo, tvg_id = parts[0], parts[1].title(), parts[2], parts[3]
    return (f'#EXTINF:-1 group-title="{grp_title}" tvg-logo="{tvg_logo}" '
            f'tvg-id="{tvg_id}", {ch_name}')


def cleanup():
    for path in ['temp.txt'] + glob.glob('watch*'):
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        except OSError as exc:
            print(f'# could not remove {path}: {exc}', file=sys.stderr)


def main(channel_info_file=CHANNEL_INFO_FILE):
    """Write the playlist to stdout; return the number of resolved channels."""
    print('#EXTM3U x-tvg-url="https://github.com/botallen/epg/releases/download/latest/epg.xml"')
    print(banner)
    resolved = total = 0
    try:
        with open(channel_info_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('~~'):
                    continue
                if not line.startswith('https:'):
                    extinf = parse_channel_line(line)
                    if extinf:
                        print(f'\n{extinf}')
                else:
                    total += 1
                    resolved += grab(line)
    finally:
        cleanup()
    print(f'# resolved {resolved}/{total} channels', file=sys.stderr)
    if total and not resolved:
        print('# nothing resolved: YouTube is blocking these requests. Refresh the '
              f'{COOKIES_ENV} cookies export, set {PROXY_ENV}, or install a JS runtime '
              '(deno) so yt-dlp can solve the player challenge.', file=sys.stderr)
    return resolved


if __name__ == '__main__':
    # Non-zero exit keeps CI from committing a playlist of placeholders.
    try:
        resolved_channels = main()
    except OSError as exc:
        print(f'# could not read {CHANNEL_INFO_FILE}: {exc}', file=sys.stderr)
        sys.exit(1)
    sys.exit(0 if resolved_channels else 1)