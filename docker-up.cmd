@echo off
REM Start all services in detached mode and build images as needed
cd /d %~dp0
docker compose up -d --build
IF %ERRORLEVEL% NEQ 0 (
  echo Failed to start Docker services.
  exit /b 1
)
echo Services started. Open http://localhost:3000 (frontend) and http://localhost:8000 (backend)
exit /b 0
