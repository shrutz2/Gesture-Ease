#!/bin/bash

CLUSTER_NAME="gesture-ease-cluster"
REGION="ap-south-1"

# Create services if they don't exist
create_service_if_not_exists() {
    local service_name=$1
    local task_definition=$2
    
    if ! aws ecs describe-services --cluster $CLUSTER_NAME --services $service_name --region $REGION --query 'services[0].status' --output text 2>/dev/null | grep -q ACTIVE; then
        echo "Creating service: $service_name"
        aws ecs create-service \
            --cluster $CLUSTER_NAME \
            --service-name $service_name \
            --task-definition $task_definition \
            --desired-count 1 \
            --region $REGION
    else
        echo "Service $service_name already exists"
    fi
}

# Create services
create_service_if_not_exists "gesture-ease-service" "gesture-ease-task"
create_service_if_not_exists "gesture-ease-frontend" "gesture-ease-frontend-task"  
create_service_if_not_exists "gesture-ease-app" "gesture-ease-task-fixed"

echo "ECS services setup complete"