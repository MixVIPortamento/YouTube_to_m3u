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

import os
import sys

import requests

NOT_AVAILABLE_LINK = 'https://raw.githubusercontent.com/benmoose39/YouTube_to_m3u/main/assets/moose_na.m3u'
CHANNEL_INFO_FILE = '../youtube_channel_info.txt'

windows = False
if 'win' in sys.platform:
    windows = True


def fetch(url):
    return requests.get(url, timeout=15).text


def fetch_with_curl(url, temp_file='temp.txt'):
    os.system(f'curl "{url}" > {temp_file}')
    with open(temp_file) as f:
        return ''.join(f.readlines())


def extract_m3u8_link(response):
    """Return the first https .m3u8 link found in response, or None."""
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


def grab(url):
    """Print the live .m3u8 link for a YouTube channel url."""
    response = fetch(url)
    if '.m3u8' not in response:
        if windows:
            print(NOT_AVAILABLE_LINK)
            return
        response = fetch_with_curl(url)
        if '.m3u8' not in response:
            print(NOT_AVAILABLE_LINK)
            return
    link = extract_m3u8_link(response)
    if link is None:
        print(NOT_AVAILABLE_LINK)
        return
    print(link)


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
        os.system('rm temp.txt')
        os.system('rm watch*')


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
