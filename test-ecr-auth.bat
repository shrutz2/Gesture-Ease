@echo off
echo Testing ECR Authentication...
echo.

REM Set your AWS credentials (replace with your actual values)
set AWS_ACCESS_KEY_ID=AKIA3UQER2FAJK64AJ71
set AWS_SECRET_ACCESS_KEY=mcVkjA12baH1Zy7B34REIAmlqtiq8INR74EMtqkp
set AWS_DEFAULT_REGION=us-east-1
set AWS_ACCOUNT_ID=000000000000

echo Step 1: Testing AWS CLI access...
aws sts get-caller-identity

echo.
echo Step 2: Getting ECR login token...
aws ecr get-login-password --region %AWS_DEFAULT_REGION% > ecr_token.txt

echo.
echo Step 3: Logging into ECR...
type ecr_token.txt | docker login --username AWS --password-stdin %AWS_ACCOUNT_ID%.dkr.ecr.%AWS_DEFAULT_REGION%.amazonaws.com

echo.
echo Step 4: Testing ECR repositories...
aws ecr describe-repositories --region %AWS_DEFAULT_REGION%

echo.
echo Step 5: Building and pushing backend image...
cd backend
docker build -t %AWS_ACCOUNT_ID%.dkr.ecr.%AWS_DEFAULT_REGION%.amazonaws.com/gesture-ease-prod-backend:test .
docker push %AWS_ACCOUNT_ID%.dkr.ecr.%AWS_DEFAULT_REGION%.amazonaws.com/gesture-ease-prod-backend:test

echo.
echo Done! If this worked, your ECR setup is correct.
pause