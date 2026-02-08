# Deploy ECS Services for Gesture Ease
# This script creates ECS task definitions and services using existing infrastructure

$ErrorActionPreference = "Stop"

# Configuration
$REGION = "ap-south-1"
$CLUSTER_NAME = "gesture-ease-cluster"
$PROJECT_NAME = "gesture-ease"

# ECR Repository URIs (from your existing repositories)
$BACKEND_IMAGE = "799947215168.dkr.ecr.ap-south-1.amazonaws.com/gesture-ease-prod-backend:latest"
$FRONTEND_IMAGE = "799947215168.dkr.ecr.ap-south-1.amazonaws.com/gesture-ease-prod-frontend:latest"

Write-Host "Deploying ECS Services for Gesture Ease" -ForegroundColor Green
Write-Host "=======================================" -ForegroundColor Green

# Get VPC and subnet information
Write-Host "Getting VPC and subnet information..." -ForegroundColor Yellow
$vpc = aws ec2 describe-vpcs --filters "Name=tag:Name,Values=gesture-ease-vpc" --region $REGION --query "Vpcs[0].VpcId" --output text
if ($vpc -eq "None") {
    Write-Host "VPC not found. Please ensure your infrastructure is deployed." -ForegroundColor Red
    exit 1
}

$privateSubnets = aws ec2 describe-subnets --filters "Name=vpc-id,Values=$vpc" "Name=tag:Type,Values=Private" --region $REGION --query "Subnets[].SubnetId" --output text
$publicSubnets = aws ec2 describe-subnets --filters "Name=vpc-id,Values=$vpc" "Name=tag:Type,Values=Public" --region $REGION --query "Subnets[].SubnetId" --output text

if ([string]::IsNullOrEmpty($privateSubnets)) {
    Write-Host "Private subnets not found. Using public subnets for both services." -ForegroundColor Yellow
    $privateSubnets = $publicSubnets
}

# Get security group
$securityGroup = aws ec2 describe-security-groups --filters "Name=vpc-id,Values=$vpc" "Name=group-name,Values=*ecs*" --region $REGION --query "SecurityGroups[0].GroupId" --output text

# Get target group ARNs
$backendTgArn = aws elbv2 describe-target-groups --names "gesture-ease-backend-tg" --region $REGION --query "TargetGroups[0].TargetGroupArn" --output text
$frontendTgArn = aws elbv2 describe-target-groups --names "gesture-ease-frontend-tg" --region $REGION --query "TargetGroups[0].TargetGroupArn" --output text

# Get ALB DNS name for frontend environment variable
$albDns = aws elbv2 describe-load-balancers --names "gesture-ease-alb" --region $REGION --query "LoadBalancers[0].DNSName" --output text

Write-Host "Infrastructure details:" -ForegroundColor Cyan
Write-Host "  VPC: $vpc"
Write-Host "  Private Subnets: $privateSubnets"
Write-Host "  Public Subnets: $publicSubnets"
Write-Host "  Security Group: $securityGroup"
Write-Host "  ALB DNS: $albDns"

# Create execution role if it doesn't exist
Write-Host "Checking IAM roles..." -ForegroundColor Yellow
$executionRoleArn = aws iam get-role --role-name "gesture-ease-ecs-execution-role" --query "Role.Arn" --output text 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating ECS execution role..." -ForegroundColor Yellow
    
    $trustPolicy = @"
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
"@
    
    aws iam create-role --role-name "gesture-ease-ecs-execution-role" --assume-role-policy-document $trustPolicy --region $REGION
    aws iam attach-role-policy --role-name "gesture-ease-ecs-execution-role" --policy-arn "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy" --region $REGION
    
    $executionRoleArn = aws iam get-role --role-name "gesture-ease-ecs-execution-role" --query "Role.Arn" --output text
}

# Create CloudWatch log groups
Write-Host "Creating CloudWatch log groups..." -ForegroundColor Yellow
aws logs create-log-group --log-group-name "/ecs/gesture-ease-backend" --region $REGION 2>$null
aws logs create-log-group --log-group-name "/ecs/gesture-ease-frontend" --region $REGION 2>$null

