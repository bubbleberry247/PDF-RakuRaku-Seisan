@echo off
rem ============================================================
rem print_help.cmd - Agent Browser ヘルプ表示
rem ============================================================
setlocal

set ROOT=C:\ProgramData\RK10\tools\agent-browser
set AGENT_BROWSER_HOME=%ROOT%\app\agent-browser\agent-browser
set PLAYWRIGHT_BROWSERS_PATH=%ROOT%\pw-browsers

echo [Agent Browser Help]
echo.
"%ROOT%\agent-browser-win32-x64.exe" --help

endlocal
