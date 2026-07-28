@echo off

REM Exit codes: 0 playlist regenerated, 1 the grabber failed, 2 no stream could
REM be resolved at all. The previous youtube.m3u is left in place unless 0.

cd /d "%~dp0"

pip install requests || exit /b 1

python scripts\youtube_m3ugrabber.py > youtube.m3u.tmp
set status=%errorlevel%
if not "%status%"=="0" (
    echo m3u grab failed ^(exit %status%^), keeping the previous youtube.m3u 1>&2
    del youtube.m3u.tmp
    exit /b %status%
)

move /y youtube.m3u.tmp youtube.m3u

echo m3u grabbed
