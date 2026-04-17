@echo off
chcp 65001 >nul
REM Шаблон: скопируйте в ssh-local.bat (в корне репозитория).
REM   copy cloud_guarddoc\ssh-local.example.bat ssh-local.bat
REM ssh-local.bat в .gitignore.
REM
REM Сначала один раз выполните (PowerShell):
REM   powershell -ExecutionPolicy Bypass -File cloud_guarddoc\setup-ssh-key-windows.ps1
REM
set "SSH_TARGET=root@195.208.2.62"
set "SSH_KEY=%USERPROFILE%\.ssh\id_ed25519_guarddoc"
if exist "%SSH_KEY%" (
  ssh -i "%SSH_KEY%" "%SSH_TARGET%"
) else (
  ssh "%SSH_TARGET%"
)
exit /b %ERRORLEVEL%
