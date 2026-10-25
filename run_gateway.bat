@echo off
setlocal enabledelayedexpansion
title TheDoom Gateway - Administrator Launcher

:: 1. Force Administrator Privileges
net session >nul 2>&1
if !errorlevel! neq 0 (
    echo =====================================================================
    echo   TheDoom Gateway - Administrator Elevation Required
    echo =====================================================================
    echo [INFO] Requesting Administrator privileges [UAC prompt]...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs" 2>nul
    if !errorlevel! equ 0 exit /b 0
    echo [INFO] Elevation prompt not available or cancelled.
    echo Please right-click run_gateway.bat and select "Run as administrator".
    echo.
    pause
    exit /b 1
)

cd /d "%~dp0"

echo =====================================================================
echo   TheDoom Gateway - 1-Click Administrator Launcher
echo   Develop by YourHacker with love
echo =====================================================================
echo.

:: 2. Check if already running on port 6969
powershell -NoProfile -Command "try { (New-Object Net.Sockets.TcpClient).Connect('127.0.0.1', 6969); exit 0 } catch { exit 1 }" >nul 2>&1
if !errorlevel! equ 0 (
    echo [OK] TheDoom Gateway is already running on port 6969.
    start http://localhost:6969
    exit /b 0
)

:: 3. Locate Python executable dynamically without hardcoded usernames
set "PY_BIN="

:: 3a. Check pythonw on PATH (preferred for silent background launch)
where pythonw >nul 2>&1
if !errorlevel! equ 0 set "PY_BIN=pythonw"

:: 3b. Check python on PATH
if "!PY_BIN!"=="" (
    where python >nul 2>&1
    if !errorlevel! equ 0 set "PY_BIN=python"
)

:: 3c. Check user AppData WindowsApps
if "!PY_BIN!"=="" (
    if exist "%LOCALAPPDATA%\Microsoft\WindowsApps\pythonw.exe" set "PY_BIN=%LOCALAPPDATA%\Microsoft\WindowsApps\pythonw.exe"
)
if "!PY_BIN!"=="" (
    if exist "%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe" set "PY_BIN=%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe"
)
if "!PY_BIN!"=="" (
    if exist "%USERPROFILE%\AppData\Local\Microsoft\WindowsApps\pythonw.exe" set "PY_BIN=%USERPROFILE%\AppData\Local\Microsoft\WindowsApps\pythonw.exe"
)
if "!PY_BIN!"=="" (
    if exist "%USERPROFILE%\AppData\Local\Microsoft\WindowsApps\python.exe" set "PY_BIN=%USERPROFILE%\AppData\Local\Microsoft\WindowsApps\python.exe"
)

:: 3d. Check all user accounts dynamically under %SystemDrive%\Users
if "!PY_BIN!"=="" (
    for /d %%U in ("%SystemDrive%\Users\*") do (
        if "!PY_BIN!"=="" (
            if exist "%%U\AppData\Local\Microsoft\WindowsApps\pythonw.exe" set "PY_BIN=%%U\AppData\Local\Microsoft\WindowsApps\pythonw.exe"
            if exist "%%U\AppData\Local\Microsoft\WindowsApps\python.exe" set "PY_BIN=%%U\AppData\Local\Microsoft\WindowsApps\python.exe"
        )
    )
)

:: 3e. Check py launcher
if "!PY_BIN!"=="" (
    where py >nul 2>&1
    if !errorlevel! equ 0 set "PY_BIN=py"
)

:: 3f. Check standard installation directories
if "!PY_BIN!"=="" (
    for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python*") do (
        if exist "%%D\pythonw.exe" set "PY_BIN=%%D\pythonw.exe"
        if exist "%%D\python.exe" set "PY_BIN=%%D\python.exe"
    )
)
if "!PY_BIN!"=="" (
    for /d %%D in ("%ProgramFiles%\Python*") do (
        if exist "%%D\pythonw.exe" set "PY_BIN=%%D\pythonw.exe"
        if exist "%%D\python.exe" set "PY_BIN=%%D\python.exe"
    )
)

if "!PY_BIN!"=="" (
    echo [ERROR] Python 3 was not detected on your system.
    echo Please install Python from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [OK] Running with Elevated Administrator Privileges.
echo Launching TheDoom Gateway in background...
cd /d "%~dp0core"
wscript.exe "%~dp0core\bin\start_gateway.vbs" >nul 2>&1
if !errorlevel! neq 0 (
    start "" "!PY_BIN!" "%~dp0core\thedoomcontrol.py"
)

:: 4. Wait for server to bind port 6969
set "ATTEMPTS=0"
:wait_loop
timeout /t 1 /nobreak >nul 2>&1
powershell -NoProfile -Command "try { (New-Object Net.Sockets.TcpClient).Connect('127.0.0.1', 6969); exit 0 } catch { exit 1 }" >nul 2>&1
if !errorlevel! equ 0 goto :ready
set /a ATTEMPTS+=1
if !ATTEMPTS! lss 4 goto :wait_loop

:ready
echo [OK] Gateway is online at http://localhost:6969
start http://localhost:6969
timeout /t 1 /nobreak >nul 2>&1
exit /b 0
