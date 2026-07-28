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
import subprocess
import sys

import requests

NA_LINK = 'https://raw.githubusercontent.com/benmoose39/YouTube_to_m3u/main/assets/moose_na.m3u'
CHANNEL_INFO = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'youtube_channel_info.txt')
TEMP_FILE = 'temp.txt'
EXIT_ERROR = 1
EXIT_NO_STREAMS = 2

windows = 'win' in sys.platform


def warn(message):
    print(f'WARNING: {message}', file=sys.stderr)


def fetch(url):
    """Return the page body for url, or None if it could not be fetched."""
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        warn(f'request for {url} failed: {e}')
        return None


def fetch_with_curl(url):
    """Fallback fetch via curl, used when requests returns a page without a stream."""
    try:
        result = subprocess.run(
            ['curl', '--silent', '--show-error', '--location', '--max-time', '15', url],
            capture_output=True,
            text=True,
        )
    except OSError as e:
        warn(f'could not run curl for {url}: {e}')
        return None
    if result.returncode != 0:
        warn(f'curl for {url} exited with {result.returncode}: {result.stderr.strip()}')
        return None
    try:
        with open(TEMP_FILE, 'w') as f:
            f.write(result.stdout)
    except OSError as e:
        warn(f'could not write {TEMP_FILE}: {e}')
    return result.stdout


def extract_link(response):
    """Extract the first https .m3u8 link from response, or None if there is none."""
    end = response.find('.m3u8') + 5
    tuner = 100
    while True:
        window = response[max(end - tuner, 0): end]
        if 'https://' in window:
            start = window.find('https://')
            stop = window.find('.m3u8') + 5
            return window[start: stop]
        if end - tuner <= 0:
            warn('found a .m3u8 reference with no https:// prefix')
            return None
        tuner += 5


def grab(url):
    """Print the stream link for url. Returns True when a real link was found."""
    response = fetch(url)
    if (response is None or '.m3u8' not in response) and not windows:
        response = fetch_with_curl(url)
    if response is None or '.m3u8' not in response:
        warn(f'no stream found for {url}')
        print(NA_LINK)
        return False
    link = extract_link(response)
    if link is None:
        warn(f'no stream found for {url}')
        print(NA_LINK)
        return False
    print(link)
    return True


def parse_channel_info(line, line_number):
    """Parse a channel metadata line into an #EXTINF line, or None if malformed."""
    fields = [field.strip() for field in line.split('|')]
    if len(fields) < 4:
        warn(f'channel info line {line_number} is not '
             f'"<name> | <group> | <logo> | <tvg-id>", skipping: {line}')
        return None
    ch_name, grp_title, tvg_logo, tvg_id = fields[0], fields[1].title(), fields[2], fields[3]
    return (f'\n#EXTINF:-1 group-title="{grp_title}" tvg-logo="{tvg_logo}" '
            f'tvg-id="{tvg_id}", {ch_name}')


def cleanup():
    for path in [TEMP_FILE] + glob.glob('watch*'):
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        except OSError as e:
            warn(f'could not remove {path}: {e}')


def main():
    print('#EXTM3U x-tvg-url="https://github.com/botallen/epg/releases/download/latest/epg.xml"')
    print(banner)

    try:
        with open(CHANNEL_INFO) as f:
            lines = f.readlines()
    except OSError as e:
        print(f'ERROR: could not read {CHANNEL_INFO}: {e}', file=sys.stderr)
        return EXIT_ERROR

    attempted = 0
    succeeded = 0
    try:
        for line_number, line in enumerate(lines, start=1):
            line = line.strip()
            if not line or line.startswith('~~'):
                continue
            if not line.startswith('https:'):
                extinf = parse_channel_info(line, line_number)
                if extinf is not None:
                    print(extinf)
            else:
                attempted += 1
                if grab(line):
                    succeeded += 1
    finally:
        cleanup()

    if attempted and not succeeded:
        print(f'ERROR: none of the {attempted} channels could be resolved', file=sys.stderr)
        return EXIT_NO_STREAMS
    if succeeded < attempted:
        warn(f'{attempted - succeeded} of {attempted} channels could not be resolved')
    return 0


if __name__ == '__main__':
    sys.exit(main())
