@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Electronic Customs Records Auditor v1.7 - Screenshots Only
if not exist "output" mkdir "output"

echo ============================================================
echo  Electronic Customs Records Auditor v1.7
echo  SCREENSHOTS-ONLY MODE

echo ============================================================
echo.
echo This mode intentionally skips MP4 recording.
echo Use RUN_ALL.bat for the final portfolio video.
echo.

set "PYMODE="
where py >nul 2>nul
if not errorlevel 1 set "PYMODE=PYLAUNCHER"
if not defined PYMODE (
  where python >nul 2>nul
  if not errorlevel 1 set "PYMODE=PYTHON"
)
if not defined PYMODE goto :NO_PYTHON

if "%PYMODE%"=="PYLAUNCHER" (
  py -3 -u setup_recording.py --screenshots-only
  if errorlevel 1 goto :ERROR
  py -3 -u workflow_runner.py
  set "RC=!ERRORLEVEL!"
) else (
  python -u setup_recording.py --screenshots-only
  if errorlevel 1 goto :ERROR
  python -u workflow_runner.py
  set "RC=!ERRORLEVEL!"
)
if not "%RC%"=="0" goto :ERROR
exit /b 0

:NO_PYTHON
echo [ERROR] Python 3 was not detected.
pause
exit /b 1

:ERROR
echo.
echo [ERROR] Screenshot sequence did not complete.
echo Review output\RUN_ALL_LOG.txt
pause
exit /b 1
