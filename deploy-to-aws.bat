@echo off
echo Deploying Gesture-Ease to AWS...
echo.

echo Step 1: Creating AWS resources...
call setup-aws.bat

echo.
echo Step 2: Testing local Docker build...
call test-local-docker.bat

echo.
echo Step 3: Pushing to GitHub (triggers CI/CD)...
git add .
git status

echo.
set /p commit_msg="Enter commit message: "
git commit -m "%commit_msg%"
git push origin main

echo.
echo Deployment initiated! Check GitHub Actions for progress:
echo https://github.com/YOUR_USERNAME/YOUR_REPO/actions
echo.
echo AWS Resources created:
echo - ECR Repositories: gesture-ease-prod-backend, gesture-ease-prod-frontend  
echo - S3 Bucket: 5gesture-ease-prod-models
echo - ECS Cluster: 5gesture-ease-prod-cluster
echo.
pause