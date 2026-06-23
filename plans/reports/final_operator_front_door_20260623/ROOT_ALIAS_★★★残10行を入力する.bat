@echo off
setlocal
set "CANONICAL_AUTO=C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\reports\minimum_operator_review_input_20260623\AUTO_FILL_AND_APPLY_FROM_CODEX_EVIDENCE_minimum_operator_review_input.bat"
if exist "%CANONICAL_AUTO%" (
  call "%CANONICAL_AUTO%"
  exit /b %ERRORLEVEL%
)
set "KIT_ROOT=%~dp0"
set "AUTO_BAT=%KIT_ROOT%final_operator_front_door_20260623_1545\plans\reports\minimum_operator_review_input_20260623\AUTO_FILL_AND_APPLY_FROM_CODEX_EVIDENCE_minimum_operator_review_input.bat"
if exist "%AUTO_BAT%" (
  call "%AUTO_BAT%"
  exit /b %ERRORLEVEL%
)
set "GUIDED_BAT=%KIT_ROOT%final_operator_front_door_20260623_1545\plans\reports\minimum_operator_review_input_20260623\GUIDED_FILL_minimum_operator_review_input.bat"
if not exist "%GUIDED_BAT%" (
  echo Codex auto and guided minimum-operator input were not found:
  echo %AUTO_BAT%
  echo %GUIDED_BAT%
  pause
  exit /b 1
)
echo Codex auto entry was not found. Falling back to guided manual input.
call "%GUIDED_BAT%"
exit /b %ERRORLEVEL%
