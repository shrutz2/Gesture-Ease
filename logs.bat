@echo off
title Gesture-Ease Logs
color 0B

echo ========================================
echo    GESTURE-EASE LOGS
echo ========================================
echo.

echo Choose option:
echo 1. View all logs
echo 2. View backend logs only
echo 3. View frontend logs only
echo 4. Follow live logs
echo.

set /p choice="Enter choice (1-4): "

if "%choice%"=="1" (
    docker-compose logs
) else if "%choice%"=="2" (
    docker-compose logs backend
) else if "%choice%"=="3" (
    docker-compose logs frontend
) else if "%choice%"=="4" (
    echo Press Ctrl+C to stop following logs...
    docker-compose logs -f
) else (
    echo Invalid choice!
)

echo.
pause