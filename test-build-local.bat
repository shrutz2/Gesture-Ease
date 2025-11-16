@echo off
echo Testing Local Docker Build and Push...
echo.

REM Set AWS credentials
set AWS_ACCESS_KEY_ID=AKIA3UQER2FAJK64AJ71
set AWS_SECRET_ACCESS_KEY=mcVkjA12baH1Zy7B34REIAmlqtiq8INR74EMtqkp
set AWS_DEFAULT_REGION=us-east-1
set AWS_ACCOUNT_ID=000000000000

echo Step 1: Login to ECR...
aws ecr get-login-password --region %AWS_DEFAULT_REGION% | docker login --username AWS --password-stdin %AWS_ACCOUNT_ID%.dkr.ecr.%AWS_DEFAULT_REGION%.amazonaws.com

if %ERRORLEVEL% NEQ 0 (
    echo ECR login failed! Check your AWS credentials.
    pause
    exit /b 1
)

echo.
echo Step 2: Building backend image...
cd backend
docker build -t %AWS_ACCOUNT_ID%.dkr.ecr.%AWS_DEFAULT_REGION%.amazonaws.com/gesture-ease-prod-backend:test .

if %ERRORLEVEL% NEQ 0 (
    echo Backend build failed!
    pause
    exit /b 1
)

echo.
echo Step 3: Pushing backend image...
docker push %AWS_ACCOUNT_ID%.dkr.ecr.%AWS_DEFAULT_REGION%.amazonaws.com/gesture-ease-prod-backend:test

if %ERRORLEVEL% NEQ 0 (
    echo Backend push failed!
    pause
    exit /b 1
)

echo.
echo Step 4: Building frontend image...
cd ..\frontend
docker build -t %AWS_ACCOUNT_ID%.dkr.ecr.%AWS_DEFAULT_REGION%.amazonaws.com/gesture-ease-prod-frontend:test .

if %ERRORLEVEL% NEQ 0 (
    echo Frontend build failed!
    pause
    exit /b 1
)

echo.
echo Step 5: Pushing frontend image...
docker push %AWS_ACCOUNT_ID%.dkr.ecr.%AWS_DEFAULT_REGION%.amazonaws.com/gesture-ease-prod-frontend:test

if %ERRORLEVEL% NEQ 0 (
    echo Frontend push failed!
    pause
    exit /b 1
)

echo.
echo SUCCESS! Both images built and pushed successfully.
echo.
echo Images pushed:
echo - Backend: %AWS_ACCOUNT_ID%.dkr.ecr.%AWS_DEFAULT_REGION%.amazonaws.com/gesture-ease-prod-backend:test
echo - Frontend: %AWS_ACCOUNT_ID%.dkr.ecr.%AWS_DEFAULT_REGION%.amazonaws.com/gesture-ease-prod-frontend:test
echo.
echo Now your GitHub Actions should work!
pause