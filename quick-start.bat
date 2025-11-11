@echo off
echo Stopping any running containers...
docker-compose down 2>nul

echo Building with simplified setup...
docker-compose -f docker-compose-simple.yml up --build

pause