# Backend Task Definition
Write-Host "Creating backend task definition..." -ForegroundColor Yellow
$backendTaskDef = @"
{
  "family": "gesture-ease-backend",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "$executionRoleArn",
  "containerDefinitions": [
    {
      "name": "backend",
      "image": "$BACKEND_IMAGE",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 5000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "FLASK_ENV",
          "value": "production"
        },
        {
          "name": "PYTHONUNBUFFERED",
          "value": "1"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/gesture-ease-backend",
          "awslogs-region": "$REGION",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:5000/health || exit 1"],
        "interval": 30,
        "timeout": 10,
        "retries": 3,
        "startPeriod": 120
      }
    }
  ]
}
"@

$backendTaskDef | Out-File -FilePath "backend-task-def.json" -Encoding UTF8
$backendTaskDefArn = aws ecs register-task-definition --cli-input-json file://backend-task-def.json --region $REGION --query "taskDefinition.taskDefinitionArn" --output text

# Frontend Task Definition
Write-Host "Creating frontend task definition..." -ForegroundColor Yellow
$frontendTaskDef = @"
{
  "family": "gesture-ease-frontend",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "$executionRoleArn",
  "containerDefinitions": [
    {
      "name": "frontend",
      "image": "$FRONTEND_IMAGE",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 3000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "NODE_ENV",
          "value": "production"
        },
        {
          "name": "REACT_APP_BACKEND_URL",
          "value": "http://$albDns/api"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/gesture-ease-frontend",
          "awslogs-region": "$REGION",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "wget --no-verbose --tries=1 --spider http://localhost:3000/ || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 30
      }
    }
  ]
}
"@

$frontendTaskDef | Out-File -FilePath "frontend-task-def.json" -Encoding UTF8
$frontendTaskDefArn = aws ecs register-task-definition --cli-input-json file://frontend-task-def.json --region $REGION --query "taskDefinition.taskDefinitionArn" --output text

# Create Backend Service
Write-Host "Creating backend ECS service..." -ForegroundColor Yellow
$backendService = @"
{
  "serviceName": "gesture-ease-backend",
  "cluster": "$CLUSTER_NAME",
  "taskDefinition": "$backendTaskDefArn",
  "desiredCount": 1,
  "launchType": "FARGATE",
  "networkConfiguration": {
    "awsvpcConfiguration": {
      "subnets": ["$($privateSubnets -split '\s+' -join '","')"],
      "securityGroups": ["$securityGroup"],
      "assignPublicIp": "DISABLED"
    }
  },
  "loadBalancers": [
    {
      "targetGroupArn": "$backendTgArn",
      "containerName": "backend",
      "containerPort": 5000
    }
  ],
  "healthCheckGracePeriodSeconds": 180
}
"@

$backendService | Out-File -FilePath "backend-service.json" -Encoding UTF8
aws ecs create-service --cli-input-json file://backend-service.json --region $REGION

# Create Frontend Service
Write-Host "Creating frontend ECS service..." -ForegroundColor Yellow
$frontendService = @"
{
  "serviceName": "gesture-ease-frontend",
  "cluster": "$CLUSTER_NAME",
  "taskDefinition": "$frontendTaskDefArn",
  "desiredCount": 1,
  "launchType": "FARGATE",
  "networkConfiguration": {
    "awsvpcConfiguration": {
      "subnets": ["$($publicSubnets -split '\s+' -join '","')"],
      "securityGroups": ["$securityGroup"],
      "assignPublicIp": "ENABLED"
    }
  },
  "loadBalancers": [
    {
      "targetGroupArn": "$frontendTgArn",
      "containerName": "frontend",
      "containerPort": 3000
    }
  ],
  "healthCheckGracePeriodSeconds": 60
}
"@

$frontendService | Out-File -FilePath "frontend-service.json" -Encoding UTF8
aws ecs create-service --cli-input-json file://frontend-service.json --region $REGION

# Clean up temporary files
Remove-Item "backend-task-def.json", "frontend-task-def.json", "backend-service.json", "frontend-service.json" -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Deployment initiated successfully!" -ForegroundColor Green
Write-Host "Services are starting up. This may take 5-10 minutes." -ForegroundColor Yellow
Write-Host ""
Write-Host "Monitor deployment with:" -ForegroundColor Cyan
Write-Host "  .\check-ecs-services.ps1" -ForegroundColor White
Write-Host ""
Write-Host "Your application will be available at:" -ForegroundColor Cyan
Write-Host "  http://$albDns" -ForegroundColor White