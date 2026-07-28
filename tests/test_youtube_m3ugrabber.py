import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import youtube_m3ugrabber as grabber  # noqa: E402


HLS_LINK = 'https://manifest.googlevideo.com/api/manifest/hls_playlist/index.m3u8'


class TestExtractM3u8Link:
    def test_returns_none_when_no_m3u8_present(self):
        assert grabber.extract_m3u8_link('<html>no stream here</html>') is None

    def test_returns_none_when_m3u8_has_no_https_prefix(self):
        assert grabber.extract_m3u8_link('"hlsManifestUrl":"index.m3u8"') is None

    def test_extracts_link_from_embedded_json(self):
        response = 'x' * 500 + f'"hlsManifestUrl":"{HLS_LINK}"' + 'y' * 500
        assert grabber.extract_m3u8_link(response) == HLS_LINK

    def test_extracts_first_link_when_multiple_present(self):
        second = 'https://example.com/other.m3u8'
        assert grabber.extract_m3u8_link(f'a {HLS_LINK} b {second} c') == HLS_LINK

    def test_extracts_link_longer_than_initial_window(self):
        long_link = 'https://manifest.googlevideo.com/' + 'p' * 200 + '/index.m3u8'
        assert grabber.extract_m3u8_link(f'prefix {long_link} suffix') == long_link

    def test_extracts_link_at_start_of_response(self):
        assert grabber.extract_m3u8_link(HLS_LINK) == HLS_LINK


class TestParseChannelLine:
    def test_builds_extinf_line(self):
        line = 'Gazi TV Live | bangla | https://logo.test/gtv.png | gazi.bd'
        assert grabber.parse_channel_line(line) == (
            '#EXTINF:-1 group-title="Bangla" tvg-logo="https://logo.test/gtv.png" '
            'tvg-id="gazi.bd", Gazi TV Live'
        )

    def test_title_cases_group_and_allows_empty_tvg_id(self):
        line = 'Some News | news channels | https://logo.test/l.png |'
        assert grabber.parse_channel_line(line) == (
            '#EXTINF:-1 group-title="News Channels" tvg-logo="https://logo.test/l.png" '
            'tvg-id="", Some News'
        )

    def test_raises_on_missing_fields(self):
        with pytest.raises(IndexError):
            grabber.parse_channel_line('Only Name | group')


class TestGrab:
    def test_prints_link_when_request_contains_m3u8(self, monkeypatch, capsys):
        monkeypatch.setattr(grabber, 'fetch', lambda url: f'junk {HLS_LINK} junk')
        grabber.grab('https://youtube.test/live')
        assert capsys.readouterr().out.strip() == HLS_LINK

    def test_falls_back_to_curl_when_request_has_no_m3u8(self, monkeypatch, capsys):
        calls = []
        monkeypatch.setattr(grabber, 'windows', False)
        monkeypatch.setattr(grabber, 'fetch', lambda url: 'offline')
        monkeypatch.setattr(grabber, 'fetch_with_curl',
                            lambda url: calls.append(url) or f'x {HLS_LINK}')
        grabber.grab('https://youtube.test/live')
        assert calls == ['https://youtube.test/live']
        assert capsys.readouterr().out.strip() == HLS_LINK

    def test_prints_not_available_when_curl_also_fails(self, monkeypatch, capsys):
        monkeypatch.setattr(grabber, 'windows', False)
        monkeypatch.setattr(grabber, 'fetch', lambda url: 'offline')
        monkeypatch.setattr(grabber, 'fetch_with_curl', lambda url: 'offline')
        grabber.grab('https://youtube.test/live')
        assert capsys.readouterr().out.strip() == grabber.NOT_AVAILABLE_LINK

    def test_skips_curl_fallback_on_windows(self, monkeypatch, capsys):
        def boom(url):
            raise AssertionError('curl fallback must not run on windows')

        monkeypatch.setattr(grabber, 'windows', True)
        monkeypatch.setattr(grabber, 'fetch', lambda url: 'offline')
        monkeypatch.setattr(grabber, 'fetch_with_curl', boom)
        grabber.grab('https://youtube.test/live')
        assert capsys.readouterr().out.strip() == grabber.NOT_AVAILABLE_LINK

    def test_prints_not_available_when_m3u8_has_no_https(self, monkeypatch, capsys):
        monkeypatch.setattr(grabber, 'fetch', lambda url: 'ref="index.m3u8"')
        grabber.grab('https://youtube.test/live')
        assert capsys.readouterr().out.strip() == grabber.NOT_AVAILABLE_LINK


class TestFetchWithCurl:
    def test_reads_output_file_written_by_curl(self, monkeypatch, tmp_path):
        temp_file = tmp_path / 'temp.txt'
        commands = []

        def fake_system(cmd):
            commands.append(cmd)
            temp_file.write_text('line1\nline2\n')
            return 0

        monkeypatch.setattr(grabber.os, 'system', fake_system)
        assert grabber.fetch_with_curl('https://youtube.test/live',
                                       temp_file=str(temp_file)) == 'line1\nline2\n'
        assert commands == [f'curl "https://youtube.test/live" > {temp_file}']


class TestFetch:
    def test_requests_url_with_timeout(self, monkeypatch):
        captured = {}

        class Response:
            text = 'body'

        def fake_get(url, timeout):
            captured['url'] = url
            captured['timeout'] = timeout
            return Response()

        monkeypatch.setattr(grabber.requests, 'get', fake_get)
        assert grabber.fetch('https://youtube.test/live') == 'body'
        assert captured == {'url': 'https://youtube.test/live', 'timeout': 15}


class TestCleanup:
    def test_removes_temp_files_when_temp_exists(self, monkeypatch):
        commands = []
        monkeypatch.setattr(grabber.os, 'listdir', lambda: ['temp.txt', 'watch1'])
        monkeypatch.setattr(grabber.os, 'system', lambda cmd: commands.append(cmd))
        grabber.cleanup()
        assert commands == ['rm temp.txt', 'rm watch*']

    def test_does_nothing_when_temp_missing(self, monkeypatch):
        def boom(cmd):
            raise AssertionError('nothing should be removed')

        monkeypatch.setattr(grabber.os, 'listdir', lambda: ['youtube.m3u'])
        monkeypatch.setattr(grabber.os, 'system', boom)
        grabber.cleanup()


class TestMain:
    def test_emits_playlist_for_channel_file(self, monkeypatch, tmp_path, capsys):
        channel_file = tmp_path / 'youtube_channel_info.txt'
        channel_file.write_text(
            '~~ DO NOT EDIT\n'
            '\n'
            'Gazi TV Live | bangla | https://logo.test/gtv.png | gazi.bd\n'
            'https://youtube.test/gazi/live\n'
        )
        monkeypatch.setattr(grabber, 'fetch', lambda url: f'junk {HLS_LINK}')
        monkeypatch.setattr(grabber, 'cleanup', lambda: None)

        grabber.main(str(channel_file))

        out = capsys.readouterr().out
        assert out.startswith('#EXTM3U x-tvg-url="https://github.com/botallen/epg/'
                              'releases/download/latest/epg.xml"')
        assert grabber.banner in out
        assert '#EXTINF:-1 group-title="Bangla"' in out
        assert out.rstrip().endswith(HLS_LINK)
        assert '~~' not in out.split(grabber.banner)[1]

    def test_runs_cleanup_after_processing(self, monkeypatch, tmp_path):
        channel_file = tmp_path / 'channels.txt'
        channel_file.write_text('')
        called = []
        monkeypatch.setattr(grabber, 'cleanup', lambda: called.append(True))
        grabber.main(str(channel_file))
        assert called == [True]
