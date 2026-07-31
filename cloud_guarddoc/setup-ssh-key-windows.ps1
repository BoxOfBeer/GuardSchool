#Requires -Version 5.1
<#
.SYNOPSIS
    Creates ed25519 SSH key and appends public key to server's ~/.ssh/authorized_keys.

.DESCRIPTION
    Run from repo root:
      powershell -ExecutionPolicy Bypass -File .\cloud_guarddoc\setup-ssh-key-windows.ps1
      powershell -ExecutionPolicy Bypass -File .\cloud_guarddoc\setup-ssh-key-windows.ps1 -UserHost "root@195.208.2.62"

    Prompts SSH password once. Then: ssh -i %USERPROFILE%\.ssh\id_ed25519_guarddoc root@...

.PARAMETER UserHost
    user@host (default: root@195.208.2.62).

.PARAMETER KeyPath
    Private key path without .pub (default: %USERPROFILE%\.ssh\id_ed25519_guarddoc).

.PARAMETER SkipInstall
    Only create key and print .pub; do not run ssh.
#>
param(
    [string] $UserHost = "root@195.208.2.62",
    [string] $KeyPath = $(Join-Path $env:USERPROFILE ".ssh\id_ed25519_guarddoc"),
    [switch] $SkipInstall
)

$ErrorActionPreference = "Stop"
$sshDir = Split-Path -Parent $KeyPath
if (-not (Test-Path $sshDir)) {
    New-Item -ItemType Directory -Path $sshDir -Force | Out-Null
}

if (-not (Test-Path $KeyPath)) {
    Write-Host "Creating key: $KeyPath (empty passphrase). To use a passphrase, delete the key and run ssh-keygen manually." -ForegroundColor Cyan
    & ssh-keygen -t ed25519 -f $KeyPath -q -N '""' -C "guarddoc-$($env:COMPUTERNAME)"
    Write-Host "Key created." -ForegroundColor Green
} else {
    Write-Host "Key already exists: $KeyPath" -ForegroundColor Yellow
}

$pubPath = "$KeyPath.pub"
if (-not (Test-Path $pubPath)) {
    throw "Public key file not found: $pubPath"
}

Write-Host "`nPublic key (one line):`n" -ForegroundColor Cyan
Get-Content $pubPath -Raw
Write-Host ""

if ($SkipInstall) {
    Write-Host "-SkipInstall: append the line above to ~/.ssh/authorized_keys on the server manually." -ForegroundColor Yellow
    exit 0
}

Write-Host "Running ssh $UserHost -- enter the account password ONCE to append the key to authorized_keys.`n" -ForegroundColor Cyan
$remoteCmd = "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
Get-Content $pubPath -Raw | & ssh $UserHost $remoteCmd

if ($LASTEXITCODE -ne 0) {
    throw "ssh exited with code $LASTEXITCODE"
}

Write-Host "`nDone. Test key login:" -ForegroundColor Green
Write-Host "  ssh -i `"$KeyPath`" $UserHost" -ForegroundColor White

$configPath = Join-Path $sshDir "config"
$hostAlias = "guarddoc"
$configBlock = @"

Host $hostAlias
    HostName $($UserHost.Split('@')[1])
    User $($UserHost.Split('@')[0])
    IdentityFile $KeyPath
"@
Write-Host "`nAdd to $configPath (create file if needed):`n$configBlock`n" -ForegroundColor DarkGray
Write-Host "Then run: ssh $hostAlias" -ForegroundColor DarkGray
