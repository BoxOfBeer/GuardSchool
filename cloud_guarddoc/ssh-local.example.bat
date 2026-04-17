@echo off
chcp 65001 >nul
REM Скопируйте этот файл в ssh-local.bat (в корне репо или сюда) — ssh-local.bat в .gitignore, в git не попадёт.
REM Подставьте пользователя и хост. Пароль лучше не хранить в файле: используйте SSH-ключ (ssh-keygen + authorized_keys на сервере).
REM
REM   copy cloud_guarddoc\ssh-local.example.bat ssh-local.bat
REM   notepad ssh-local.bat
REM
set "SSH_TARGET=root@195.208.2.62"
ssh "%SSH_TARGET%"
exit /b %ERRORLEVEL%
