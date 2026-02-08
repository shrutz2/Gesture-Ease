# Quick health check script
# Run: .\scripts\check-service-health.ps1

$AWS_REGION = "ap-south-1"
$CLUSTER_NAME = "gesture-ease-cluster"
$ALB_DNS = "gesture-ease-alb-2098950132.ap-south-1.elb.amazonaws.com"

Write-Host "`n🔍 Checking Service Health...`n" -ForegroundColor Cyan

# Check ECS Services
Write-Host "📊 ECS Services Status:" -ForegroundColor Yellow
aws ecs describe-services `
  --cluster $CLUSTER_NAME `
  --services gesture-ease-backend gesture-ease-frontend `
  --region $AWS_REGION `
  --query 'services[*].[serviceName,status,runningCount,desiredCount]' `
  --output table

# Check Running Tasks
Write-Host "`n📦 Running Tasks:" -ForegroundColor Yellow
aws ecs list-tasks `
  --cluster $CLUSTER_NAME `
  --region $AWS_REGION `
  --query 'taskArns[*]' `
  --output table

# Check Target Groups (if ALB name is known)
Write-Host "`n🎯 Target Group Health:" -ForegroundColor Yellow
$TG_ARN = aws elbv2 describe-target-groups `
  --region $AWS_REGION `
  --query "TargetGroups[?contains(TargetGroupName, 'gesture-ease')].TargetGroupArn" `
  --output text

if ($TG_ARN) {
    $TG_ARNS = $TG_ARN -split "`n"
    foreach ($arn in $TG_ARNS) {
        Write-Host "`nTarget Group: $arn" -ForegroundColor Cyan
        aws elbv2 describe-target-health `
          --target-group-arn $arn `
          --region $AWS_REGION `
          --query 'TargetHealthDescriptions[*].[Target.Id,TargetHealth.State,TargetHealth.Reason]' `
          --output table
    }
}

# Test ALB endpoints
Write-Host "`n🌐 Testing ALB Endpoints:" -ForegroundColor Yellow
try {
    $healthResponse = Invoke-WebRequest -Uri "http://${ALB_DNS}/health" -TimeoutSec 10 -UseBasicParsing
    Write-Host "✅ /health: $($healthResponse.StatusCode)" -ForegroundColor Green
} catch {
    Write-Host "❌ /health: Failed - $($_.Exception.Message)" -ForegroundColor Red
}

try {
    $apiResponse = Invoke-WebRequest -Uri "http://${ALB_DNS}/api/status" -TimeoutSec 10 -UseBasicParsing
    Write-Host "✅ /api/status: $($apiResponse.StatusCode)" -ForegroundColor Green
} catch {
    Write-Host "❌ /api/status: Failed - $($_.Exception.Message)" -ForegroundColor Red
}

try {
    $rootResponse = Invoke-WebRequest -Uri "http://${ALB_DNS}/" -TimeoutSec 10 -UseBasicParsing
    Write-Host "✅ / (root): $($rootResponse.StatusCode)" -ForegroundColor Green
} catch {
    Write-Host "❌ / (root): Failed - $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n✅ Health check complete!`n" -ForegroundColor Green

