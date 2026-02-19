@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

REM ============================================================
REM  Autonomous Claude Code Loop
REM  Usage: run_claude_loop.bat [max_iterations]
REM  Default: 5 iterations (safety limit)
REM  Stop: Ctrl+C or close terminal
REM ============================================================

set "PROJECT_DIR=c:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan"
set "PROMPT_FILE=%PROJECT_DIR%\AGENT_PROMPT_CLAUDE.md"
set "LOG_DIR=%PROJECT_DIR%\logs\autonomous"

REM Max iterations (default 5, override with argument)
set MAX_ITER=5
if not "%~1"=="" set MAX_ITER=%~1

REM Create log directory
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM Timestamp for this run
for /f "tokens=1-6 delims=/:. " %%a in ("%date% %time%") do (
    set "TIMESTAMP=%%a%%b%%c_%%d%%e%%f"
)
set "LOG_FILE=%LOG_DIR%\run_%TIMESTAMP%.log"

echo ============================================================
echo  Claude Autonomous Loop
echo  Project: %PROJECT_DIR%
echo  Max iterations: %MAX_ITER%
echo  Log: %LOG_FILE%
echo  Stop: Ctrl+C
echo ============================================================
echo.

cd /d "%PROJECT_DIR%"

set ITER=0

:loop
set /a ITER+=1

if %ITER% gtr %MAX_ITER% (
    echo.
    echo [DONE] Reached max iterations (%MAX_ITER%). Stopping.
    echo [DONE] Reached max iterations (%MAX_ITER%). >> "%LOG_FILE%"
    goto :end
)

echo [%date% %time%] Iteration %ITER%/%MAX_ITER% starting...
echo [%date% %time%] Iteration %ITER%/%MAX_ITER% >> "%LOG_FILE%"

REM Pass explicit autonomous workflow prompt to claude
claude -p "You are an autonomous improvement agent. DO NOT ask questions. DO NOT wait for instructions. Execute immediately: STEP 1: Read plans/handoff.md. STEP 2: Pick ONE actionable task within scope (Video2PDD, PDF OCR, Documentation, Cross-project). Do NOT touch Scenario 55 production files or anything outside this repository. STEP 3: Execute the task. STEP 4: Update plans/handoff.md with what you did. STEP 5: git add and commit. If no tasks, update handoff.md with 'No pending autonomous tasks' and stop. This is iteration %ITER% of %MAX_ITER%. START NOW." --dangerously-skip-permissions --model claude-sonnet-4-5-20250929 >> "%LOG_FILE%" 2>&1

if errorlevel 1 (
    echo [ERROR] Claude exited with error. Check log.
    echo [ERROR] Claude exited with error at iteration %ITER% >> "%LOG_FILE%"
    goto :end
)

echo [%date% %time%] Iteration %ITER% completed.
echo.

REM Brief pause between iterations (5 seconds)
timeout /t 5 /nobreak >nul

goto :loop

:end
echo.
echo Loop finished. Log saved to: %LOG_FILE%
pause
