@echo off

cd /d "%~dp0"

pip install requests || exit /b 1

python scripts\youtube_m3ugrabber.py > youtube.m3u.tmp
if errorlevel 1 (
    echo m3u grab failed, keeping the previous youtube.m3u 1>&2
    del youtube.m3u.tmp
    exit /b 1
)

move /y youtube.m3u.tmp youtube.m3u

echo m3u grabbed
