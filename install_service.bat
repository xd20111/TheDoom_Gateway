@echo off
setlocal enabledelayedexpansion

:: 0. Force Administrator Privileges
net session >nul 2>&1
if !errorlevel! neq 0 (
    echo =====================================================================
    echo   TheDoom Gateway - Administrator Elevation Required
    echo =====================================================================
    echo [INFO] Requesting Administrator privileges [UAC prompt]...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs" 2>nul
    if !errorlevel! equ 0 exit /b 0
    echo [INFO] Elevation prompt not available or cancelled.
    echo Please right-click install_service.bat and select "Run as administrator".
    echo.
    pause
    exit /b 1
)

title TheDoom Gateway - 1-Click Start ^& Startup Installer
cd /d "%~dp0"

echo =====================================================================
echo   TheDoom Gateway - 1-Click Start ^& Windows Startup Installer
echo   Develop by YourHacker with love
echo =====================================================================
echo [OK] Running with Elevated Administrator Privileges.
echo.

:: 1. Verify Python availability
echo [1/4] Checking Python Runtime...
set "PY_CMD="

:: 1a. Check python in PATH
where python >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=python"
)

:: 1b. Check WindowsApps python
if "!PY_CMD!"=="" (
    if exist "%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe" (
        set "PY_CMD=%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe"
    )
)
if "!PY_CMD!"=="" (
    if exist "%USERPROFILE%\AppData\Local\Microsoft\WindowsApps\python.exe" (
        set "PY_CMD=%USERPROFILE%\AppData\Local\Microsoft\WindowsApps\python.exe"
    )
)
if "!PY_CMD!"=="" (
    for /d %%U in ("%SystemDrive%\Users\*") do (
        if "!PY_CMD!"=="" (
            if exist "%%U\AppData\Local\Microsoft\WindowsApps\python.exe" set "PY_CMD=%%U\AppData\Local\Microsoft\WindowsApps\python.exe"
        )
    )
)

:: 1c. Check py launcher
if "!PY_CMD!"=="" (
    where py >nul 2>&1
    if !errorlevel! equ 0 (
        set "PY_CMD=py"
    )
)

:: 1d. Check pythonw
if "!PY_CMD!"=="" (
    where pythonw >nul 2>&1
    if !errorlevel! equ 0 (
        set "PY_CMD=pythonw"
    )
)

:: 1e. Direct execution fallback
if "!PY_CMD!"=="" (
    python --version >nul 2>&1
    if !errorlevel! equ 0 (
        set "PY_CMD=python"
    )
)

:: 1f. Check common AppData / ProgramFiles directories
if "!PY_CMD!"=="" (
    for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python*") do (
        if exist "%%D\python.exe" set "PY_CMD=%%D\python.exe"
    )
)
if "!PY_CMD!"=="" (
    for /d %%D in ("%ProgramFiles%\Python*") do (
        if exist "%%D\python.exe" set "PY_CMD=%%D\python.exe"
    )
)

if "!PY_CMD!"=="" (
    echo [ERROR] Python 3 was not detected on your system.
    echo Please install Python 3 from https://www.python.org/downloads/
    echo During installation, be sure to check "Add python.exe to PATH".
    echo.
    echo Press any key to exit...
    pause >nul
    exit /b 1
)

for /f "delims=" %%v in ('"!PY_CMD!" --version 2^>^&1') do echo [OK] Found %%v (!PY_CMD!)

:: Stop any stale/zombie process on port 6969 first
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr :6969 ^| findstr LISTENING') do (
    echo [INFO] Stopping stale gateway process on port 6969 [PID: %%a]...
    taskkill /f /pid %%a >nul 2>&1
)

:: 2. Configure Local Network by Default
echo.
echo [2/4] Setting up Network Configuration (Local Network LAN by Default)...
if not exist "%~dp0core\config" mkdir "%~dp0core\config" >nul 2>&1
if not exist "%~dp0core\logs" mkdir "%~dp0core\logs" >nul 2>&1

