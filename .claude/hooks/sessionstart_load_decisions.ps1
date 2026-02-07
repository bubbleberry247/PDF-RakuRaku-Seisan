# .claude/hooks/sessionstart_load_decisions.ps1
# Purpose:
# - SessionStart時に plans/handoff.md を追加コンテキストとして注入する
# - 3-tier context system: Tier1=handoff(always), Tier2=skills(keyword), Tier3=decisions(on-demand)
# - Legacy decisions.md (5,278 lines) is NO LONGER loaded at session start
# - Per-project decisions are in plans/decisions/projects/*.md (read on demand)

$raw = [Console]::In.ReadToEnd()

$payload = $null
try {
    if ($raw -and $raw.Trim().Length -gt 0) {
        $payload = $raw | ConvertFrom-Json
    }
} catch {
    $payload = $null
}

$sessionId = ""
if ($payload -and $payload.session_id) {
    $sessionId = [string]$payload.session_id
}
$sid8 = if ($sessionId.Length -ge 8) { $sessionId.Substring(0, 8) } else { $sessionId }

$projectDir = $env:CLAUDE_PROJECT_DIR
if (-not $projectDir) {
    $projectDir = (Get-Location).Path
}

$handoffPath = Join-Path $projectDir "plans\handoff.md"

function Write-FileWithGuard {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Label,
        [int]$MaxBytes = 20000,
        [int]$TailLines = 200
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        Write-Output "--- $Label (missing) ---"
        Write-Output "Not found: $Path"
        Write-Output ""
        return
    }

    $bytes = (Get-Item -LiteralPath $Path).Length
    if ($bytes -le $MaxBytes) {
        Write-Output "--- $Label (full, <= $MaxBytes bytes) ---"
        Get-Content -LiteralPath $Path -Raw
        Write-Output ""
    } else {
        Write-Output "--- $Label (tail, > $MaxBytes bytes) ---"
        Write-Output "(File is large; showing last $TailLines lines. Open the file for full history.)"
        Get-Content -LiteralPath $Path -Tail $TailLines
        Write-Output ""
    }
}

Write-Output "=== Session Handoff (sid=$sid8) ==="
Write-Output "Tier 1: CLAUDE.md + AGENTS.md loaded automatically by Claude Code"
Write-Output "Tier 2: Skills loaded by keyword match (.claude/skills/)"
Write-Output "Tier 3: Per-project decisions in plans/decisions/projects/ (read on demand)"
Write-Output ""

# Only load handoff (compact current status)
Write-FileWithGuard -Path $handoffPath -Label "handoff.md" -MaxBytes 8000 -TailLines 120
