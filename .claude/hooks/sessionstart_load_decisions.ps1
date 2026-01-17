# SessionStart hook: Load decisions.md at session start
# Windows PowerShell version

$ErrorActionPreference = "Stop"

# Read stdin (SessionStart JSON input)
$input_json = $input | Out-String

# Extract session_id using simple regex (avoid jq dependency)
$sid = ""
if ($input_json -match '"session_id"\s*:\s*"([^"]+)"') {
    $sid = $Matches[1]
}
$sid8 = if ($sid.Length -ge 8) { $sid.Substring(0, 8) } else { $sid }

# Persist SESSION_ID for later Bash tool calls
if ($env:CLAUDE_ENV_FILE -and $sid) {
    Add-Content -Path $env:CLAUDE_ENV_FILE -Value "export SESSION_ID='$sid'"
}

$decisions = Join-Path $env:CLAUDE_PROJECT_DIR "plans\decisions.md"

Write-Output "=== Session Handoff (sid=$sid8) ==="
Write-Output "First action: read decisions at: plans/decisions.md"
Write-Output ""

if (-not (Test-Path $decisions)) {
    Write-Output "No decisions file found yet: $decisions"
    Write-Output "Create it at plans/decisions.md if you want persistent decisions."
    exit 0
}

# If file is small, include all; otherwise include tail to avoid context bloat
$bytes = (Get-Item $decisions).Length
if ($bytes -le 20000) {
    Write-Output "--- decisions.md (full, <=20KB) ---"
    Get-Content $decisions
} else {
    Write-Output "--- decisions.md (tail, >20KB) ---"
    Write-Output "(File is large; showing last 200 lines. Open plans/decisions.md for full history.)"
    Get-Content $decisions -Tail 200
}
