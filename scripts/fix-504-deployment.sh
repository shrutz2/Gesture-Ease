#!/bin/bash
# Script to fix 504 Gateway Timeout by rebuilding and redeploying

set -e

AWS_REGION="ap-south-1"
CLUSTER_NAME="gesture-ease-cluster"
BACKEND_SERVICE="gesture-ease-backend"
FRONTEND_SERVICE="gesture-ease-frontend"

echo "🔧 Fixing 504 Gateway Timeout..."

# Get AWS account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_BACKEND_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/gesture-ease-backend"
ECR_FRONTEND_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/gesture-ease-frontend"

echo "📦 Step 1: Building backend image with curl..."
cd backend
docker build -f Dockerfile.production -t gesture-ease-backend:latest .
docker tag gesture-ease-backend:latest ${ECR_BACKEND_URI}:latest

echo "📤 Step 2: Pushing backend image to ECR..."
aws ecr get-login-password --region ${AWS_REGION} | \
  docker login --username AWS --password-stdin ${ECR_BACKEND_URI}
docker push ${ECR_BACKEND_URI}:latest

echo "📦 Step 3: Building frontend image..."
cd ../frontend
docker build -f Dockerfile.production -t gesture-ease-frontend:latest .
docker tag gesture-ease-frontend:latest ${ECR_FRONTEND_URI}:latest

echo "📤 Step 4: Pushing frontend image to ECR..."
aws ecr get-login-password --region ${AWS_REGION} | \
  docker login --username AWS --password-stdin ${ECR_FRONTEND_URI}
docker push ${ECR_FRONTEND_URI}:latest

echo "🔄 Step 5: Updating infrastructure (health checks)..."
cd ../infrastructure
terraform apply -auto-approve

echo "🚀 Step 6: Forcing ECS service updates..."
aws ecs update-service \
  --cluster ${CLUSTER_NAME} \
  --service ${BACKEND_SERVICE} \
  --force-new-deployment \
  --region ${AWS_REGION}

aws ecs update-service \
  --cluster ${CLUSTER_NAME} \
  --service ${FRONTEND_SERVICE} \
  --force-new-deployment \
  --region ${AWS_REGION}

echo "⏳ Step 7: Waiting for services to stabilize..."
aws ecs wait services-stable \
  --cluster ${CLUSTER_NAME} \
  --services ${BACKEND_SERVICE} ${FRONTEND_SERVICE} \
  --region ${AWS_REGION}

echo "✅ Deployment complete! Services should be healthy now."
echo "🌐 Test your ALB URL in a few minutes"

