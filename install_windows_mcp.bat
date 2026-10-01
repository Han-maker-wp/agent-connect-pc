@echo off
setlocal EnableExtensions
REM ============================================================
REM  windows-mcp deploy script for the CONTROLLED Windows PC
REM  (PC Interconnect: an AI agent on another PC controls this
REM   PC through MCP over streamable HTTP)
REM
REM  v0.3.0 - OFFLINE FIRST:
REM    If windows-mcp-server.exe sits next to this script, the
REM    install needs NO network, NO uv, NO Python download.
REM    Otherwise the ONLINE path is fully China-CDN based:
REM    npmmirror (python-build-standalone runtime) + Tsinghua PyPI
REM    mirror - NO GitHub, NO winget, NO uv required. Windows 10
REM    1809+ (built-in bsdtar). Fallbacks: ghproxy/GitHub and
REM    aliyun/pypi.org indexes.
REM
REM  Usage:
REM    install_windows_mcp.bat [port] [auth_key]
REM    Defaults: port 8808, key auto-generated (printed at the end)
REM
REM  What it does (NO admin rights required; firewall wants admin once):
REM    - Register a per-user Run-key autostart serving 0.0.0.0
REM      with Bearer auth, then start the server right now
REM      (a minimized console window = the server; close it to stop)
REM    - Add a firewall rule for the TCP port
REM
REM  Uninstall: uninstall_windows_mcp.bat
REM  NOTE: keep this file pure ASCII with CRLF line endings -
REM        cmd mis-parses UTF-8 bats (GBK codepage).
REM ============================================================

set "PORT=%~1"
if "%PORT%"=="" set PORT=8808
set "KEY=%~2"
if "%KEY%"=="" for /f %%i in ('powershell -NoProfile -Command "[guid]::NewGuid().ToString('N')"') do set "KEY=%%i"
set "SRVARGS=--transport streamable-http --host 0.0.0.0 --port %PORT% --auth-key %KEY%"
set "ROOT=%LOCALAPPDATA%\WindowsMCP"
set "PY=%ROOT%\python\python.exe"

if exist "%~dp0windows-mcp-server.exe" goto offline

echo [ONLINE MODE] windows-mcp-server.exe not found next to this script.
echo               Better: download it from the GitHub Release and put it
echo               here - then this install needs no network at all.
echo.

echo [1/5] Checking existing install ...
if exist "%PY%" (
    echo   Found runtime in %ROOT% - skipping download steps.
    goto PIP_INSTALL
)
if not exist "%ROOT%" mkdir "%ROOT%"
set "TARFILE=%ROOT%\python.tar.gz"
set "PSA_TAG=20260929"
set "PSA_FILE=cpython-3.14.7+20260929-x86_64-pc-windows-msvc-install_only.tar.gz"

echo [2/5] Downloading Python 3.14.7 runtime (~48 MB, China CDN, no VPN) ...
set "URL1=https://registry.npmmirror.com/-/binary/python-build-standalone/%PSA_TAG%/%PSA_FILE%"
set "URL2=https://ghproxy.cn/https://github.com/astral-sh/python-build-standalone/releases/download/%PSA_TAG%/%PSA_FILE%"
set "URL3=https://github.com/astral-sh/python-build-standalone/releases/download/%PSA_TAG%/%PSA_FILE%"

set "URL=%URL1%"
call :DOWNLOAD
if "%DOWNLOADED%"=="1" goto EXTRACT
set "URL=%URL2%"
call :DOWNLOAD
if "%DOWNLOADED%"=="1" goto EXTRACT
set "URL=%URL3%"
call :DOWNLOAD
if "%DOWNLOADED%"=="1" goto EXTRACT
echo   [ERROR] All download sources failed. Check the network, or use the
echo           offline windows-mcp-server.exe from the project Releases page.
pause
exit /b 1

:EXTRACT
echo [3/5] Extracting with the built-in bsdtar ...
if not exist "%SYSTEMROOT%\System32\tar.exe" (
    echo   [ERROR] Built-in tar.exe not found. Windows 10 1809+ is required.
    echo           Use the offline windows-mcp-server.exe from Releases instead.
    pause
    exit /b 1
)
"%SYSTEMROOT%\System32\tar.exe" -xf "%TARFILE%" -C "%ROOT%" >nul 2>nul
if errorlevel 1 (
    echo   [ERROR] Extraction failed.
    pause
    exit /b 1
)
del "%TARFILE%" >nul 2>nul
if not exist "%PY%" (
    echo   [ERROR] python.exe not found after extraction.
    pause
    exit /b 1
)
"%PY%" --version

