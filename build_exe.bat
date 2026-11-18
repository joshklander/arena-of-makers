@echo off
REM Arena of Makers - build both Windows exes on this computer.
REM Double-click this file. No commands to type.
REM
REM It installs what the game needs, then builds:
REM   dist\ArenaOfMakers.exe         - the game, everything bundled in
REM   dist\ArenaOfMakersUpdater.exe  - the updater, checks GitHub Releases
REM
REM Your .env file is NOT bundled in and is NOT touched.
REM Put your own .env file next to the exes when you run them,
REM in the same folder as the exes. There is no local save file.

cd /d "%~dp0"

echo Installing what the game needs. This can take a few minutes the first time.
python -m pip install --upgrade pip
if errorlevel 1 goto :error
pip install -r requirements.txt
if errorlevel 1 goto :error
pip install pyinstaller
if errorlevel 1 goto :error

echo.
echo Building the game exe. This takes a few minutes.
pyinstaller --noconfirm --clean --onefile --windowed --name ArenaOfMakers --add-data "sounds;sounds" main.py
if errorlevel 1 goto :error

echo.
echo Building the updater exe.
pyinstaller --noconfirm --clean --onefile --windowed --name ArenaOfMakersUpdater arena_of_makers_updater.py
if errorlevel 1 goto :error

echo.
echo Done. Your exes are in the dist folder:
echo   dist\ArenaOfMakers.exe
echo   dist\ArenaOfMakersUpdater.exe
echo Put both exes in one folder, add your .env file next to them, and double-click ArenaOfMakers.exe to play.
pause
exit /b 0

:error
echo.
echo Something went wrong. The lines above say what failed.
pause
exit /b 1
