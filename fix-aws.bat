@echo off
echo Configuring AWS credentials...
echo.
echo You need to set up AWS credentials first:
echo 1. Get AWS Access Key ID and Secret from AWS Console
echo 2. Run: aws configure
echo 3. Enter your credentials when prompted
echo.
aws configure
echo.
echo Testing AWS connection...
aws sts get-caller-identity
echo.
echo If successful, run deploy-to-aws.bat again
pause