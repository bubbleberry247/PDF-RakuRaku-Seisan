<#
.SYNOPSIS
Remove or disable "AI Conversation to Obsidian sync" artifacts with evidence.

.DESCRIPTION
Default is Dry-Run. Use -Execute to apply changes.

.PARAMETER Execute
Apply changes. Without this, the script only reports what it would do.

.PARAMETER IncludeWeak
Include weak keyword matches (e.g., "sync", "claude", "codex").
By default, weak-only matches are reported but skipped.

.PARAMETER DeleteObsidianNotes
Allow deletion under the Obsidian notes folder.

.PARAMETER DeleteLog
Delete the log file if found.
#>

[CmdletBinding()]
param(
    [switch]$Execute,
    [switch]$IncludeWeak,
    [switch]$DeleteObsidianNotes,
    [switch]$DeleteLog
)

Set-StrictMode -Version Latest

$strongPattern = '(?i)obsidian-sync|obsidian|AI Conversations|Obsidian Vault|\\\.claude\\projects|\\\.codex\\sessions'
$weakPattern = '(?i)claude|codex|sync'
$processPattern = '(?i)obsidian-sync|Obsidian Vault|AI Conversations|\\\.claude|\\\.codex'

$excludeRoots = @(
    'C:\Users\masam\.claude\projects',
    'C:\Users\masam\.codex\sessions'
)
$obsidianNotesRoot = 'C:\Users\masam\Documents\Obsidian Vault\AI Conversations'
if (-not $DeleteObsidianNotes) {
    $excludeRoots += $obsidianNotesRoot
}

$logPath = 'C:\Users\masam\.claude\logs\obsidian-sync.log'

function Test-PatternMatch {
    param([string]$Text, [string]$Pattern)
    if (-not $Text) { return $false }
    return $Text -match $Pattern
}

function Normalize-Path {
    param([string]$Path)
    if (-not $Path) { return $null }
    $trimmed = $Path.Trim('"')
    $expanded = [Environment]::ExpandEnvironmentVariables($trimmed)
    try {
        if (Test-Path -LiteralPath $expanded) {
            return (Resolve-Path -LiteralPath $expanded).Path
        }
    } catch { }
    try {
        return [IO.Path]::GetFullPath($expanded)
    } catch {
        return $expanded
    }
}

