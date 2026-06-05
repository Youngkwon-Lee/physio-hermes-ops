[CmdletBinding()]
param(
    [string[]]$Ports = @('8792'),
    [string]$ListenAddress = '0.0.0.0',
    [string]$RuleNamePrefix = 'MissionControl',
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-WslIpv4 {
    $raw = & wsl.exe hostname -I
    if (-not $raw) {
        throw 'Failed to read WSL IP from `wsl.exe hostname -I`.'
    }

    $ip = ($raw -split '\s+' | Where-Object { $_ -match '^\d+\.\d+\.\d+\.\d+$' } | Select-Object -First 1)
    if (-not $ip) {
        throw "Could not find IPv4 address in WSL output: $raw"
    }
    return $ip.Trim()
}

function Ensure-Admin {
    $currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentIdentity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'This script must be run in an elevated Administrator PowerShell session.'
    }
}

function Ensure-FirewallRule {
    param(
        [string]$Name,
        [int]$Port
    )

    $ruleExists = $false
    try {
        $null = netsh advfirewall firewall show rule name="$Name"
        if ($LASTEXITCODE -eq 0) {
            $ruleExists = $true
        }
    }
    catch {
        $ruleExists = $false
    }

    if ($ruleExists) {
        Write-Host "[firewall] exists: $Name"
        return
    }

    $command = 'netsh advfirewall firewall add rule name="' + $Name + '" dir=in action=allow protocol=TCP localport=' + $Port
    if ($DryRun) {
        Write-Host "[dry-run] $command"
        return
    }

    Write-Host "[firewall] add: $Name"
    netsh advfirewall firewall add rule name="$Name" dir=in action=allow protocol=TCP localport=$Port | Out-Null
}

function Reset-PortProxy {
    param(
        [string]$ListenAddress,
        [int]$Port,
        [string]$ConnectAddress
    )

    $deleteCommand = "netsh interface portproxy delete v4tov4 listenaddress=$ListenAddress listenport=$Port"
    $addCommand = "netsh interface portproxy add v4tov4 listenaddress=$ListenAddress listenport=$Port connectaddress=$ConnectAddress connectport=$Port"

    if ($DryRun) {
        Write-Host "[dry-run] $deleteCommand"
        Write-Host "[dry-run] $addCommand"
        return
    }

    Write-Host "[portproxy] reset ${ListenAddress}:${Port} -> ${ConnectAddress}:${Port}"
    netsh interface portproxy delete v4tov4 listenaddress=$ListenAddress listenport=$Port | Out-Null
    netsh interface portproxy add v4tov4 listenaddress=$ListenAddress listenport=$Port connectaddress=$ConnectAddress connectport=$Port | Out-Null
}

function Resolve-Ports {
    param([string[]]$RawPorts)

    $resolved = @()
    foreach ($item in $RawPorts) {
        foreach ($piece in ($item -split ',')) {
            $trimmed = $piece.Trim()
            if (-not $trimmed) {
                continue
            }
            $parsed = 0
            if (-not [int]::TryParse($trimmed, [ref]$parsed)) {
                throw "Invalid port value: $trimmed"
            }
            $resolved += $parsed
        }
    }
    return $resolved
}

if (-not $DryRun) {
    Ensure-Admin
}
$wslIp = Get-WslIpv4
$resolvedPorts = Resolve-Ports -RawPorts $Ports
Write-Host "Detected WSL IPv4: $wslIp"

foreach ($port in $resolvedPorts) {
    Reset-PortProxy -ListenAddress $ListenAddress -Port $port -ConnectAddress $wslIp
    Ensure-FirewallRule -Name "$RuleNamePrefix-$port" -Port $port
}

Write-Host ''
Write-Host 'Current portproxy table:'
netsh interface portproxy show all
