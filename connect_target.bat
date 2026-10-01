@echo off
setlocal
REM ============================================================
REM  CONTROLLER-SIDE: wait for a target PC to finish installing,
REM  auto-detect it in the tailnet, verify the connection and
REM  print the ready-to-paste MCP config.
REM
REM  Usage: connect_target.bat <nickname>     (from make_target_installer)
REM         connect_target.bat <nickname> --ip 100.x.y.z   (skip discovery)
REM ============================================================
set "NAME=%~1"
if "%NAME%"=="" set /p "NAME=Target nickname: "
if "%NAME%"=="" exit /b 1
shift
set "REST=%1 %2 %3 %4"
python "%~dp0scripts\auto_connect_target.py" --name "%NAME%" %REST%
pause
