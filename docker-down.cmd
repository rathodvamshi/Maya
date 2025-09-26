@echo off
REM Stop and remove all services and networks
cd /d %~dp0
docker compose down
exit /b 0
