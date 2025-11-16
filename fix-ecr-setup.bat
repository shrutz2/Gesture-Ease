@echo off
echo Fixing ECR Setup...
echo.

REM Set AWS credentials
set AWS_ACCESS_KEY_ID=AKIA3UQER2FAJK64AJ71
set AWS_SECRET_ACCESS_KEY=mcVkjA12baH1Zy7B34REIAmlqtiq8INR74EMtqkp
set AWS_DEFAULT_REGION=us-east-1
set AWS_ACCOUNT_ID=799947215168

echo Step 1: Creating ECR repositories if they don't exist...

echo Creating backend repository...
aws ecr create-repository --repository-name gesture-ease-prod-backend --region %AWS_DEFAULT_REGION% 2>nul || echo "Backend repository already exists"

echo Creating frontend repository...
aws ecr create-repository --repository-name gesture-ease-prod-frontend --region %AWS_DEFAULT_REGION% 2>nul || echo "Frontend repository already exists"

echo.
echo Step 2: Listing all repositories...
aws ecr describe-repositories --region %AWS_DEFAULT_REGION%

echo.
echo Step 3: Testing Docker login...
aws ecr get-login-password --region %AWS_DEFAULT_REGION% | docker login --username AWS --password-stdin %AWS_ACCOUNT_ID%.dkr.ecr.%AWS_DEFAULT_REGION%.amazonaws.com

echo.
echo ECR setup complete!
echo.
echo Your repositories:
echo - Backend: %AWS_ACCOUNT_ID%.dkr.ecr.%AWS_DEFAULT_REGION%.amazonaws.com/gesture-ease-prod-backend
echo - Frontend: %AWS_ACCOUNT_ID%.dkr.ecr.%AWS_DEFAULT_REGION%.amazonaws.com/gesture-ease-prod-frontend
echo.
pause