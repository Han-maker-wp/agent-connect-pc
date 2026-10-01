@echo off
setlocal EnableExtensions
REM ============================================================
REM  Fix-up: install + join Tailscale (key embedded).
REM  Run this if the first install did not reach the tailnet.
REM  Tries: existing install -> winget -> direct MSI download.
REM  Pure ASCII. Safe to run more than once.
REM ============================================================
set "TSKEY=__TSKEY__"
set "PATH=%PATH%;C:\Program Files\Tailscale"

echo [1/3] Checking Tailscale ...
if exist "C:\Program Files\Tailscale\tailscale.exe" (
    echo   Already installed.
    goto join
)
where winget >nul 2>nul
if not errorlevel 1 (
    echo   Installing via winget - ONE admin prompt will appear ...
    winget install --id Tailscale.Tailscale -e --source winget --accept-source-agreements --accept-package-agreements
    if not errorlevel 1 goto after_install
)
echo   winget unavailable or failed - downloading MSI from Tailscale CDN ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://pkgs.tailscale.com/stable/tailscale-setup-latest-amd64.msi' -OutFile \"$env:TEMP\tailscale_setup.msi\" -UseBasicParsing"
if not exist "%TEMP%\tailscale_setup.msi" (
    echo   [ERROR] Download failed. Check internet, or download manually:
    echo           https://tailscale.com/download
    goto done
)
echo   Installing MSI - ONE admin prompt will appear ...
powershell -NoProfile -Command "Start-Process msiexec -ArgumentList '/i', \"$env:TEMP\tailscale_setup.msi\", '/qn', '/norestart' -Verb RunAs -Wait" >nul 2>nul
del "%TEMP%\tailscale_setup.msi" >nul 2>nul
:after_install
if not exist "C:\Program Files\Tailscale\tailscale.exe" (
    echo   [ERROR] Tailscale still not installed. Screenshot this window and
    echo           send it back.
    goto done
)
echo   Tailscale installed.

:join
echo [2/3] Joining the tailnet with the embedded key ...
"C:\Program Files\Tailscale\tailscale.exe" up --auth-key "%TSKEY%"
if errorlevel 1 (
    echo   [ERROR] Join failed. Screenshot this window and send it back.
    goto done
)
echo [3/3] Current tailnet status:
"C:\Program Files\Tailscale\tailscale.exe" status
echo   This PC tailnet IP:
"C:\Program Files\Tailscale\tailscale.exe" ip -4
echo.
echo  SUCCESS - you can close this window and tell the controller.

:done
pause
