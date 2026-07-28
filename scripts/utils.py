#! /usr/bin/python3

"""Shared helpers used by the m3u grabber scripts."""

import os
import sys

import requests

REPO_RAW_BASE = 'https://raw.githubusercontent.com/benmoose39/YouTube_to_m3u/main'
NOT_AVAILABLE_URL = f'{REPO_RAW_BASE}/assets/moose_na.m3u'
EPG_URL = 'https://github.com/botallen/epg/releases/download/latest/epg.xml'

M3U8_EXT = '.m3u8'
REQUEST_TIMEOUT = 15
TEMP_FILE = 'temp.txt'

IS_WINDOWS = 'win' in sys.platform


def fetch_page(url):
    """Return the page source for `url`, or None if it holds no m3u8 link.

    Falls back to curl on non-Windows platforms, since some responses are
    only served correctly outside of requests.
    """
    response = requests.get(url, timeout=REQUEST_TIMEOUT).text
    if M3U8_EXT in response:
        return response
    if IS_WINDOWS:
        return None
    os.system(f'curl "{url}" > {TEMP_FILE}')
    with open(TEMP_FILE) as f:
        response = f.read()
    return response if M3U8_EXT in response else None


def extract_m3u8_link(response):
    """Pull the first m3u8 URL out of a page source."""
    end = response.find(M3U8_EXT) + len(M3U8_EXT)
    tuner = 100
    while 'https://' not in response[end - tuner: end]:
        tuner += 5
    link = response[end - tuner: end]
    return link[link.find('https://'): link.find(M3U8_EXT) + len(M3U8_EXT)]


def cleanup_temp_files():
    """Remove the scratch files left behind by the curl fallback."""
    if TEMP_FILE in os.listdir():
        os.system(f'rm {TEMP_FILE}')
        os.system('rm watch*')


def is_comment(line):
    return not line or line.startswith('~~')


def parse_channel_line(line):
    """Turn a `name | group | logo | tvg-id` line into an #EXTINF header."""
    parts = [part.strip() for part in line.split('|')]
    ch_name, grp_title, tvg_logo, tvg_id = parts[0], parts[1], parts[2], parts[3]
    return (
        f'#EXTINF:-1 group-title="{grp_title.title()}" '
        f'tvg-logo="{tvg_logo}" tvg-id="{tvg_id}", {ch_name}'
    )
