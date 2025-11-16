@echo off
echo Testing Docker build locally before AWS deployment...
echo.

echo Building and starting containers...
docker-compose -f docker-compose-production.yml up --build -d

echo.
echo Waiting for services to start...
timeout /t 30

echo.
echo Testing backend health...
curl -f http://localhost:5000/health

echo.
echo Testing frontend...
curl -f http://localhost:3000

echo.
echo Services are running:
echo - Backend: http://localhost:5000
echo - Frontend: http://localhost:3000
echo.
echo Press any key to stop containers...
pause

echo Stopping containers...
docker-compose -f docker-compose-production.yml down

echo Done!