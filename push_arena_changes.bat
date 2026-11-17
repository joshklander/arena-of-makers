@echo off
REM Arena of Makers - double-click to push your changes to GitHub.
REM It also pushes arena_log.txt, so Muse can read the log without
REM you having to send the file by hand. The repo is public, so the
REM log (including Windows file paths) is visible to anyone.
python push_arena_changes.py
pause
