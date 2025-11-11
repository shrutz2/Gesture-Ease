@echo off
title Gesture-Ease Docker Setup
color 0A

echo ========================================
echo    GESTURE-EASE DOCKER SETUP
echo ========================================
echo.

echo [1/5] Cleaning up old containers...
docker-compose down --volumes --remove-orphans 2>nul

echo [2/5] Building backend image...
docker build -t gesture-ease-backend ./backend
if %errorlevel% neq 0 (
    echo ERROR: Backend build failed!
    pause
    exit /b 1
)

echo [3/5] Building frontend image...
docker build -t gesture-ease-frontend ./frontend
if %errorlevel% neq 0 (
    echo ERROR: Frontend build failed!
    pause
    exit /b 1
)

echo [4/5] Starting containers...
docker-compose up -d
if %errorlevel% neq 0 (
    echo ERROR: Container startup failed!
    pause
    exit /b 1
)

echo [5/5] Checking status...
timeout /t 5 >nul
docker-compose ps

echo.
echo ========================================
echo    APPLICATION READY!
echo ========================================
echo Backend:  http://localhost:5000
echo Frontend: http://localhost:3000
echo Health:   http://localhost:5000/api/status
echo.
echo To view logs: docker-compose logs -f
echo To stop: docker-compose down
echo.

pause