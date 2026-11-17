@echo off
REM Arena of Makers - double-click to play.
REM Needs Python, wxPython, edge-tts (the free Edge voice) and pygame:
REM   pip install wxPython edge-tts pygame
REM Or install everything in requirements.txt:
REM   pip install -r requirements.txt
python main.py
if errorlevel 1 pause
