# PowerShell script to fix 504 Gateway Timeout
# Run: .\scripts\fix-504-deployment.ps1

$ErrorActionPreference = "Stop"

$AWS_REGION = "ap-south-1"
$CLUSTER_NAME = "gesture-ease-cluster"
$BACKEND_SERVICE = "gesture-ease-backend"
$FRONTEND_SERVICE = "gesture-ease-frontend"

Write-Host "🔧 Fixing 504 Gateway Timeout..." -ForegroundColor Cyan

# Get AWS account ID
$AWS_ACCOUNT_ID = (aws sts get-caller-identity --query Account --output text).Trim()
$ECR_BACKEND_URI = "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/gesture-ease-backend"
$ECR_FRONTEND_URI = "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/gesture-ease-frontend"

Write-Host "`n📦 Step 1: Building backend image with curl..." -ForegroundColor Yellow
Set-Location backend
docker build -f Dockerfile.production -t gesture-ease-backend:latest .
docker tag gesture-ease-backend:latest "${ECR_BACKEND_URI}:latest"

Write-Host "📤 Step 2: Pushing backend image to ECR..." -ForegroundColor Yellow
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_BACKEND_URI
docker push "${ECR_BACKEND_URI}:latest"

Write-Host "📦 Step 3: Building frontend image..." -ForegroundColor Yellow
Set-Location ../frontend
docker build -f Dockerfile.production -t gesture-ease-frontend:latest .
docker tag gesture-ease-frontend:latest "${ECR_FRONTEND_URI}:latest"

Write-Host "📤 Step 4: Pushing frontend image to ECR..." -ForegroundColor Yellow
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_FRONTEND_URI
docker push "${ECR_FRONTEND_URI}:latest"

Write-Host "🔄 Step 5: Updating infrastructure (health checks)..." -ForegroundColor Yellow
Set-Location ../infrastructure
terraform apply -auto-approve

Write-Host "🚀 Step 6: Forcing ECS service updates..." -ForegroundColor Yellow
aws ecs update-service `
  --cluster $CLUSTER_NAME `
  --service $BACKEND_SERVICE `
  --force-new-deployment `
  --region $AWS_REGION

aws ecs update-service `
  --cluster $CLUSTER_NAME `
  --service $FRONTEND_SERVICE `
  --force-new-deployment `
  --region $AWS_REGION

Write-Host "⏳ Step 7: Waiting for services to stabilize..." -ForegroundColor Yellow
Start-Sleep -Seconds 30
aws ecs wait services-stable `
  --cluster $CLUSTER_NAME `
  --services $BACKEND_SERVICE $FRONTEND_SERVICE `
  --region $AWS_REGION

Write-Host "`n✅ Deployment complete! Services should be healthy now." -ForegroundColor Green
Write-Host "🌐 Test your ALB URL: http://gesture-ease-alb-2098950132.ap-south-1.elb.amazonaws.com/" -ForegroundColor Cyan
Write-Host "⏰ Wait 2-3 minutes for health checks to pass" -ForegroundColor Yellow

Set-Location ..

