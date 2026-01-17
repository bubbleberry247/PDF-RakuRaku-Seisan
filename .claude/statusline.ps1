# .claude/statusline.ps1
# Purpose: Show model, session ID, and context usage percentage with warning

$raw = [Console]::In.ReadToEnd()

$p = $null
try {
    if ($raw -and $raw.Trim().Length -gt 0) {
        $p = $raw | ConvertFrom-Json
    }
} catch {
    $p = $null
}

$model = "?"
if ($p -and $p.model -and $p.model.display_name) {
    $model = [string]$p.model.display_name
}

$sid6 = ""
if ($p -and $p.session_id) {
    $sid = [string]$p.session_id
    $sid6 = if ($sid.Length -ge 6) { $sid.Substring(0, 6) } else { $sid }
}

$used = 0
if ($p -and $p.context_window -and $p.context_window.used_percentage -ne $null) {
    try {
        $used = [int][math]::Floor([double]$p.context_window.used_percentage)
    } catch {
        $used = 0
    }
}

$warn = if ($used -ge 70) { " WARN:CTX>=70%" } else { "" }

Write-Output "[$model] sid=$sid6 ctx=$used%$warn"
