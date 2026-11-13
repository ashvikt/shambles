@echo off
setlocal
title Shambles
cd /d "%~dp0"

set "PY="
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
  if not errorlevel 1 set "PY=py -3"
)
if not defined PY (
  python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
  if not errorlevel 1 set "PY=python"
)
if not defined PY goto :nopython

if not exist ".venv\Scripts\python.exe" (
  echo Setting up Shambles for the first time. This takes a few minutes...
  %PY% -m venv .venv
  if errorlevel 1 goto :fail
)

".venv\Scripts\python.exe" -c "import importlib.metadata as m, sys; sys.exit(0 if m.version('pymobiledevice3') == '11.55.0' else 1)" >nul 2>nul
if errorlevel 1 (
  echo Downloading the iPhone tools. Please wait...
  ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
  ".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
  if errorlevel 1 goto :fail
)

".venv\Scripts\python.exe" shambles.py
echo.
echo Shambles stopped. Your iPhone is back on its real location.
pause
exit /b 0

:nopython
echo Shambles needs Python, a free program from python.org, and it is not installed yet.
echo.
echo Press any key to install it now, or close this window to cancel.
pause >nul
winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
echo.
echo Done. Close this window, then double-click "Start Shambles.bat" again.
echo If the install did not work, get Python from https://www.python.org/downloads/
echo and tick "Add python.exe to PATH" in its installer.
pause
exit /b 1

:fail
echo.
echo Something went wrong during setup. Check your internet connection and try again.
echo If it keeps failing, send a screenshot of this window.
pause
exit /b 1
