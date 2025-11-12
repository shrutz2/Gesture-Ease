@echo off
echo Setting up AWS CLI...

REM Configure AWS CLI
aws configure set aws_access_key_id AKIA3UQER2FAJK64AJ71
aws configure set aws_secret_access_key mcVkjA12baH1Zy7B34REIAmlqtiq8INR74EMtqkp
aws configure set default.region us-east-1
aws configure set default.output json

echo Testing AWS connection...
aws sts get-caller-identity

echo Creating ECR repositories...
aws ecr create-repository --repository-name gesture-ease-prod-backend --region us-east-1
aws ecr create-repository --repository-name gesture-ease-prod-frontend --region us-east-1

echo Creating S3 bucket...
aws s3 mb s3://5gesture-ease-prod-models --region us-east-1

echo Creating ECS cluster...
aws ecs create-cluster --cluster-name 5gesture-ease-prod-cluster --region us-east-1

echo Setup complete! Now add secrets to GitHub and run workflows.
pause