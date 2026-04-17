#Requires -Version 5.1
<#
.SYNOPSIS
    Создаёт SSH-ключ (ed25519) для GuardDoc и добавляет публичную часть на сервер в ~/.ssh/authorized_keys.

.DESCRIPTION
    Запуск из PowerShell в корне репозитория (или с любого пути):
      powershell -ExecutionPolicy Bypass -File .\cloud_guarddoc\setup-ssh-key-windows.ps1
      powershell -ExecutionPolicy Bypass -File .\cloud_guarddoc\setup-ssh-key-windows.ps1 -UserHost "root@195.208.2.62"

    Один раз запросит пароль SSH при добавлении ключа. После этого: ssh -i ~/.ssh/id_ed25519_guarddoc root@...

.PARAMETER UserHost
    user@host (по умолчанию root@195.208.2.62).

.PARAMETER KeyPath
    Путь к приватному ключу без .pub (по умолчанию %USERPROFILE%\.ssh\id_ed25519_guarddoc).

.PARAMETER SkipInstall
    Только создать ключ и показать .pub, не вызывать ssh на сервер.
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
    Write-Host "Создаю ключ: $KeyPath (без passphrase — для удобства; при желании удалите ключ и выполните: ssh-keygen -t ed25519 -f `"$KeyPath`")" -ForegroundColor Cyan
    # Пустой passphrase — удобно для агента/скриптов; для максимальной безопасности создайте ключ вручную с -N и фразой.
    & ssh-keygen -t ed25519 -f $KeyPath -q -N '""' -C "guarddoc-$($env:COMPUTERNAME)"
    Write-Host "Ключ создан." -ForegroundColor Green
} else {
    Write-Host "Ключ уже есть: $KeyPath" -ForegroundColor Yellow
}

$pubPath = "$KeyPath.pub"
if (-not (Test-Path $pubPath)) {
    throw "Не найден файл $pubPath"
}

Write-Host "`nПубличный ключ (одна строка):`n" -ForegroundColor Cyan
Get-Content $pubPath -Raw
Write-Host ""

if ($SkipInstall) {
    Write-Host "Пропуск установки на сервер (-SkipInstall). Добавьте строку выше вручную в ~/.ssh/authorized_keys на сервере." -ForegroundColor Yellow
    exit 0
}

Write-Host "Сейчас будет ssh $UserHost — введите пароль пользователя ОДИН раз для добавления ключа в authorized_keys.`n" -ForegroundColor Cyan
$remoteCmd = "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
Get-Content $pubPath -Raw | & ssh $UserHost $remoteCmd

if ($LASTEXITCODE -ne 0) {
    throw "ssh завершился с кодом $LASTEXITCODE"
}

Write-Host "`nГотово. Проверка входа по ключу:" -ForegroundColor Green
Write-Host "  ssh -i `"$KeyPath`" $UserHost" -ForegroundColor White

$configPath = Join-Path $sshDir "config"
$hostAlias = "guarddoc"
$configBlock = @"

Host $hostAlias
    HostName $($UserHost.Split('@')[1])
    User $($UserHost.Split('@')[0])
    IdentityFile $KeyPath
"@
Write-Host "`nДобавьте в $configPath (создайте файл при необходимости):`n$configBlock`n" -ForegroundColor DarkGray
Write-Host "После этого: ssh $hostAlias" -ForegroundColor DarkGray
