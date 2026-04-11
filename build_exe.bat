@echo off
setlocal

if not exist ".venv\Scripts\python.exe" (
  echo Сначала создайте виртуальное окружение .venv
  exit /b 1
)

set "PYI_EXTRA="
if exist "ico.png" set "PYI_EXTRA=--add-data ico.png;."

".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --console ^
  --name GuardSchool ^
  --add-data "static;static" %PYI_EXTRA% ^
  run_server.py

if exist "ico.png" (
  copy /Y "ico.png" "dist\ico.png" >nul
) else (
  echo Внимание: нет ico.png — скопируйте его в dist рядом с exe для лого в админке.
)

if errorlevel 1 (
  echo.
  echo Ошибка: сборка через PyInstaller завершилась неуспешно.
  exit /b 1
)

echo.
echo Готово. Файл: dist\GuardSchool.exe