:PIP_INSTALL
echo [4/5] Installing windows-mcp==0.8.7 (wheels only, no compiler needed) ...
set "IDX1=https://pypi.tuna.tsinghua.edu.cn/simple"
set "IDX2=https://mirrors.aliyun.com/pypi/simple/"
set "IDX3=https://pypi.org/simple"
set "PIPOK="
for %%I in ("%IDX1%" "%IDX2%" "%IDX3%") do (
    if not defined PIPOK (
        echo   Trying mirror: %%~I
        "%PY%" -m pip install --only-binary=:all: --no-warn-script-location -q windows-mcp==0.8.7 -i %%~I
        if not errorlevel 1 set "PIPOK=1"
    )
)
if not defined PIPOK (
    echo   [ERROR] pip failed on all mirrors. Use the offline
    echo           windows-mcp-server.exe from the project Releases page.
    pause
    exit /b 1
)

:REGISTER
echo [5/5] Registering per-user autostart (Run key, NO admin needed) ...
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v WindowsMCP /f >nul 2>nul
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v WindowsMCP /t REG_SZ /d "\"%PY%\" -m windows_mcp serve %SRVARGS%" /f >nul
if errorlevel 1 (
    echo   [ERROR] Failed to write the Run key.
    pause
    exit /b 1
)
taskkill /F /FI "WINDOWTITLE eq windows-mcp server*" >nul 2>nul
start "windows-mcp server" /min "%PY%" -m windows_mcp serve %SRVARGS%
goto firewall

:offline
echo [OFFLINE MODE] windows-mcp-server.exe found - no download needed.
echo [1/3] Skipped (bundled runtime).
echo [2/3] Skipped (bundled runtime).
echo [3/3] Registering per-user autostart (Run key, NO admin needed) ...
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v WindowsMCP /f >nul 2>nul
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v WindowsMCP /t REG_SZ /d "\"%~dp0windows-mcp-server.exe\" serve %SRVARGS%" /f >nul
if errorlevel 1 (
    echo   [ERROR] Failed to write the Run key.
    pause
    exit /b 1
)
taskkill /F /FI "WINDOWTITLE eq windows-mcp server*" >nul 2>nul
start "windows-mcp server" /min "%~dp0windows-mcp-server.exe" serve %SRVARGS%

:firewall
echo Firewall rule for TCP %PORT% (needs admin; skip if Tailscale-only) ...
netsh advfirewall firewall add rule name="windows-mcp-%PORT%" dir=in action=allow protocol=TCP localport=%PORT% >nul 2>nul
if errorlevel 1 (
    echo   [INFO] No admin rights - firewall rule NOT added. Run once in an
    echo   ADMIN terminal:
    echo     netsh advfirewall firewall add rule name="windows-mcp-%PORT%" dir=in action=allow protocol=TCP localport=%PORT%
) else (
    echo   Firewall rule added. Rollback: netsh advfirewall firewall delete rule name="windows-mcp-%PORT%"
)

echo Tailscale check (cross-network access) ...
set "PATH=%PATH%;C:\Program Files\Tailscale"
set "TSIP="
for /f "tokens=*" %%i in ('tailscale ip -4 2^>nul') do if not defined TSIP set "TSIP=%%i"
if defined TSIP (
    echo   Tailscale detected - this PC is reachable from ANYWHERE at %TSIP%
) else (
    echo   Same-LAN only for now. For access from ANYWHERE also run:
    echo     install_tailscale.bat
)

timeout /t 3 >nul
echo.
echo ============================================================
echo  Done! Give these lines to the controller PC:
echo    PORT: %PORT%
echo    AUTH KEY: %KEY%
if defined TSIP echo    Tailscale IP: %TSIP%   ^(works from any network^)
echo  Verify from the controller PC:
echo    python scripts/test_mcp_http_handshake.py http://THIS_PC_IP:%PORT%/mcp --auth-key %KEY%
echo  Notes:
echo    - The minimized "windows-mcp server" console IS the server;
echo      closing it stops remote control (by design, stays visible).
echo    - Uninstall: uninstall_windows_mcp.bat
echo ============================================================
pause
exit /b 0

:DOWNLOAD
REM Downloads %URL% into %TARFILE%; sets DOWNLOADED=1 when size >= 10 MB
echo   Trying source: %URL%
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%URL%' -OutFile '%TARFILE%' -UseBasicParsing" >nul 2>nul
set "DOWNLOADED="
if exist "%TARFILE%" for %%A in ("%TARFILE%") do if %%~zA GEQ 10000000 set "DOWNLOADED=1"
if not "%DOWNLOADED%"=="1" if exist "%TARFILE%" del "%TARFILE%" >nul 2>nul
goto :eof
