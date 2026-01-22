@echo off
rem ============================================================
rem check_version.cmd - Agent Browser バージョン確認
rem ============================================================
setlocal

set ROOT=C:\ProgramData\RK10\tools\agent-browser
set AGENT_BROWSER_HOME=%ROOT%\app\agent-browser\agent-browser
set PLAYWRIGHT_BROWSERS_PATH=%ROOT%\pw-browsers

echo [Agent Browser Version Check]
echo.
"%ROOT%\agent-browser-win32-x64.exe" --version

endlocal
