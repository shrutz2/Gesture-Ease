@echo off
title Gesture-Ease Local Run
color 0A

echo ========================================
echo    RUNNING WITHOUT DOCKER
echo ========================================

echo Starting Backend...
start "Backend" cmd /k "cd backend && python app.py"

timeout /t 3

echo Starting Frontend...
start "Frontend" cmd /k "cd frontend && npm start"

echo.
echo Backend: http://localhost:5000
echo Frontend: http://localhost:3000
echo.
echo Both services started in separate windows!
pause