@echo off
setlocal EnableExtensions
REM ============================================================
REM  ONE COMMAND to onboard a new client (controller side):
REM    new_client.bat <nickname>
REM
REM  1. Generates a single-use Tailscale Auth Key via the API
REM     (management token from my-targets\tailscale-api.env)
REM  2. Builds target-<nickname>\ with everything baked in
REM  3. Prints: send the folder, then run connect_target.bat
REM
REM  If API key generation fails (token missing/expired), it
REM  falls back to prompting for a manually generated Auth Key.
REM ============================================================
set "NAME=%~1"
if "%NAME%"=="" set /p "NAME=Target nickname: "
if "%NAME%"=="" exit /b 1

set "TSKEY="
for /f "usebackq delims=" %%i in (`python "%~dp0scripts\tailscale_new_authkey.py" --name "%NAME%"`) do set "TSKEY=%%i"
if "%TSKEY:~0,10%"=="tskey-auth-" goto have_key
echo.
echo [FALLBACK] API key generation failed (see message above).
echo            Paste a manually generated Auth Key instead
echo            (https://login.tailscale.com/admin/settings/keys):
set "TSKEY="
set /p "TSKEY=Auth key: "
if "%TSKEY%"=="" exit /b 1

:have_key
call "%~dp0make_target_installer.bat" "%NAME%" "%TSKEY%"
