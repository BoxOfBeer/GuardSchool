@echo off
setlocal
cd /d "%~dp0CCode"
echo Building GuardSchool.sln Release -^> ..\CApp\Release\
dotnet build GuardSchool.sln -c Release
set "ERR=%ERRORLEVEL%"
if %ERR% neq 0 (
  echo Build failed with code %ERR%.
  exit /b %ERR%
)
echo OK: CApp\Release\GuardSchool.Wpf.exe ^(GUI^) and GuardSchool.exe ^(консоль^)
exit /b 0
