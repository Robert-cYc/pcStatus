@echo off
setlocal EnableExtensions
rem ============================================================
rem  247 System Monitor - one-click launcher
rem  Double-click to start. Optional settings: local_env.bat
rem  (copy local_env.bat.example). Set NO_BROWSER=1 / NO_PAUSE=1
rem  to skip opening the browser / the final pause.
rem ============================================================
chcp 65001 >nul
cd /d "%~dp0"
title 247 System Monitor

rem --- 1. Locate Python (3.11+) ---------------------------------
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY (
    where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo [ERROR] Python 3 was not found. Install it from https://www.python.org/downloads/
    echo         and tick "Add python.exe to PATH".
    goto :end
)

rem --- 2. Create virtual environment outside the synced folder ---
rem     (Google Drive would sync thousands of venv files)
set "APP_HOME=%LOCALAPPDATA%\siAgent"
set "VENV=%APP_HOME%\venv"
if not exist "%APP_HOME%" mkdir "%APP_HOME%"
if not exist "%VENV%\Scripts\python.exe" (
    echo [SETUP] Creating virtual environment...
    %PY% -m venv "%VENV%"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        goto :end
    )
)

rem --- 3. Install / update dependencies --------------------------
echo [SETUP] Checking dependencies...
"%VENV%\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Dependency installation failed. Check your network connection.
    goto :end
)

rem --- 4. Configuration -------------------------------------------
rem     Secrets (password, Telegram token, ...) live in local_env.bat,
rem     which is git-ignored.
if exist "local_env.bat" call "local_env.bat"
if not defined MONITOR_PORT set "MONITOR_PORT=5000"
rem     Keep SQLite on a local disk (avoids Drive sync locks).
if not defined MONITOR_DB set "MONITOR_DB=%APP_HOME%\agent_data.db"
set "PYTHONUTF8=1"

rem --- 5. Open the dashboard shortly after the server starts -----
if not defined NO_BROWSER (
    start "" /b cmd /c "timeout /t 4 /nobreak >nul & start "" http://127.0.0.1:%MONITOR_PORT%"
)

rem --- 6. Run (Ctrl+C to stop) ------------------------------------
echo.
echo [START] Dashboard: http://127.0.0.1:%MONITOR_PORT%   (Ctrl+C to stop)
echo.
"%VENV%\Scripts\python.exe" monitor.py
echo.
echo [STOPPED] Monitor exited with code %errorlevel%.

:end
if not defined NO_PAUSE pause
endlocal