function Test-IsExcludedPath {
    param([string]$Path)
    $normalized = Normalize-Path $Path
    if (-not $normalized) { return $false }
    foreach ($root in $excludeRoots) {
        $rootNormalized = Normalize-Path $root
        if ($rootNormalized -and $normalized.StartsWith($rootNormalized, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }
    return $false
}

function Get-CommandLinePaths {
    param([string]$CommandLine)
    $results = New-Object System.Collections.Generic.List[string]
    if (-not $CommandLine) { return @() }
    $pattern = '(?i)(?:"(?<p>[A-Za-z]:\\[^"]+?\\.(?:exe|ps1|bat|cmd|py|js))"|(?<p>[A-Za-z]:\\[^\\s]+?\\.(?:exe|ps1|bat|cmd|py|js))|(?<p>%[A-Za-z0-9_]+%\\[^\\s"]+?\\.(?:exe|ps1|bat|cmd|py|js)))'
    foreach ($m in [regex]::Matches($CommandLine, $pattern)) {
        $p = $m.Groups['p'].Value
        if ($p) { $results.Add($p) }
    }
    return $results | Select-Object -Unique
}

function Is-InterpreterPath {
    param([string]$Path)
    if (-not $Path) { return $false }
    $name = [IO.Path]::GetFileName($Path).ToLowerInvariant()
    return @('python.exe', 'pythonw.exe', 'node.exe', 'pwsh.exe', 'powershell.exe', 'cmd.exe', 'wscript.exe', 'cscript.exe') -contains $name
}

$findings = New-Object System.Collections.Generic.List[object]
$binaryCandidates = New-Object System.Collections.Generic.HashSet[string]([System.StringComparer]::OrdinalIgnoreCase)

function Add-Finding {
    param($Category, $Name, $Evidence, $Action, $Status)
    $findings.Add([PSCustomObject]@{
        Category = $Category
        Name     = $Name
        Evidence = $Evidence
        Action   = $Action
        Status   = $Status
    }) | Out-Null
}

Write-Host ("Mode: " + ($(if ($Execute) { 'EXECUTE' } else { 'DRY-RUN' })))
if ($IncludeWeak) {
    Write-Host "Weak matches: INCLUDED"
} else {
    Write-Host "Weak matches: SKIPPED (use -IncludeWeak to include)"
}

# Processes
try {
    $procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match $processPattern }
    foreach ($p in $procs) {
        $evidence = $p.CommandLine
        $status = 'DRY-RUN'
        if ($Execute) {
            try {
                Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
                $status = 'Stopped'
            } catch {
                $status = "ERROR: $($_.Exception.Message)"
            }
        }
        Add-Finding -Category 'Process' -Name "$($p.Name) (PID $($p.ProcessId))" -Evidence $evidence -Action 'Stop-Process -Force' -Status $status

        $paths = Get-CommandLinePaths $evidence
        foreach ($path in $paths) {
            $normalized = Normalize-Path $path
            if (-not $normalized) { continue }
            $pathStrong = Test-PatternMatch $normalized $strongPattern
            $evidenceStrong = Test-PatternMatch $evidence $strongPattern
            $weak = (Test-PatternMatch $normalized $weakPattern) -or (Test-PatternMatch $evidence $weakPattern)

            if (Is-InterpreterPath $normalized -and -not $pathStrong) { continue }

            if ($pathStrong -or $evidenceStrong -or ($IncludeWeak -and $weak)) {
                $binaryCandidates.Add($normalized) | Out-Null
            }
        }
    }
} catch {
    Add-Finding -Category 'Process' -Name 'Win32_Process' -Evidence $_.Exception.Message -Action 'Query' -Status 'ERROR'
}

# Scheduled tasks
try {
    $tasks = Get-ScheduledTask | ForEach-Object {
        $actionText = ($_.Actions | ForEach-Object { "$($_.Execute) $($_.Arguments)" }) -join '; '
        [PSCustomObject]@{ TaskName = $_.TaskName; TaskPath = $_.TaskPath; Action = $actionText }
    } | Where-Object { $_.TaskName -match '(?i)obsidian|sync|claude|codex' -or $_.Action -match '(?i)obsidian|sync|claude|codex' }

    foreach ($t in $tasks) {
        $evidence = "$($t.TaskPath)$($t.TaskName) :: $($t.Action)"
        $strong = Test-PatternMatch $evidence $strongPattern
        $weak = Test-PatternMatch $evidence $weakPattern
        if (-not $strong -and -not ($IncludeWeak -and $weak)) {
            Add-Finding -Category 'ScheduledTask' -Name "$($t.TaskPath)$($t.TaskName)" -Evidence $t.Action -Action 'Unregister-ScheduledTask' -Status 'SKIPPED (weak match only)'
            continue
        }

        $status = 'DRY-RUN'
        if ($Execute) {
            try {
                Unregister-ScheduledTask -TaskName $t.TaskName -TaskPath $t.TaskPath -Confirm:$false -ErrorAction Stop
                $status = 'Removed'
            } catch {
                $status = "ERROR: $($_.Exception.Message)"
            }
        }
        Add-Finding -Category 'ScheduledTask' -Name "$($t.TaskPath)$($t.TaskName)" -Evidence $t.Action -Action 'Unregister-ScheduledTask' -Status $status
    }
} catch {
    Add-Finding -Category 'ScheduledTask' -Name 'Get-ScheduledTask' -Evidence $_.Exception.Message -Action 'Query' -Status 'ERROR'
}

# Run keys
$runKeys = @(
    'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run',
    'HKLM:\Software\Microsoft\Windows\CurrentVersion\Run'
)
foreach ($key in $runKeys) {
    try {
        if (-not (Test-Path $key)) { continue }
        $props = Get-ItemProperty $key
        $props.PSObject.Properties | Where-Object { $_.Name -notmatch '^PS' } | ForEach-Object {
            $name = $_.Name
            $value = [string]$_.Value
            if ($name -notmatch '(?i)obsidian|sync|claude|codex' -and $value -notmatch '(?i)obsidian|sync|claude|codex') { return }

            $evidence = $value
            $strong = Test-PatternMatch $evidence $strongPattern
            $weak = Test-PatternMatch $evidence $weakPattern

            if (-not $strong -and -not ($IncludeWeak -and $weak)) {
                Add-Finding -Category 'RunKey' -Name "$key::$name" -Evidence $value -Action 'Remove-ItemProperty' -Status 'SKIPPED (weak match only)'
                return
            }

            $status = 'DRY-RUN'
            if ($Execute) {
                try {
                    Remove-ItemProperty -Path $key -Name $name -ErrorAction Stop
                    $status = 'Removed'
                } catch {
                    $status = "ERROR: $($_.Exception.Message)"
                }
            }
            Add-Finding -Category 'RunKey' -Name "$key::$name" -Evidence $value -Action 'Remove-ItemProperty' -Status $status
        }
    } catch {
        Add-Finding -Category 'RunKey' -Name $key -Evidence $_.Exception.Message -Action 'Query' -Status 'ERROR'
    }
}

# Startup folder
try {
    $startup = [Environment]::GetFolderPath('Startup')
    $items = Get-ChildItem -LiteralPath $startup -ErrorAction SilentlyContinue
    foreach ($item in $items) {
        $target = $null
        $args = $null
        if ($item.Extension -ieq '.lnk') {
            try {
                $shell = New-Object -ComObject WScript.Shell
                $shortcut = $shell.CreateShortcut($item.FullName)
                $target = $shortcut.TargetPath
                $args = $shortcut.Arguments
            } catch { }
        }
        $evidence = "$($item.FullName) $target $args"
        if ($evidence -notmatch '(?i)obsidian|sync|claude|codex') { continue }

        $strong = Test-PatternMatch $evidence $strongPattern
        $weak = Test-PatternMatch $evidence $weakPattern
        if (-not $strong -and -not ($IncludeWeak -and $weak)) {
            Add-Finding -Category 'StartupFolder' -Name $item.FullName -Evidence $evidence -Action 'Remove-Item' -Status 'SKIPPED (weak match only)'
            continue
        }

        $status = 'DRY-RUN'
        if ($Execute) {
            try {
                Remove-Item -LiteralPath $item.FullName -Force -ErrorAction Stop
                $status = 'Removed'
            } catch {
                $status = "ERROR: $($_.Exception.Message)"
            }
        }
        Add-Finding -Category 'StartupFolder' -Name $item.FullName -Evidence $evidence -Action 'Remove-Item' -Status $status
    }
} catch {
    Add-Finding -Category 'StartupFolder' -Name 'StartupFolder' -Evidence $_.Exception.Message -Action 'Query' -Status 'ERROR'
}

# Services
try {
    $services = Get-Service | Where-Object { $_.Name -match '(?i)obsidian|sync|claude|codex' -or $_.DisplayName -match '(?i)obsidian|sync|claude|codex' }
    foreach ($s in $services) {
        $reg = "HKLM:\SYSTEM\CurrentControlSet\Services\$($s.Name)"
        $image = (Get-ItemProperty -Path $reg -Name ImagePath -ErrorAction SilentlyContinue).ImagePath
        $evidence = "$($s.DisplayName) :: $image"
        $strong = Test-PatternMatch $evidence $strongPattern
        $weak = Test-PatternMatch $evidence $weakPattern

        if (-not $strong -and -not ($IncludeWeak -and $weak)) {
            Add-Finding -Category 'Service' -Name $s.Name -Evidence $evidence -Action 'Stop-Service / sc.exe delete' -Status 'SKIPPED (weak match only)'
            continue
        }

        if (Test-IsExcludedPath $image) {
            Add-Finding -Category 'Service' -Name $s.Name -Evidence $evidence -Action 'Stop-Service / sc.exe delete' -Status 'SKIPPED (excluded path)'
            continue
        }

        $status = 'DRY-RUN'
        if ($Execute) {
            try {
                if ($s.Status -ne 'Stopped') {
                    Stop-Service -Name $s.Name -Force -ErrorAction Stop
                }
                sc.exe delete $s.Name | Out-Null
                $status = 'Removed'
            } catch {
                $status = "ERROR: $($_.Exception.Message)"
            }
        }
        Add-Finding -Category 'Service' -Name $s.Name -Evidence $evidence -Action 'Stop-Service / sc.exe delete' -Status $status
    }
} catch {
    Add-Finding -Category 'Service' -Name 'Get-Service' -Evidence $_.Exception.Message -Action 'Query' -Status 'ERROR'
}

# Remove binaries discovered from process CommandLine
foreach ($path in $binaryCandidates) {
    if (Test-IsExcludedPath $path) {
        Add-Finding -Category 'Binary' -Name $path -Evidence $path -Action 'Remove-Item' -Status 'SKIPPED (excluded path)'
        continue
    }

    if (-not (Test-Path -LiteralPath $path)) {
        Add-Finding -Category 'Binary' -Name $path -Evidence $path -Action 'Remove-Item' -Status 'SKIPPED (not found)'
        continue
    }

    $status = 'DRY-RUN'
    if ($Execute) {
        try {
            Remove-Item -LiteralPath $path -Force -ErrorAction Stop
            $status = 'Removed'
        } catch {
            $status = "ERROR: $($_.Exception.Message)"
        }
    }
    Add-Finding -Category 'Binary' -Name $path -Evidence $path -Action 'Remove-Item' -Status $status
}

# Optional log removal
if ($DeleteLog) {
    if (Test-Path -LiteralPath $logPath) {
        $status = 'DRY-RUN'
        if ($Execute) {
            try {
                Remove-Item -LiteralPath $logPath -Force -ErrorAction Stop
                $status = 'Removed'
            } catch {
                $status = "ERROR: $($_.Exception.Message)"
            }
        }
        Add-Finding -Category 'Log' -Name $logPath -Evidence $logPath -Action 'Remove-Item' -Status $status
    } else {
        Add-Finding -Category 'Log' -Name $logPath -Evidence $logPath -Action 'Remove-Item' -Status 'SKIPPED (not found)'
    }
}

$findings | Sort-Object Category, Name | Format-Table -AutoSize
