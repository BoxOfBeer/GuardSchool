@echo off
setlocal

if not exist ".venv\Scripts\python.exe" (
  echo Сначала создайте виртуальное окружение .venv
  exit /b 1
)

if exist "full" rmdir /s /q "full"

".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean ^
  --distpath full ^
  --workpath build_full ^
  GuardSchool_full.spec

if errorlevel 1 (
  echo.
  echo Ошибка: сборка через PyInstaller завершилась неуспешно.
  exit /b 1
)

xcopy /E /I /Y "data" "full\GuardSchool\data" >nul

if exist "ico.png" (
  copy /Y "ico.png" "full\GuardSchool\ico.png" >nul
  echo Скопирован ico.png рядом с GuardSchool.exe
) else (
  echo Внимание: нет ico.png в корне проекта — лого в админке будет 404, пока не положите файл.
)

echo.
echo Готово. Запуск: full\GuardSchool\GuardSchool.exe ^(рядом — папка _internal с зависимостями^)
echo Рабочие данные: full\GuardSchool\data
