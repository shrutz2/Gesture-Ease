# Check ECS Services Status
$ErrorActionPreference = "Continue"

$AWS_REGION = "ap-south-1"
$CLUSTER_NAME = "gesture-ease-cluster"

Write-Host "Checking ECS Services Status" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan

# Check if cluster exists
Write-Host "`nChecking ECS Cluster..." -ForegroundColor Yellow
try {
    $clusterInfo = aws ecs describe-clusters --clusters $CLUSTER_NAME --region $AWS_REGION --query 'clusters[0].{Name:clusterName,Status:status,ActiveServices:activeServicesCount,RunningTasks:runningTasksCount}' --output table
    Write-Host "Cluster found:" -ForegroundColor Green
    Write-Host $clusterInfo
} catch {
    Write-Host "Cluster '$CLUSTER_NAME' not found" -ForegroundColor Red
    Write-Host "Create cluster with: aws ecs create-cluster --cluster-name $CLUSTER_NAME --region $AWS_REGION" -ForegroundColor Yellow
    exit 1
}

# Check backend service
Write-Host "`nChecking Backend Service..." -ForegroundColor Yellow
try {
    $backendService = aws ecs describe-services --cluster $CLUSTER_NAME --services gesture-ease-backend --region $AWS_REGION --query 'services[0].{Name:serviceName,Status:status,Running:runningCount,Desired:desiredCount}' --output table 2>$null
    if ($backendService) {
        Write-Host "Backend service found:" -ForegroundColor Green
        Write-Host $backendService
    } else {
        throw "Service not found"
    }
} catch {
    Write-Host "Backend service 'gesture-ease-backend' not found" -ForegroundColor Red
    Write-Host "You need to create the backend service first" -ForegroundColor Yellow
}

# Check frontend service
Write-Host "`nChecking Frontend Service..." -ForegroundColor Yellow
try {
    $frontendService = aws ecs describe-services --cluster $CLUSTER_NAME --services gesture-ease-frontend --region $AWS_REGION --query 'services[0].{Name:serviceName,Status:status,Running:runningCount,Desired:desiredCount}' --output table 2>$null
    if ($frontendService) {
        Write-Host "Frontend service found:" -ForegroundColor Green
        Write-Host $frontendService
    } else {
        throw "Service not found"
    }
} catch {
    Write-Host "Frontend service 'gesture-ease-frontend' not found" -ForegroundColor Red
    Write-Host "You need to create the frontend service first" -ForegroundColor Yellow
}

# Check target groups
Write-Host "`nChecking Target Groups..." -ForegroundColor Yellow
try {
    $backendTg = aws elbv2 describe-target-groups --names gesture-ease-backend-tg --region $AWS_REGION --query 'TargetGroups[0].{Name:TargetGroupName,Protocol:Protocol,Port:Port,HealthPath:HealthCheckPath}' --output table 2>$null
    if ($backendTg) {
        Write-Host "Backend target group found:" -ForegroundColor Green
        Write-Host $backendTg
    } else {
        throw "Target group not found"
    }
} catch {
    Write-Host "Backend target group 'gesture-ease-backend-tg' not found" -ForegroundColor Red
}

try {
    $frontendTg = aws elbv2 describe-target-groups --names gesture-ease-frontend-tg --region $AWS_REGION --query 'TargetGroups[0].{Name:TargetGroupName,Protocol:Protocol,Port:Port,HealthPath:HealthCheckPath}' --output table 2>$null
    if ($frontendTg) {
        Write-Host "Frontend target group found:" -ForegroundColor Green
        Write-Host $frontendTg
    } else {
        throw "Target group not found"
    }
} catch {
    Write-Host "Frontend target group 'gesture-ease-frontend-tg' not found" -ForegroundColor Red
}

# Check ALB
Write-Host "`nChecking Application Load Balancer..." -ForegroundColor Yellow
try {
    $alb = aws elbv2 describe-load-balancers --region $AWS_REGION --query 'LoadBalancers[?contains(DNSName, `gesture-ease-alb`)].{Name:LoadBalancerName,DNS:DNSName,State:State.Code}' --output table
    if ($alb) {
        Write-Host "ALB found:" -ForegroundColor Green
        Write-Host $alb
    } else {
        Write-Host "No ALB found with 'gesture-ease-alb' in DNS name" -ForegroundColor Red
    }
} catch {
    Write-Host "Error checking ALB" -ForegroundColor Red
}

Write-Host "`nNext Steps:" -ForegroundColor Cyan
Write-Host "1. If services do not exist, you need to deploy them first using your deployment scripts" -ForegroundColor Yellow
Write-Host "2. If services exist but are unhealthy, run the quick fix script" -ForegroundColor Yellow
Write-Host "3. Check CloudFormation stacks: aws cloudformation list-stacks --region $AWS_REGION" -ForegroundColor Yellow