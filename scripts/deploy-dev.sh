#!/bin/bash
# ============================================
# Yeirin-AI Backend - Development Deployment Script
# Usage: ./scripts/deploy-dev.sh [tag]
# ============================================

set -e

# Configuration
AWS_REGION="ap-northeast-2"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPOSITORY="yeirin-ai"
IMAGE_TAG="${1:-latest}"

echo "🚀 Starting deployment for yeirin-ai..."
echo "   AWS Account: ${AWS_ACCOUNT_ID}"
echo "   Region: ${AWS_REGION}"
echo "   Tag: ${IMAGE_TAG}"

# Step 1: Login to ECR
echo "📦 Logging into ECR..."
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

# Step 2: Create ECR repository if not exists
echo "📦 Ensuring ECR repository exists..."
aws ecr describe-repositories --repository-names ${ECR_REPOSITORY} --region ${AWS_REGION} 2>/dev/null || \
    aws ecr create-repository --repository-name ${ECR_REPOSITORY} --region ${AWS_REGION}

# Step 3: Build Docker image
echo "🔨 Building Docker image..."
docker build -t ${ECR_REPOSITORY}:${IMAGE_TAG} .

# Step 4: Tag image for ECR
echo "🏷️ Tagging image for ECR..."
docker tag ${ECR_REPOSITORY}:${IMAGE_TAG} ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}:${IMAGE_TAG}

# Step 5: Push to ECR
echo "📤 Pushing to ECR..."
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}:${IMAGE_TAG}

echo "✅ Deployment complete!"
echo "   Image: ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}:${IMAGE_TAG}"
