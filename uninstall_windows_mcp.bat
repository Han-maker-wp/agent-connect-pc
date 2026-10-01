@echo off
setlocal EnableExtensions
REM ============================================================
REM  Remove windows-mcp autostart (Run key) and firewall rule.
REM  To stop the CURRENTLY RUNNING server, just close its console
REM  window (titled "windows-mcp server").
REM  Usage: uninstall_windows_mcp.bat [port]   (default port 8808)
REM ============================================================
set PORT=%1
if "%PORT%"=="" set PORT=8808

echo Removing autostart Run key "WindowsMCP" ...
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v WindowsMCP /f >nul 2>nul
if errorlevel 1 (echo   Key not found or already removed.) else echo   Key removed.

echo Removing firewall rule "windows-mcp-%PORT%" ...
netsh advfirewall firewall delete rule name="windows-mcp-%PORT%" >nul 2>nul
if errorlevel 1 (echo   Rule not removed (not found, or needs an ADMIN terminal).) else echo   Rule removed.

echo.
echo If a "windows-mcp server" console window is open, close it to stop
echo the running server.
echo Optional deep clean: uv cache clean windows-mcp
echo Uninstall done.
pause
