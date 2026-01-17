# .claude/hooks/sessionstart_load_decisions.ps1
# Purpose:
# - SessionStart時に plans/decisions.md と plans/handoff.md を追加コンテキストとして注入する
# - ファイル肥大化時は末尾のみ表示してコンテキスト消費を抑える

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

$decisionsPath = Join-Path $projectDir "plans\decisions.md"
$handoffPath   = Join-Path $projectDir "plans\handoff.md"

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
Write-Output "Must read first: plans/decisions.md"
Write-Output ""

Write-FileWithGuard -Path $decisionsPath -Label "decisions.md" -MaxBytes 20000 -TailLines 200
Write-FileWithGuard -Path $handoffPath   -Label "handoff.md"   -MaxBytes 8000  -TailLines 120
