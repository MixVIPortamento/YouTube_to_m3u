@echo off

cd /d "%~dp0"

python -m pip install --upgrade -r requirements.txt || exit /b 1

REM Written to a temp file first so a failed run keeps the previous youtube.m3u.
python scripts\youtube_m3ugrabber.py > youtube.m3u.tmp
set status=%errorlevel%
if not "%status%"=="0" (
    echo m3u grab failed ^(exit %status%^), keeping the previous youtube.m3u 1>&2
    del youtube.m3u.tmp
    exit /b %status%
)

move /y youtube.m3u.tmp youtube.m3u

echo m3u grabbed
