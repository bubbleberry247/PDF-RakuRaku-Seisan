<#
.SYNOPSIS
    Wi-Fi優先時のネットワーク切り替えスクリプト（失敗時自動ロールバック）

.DESCRIPTION
    - 有線(LAN)を無効化
    - Wi-Fiを有効化
    - Wi-FiのDNSを静的に更新（任意）
    - 接続確認
    - いずれかで失敗した場合は開始時状態へロールバック
#>

param(
    [ValidateSet("Wifi", "Ethernet", "Status")]
    [string]$Mode = "Wifi",

    [string[]]$DnsServers = @("1.1.1.1", "8.8.8.8"),

    [string]$EthernetAlias = "",
    [string]$WifiAlias = "",

    [string[]]$VerifyTargets = @("8.8.8.8", "docs.google.com", "script.google.com"),
    [int]$PingCount = 4,
    [int]$RetryCount = 1,
    [int]$RetryIntervalSec = 2,

    [string]$LogPath = "$PSScriptRoot\\NetworkSwitchSafe.log"
)

$ErrorActionPreference = "Stop"

function Write-Log {
    param([string]$Message)
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $LogPath -Value "[$ts] $Message" -ErrorAction SilentlyContinue
}

function Ensure-Admin {
    $user = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $user.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "管理者権限で実行してください。PowerShellを「管理者として実行」してください。"
    }
}

function Get-AdapterByRole {
    param(
        [ValidateSet("Ethernet", "WiFi")][string]$Role,
        [string]$AliasHint
    )

    $ifType = @{ Ethernet = 6; WiFi = 71 }[$Role]
    $adapters = Get-NetAdapter -Physical -ErrorAction Stop

    if ($AliasHint) {
        $exact = $adapters | Where-Object { $_.InterfaceAlias -eq $AliasHint -or $_.Name -eq $AliasHint }
        if ($exact) { return ($exact | Select-Object -First 1) }

        $like = $adapters | Where-Object { $_.InterfaceAlias -like "*$AliasHint*" -or $_.Name -like "*$AliasHint*" }
        if ($like) { return ($like | Select-Object -First 1) }
    }

    $typed = $adapters | Where-Object { $_.InterfaceType -eq $ifType }
    if (-not $typed) {
        throw "$Role の物理アダプタが見つかりません。必要なら -EthernetAlias / -WifiAlias を指定してください。"
    }

    $up = $typed | Where-Object { $_.Status -eq "Up" }
    if ($up) { return ($up | Select-Object -First 1) }

    return ($typed | Select-Object -First 1)
}

function Get-NetworkState {
    param([Microsoft.Management.Infrastructure.CimInstance]$Adapter)

    $dnsEntry = Get-DnsClientServerAddress -InterfaceAlias $Adapter.InterfaceAlias -AddressFamily IPv4 -ErrorAction SilentlyContinue
    $dnsServers = @()
    if ($dnsEntry -and $dnsEntry.ServerAddresses) {
        $dnsServers = @($dnsEntry.ServerAddresses | Where-Object { $_ })
    }

    return [PSCustomObject]@{
        InterfaceAlias  = $Adapter.InterfaceAlias
        Name           = $Adapter.Name
        Status         = $Adapter.Status
        LinkSpeed      = $Adapter.LinkSpeed
        Enabled        = ($Adapter.Status -eq "Up")
        DnsServers     = $dnsServers
        InterfaceIndex  = $Adapter.ifIndex
    }
}

function Set-AdapterState {
    param(
        [string]$InterfaceAlias,
        [ValidateSet("Up", "Down")][string]$TargetState
    )

    if ($TargetState -eq "Down") {
        Write-Log "Disable-NetAdapter $InterfaceAlias"
        Disable-NetAdapter -InterfaceAlias $InterfaceAlias -Confirm:$false -ErrorAction Stop
    } else {
        Write-Log "Enable-NetAdapter $InterfaceAlias"
        Enable-NetAdapter -InterfaceAlias $InterfaceAlias -Confirm:$false -ErrorAction Stop
    }
}

function Set-Dns {
    param(
        [string]$InterfaceAlias,
        [string[]]$Servers,
        [bool]$UseDhcp
    )

    if ($UseDhcp) {
        Write-Log "Set DNS to DHCP for $InterfaceAlias"
        Set-DnsClientServerAddress -InterfaceAlias $InterfaceAlias -ResetServerAddresses -ErrorAction Stop
    } else {
        Write-Log "Set DNS $($Servers -join ',') for $InterfaceAlias"
        Set-DnsClientServerAddress -InterfaceAlias $InterfaceAlias -ServerAddresses $Servers -ErrorAction Stop
    }
}

function Restore-OriginalState {
    param([hashtable]$OriginalState)

    foreach ($item in $OriginalState.Keys) {
        $s = $OriginalState[$item]
        if (-not $s) { continue }

        $adapter = Get-NetAdapter -InterfaceAlias $s.InterfaceAlias -ErrorAction SilentlyContinue
        if (-not $adapter) { continue }

        if ($s.Status -eq "Up") {
            Enable-NetAdapter -InterfaceAlias $s.InterfaceAlias -Confirm:$false -ErrorAction SilentlyContinue
        } else {
            Disable-NetAdapter -InterfaceAlias $s.InterfaceAlias -Confirm:$false -ErrorAction SilentlyContinue
        }

        if ($s.DnsServers.Count -gt 0) {
            Set-Dns -InterfaceAlias $s.InterfaceAlias -Servers $s.DnsServers -UseDhcp $false
        } else {
            Set-Dns -InterfaceAlias $s.InterfaceAlias -Servers @() -UseDhcp $true
        }
    }
}

