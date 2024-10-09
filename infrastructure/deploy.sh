#!/bin/bash

# Stop the script if any command fails
set -e

# Load environment variables from .env file
if [ -f .env ]; then
    export $(cat .env | xargs)
fi

# Check if required environment variables are set
if [ -z "$TF_VAR_db_password" ]; then
    echo "ERROR: TF_VAR_db_password is not set. Please set this environment variable in your .env file."
    exit 1
fi

# Configure variables
PROJECT_ID="misinformation-mitigation"
REGION="northamerica-northeast1"
CLUSTER_NAME="misinformation-mitigation-gke-cluster"
IMAGE_NAME="misinformation-mitigation-api"
TERRAFORM_DIR="./infrastructure/terraform"
KUBERNETES_DIR="./infrastructure/kubernetes"

# Function to check if a command is available
check_command() {
    if ! command -v $1 &> /dev/null
    then
        echo "$1 is not installed. Please install it before continuing."
        exit 1
    fi
}

# Check dependencies
check_command gcloud
check_command docker
check_command terraform
check_command kubectl

# Log in to GCP and set up application default credentials
echo "Logging in to Google Cloud and setting up application default credentials..."
gcloud auth login
gcloud auth application-default login
gcloud config set project $PROJECT_ID

# Enable Docker BuildKit
export DOCKER_BUILDKIT=1

# Build and push multi-architecture Docker image
echo "Building and pushing multi-architecture Docker image..."
IMAGE_TAG=$(git rev-parse --short HEAD)

# Check if the builder already exists
if docker buildx inspect mybuilder > /dev/null 2>&1; then
    echo "Builder 'mybuilder' already exists. Using it."
    docker buildx use mybuilder
else
    echo "Creating new builder 'mybuilder'."
    docker buildx create --name mybuilder --use
fi

docker buildx inspect --bootstrap

# Build and push the multi-arch image
docker buildx build --platform linux/amd64,linux/arm64 \
  -t gcr.io/$PROJECT_ID/$IMAGE_NAME:$IMAGE_TAG \
  -t gcr.io/$PROJECT_ID/$IMAGE_NAME:latest \
  --push .

# Apply Terraform configuration
echo "Applying Terraform configuration..."
cd $TERRAFORM_DIR
terraform init -reconfigure
terraform apply -auto-approve

DB_CONNECTION_NAME=$(terraform output -raw database_connection_name)
cd -

echo "Connecting to GKE cluster..."
gcloud container clusters get-credentials $CLUSTER_NAME --region ${REGION}-a

kubectl rollout status deployment/misinformation-mitigation-api -n misinformation-mitigation

echo "Deployment completed successfully!"
echo "You can access your API via the URL configured in the Ingress."