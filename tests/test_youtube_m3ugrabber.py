import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import youtube_m3ugrabber as grabber  # noqa: E402


HLS_LINK = 'https://manifest.googlevideo.com/api/manifest/hls_playlist/index.m3u8'

# grab() is stubbed out by the no_network fixture below, so keep the real one.
hls_from_ytdlp = grabber.hls_from_ytdlp


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Fail loudly if a test forgets to stub an outbound call."""
    def blocked(*args, **kwargs):
        raise AssertionError('unexpected network call')

    monkeypatch.setattr(grabber.requests, 'get', blocked)
    monkeypatch.setattr(grabber, 'hls_from_ytdlp', lambda url: None)


class TestExtractM3u8Link:
    def test_returns_none_when_no_m3u8_present(self):
        assert grabber.extract_m3u8_link('<html>no stream here</html>') is None

    def test_returns_none_when_m3u8_has_no_https_prefix(self):
        assert grabber.extract_m3u8_link('ref="index.m3u8"') is None

    def test_prefers_hls_manifest_url_field(self):
        response = f'{{"streamingData":{{"hlsManifestUrl":"{HLS_LINK}?variant=1"}}}}'
        assert grabber.extract_m3u8_link(response) == f'{HLS_LINK}?variant=1'

    def test_unescapes_hls_manifest_url(self):
        escaped = HLS_LINK.replace('/', r'\/')
        response = f'"hlsManifestUrl": "{escaped}"'
        assert grabber.extract_m3u8_link(response) == HLS_LINK

    def test_extracts_link_from_embedded_json(self):
        response = 'x' * 500 + f'"someOtherUrl":"{HLS_LINK}"' + 'y' * 500
        assert grabber.extract_m3u8_link(response) == HLS_LINK

    def test_extracts_first_link_when_multiple_present(self):
        second = 'https://example.com/other.m3u8'
        assert grabber.extract_m3u8_link(f'a {HLS_LINK} b {second} c') == HLS_LINK

    def test_extracts_link_longer_than_initial_window(self):
        long_link = 'https://manifest.googlevideo.com/' + 'p' * 200 + '/index.m3u8'
        assert grabber.extract_m3u8_link(f'prefix {long_link} suffix') == long_link

    def test_extracts_link_at_start_of_response(self):
        assert grabber.extract_m3u8_link(HLS_LINK) == HLS_LINK


class TestYtdlpOptions:
    def test_omits_cookies_and_proxy_when_unset(self, monkeypatch):
        monkeypatch.delenv(grabber.COOKIES_ENV, raising=False)
        monkeypatch.delenv(grabber.PROXY_ENV, raising=False)
        options = grabber.ytdlp_options()
        assert 'cookiefile' not in options and 'proxy' not in options
        assert options['skip_download'] is True

    def test_passes_cookies_and_proxy_from_env(self, monkeypatch):
        monkeypatch.setenv(grabber.COOKIES_ENV, '/tmp/cookies.txt')
        monkeypatch.setenv(grabber.PROXY_ENV, 'http://proxy.test:8080')
        options = grabber.ytdlp_options()
        assert options['cookiefile'] == '/tmp/cookies.txt'
        assert options['proxy'] == 'http://proxy.test:8080'


class FakeYoutubeDL:
    """Minimal stand-in for yt_dlp.YoutubeDL."""

    def __init__(self, info=None, error=None):
        self.info = info
        self.error = error
        self.options = None
        self.requested = None

    def __call__(self, options):
        self.options = options
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def extract_info(self, url, download=False):
        self.requested = (url, download)
        if self.error:
            raise self.error
        return self.info


@pytest.fixture
def fake_yt_dlp(monkeypatch):
    def install(info=None, error=None):
        fake = FakeYoutubeDL(info=info, error=error)
        monkeypatch.setattr(grabber, 'yt_dlp',
                            type('module', (), {'YoutubeDL': fake})())
        return fake

    return install


class FlakyYoutubeDL(FakeYoutubeDL):
    """Raises `error` for the first `failures` calls, then returns `info`."""

    def __init__(self, failures, error, info):
        super().__init__(info=info, error=error)
        self.failures = failures
        self.calls = 0

    def extract_info(self, url, download=False):
        self.requested = (url, download)
        self.calls += 1
        if self.calls <= self.failures:
            raise self.error
        return self.info


class TestThrottleHandling:
    @pytest.mark.parametrize('message', [
        "Sign in to confirm you're not a bot",
        'Sign in to confirm you\u2019re not a bot',
        'HTTP Error 429: Too Many Requests',
    ])
    def test_detects_rate_limiting(self, message):
        assert grabber.is_throttled(RuntimeError(message)) is True

    def test_ignores_unrelated_errors(self):
        assert grabber.is_throttled(RuntimeError('Video unavailable')) is False

    def test_retries_until_the_limiter_relaxes(self, monkeypatch, capsys):
        fake = FlakyYoutubeDL(failures=2, info={'manifest_url': HLS_LINK},
                              error=RuntimeError("Sign in to confirm you're not a bot"))
        monkeypatch.setattr(grabber, 'yt_dlp', type('module', (), {'YoutubeDL': fake})())
        slept = []
        monkeypatch.setattr(grabber.time, 'sleep', slept.append)

        assert hls_from_ytdlp('https://youtube.test/live') == HLS_LINK
        assert fake.calls == 3
        assert slept == list(grabber.THROTTLE_RETRY_DELAYS)
        assert 'rate limited' in capsys.readouterr().err

    def test_gives_up_after_the_last_retry(self, monkeypatch, capsys):
        fake = FlakyYoutubeDL(failures=99, info=None,
                              error=RuntimeError("Sign in to confirm you're not a bot"))
        monkeypatch.setattr(grabber, 'yt_dlp', type('module', (), {'YoutubeDL': fake})())
        monkeypatch.setattr(grabber.time, 'sleep', lambda seconds: None)

        assert hls_from_ytdlp('https://youtube.test/live') is None
        assert fake.calls == len(grabber.THROTTLE_RETRY_DELAYS) + 1
        assert 'yt-dlp failed' in capsys.readouterr().err

    def test_does_not_retry_other_failures(self, monkeypatch):
        fake = FlakyYoutubeDL(failures=99, info=None, error=RuntimeError('Video unavailable'))
        monkeypatch.setattr(grabber, 'yt_dlp', type('module', (), {'YoutubeDL': fake})())
        monkeypatch.setattr(grabber.time, 'sleep', lambda seconds: pytest.fail('slept'))

        assert hls_from_ytdlp('https://youtube.test/live') is None
        assert fake.calls == 1


class TestHlsFromYtdlp:
    def test_returns_none_when_yt_dlp_missing(self, monkeypatch):
        monkeypatch.setattr(grabber, 'yt_dlp', None)
        assert hls_from_ytdlp('https://youtube.test/live') is None

    def test_returns_manifest_url(self, fake_yt_dlp):
        fake = fake_yt_dlp(info={'manifest_url': HLS_LINK, 'is_live': True})
        assert hls_from_ytdlp('https://youtube.test/live') == HLS_LINK
        assert fake.requested == ('https://youtube.test/live', False)
        assert fake.options['skip_download'] is True

    def test_falls_back_to_format_urls(self, fake_yt_dlp):
        fake_yt_dlp(info={'formats': [
            {'url': 'https://example.com/audio.mp4'},
            {'url': f'{HLS_LINK}?itag=96'},
        ]})
        assert hls_from_ytdlp('https://youtube.test/live') == f'{HLS_LINK}?itag=96'

    def test_returns_none_when_no_hls_format(self, fake_yt_dlp):
        fake_yt_dlp(info={'formats': [{'url': 'https://example.com/video.mp4'}]})
        assert hls_from_ytdlp('https://youtube.test/live') is None

    def test_returns_none_and_warns_on_extraction_error(self, fake_yt_dlp, capsys):
        fake_yt_dlp(error=RuntimeError('Sign in to confirm you are not a bot'))
        assert hls_from_ytdlp('https://youtube.test/live') is None
        assert 'not a bot' in capsys.readouterr().err

    def test_returns_none_when_info_is_none(self, fake_yt_dlp):
        fake_yt_dlp(info=None)
        assert hls_from_ytdlp('https://youtube.test/live') is None


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

    def test_skips_and_warns_on_missing_fields(self, capsys):
        assert grabber.parse_channel_line('Only Name | group') is None
        assert 'malformed channel line' in capsys.readouterr().err


class TestHlsFromHtml:
    def test_returns_link_from_page(self, monkeypatch):
        monkeypatch.setattr(grabber, 'fetch',
                            lambda url: f'"hlsManifestUrl":"{HLS_LINK}"')
        assert grabber.hls_from_html('https://youtube.test/live') == HLS_LINK

    def test_falls_back_to_curl(self, monkeypatch):
        monkeypatch.setattr(grabber, 'windows', False)
        monkeypatch.setattr(grabber, 'fetch', lambda url: 'offline')
        monkeypatch.setattr(grabber, 'fetch_with_curl',
                            lambda url: f'"hlsManifestUrl":"{HLS_LINK}"')
        assert grabber.hls_from_html('https://youtube.test/live') == HLS_LINK

    def test_skips_curl_fallback_on_windows(self, monkeypatch):
        def boom(url):
            raise AssertionError('curl fallback must not run on windows')

        monkeypatch.setattr(grabber, 'windows', True)
        monkeypatch.setattr(grabber, 'fetch', lambda url: 'offline')
        monkeypatch.setattr(grabber, 'fetch_with_curl', boom)
        assert grabber.hls_from_html('https://youtube.test/live') is None

    def test_reports_playability_status(self, monkeypatch, capsys):
        monkeypatch.setattr(grabber, 'windows', False)
        monkeypatch.setattr(
            grabber, 'fetch',
            lambda url: '"playabilityStatus":{"status":"LOGIN_REQUIRED","reason":"bot"}')
        monkeypatch.setattr(grabber, 'fetch_with_curl', lambda url: 'offline')
        assert grabber.hls_from_html('https://youtube.test/live') is None
        assert 'LOGIN_REQUIRED' in capsys.readouterr().err


class TestGrab:
    def test_prefers_ytdlp_result(self, monkeypatch, capsys):
        def boom(url):
            raise AssertionError('html scrape must not run when yt-dlp succeeds')

        monkeypatch.setattr(grabber, 'hls_from_ytdlp', lambda url: HLS_LINK)
        monkeypatch.setattr(grabber, 'hls_from_html', boom)
        assert grabber.grab('https://youtube.test/live') is True
        assert capsys.readouterr().out.strip() == HLS_LINK

    def test_falls_back_to_html_scrape(self, monkeypatch, capsys):
        monkeypatch.setattr(grabber, 'hls_from_html', lambda url: HLS_LINK)
        grabber.grab('https://youtube.test/live')
        assert capsys.readouterr().out.strip() == HLS_LINK

    def test_prints_not_available_when_both_paths_fail(self, monkeypatch, capsys):
        monkeypatch.setattr(grabber, 'hls_from_html', lambda url: None)
        assert grabber.grab('https://youtube.test/live') is False
        assert capsys.readouterr().out.strip() == grabber.NOT_AVAILABLE_LINK

    def test_survives_request_exception(self, monkeypatch, capsys):
        def raise_timeout(url):
            raise grabber.requests.Timeout('too slow')

        monkeypatch.setattr(grabber, 'hls_from_html', raise_timeout)
        grabber.grab('https://youtube.test/live')
        captured = capsys.readouterr()
        assert captured.out.strip() == grabber.NOT_AVAILABLE_LINK
        assert 'request failed' in captured.err


class TestFetchWithCurl:
    def test_returns_body_and_writes_temp_file(self, monkeypatch, tmp_path):
        temp_file = tmp_path / 'temp.txt'
        calls = []

        def fake_run(argv, **kwargs):
            calls.append(argv)
            return subprocess.CompletedProcess(argv, 0, stdout='line1\nline2\n', stderr='')

        monkeypatch.setattr(grabber.subprocess, 'run', fake_run)
        assert grabber.fetch_with_curl('https://youtube.test/live',
                                       temp_file=str(temp_file)) == 'line1\nline2\n'
        assert calls[0][0] == 'curl' and calls[0][-1] == 'https://youtube.test/live'
        assert temp_file.read_text() == 'line1\nline2\n'

    def test_returns_empty_body_and_warns_when_curl_fails(self, monkeypatch, capsys):
        def fake_run(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 6, stdout='', stderr='resolve failed')

        monkeypatch.setattr(grabber.subprocess, 'run', fake_run)
        assert grabber.fetch_with_curl('https://youtube.test/live') == ''
        assert 'curl exited 6' in capsys.readouterr().err

    def test_returns_empty_body_when_curl_is_missing(self, monkeypatch, capsys):
        def fake_run(argv, **kwargs):
            raise FileNotFoundError('curl')

        monkeypatch.setattr(grabber.subprocess, 'run', fake_run)
        assert grabber.fetch_with_curl('https://youtube.test/live') == ''
        assert 'could not run curl' in capsys.readouterr().err


class TestFetch:
    def test_requests_url_with_timeout_and_browser_headers(self, monkeypatch):
        captured = {}

        class Response:
            text = 'body'

            def raise_for_status(self):
                pass

        def fake_get(url, timeout, headers):
            captured.update(url=url, timeout=timeout, headers=headers)
            return Response()

        monkeypatch.setattr(grabber.requests, 'get', fake_get)
        assert grabber.fetch('https://youtube.test/live') == 'body'
        assert captured['url'] == 'https://youtube.test/live'
        assert captured['timeout'] == 15
        assert captured['headers'] == grabber.BROWSER_HEADERS

    def test_raises_on_error_status(self, monkeypatch):
        class Response:
            text = 'Too Many Requests'

            def raise_for_status(self):
                raise grabber.requests.HTTPError('429 Client Error')

        monkeypatch.setattr(grabber.requests, 'get',
                            lambda url, timeout, headers: Response())
        with pytest.raises(grabber.requests.HTTPError):
            grabber.fetch('https://youtube.test/live')


class TestCleanup:
    def test_removes_temp_and_watch_files(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        for name in ['temp.txt', 'watch1', 'youtube.m3u']:
            (tmp_path / name).write_text('x')
        grabber.cleanup()
        assert sorted(os.listdir(tmp_path)) == ['youtube.m3u']

    def test_does_nothing_when_temp_files_missing(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        grabber.cleanup()

    def test_warns_when_a_file_cannot_be_removed(self, monkeypatch, tmp_path, capsys):
        monkeypatch.chdir(tmp_path)
        (tmp_path / 'temp.txt').write_text('x')

        def refuse(path):
            raise PermissionError('read-only')

        monkeypatch.setattr(grabber.os, 'remove', refuse)
        grabber.cleanup()
        assert 'could not remove temp.txt' in capsys.readouterr().err


class TestMain:
    def test_emits_playlist_for_channel_file(self, monkeypatch, tmp_path, capsys):
        channel_file = tmp_path / 'youtube_channel_info.txt'
        channel_file.write_text(
            '~~ DO NOT EDIT\n'
            '\n'
            'Gazi TV Live | bangla | https://logo.test/gtv.png | gazi.bd\n'
            'https://youtube.test/gazi/live\n'
        )
        monkeypatch.setattr(grabber, 'hls_from_ytdlp', lambda url: HLS_LINK)
        monkeypatch.setattr(grabber, 'cleanup', lambda: None)

        assert grabber.main(str(channel_file)) == 1

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
        assert grabber.main(str(channel_file)) == 0
        assert called == [True]

    def test_warns_when_nothing_resolved(self, monkeypatch, tmp_path, capsys):
        channel_file = tmp_path / 'channels.txt'
        channel_file.write_text('A | g | l |\nhttps://youtube.test/a/live\n')
        monkeypatch.setattr(grabber, 'hls_from_html', lambda url: None)
        monkeypatch.setattr(grabber, 'cleanup', lambda: None)

        assert grabber.main(str(channel_file)) == 0

        err = capsys.readouterr().err
        assert '# resolved 0/1 channels' in err
        assert grabber.COOKIES_ENV in err
