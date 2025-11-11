@echo off
echo Starting Gesture-Ease Application...

echo Cleaning up previous containers...
docker-compose down --volumes --remove-orphans

echo Building fresh images...
docker-compose build --no-cache

echo Starting services...
docker-compose up -d

echo Waiting for services to start...
timeout /t 10

echo Checking service status...
docker-compose ps

echo.
echo Application URLs:
echo Backend: http://localhost:5000
echo Frontend: http://localhost:3000
echo.

echo To view logs, run:
echo docker-compose logs -f

pause