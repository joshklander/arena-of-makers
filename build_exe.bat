@echo off
REM Arena of Makers - build both Windows exes on this computer.
REM Double-click this file. No commands to type.
REM
REM It installs what the game needs, then runs build_exe.py, which builds:
REM   dist\ArenaOfMakers.exe         - the game, everything bundled in
REM   dist\ArenaOfMakersUpdater.exe  - the updater, checks GitHub Releases
REM
REM Your .env file is NOT bundled in and is NOT touched.
REM Put your own .env file next to the exes when you run them,
REM in the same folder as the exes. There is no local save file.
REM
REM pip and PyInstaller are run through python (python -m ...), so
REM this works even when their commands are not on PATH.

cd /d "%~dp0"

echo Installing what the game needs. This can take a few minutes the first time.
python -m pip install --upgrade pip
if errorlevel 1 goto :error
python -m pip install -r requirements.txt
if errorlevel 1 goto :error
python -m pip install pyinstaller
if errorlevel 1 goto :error

echo.
echo Building both exes. It asks for the version, like v1.0.1,
echo the same tag you will give the GitHub Release. This takes a few minutes.
python build_exe.py %1
if errorlevel 1 goto :error
pause
exit /b 0

:error
echo.
echo Something went wrong. The lines above say what failed.
pause
exit /b 1
