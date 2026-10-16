@echo off
title Static Group QTO server
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 goto nopython

rem A .venv copied from another computer points to that computer's Python and does not work here: rebuild it.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import fastapi, ezdxf, shapely, openpyxl, uvicorn" >nul 2>nul
  if errorlevel 1 (
    echo The Python environment in this folder does not work on this computer - rebuilding it...
    rmdir /s /q ".venv"
  )
)

if not exist ".venv\Scripts\python.exe" (
  echo First start: creating Python environment and installing packages ^(one time, needs internet^)...
  python -m venv .venv
  if errorlevel 1 goto fail
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto fail
)

".venv\Scripts\python.exe" tools\relink_paths.py
echo.
echo   Static Group QTO is starting...
echo   Your browser will open at  http://127.0.0.1:8765  in a few seconds.
echo   Keep this window open while you use the app. Close it to stop.
echo.
start "" /min cmd /c "timeout /t 4 /nobreak >nul & start http://127.0.0.1:8765"
".venv\Scripts\python.exe" -m uvicorn server.app:app --host 127.0.0.1 --port 8765
echo.
echo The server stopped. If you saw "address already in use", the app is already running in another window:
echo just open http://127.0.0.1:8765 in your browser.
pause
goto :eof

:nopython
echo Python was not found.
echo Install Python 3.10 or newer from https://www.python.org/downloads/
echo and tick "Add python.exe to PATH" during setup, then run this file again.
pause
goto :eof

:fail
echo Setup failed. Check your internet connection, then delete the .venv folder and run this file again.
pause
