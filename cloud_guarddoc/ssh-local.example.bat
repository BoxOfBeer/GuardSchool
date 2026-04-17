@echo off
chcp 65001 >nul
REM Шаблон: скопируйте в ssh-local.bat (в корне репозитория или сюда).
REM   copy cloud_guarddoc\ssh-local.example.bat ssh-local.bat
REM ssh-local.bat в .gitignore — в git не попадёт.
REM В ssh-local.bat при необходимости смените только SSH_TARGET (user@host).
REM Пароль в файл не записывайте; удобнее настроить SSH-ключ на сервере.
REM
set "SSH_TARGET=root@195.208.2.62"
ssh "%SSH_TARGET%"
exit /b %ERRORLEVEL%
