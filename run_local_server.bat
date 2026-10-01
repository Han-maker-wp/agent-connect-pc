@echo off
REM ============================================================
REM  Temporary LOCAL test server on the CONTROLLER PC (loopback
REM  only, no auth). Pairs with an MCP entry that points to
REM  http://127.0.0.1:8808/mcp - handy for trying the toolset
REM  before deploying to a real remote PC. Close window = stop.
REM ============================================================
set "NO_PROXY=pypi.tuna.tsinghua.edu.cn,pypi.org,files.pythonhosted.org"
uvx --python 3.14 windows-mcp==0.8.7 serve --transport streamable-http --host 127.0.0.1 --port 8808
pause
