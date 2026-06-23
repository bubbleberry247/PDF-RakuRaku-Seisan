@echo off

setlocal

set "PACK_DIR=%~dp0"

for %%I in ("%PACK_DIR%..") do set "REPORTS_DIR=%%~fI"

for %%I in ("%REPORTS_DIR%\..\..") do set "ROOT_DIR=%%~fI"

set "PY=C:\Users\masam\AppData\Local\Programs\Python\Python313\python.exe"

if not exist "%PY%" set "PY=python"

set "AUTO_FILL_TOOL=%ROOT_DIR%\tools\auto_fill_minimum_operator_review_input_20260623.py"

set "MINIMUM_CSV=%PACK_DIR%minimum_operator_review_input.csv"

set "SAFE_JSON=%REPORTS_DIR%\safe_goal_checks_20260620\safe_goal_checks_summary.json"

set "SAFE_MD=%REPORTS_DIR%\safe_goal_checks_20260620\safe_goal_checks_summary.md.numbered"

set "APPLY_BAT=%PACK_DIR%APPLY_AND_RUN_AFTER_FILL_minimum_operator_review_input.bat"



if not exist "%AUTO_FILL_TOOL%" (

  echo Missing Codex auto evidence tool: "%AUTO_FILL_TOOL%"

  echo Run this from the canonical working repository, not from a detached review-only copy.

  pause

  exit /b 1

)

if not exist "%MINIMUM_CSV%" (

  echo Missing minimum CSV: "%MINIMUM_CSV%"

  pause

  exit /b 1

)

if not exist "%APPLY_BAT%" (

  echo Missing apply BAT: "%APPLY_BAT%"

  pause

  exit /b 1

)



echo [1/2] Codex auto evidence review fills the final 10 rows...

"%PY%" -X utf8 "%AUTO_FILL_TOOL%" --minimum-csv "%MINIMUM_CSV%" --safe-summary-json "%SAFE_JSON%" --safe-summary-md "%SAFE_MD%" --out-dir "%PACK_DIR%codex_auto_evidence_review"

if errorlevel 1 (

  echo Codex auto evidence review failed. Check "%PACK_DIR%codex_auto_evidence_review".

  pause

  exit /b 1

)



echo [2/2] Applying filled rows and running fixed safe checks...

call "%APPLY_BAT%"

exit /b %ERRORLEVEL%