set "DETECTED_LAN=127.0.0.1"
"!PY_CMD!" "%~dp0core\thedoomcontrol.py" --init-config > "%TEMP%\_doom_ip.tmp" 2>nul
if exist "%TEMP%\_doom_ip.tmp" (
    set /p DETECTED_LAN=<"%TEMP%\_doom_ip.tmp"
    del "%TEMP%\_doom_ip.tmp" >nul 2>&1
)
if "!DETECTED_LAN!"=="" set "DETECTED_LAN=127.0.0.1"
echo [OK] Default Mode : LOCAL NETWORK (LAN) [0.0.0.0:6969]
echo [OK] Assigned IP  : !DETECTED_LAN!

:: 3. Configure Startup Persistence
echo.
echo [3/4] Configuring Automatic Startup at Windows Boot...
set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
if not exist "%STARTUP_FOLDER%" mkdir "%STARTUP_FOLDER%" >nul 2>&1

:: Create Startup VBS shortcut
(
    echo Set WshShell = CreateObject^("WScript.Shell"^)
    echo WshShell.Run "wscript.exe ""%~dp0core\bin\start_gateway.vbs""", 0, False
) > "%STARTUP_FOLDER%\TheDoom_Gateway.vbs"
echo [OK] Windows Startup: Auto-start shortcut installed in Startup folder.

:: Register Task Scheduler with HIGHEST elevation privileges
schtasks /create /tn "TheDoom_Gateway" /tr "wscript.exe \"%~dp0core\bin\start_gateway.vbs\"" /sc onlogon /rl HIGHEST /f >nul 2>&1
if !errorlevel! equ 0 (
    echo [OK] Task Scheduler: 'TheDoom_Gateway' registered for logon with highest privileges.
)

:: 4. Start the Application Immediately
echo.
echo [4/4] Starting TheDoom Gateway now...

cd /d "%~dp0core"
wscript.exe "%~dp0core\bin\start_gateway.vbs" >nul 2>&1
if !errorlevel! neq 0 (
    start "" "!PY_CMD!" "%~dp0core\thedoomcontrol.py"
)

:: Wait up to 5 seconds for server to respond
set "SERVER_UP=0"
set "ATTEMPTS=0"

:wait_server
timeout /t 1 /nobreak >nul 2>&1
powershell -NoProfile -Command "try { (New-Object Net.Sockets.TcpClient).Connect('127.0.0.1', 6969); exit 0 } catch { exit 1 }" >nul 2>&1
if !errorlevel! equ 0 (
    set "SERVER_UP=1"
    goto :server_ready
)
set /a ATTEMPTS+=1
if !ATTEMPTS! lss 5 goto :wait_server

if "!SERVER_UP!"=="0" (
    echo.
    echo [WARNING] Background start did not respond on port 6969 within 5 seconds.
    echo Starting in foreground mode to display diagnostics / error messages:
    echo ---------------------------------------------------------------------
    "!PY_CMD!" "%~dp0core\thedoomcontrol.py"
    pause
    exit /b 1
)

:server_ready
echo.
echo =====================================================================
echo   [SUCCESS] TheDoom Gateway is ONLINE and Running!
echo =====================================================================
echo   * Status            : RUNNING (Administrator Service)
echo   * Default Mode      : LOCAL NETWORK (LAN)
echo   * URL (This PC)     : http://localhost:6969
echo   * URL (Wi-Fi / LAN) : http://!DETECTED_LAN!:6969
echo   * Startup Status    : ACTIVE (Runs automatically upon boot / sign-in)
echo   * Boot Management   : You can toggle or remove boot auto-start
echo                          directly on the Web Dashboard at any time.
echo =====================================================================
echo.

:: Automatically open browser and close terminal window
start http://localhost:6969
timeout /t 1 /nobreak >nul 2>&1
exit /b 0
