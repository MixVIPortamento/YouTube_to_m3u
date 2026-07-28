#! /usr/bin/python3

import json
import os
import re
import sys

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

NOT_AVAILABLE_LINK = 'https://raw.githubusercontent.com/benmoose39/YouTube_to_m3u/main/assets/moose_na.m3u'
CHANNEL_INFO_FILE = '../youtube_channel_info.txt'

# YouTube blocks plain scraping from most datacenter IPs ("Sign in to confirm
# you're not a bot"). Export cookies from a browser and point YOUTUBE_COOKIES
# at the file (Netscape format) to authenticate; YTDLP_PROXY routes requests
# through a proxy.
COOKIES_ENV = 'YOUTUBE_COOKIES'
PROXY_ENV = 'YTDLP_PROXY'

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


def hls_from_ytdlp(url):
    """Resolve the live HLS manifest with yt-dlp, or None if unavailable."""
    if yt_dlp is None:
        return None
    try:
        with yt_dlp.YoutubeDL(ytdlp_options()) as ydl:
            info = ydl.extract_info(url, download=False)
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
    return requests.get(url, timeout=15, headers=BROWSER_HEADERS).text


def fetch_with_curl(url, temp_file='temp.txt'):
    os.system(f'curl -sL -A "{BROWSER_HEADERS["User-Agent"]}" "{url}" > {temp_file}')
    with open(temp_file) as f:
        return ''.join(f.readlines())


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
    """Print the live .m3u8 link for a YouTube channel url."""
    link = hls_from_ytdlp(url)
    if not link:
        try:
            link = hls_from_html(url)
        except requests.RequestException as exc:
            print(f'# {url} -> request failed: {exc}', file=sys.stderr)
            link = None
    print(link or NOT_AVAILABLE_LINK)


def parse_channel_line(line):
    """Parse a `name | group | logo | tvg-id` line into an #EXTINF line."""
    parts = line.split('|')
    ch_name = parts[0].strip()
    grp_title = parts[1].strip().title()
    tvg_logo = parts[2].strip()
    tvg_id = parts[3].strip()
    return (f'#EXTINF:-1 group-title="{grp_title}" tvg-logo="{tvg_logo}" '
            f'tvg-id="{tvg_id}", {ch_name}')


def cleanup():
    if 'temp.txt' in os.listdir():
        os.system('rm -f temp.txt')
        os.system('rm -f watch*')


def main(channel_info_file=CHANNEL_INFO_FILE):
    print('#EXTM3U x-tvg-url="https://github.com/botallen/epg/releases/download/latest/epg.xml"')
    print(banner)
    with open(channel_info_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('~~'):
                continue
            if not line.startswith('https:'):
                print(f'\n{parse_channel_line(line)}')
            else:
                grab(line)
    cleanup()


if __name__ == '__main__':
    main()
