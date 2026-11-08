@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Electronic Customs Records Auditor v1.7 - Portfolio Video
if not exist "output" mkdir "output"

echo ============================================================
echo  Electronic Customs Records Auditor v1.7
echo  VIDEO + SCREENSHOTS + REPORTS
echo ============================================================
echo.
echo This run REQUIRES a working MP4 recorder.
echo A short desktop-capture test will run before the portfolio
echo sequence begins. If video cannot be verified, the sequence

echo will stop instead of silently falling back to screenshots.
echo.

set "PYMODE="
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -c "import sys; print(sys.version)" >nul 2>nul
  if not errorlevel 1 set "PYMODE=PYLAUNCHER"
)
if not defined PYMODE (
  where python >nul 2>nul
  if not errorlevel 1 (
    python -c "import sys; print(sys.version)" >nul 2>nul
    if not errorlevel 1 set "PYMODE=PYTHON"
  )
)

if not defined PYMODE goto :NO_PYTHON

if "%PYMODE%"=="PYLAUNCHER" (
  py -3 -u setup_recording.py
  set "SETUP_RC=!ERRORLEVEL!"
  if not "!SETUP_RC!"=="0" goto :SETUP_ERROR
  py -3 -u desktop_orchestrator.py
  set "RC=!ERRORLEVEL!"
) else (
  python -u setup_recording.py
  set "SETUP_RC=!ERRORLEVEL!"
  if not "!SETUP_RC!"=="0" goto :SETUP_ERROR
  python -u desktop_orchestrator.py
  set "RC=!ERRORLEVEL!"
)

if not "%RC%"=="0" goto :DEMO_ERROR

echo.
echo ============================================================
echo  SUCCESS - VIDEO VALIDATED
echo ============================================================
echo.
echo output\electronic-customs-records-auditor-demo.mp4
echo.
echo The output folder also contains the milestone screenshots,
echo Excel/CSV results, evidence map, audit log, and video

echo validation report.
echo.
exit /b 0

:NO_PYTHON
echo [ERROR] A working Python 3 installation was not detected.
echo Install Python from python.org with "Add Python to PATH" enabled.
echo.
pause
exit /b 1

:SETUP_ERROR
echo.
echo ============================================================
echo  VIDEO PREFLIGHT FAILED
echo ============================================================
echo.
echo The portfolio sequence was NOT started because a valid MP4

echo recorder could not be verified.
echo.
echo Review:
echo   output\RUN_ALL_LOG.txt
echo   output\.ffmpeg-preflight.log
echo.
echo If you only need milestone images, use:
echo   RUN_SCREENSHOTS_ONLY.bat
echo.
type "output\RUN_ALL_LOG.txt" 2>nul
pause
exit /b %SETUP_RC%

:DEMO_ERROR
echo.
echo ============================================================
echo  PORTFOLIO VIDEO WAS NOT COMPLETED SUCCESSFULLY
echo ============================================================
echo.
echo Review:
echo   output\RUN_ALL_LOG.txt
echo   output\.ffmpeg-capture.log
echo   output\VIDEO_VALIDATION.json  ^(when created^)
echo.
type "output\RUN_ALL_LOG.txt" 2>nul
pause
exit /b %RC%
