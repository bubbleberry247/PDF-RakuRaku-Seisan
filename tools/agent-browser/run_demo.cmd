@echo off
rem ============================================================
rem run_demo.cmd - Agent Browser デモ実行
rem
rem Agent BrowserはサーバーではなくCLIツールです。
rem このスクリプトはURLを開いてスナップショットを取得するデモです。
rem ============================================================
setlocal

set ROOT=C:\ProgramData\RK10\tools\agent-browser
set AGENT_BROWSER_HOME=%ROOT%\app\agent-browser\agent-browser
set PLAYWRIGHT_BROWSERS_PATH=%ROOT%\pw-browsers
set EXE=%ROOT%\agent-browser-win32-x64.exe
set SESSION=demo-session

echo ============================================================
echo Agent Browser Demo
echo ============================================================
echo.
echo [1/3] Opening https://example.com ...
"%EXE%" --session %SESSION% open https://example.com
echo.

echo [2/3] Taking snapshot (compact mode) ...
"%EXE%" --session %SESSION% snapshot -c
echo.

echo [3/3] Taking screenshot ...
"%EXE%" --session %SESSION% screenshot demo_screenshot.png
echo.

echo ============================================================
echo Demo completed.
echo - Session: %SESSION%
echo - Screenshot: demo_screenshot.png (current directory)
echo ============================================================

endlocal
