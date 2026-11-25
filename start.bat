@echo off
setlocal EnableExtensions EnableDelayedExpansion
title TablePulse One-Click Launcher

cd /d "%~dp0"

echo ============================================================
echo   TablePulse - One-Click Docker Demo Launcher
echo ============================================================
echo.

if not exist ".env" (
    if exist ".env.example" (
        echo [1/4] Creating .env from .env.example...
        copy /Y ".env.example" ".env" >nul
    )
)

echo [2/4] Checking Docker Engine...
docker info >nul 2>&1
if errorlevel 1 (
    if exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" (
        echo Starting Docker Desktop...
        start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    ) else if exist "%LOCALAPPDATA%\Programs\DockerDesktop\Docker Desktop.exe" (
        start "" "%LOCALAPPDATA%\Programs\DockerDesktop\Docker Desktop.exe"
    )
    echo Waiting for Docker Engine to become ready...
    set /a DOCKER_WAIT=0
    :wait_docker
    timeout /t 3 /nobreak >nul
    docker info >nul 2>&1
    if not errorlevel 1 goto docker_ready
    set /a DOCKER_WAIT+=1
    if !DOCKER_WAIT! GEQ 30 (
        echo [ERROR] Docker Engine did not start in time. Start Docker Desktop and re-run start.bat.
        if not "%~1"=="--no-pause" pause
        exit /b 1
    )
    goto wait_docker
)
:docker_ready
echo Docker Engine is running.
echo.

echo [3/4] Starting TablePulse services (db, valkey, mediamtx, api, cv-worker, web, caddy, demo-seed)...
docker compose version >nul 2>&1
if not errorlevel 1 (
    docker compose --profile demo up -d --build
) else (
    docker-compose --profile demo up -d --build
)
if errorlevel 1 (
    echo [ERROR] Failed to start TablePulse containers.
    if not "%~1"=="--no-pause" pause
    exit /b 1
)

echo [4/4] Waiting for API (http://localhost:8000) and Web UI (http://localhost:3000)...
set /a WAIT_TRIES=0
:wait_http
powershell -NoProfile -Command "try { $a = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 'http://127.0.0.1:8000/api/v1/health'; $w = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 'http://127.0.0.1:3000/login'; if ($a.StatusCode -eq 200 -and $w.StatusCode -lt 400) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 goto ready
set /a WAIT_TRIES+=1
if !WAIT_TRIES! GEQ 45 (
    echo [ERROR] Timed out waiting for API/Web health checks.
    if not "%~1"=="--no-pause" pause
    exit /b 1
)
timeout /t 2 /nobreak >nul
goto wait_http

:ready
echo.
echo ============================================================
echo   TablePulse is LIVE!
echo   Web UI:      http://localhost:3000
echo   API Docs:    http://localhost:8000/docs
echo   Caddy Proxy: http://localhost:8080
echo   Stop stack:  docker-compose --profile demo down
echo ============================================================
echo.

if not "%~1"=="--no-pause" (
    start "" "http://localhost:3000"
    pause
)
exit /b 0