function Get-AveragePingMs {
    param([string]$Target, [int]$Count)
    try {
        $reply = Test-Connection -TargetName $Target -Count $Count -ErrorAction Stop
        if (-not $reply) { return $null }
        return [Math]::Round(($reply | Measure-Object -Property ResponseTime -Average).Average, 2)
    } catch {
        return $null
    }
}

function Check-Target {
    param([string]$Target)

    $ping = Get-AveragePingMs -Target $Target -Count $PingCount
    if ($null -ne $ping) {
        return @{ ok = $true; detail = "$([int]$ping)ms" }
    }

    $uri = if ($Target -match "^https?://") { $Target } else { "https://$Target" }
    try {
        $resp = Invoke-WebRequest -Uri $uri -Method Head -TimeoutSec 8 -UseBasicParsing -ErrorAction Stop
        return @{ ok = $true; detail = "HTTP $($resp.StatusCode)" }
    } catch {
        return @{ ok = $false; detail = $_.Exception.Message }
    }
}

function Test-Connectivity {
    param([string[]]$Targets)

    $allOk = $true
    foreach ($target in $Targets) {
        $okTarget = $false
        $lastDetail = ""
        for ($i = 0; $i -lt [Math]::Max(1, $RetryCount); $i++) {
            $res = Check-Target -Target $target
            $lastDetail = $res.detail
            if ($res.ok) { $okTarget = $true; break }
            if ($i -lt $RetryCount - 1) { Start-Sleep -Seconds $RetryIntervalSec }
        }

        if ($okTarget) {
            Write-Host "[OK] ${target} : $lastDetail"
            Write-Log "Connectivity OK: $target ($lastDetail)"
        } else {
            Write-Host "[NG] ${target} : $lastDetail"
            Write-Log "Connectivity NG: $target ($lastDetail)"
            $allOk = $false
        }
    }
    return $allOk
}

Ensure-Admin

$ethernet = Get-AdapterByRole -Role "Ethernet" -AliasHint $EthernetAlias
$wifi = Get-AdapterByRole -Role "WiFi" -AliasHint $WifiAlias

$beforeState = @{
    Ethernet = Get-NetworkState -Adapter $ethernet
    WiFi     = Get-NetworkState -Adapter $wifi
}

Write-Host "Detected adapters:"
Write-Host "  Ethernet: $($beforeState.Ethernet.InterfaceAlias) [$($beforeState.Ethernet.Status)]"
Write-Host "  Wi-Fi   : $($beforeState.WiFi.InterfaceAlias) [$($beforeState.WiFi.Status)]"
Write-Host "Log: $LogPath"

if ($Mode -eq "Status") {
    Write-Host "`nCurrent status only. No changes applied."
    Write-Host "Ethernet DNS: $($beforeState.Ethernet.DnsServers -join ', ')"
    Write-Host "Wi-Fi DNS  : $($beforeState.WiFi.DnsServers -join ', ')"
    exit 0
}

try {
    if ($Mode -eq "Wifi") {
        Write-Log "Switch to Wi-Fi mode start"
        Set-AdapterState -InterfaceAlias $beforeState.Ethernet.InterfaceAlias -TargetState Down
        Start-Sleep -Seconds 1
        Set-AdapterState -InterfaceAlias $beforeState.WiFi.InterfaceAlias -TargetState Up
        Start-Sleep -Seconds 1

        if ($DnsServers.Count -gt 0) {
            Set-Dns -InterfaceAlias $beforeState.WiFi.InterfaceAlias -Servers $DnsServers -UseDhcp $false
        }

        ipconfig /flushdns | Out-Null
        ipconfig /renew | Out-Null

        if (-not (Test-Connectivity -Targets $VerifyTargets)) {
            throw "接続確認に失敗しました。"
        }

        Write-Host "`n[DONE] Wi-Fi mode switch completed."
        Write-Log "Switch to Wi-Fi mode completed"
    }
    elseif ($Mode -eq "Ethernet") {
        Write-Log "Switch to Ethernet mode start"
        Set-AdapterState -InterfaceAlias $beforeState.WiFi.InterfaceAlias -TargetState Down
        Start-Sleep -Seconds 1
        Set-AdapterState -InterfaceAlias $beforeState.Ethernet.InterfaceAlias -TargetState Up
        Start-Sleep -Seconds 1

        Set-Dns -InterfaceAlias $beforeState.Ethernet.InterfaceAlias -Servers $beforeState.Ethernet.DnsServers -UseDhcp ($beforeState.Ethernet.DnsServers.Count -eq 0)

        if (-not (Test-Connectivity -Targets $VerifyTargets)) {
            throw "接続確認に失敗しました。"
        }

        Write-Host "`n[DONE] Ethernet mode switch completed."
        Write-Log "Switch to Ethernet mode completed"
    }
}
catch {
    Write-Host "`n[ERROR] $($_.Exception.Message)"
    Write-Host "[REVERT] 変更を元に戻しています..."
    Write-Log "Error occurred: $($_.Exception.Message)"
    Restore-OriginalState -OriginalState $beforeState
    Write-Host "[REVERT] 元の状態へ戻しました。"
    throw
}
