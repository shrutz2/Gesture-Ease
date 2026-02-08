# Quick deployment health check script
# Run this to monitor your deployment status

$ALB_URL = "http://gesture-ease-alb-2098950132.ap-south-1.elb.amazonaws.com"
$AWS_REGION = "ap-south-1"
$CLUSTER_NAME = "gesture-ease-cluster"

Write-Host "🏥 Gesture-Ease Deployment Health Check" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan

Write-Host "`n📋 Checking ECS Services..." -ForegroundColor Yellow

# Check ECS service status
$backendStatus = aws ecs describe-services `
    --cluster $CLUSTER_NAME `
    --services gesture-ease-backend `
    --region $AWS_REGION `
    --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount,Deployment:deployments[0].status}' `
    --output table

$frontendStatus = aws ecs describe-services `
    --cluster $CLUSTER_NAME `
    --services gesture-ease-frontend `
    --region $AWS_REGION `
    --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount,Deployment:deployments[0].status}' `
    --output table

Write-Host "Backend Service:" -ForegroundColor Green
Write-Host $backendStatus

Write-Host "`nFrontend Service:" -ForegroundColor Green  
Write-Host $frontendStatus

Write-Host "`n📋 Checking Target Group Health..." -ForegroundColor Yellow

# Get target group ARNs
$backendTgArn = aws elbv2 describe-target-groups `
    --names gesture-ease-backend-tg `
    --region $AWS_REGION `
    --query 'TargetGroups[0].TargetGroupArn' `
    --output text

$frontendTgArn = aws elbv2 describe-target-groups `
    --names gesture-ease-frontend-tg `
    --region $AWS_REGION `
    --query 'TargetGroups[0].TargetGroupArn' `
    --output text

if ($backendTgArn -and $backendTgArn -ne "None") {
    $backendHealth = aws elbv2 describe-target-health `
        --target-group-arn $backendTgArn `
        --region $AWS_REGION `
        --query 'TargetHealthDescriptions[*].{Target:Target.Id,Health:TargetHealth.State,Reason:TargetHealth.Reason}' `
        --output table
    
    Write-Host "Backend Target Health:" -ForegroundColor Green
    Write-Host $backendHealth
}

if ($frontendTgArn -and $frontendTgArn -ne "None") {
    $frontendHealth = aws elbv2 describe-target-health `
        --target-group-arn $frontendTgArn `
        --region $AWS_REGION `
        --query 'TargetHealthDescriptions[*].{Target:Target.Id,Health:TargetHealth.State,Reason:TargetHealth.Reason}' `
        --output table
    
    Write-Host "`nFrontend Target Health:" -ForegroundColor Green
    Write-Host $frontendHealth
}

Write-Host "`n📋 Testing Endpoints..." -ForegroundColor Yellow

# Test health endpoint
Write-Host "Testing /health endpoint..." -ForegroundColor Cyan
try {
    $healthResponse = Invoke-WebRequest -Uri "$ALB_URL/health" -TimeoutSec 30
    Write-Host "✅ Health endpoint: $($healthResponse.StatusCode)" -ForegroundColor Green
    Write-Host "Response: $($healthResponse.Content)" -ForegroundColor Gray
} catch {
    Write-Host "❌ Health endpoint failed: $($_.Exception.Message)" -ForegroundColor Red
}

# Test API status
Write-Host "`nTesting /api/status endpoint..." -ForegroundColor Cyan
try {
    $statusResponse = Invoke-WebRequest -Uri "$ALB_URL/api/status" -TimeoutSec 30
    Write-Host "✅ API status: $($statusResponse.StatusCode)" -ForegroundColor Green
    $statusJson = $statusResponse.Content | ConvertFrom-Json
    Write-Host "Model loaded: $($statusJson.model_loaded)" -ForegroundColor Gray
    Write-Host "Total classes: $($statusJson.total_classes)" -ForegroundColor Gray
} catch {
    Write-Host "❌ API status failed: $($_.Exception.Message)" -ForegroundColor Red
}

# Test frontend
Write-Host "`nTesting frontend..." -ForegroundColor Cyan
try {
    $frontendResponse = Invoke-WebRequest -Uri "$ALB_URL/" -TimeoutSec 30
    Write-Host "✅ Frontend: $($frontendResponse.StatusCode)" -ForegroundColor Green
} catch {
    Write-Host "❌ Frontend failed: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n📋 Recent Logs (last 10 minutes)..." -ForegroundColor Yellow

# Show recent backend logs
Write-Host "Backend logs:" -ForegroundColor Green
aws logs tail /ecs/gesture-ease-backend --since 10m --region $AWS_REGION | Select-Object -Last 10

Write-Host "`n🔗 Useful Commands:" -ForegroundColor Cyan
Write-Host "View backend logs: aws logs tail /ecs/gesture-ease-backend --follow --region $AWS_REGION" -ForegroundColor Gray
Write-Host "View frontend logs: aws logs tail /ecs/gesture-ease-frontend --follow --region $AWS_REGION" -ForegroundColor Gray
Write-Host "Force restart backend: aws ecs update-service --cluster $CLUSTER_NAME --service gesture-ease-backend --force-new-deployment --region $AWS_REGION" -ForegroundColor Gray

Write-Host "`n🌐 Application URLs:" -ForegroundColor Cyan
Write-Host "Main App: $ALB_URL/" -ForegroundColor White
Write-Host "Health: $ALB_URL/health" -ForegroundColor White
Write-Host "API Status: $ALB_URL/api/status" -ForegroundColor White