@echo off
setlocal EnableExtensions
REM ============================================================
REM  Optional add-on for PC InterConnect: join Tailscale so this
REM  PC is reachable from ANYWHERE (not just the same Wi-Fi/LAN).
REM
REM  Run this AFTER install_windows_mcp.bat.
REM
REM  What it does:
REM    1. Install Tailscale via winget if missing (one UAC prompt)
REM    2. Open the browser to log in - use the SAME account as the
REM       controller PC (this is the only manual step)
REM    3. Print this machine's Tailscale IP (100.x.x.x)
REM
REM  Usage: install_tailscale.bat [tailscale-auth-key]
REM    Optional: pass an auth key generated at
REM    https://login.tailscale.com/admin/settings/keys
REM    to log in fully automatically (no browser needed).
REM ============================================================

set "PATH=%PATH%;C:\Program Files\Tailscale"

echo [1/3] Checking Tailscale ...
if not exist "C:\Program Files\Tailscale\tailscale.exe" (
    echo   Installing Tailscale via winget - ONE admin prompt will appear ...
    winget install --id tailscale.tailscale -e --accept-source-agreements --accept-package-agreements
    if errorlevel 1 (
        echo   [ERROR] winget install failed. Download manually: https://tailscale.com/download
        pause
        exit /b 1
    )
)
if not exist "C:\Program Files\Tailscale\tailscale.exe" (
    echo   [ERROR] Tailscale not found after install. Reopen this script.
    pause
    exit /b 1
)
echo   Tailscale found.

echo [2/3] Logging in ...
if "%~1"=="" (
    echo   A browser window will open - sign in with the SAME account
    echo   as the controller PC (GitHub / Google / Microsoft, any one).
    "C:\Program Files\Tailscale\tailscale.exe" login
) else (
    echo   Joining the tailnet with the provided auth key ...
    "C:\Program Files\Tailscale\tailscale.exe" up --auth-key "%~1"
)
if errorlevel 1 (
    echo   [ERROR] Login did not complete. Run this script again.
    pause
    exit /b 1
)

echo [3/3] Reading this machine's Tailscale IP ...
set "TSIP="
for /f "tokens=*" %%i in ('tailscale ip -4 2^>nul') do if not defined TSIP set "TSIP=%%i"

timeout /t 1 >nul
echo.
echo ============================================================
if defined TSIP (
    echo  Done! This PC is now reachable from anywhere at:
    echo    Tailscale IP:  %TSIP%
) else (
    echo  Login done, but the IP could not be read automatically.
    echo  Get it with:  tailscale ip -4
)
echo.
echo  Send the controller PC these THREE lines:
echo    IP:   %TSIP%
echo    PORT: 8808
echo    KEY:  the AUTH KEY printed by install_windows_mcp.bat
echo          ^(lost it? show it again with:)
echo           reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v WindowsMCP^)
echo ============================================================
pause
