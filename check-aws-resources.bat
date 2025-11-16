@echo off
echo Checking AWS Resources...

echo.
echo === Checking ECS Cluster ===
aws ecs describe-clusters --clusters 5gesture-ease-prod-cluster --region ap-south-1

echo.
echo === Checking ECS Services ===
aws ecs list-services --cluster 5gesture-ease-prod-cluster --region ap-south-1

echo.
echo === Checking ECR Repositories ===
aws ecr describe-repositories --region ap-south-1

echo.
echo === Checking CloudWatch Log Groups ===
aws logs describe-log-groups --log-group-name-prefix "/ecs/gesture-ease-prod" --region ap-south-1

echo.
echo === Checking VPC and Subnets ===
aws ec2 describe-vpcs --region ap-south-1
aws ec2 describe-subnets --region ap-south-1

pause