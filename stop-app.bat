@echo off
title Stop Gesture-Ease
color 0C

echo ========================================
echo    STOPPING GESTURE-EASE
echo ========================================
echo.

echo Stopping containers...
docker-compose down --volumes

echo Cleaning up...
docker system prune -f

echo.
echo Application stopped successfully!
echo.
pause