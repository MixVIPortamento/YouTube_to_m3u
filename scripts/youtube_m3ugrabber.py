#! /usr/bin/python3

from utils import (
    EPG_URL,
    NOT_AVAILABLE_URL,
    cleanup_temp_files,
    extract_m3u8_link,
    fetch_page,
    is_comment,
    parse_channel_line,
)

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

CHANNEL_INFO_FILE = '../youtube_channel_info.txt'


def grab(url):
    response = fetch_page(url)
    if response is None:
        print(NOT_AVAILABLE_URL)
        return
    print(extract_m3u8_link(response))


print(f'#EXTM3U x-tvg-url="{EPG_URL}"')
print(banner)
with open(CHANNEL_INFO_FILE) as f:
    for line in f:
        line = line.strip()
        if is_comment(line):
            continue
        if line.startswith('https:'):
            grab(line)
        else:
            print(f'\n{parse_channel_line(line)}')

cleanup_temp_files()
