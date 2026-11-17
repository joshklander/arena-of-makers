@echo off
REM Double-click this file to run the Arena of Makers updater.
REM It needs Python and wxPython. If wxPython is missing, run this once:
REM   pip install wxPython
cd /d "%~dp0"
python arena_of_makers_updater.py
echo.
pause
