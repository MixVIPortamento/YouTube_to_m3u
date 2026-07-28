#! /usr/bin/python3

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

import glob
import os
import re
import sys
from urllib.parse import urlparse

import requests

NA_LINK = 'https://raw.githubusercontent.com/benmoose39/YouTube_to_m3u/main/assets/moose_na.m3u'

ALLOWED_HOSTS = frozenset({
    'youtube.com',
    'www.youtube.com',
    'm.youtube.com',
    'youtu.be',
})

USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
)

M3U8_URL_RE = re.compile(r'https://[^\s"\'\\<>]+?\.m3u8')


def is_allowed_url(url):
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme == 'https' and parsed.hostname in ALLOWED_HOSTS


def sanitise_field(value):
    """Strip characters that would let a channel entry forge extra m3u directives."""
    return re.sub(r'[\r\n"]', '', value).strip()


def fetch(url, user_agent=None):
    headers = {'User-Agent': user_agent} if user_agent else {}
    try:
        response = requests.get(url, timeout=15, headers=headers)
    except requests.RequestException:
        return ''
    return response.text


def grab(url):
    if not is_allowed_url(url):
        print(f'refusing to fetch non-YouTube url: {url!r}', file=sys.stderr)
        print(NA_LINK)
        return

    response = fetch(url)
    if '.m3u8' not in response:
        response = fetch(url, user_agent=USER_AGENT)

    match = M3U8_URL_RE.search(response)
    if not match:
        print(NA_LINK)
        return
    print(match.group(0))


def main():
    print('#EXTM3U x-tvg-url="https://github.com/botallen/epg/releases/download/latest/epg.xml"')
    print(banner)
    with open('../youtube_channel_info.txt') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('~~'):
                continue
            if line.startswith('https:'):
                grab(line)
                continue
            fields = [sanitise_field(field) for field in line.split('|')]
            if len(fields) < 4:
                print(f'skipping malformed channel entry: {line!r}', file=sys.stderr)
                continue
            ch_name, grp_title, tvg_logo, tvg_id = fields[:4]
            print(
                f'\n#EXTINF:-1 group-title="{grp_title.title()}" '
                f'tvg-logo="{tvg_logo}" tvg-id="{tvg_id}", {ch_name}'
            )

    for path in ['temp.txt'] + glob.glob('watch*'):
        if os.path.isfile(path):
            os.remove(path)


if __name__ == '__main__':
    main()
