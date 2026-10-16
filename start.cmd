@echo off
rem Personal English Tutor: double-click to start the app. Keep the window open while you practise; close it to stop.
setlocal
cd /d "%~dp0"
title Personal English Tutor

where uv >nul 2>nul || set "PATH=%USERPROFILE%\.local\bin;%PATH%"
where uv >nul 2>nul || (
  echo Personal English Tutor needs uv. Install it from https://docs.astral.sh/uv/ and try again.
  pause
  exit /b 1
)

if not exist "web\dist\index.html" (
  echo Building the app for the first time...
  where pnpm >nul 2>nul || (
    echo Building needs pnpm ^(Node.js^). Install it, or build on another machine.
    pause
    exit /b 1
  )
  call pnpm -C web install || (pause & exit /b 1)
  call pnpm -C web build || (pause & exit /b 1)
)

uv run --frozen tutor serve --app-window %*
if errorlevel 1 pause
