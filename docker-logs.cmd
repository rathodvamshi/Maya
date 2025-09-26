@echo off
REM Tail logs from all compose services
cd /d %~dp0
docker compose logs -f
