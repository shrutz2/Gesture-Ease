# GitHub Secrets Setup Guide

## Required Secrets for GitHub Actions

Go to your repository → Settings → Secrets and variables → Actions → New repository secret

### For docker-publish.yml workflow:
- `AWS_ACCESS_KEY_ID`: Your AWS access key
- `AWS_SECRET_ACCESS_KEY`: Your AWS secret key  
- `AWS_REGION`: Your AWS region (e.g., us-east-1)
- `AWS_ACCOUNT_ID`: Your 12-digit AWS account ID

### For deploy.yml workflow (additional):
- `AWS_ROLE_TO_ASSUME`: ARN of IAM role for OIDC (recommended over access keys)
- `ECR_BACKEND_REPO`: Full ECR repository URI for backend
- `ECR_FRONTEND_REPO`: Full ECR repository URI for frontend
- `S3_MODELS_BUCKET`: S3 bucket name for model artifacts
- `ECS_CLUSTER`: ECS cluster name
- `ECS_SERVICE`: ECS service name

## AWS Setup Commands

```bash
# 1. Create ECR repositories
aws ecr create-repository --repository-name gesture-ease-backend
aws ecr create-repository --repository-name gesture-ease-frontend

# 2. Create S3 bucket for models
aws s3 mb s3://your-gesture-ease-models-bucket

# 3. Create ECS cluster
aws ecs create-cluster --cluster-name gesture-ease-cluster

# 4. Create IAM roles (for ECS tasks)
# - ecsTaskExecutionRole (AWS managed)
# - ecsTaskRole (custom for S3 access)
```

## Local AWS CLI Setup

After installing AWS CLI, configure it:

```bash
aws configure
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key  
# Enter your default region
# Enter output format (json)
```

## Test Your Setup

```bash
# Test AWS CLI
aws sts get-caller-identity

# Test Docker
docker --version

# Test ECR login
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com
```