@echo off
setlocal EnableExtensions
REM ============================================================
REM  windows-mcp deploy script for the CONTROLLED Windows PC
REM  (Route "PC Interconnect": an AI agent on another PC controls
REM   this PC through MCP over streamable HTTP)
REM
REM  v0.2.0 - OFFLINE FIRST:
REM    If windows-mcp-server.exe sits next to this script, the
REM    install needs NO network, NO uv, NO Python download.
REM    Otherwise it falls back to the online path (uv + China
REM    mirrors for PyPI and the Python build downloads).
REM
REM  Usage:
REM    install_windows_mcp.bat [port] [auth_key]
REM    Defaults: port 8808, key auto-generated (printed at the end)
REM
REM  What it does (NO admin rights required):
REM    - Register a per-user Run-key autostart serving 0.0.0.0
REM      with Bearer auth, then start the server right now
REM      (a minimized console window = the server; close it to stop)
REM    - Add a firewall rule for the TCP port (needs admin ONCE)
REM
REM  Uninstall: uninstall_windows_mcp.bat
REM  NOTE: keep this file pure ASCII - cmd mis-parses UTF-8 bats.
REM ============================================================

set PORT=%1
if "%PORT%"=="" set PORT=8808
set KEY=%2
if "%KEY%"=="" for /f %%i in ('powershell -NoProfile -Command "[guid]::NewGuid().ToString('N')"') do set KEY=%%i
set "SRVARGS=--transport streamable-http --host 0.0.0.0 --port %PORT% --auth-key %KEY%"

if exist "%~dp0windows-mcp-server.exe" goto offline

echo [ONLINE MODE] windows-mcp-server.exe not found next to this script.
echo               Better: download it from the GitHub Release and put it
echo               here - then this install needs no network at all.
echo.

echo [1/4] Checking uv ...
where uvx >nul 2>nul
if errorlevel 1 (
    if exist "%USERPROFILE%\.local\bin\uvx.exe" set "PATH=%PATH%;%USERPROFILE%\.local\bin"
)
where uvx >nul 2>nul
if errorlevel 1 (
    echo   uv not found. Installing via winget ...
    winget install --id=astral-sh.uv -e --accept-source-agreements --accept-package-agreements
    if errorlevel 1 (
        echo   [ERROR] winget install failed. Install uv manually:
        echo           https://docs.astral.sh/uv/getting-started/installation/
        pause
        exit /b 1
    )
    set "PATH=%PATH%;%USERPROFILE%\.local\bin"
)
set "UVX="
for /f "tokens=*" %%i in ('where uvx 2^>nul') do if not defined UVX set "UVX=%%i"
if not defined UVX (
    echo   [ERROR] uvx still not found after installation.
    pause
    exit /b 1
)
echo   uvx: %UVX%

echo [2/4] Pre-downloading windows-mcp 0.8.7 + Python 3.14 via China mirrors ...
REM Tsinghua PyPI mirror + GitHub accel mirror for the Python build download.
REM Both direct-connect (NO_PROXY); drop the env lines if you have a proxy.
set "UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple"
set "UV_PYTHON_INSTALL_MIRROR=https://ghproxy.cn/https://github.com/astral-sh/python-build-standalone/releases/download"
set "NO_PROXY=pypi.tuna.tsinghua.edu.cn,pypi.org,files.pythonhosted.org,ghproxy.cn"
"%UVX%" --python 3.14 windows-mcp==0.8.7 --help >nul 2>nul
echo [3/4] Registering per-user autostart (Run key, NO admin needed) ...
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v WindowsMCP /t REG_SZ /d "\"%UVX%\" --python 3.14 windows-mcp==0.8.7 serve %SRVARGS%" /f >nul
if errorlevel 1 (
    echo   [ERROR] Failed to write the Run key.
    pause
    exit /b 1
)
echo   Autostart registered. Starting the server now (minimized window) ...
start "windows-mcp server" /min "%UVX%" --python 3.14 windows-mcp==0.8.7 serve %SRVARGS%
goto firewall

:offline
echo [OFFLINE MODE] windows-mcp-server.exe found - no download needed.
echo [1/4] Skipped (bundled runtime).
echo [2/4] Skipped (bundled runtime).
echo [3/4] Registering per-user autostart (Run key, NO admin needed) ...
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v WindowsMCP /t REG_SZ /d "\"%~dp0windows-mcp-server.exe\" serve %SRVARGS%" /f >nul
if errorlevel 1 (
    echo   [ERROR] Failed to write the Run key.
    pause
    exit /b 1
)
echo   Autostart registered. Starting the server now (minimized window) ...
start "windows-mcp server" /min "%~dp0windows-mcp-server.exe" serve %SRVARGS%

:firewall
echo [4/4] Firewall rule for TCP %PORT% (needs admin; skip if Tailscale-only) ...
netsh advfirewall firewall add rule name="windows-mcp-%PORT%" dir=in action=allow protocol=TCP localport=%PORT% >nul 2>nul
if errorlevel 1 (
    echo   [INFO] No admin rights - firewall rule NOT added. Run once in an
    echo   ADMIN terminal:
    echo     netsh advfirewall firewall add rule name="windows-mcp-%PORT%" dir=in action=allow protocol=TCP localport=%PORT%
) else (
    echo   Firewall rule added. Rollback: netsh advfirewall firewall delete rule name="windows-mcp-%PORT%"
)

timeout /t 2 >nul
echo.
echo ============================================================
echo  Done! Give these TWO lines to the controller PC:
echo    PORT: %PORT%
echo    AUTH KEY: %KEY%
echo  Verify from the controller PC:
echo    python scripts/test_mcp_http_handshake.py http://THIS_PC_IP:%PORT%/mcp --auth-key %KEY%
echo  Notes:
echo    - A minimized console window IS the server; closing it stops
echo      remote control (by design - it stays visible).
echo    - Uninstall: uninstall_windows_mcp.bat
echo ============================================================
pause
