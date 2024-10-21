#!/bin/bash

set -e

if [ -z "$TF_VAR_db_password" ]; then
    echo "ERROR: TF_VAR_db_password is not set. Please set this environment variable."
    exit 1
fi

if [ -z "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    echo "ERROR: GOOGLE_APPLICATION_CREDENTIALS is not set. Please set this environment variable."
    exit 1
fi


echo "Authenticating with Google Cloud..."
gcloud auth activate-service-account --key-file="$GOOGLE_APPLICATION_CREDENTIALS"

PROJECT_ID="misinformation-mitigation"
CLUSTER_NAME="misinformation-mitigation-gke-cluster"
IMAGE_NAME="misinformation-mitigation-api"
ZONE="northamerica-northeast1-a"
TERRAFORM_DIR="./infrastructure/terraform"
KUBERNETES_DIR="./infrastructure/kubernetes"

gcloud config set project $PROJECT_ID

check_command() {
    if ! command -v $1 &> /dev/null
    then
        echo "$1 is not installed. Please install it before continuing."
        exit 1
    fi
}

check_command gcloud
check_command docker
check_command terraform
check_command kubectl

gcloud auth configure-docker gcr.io --quiet

export DOCKER_BUILDKIT=1

echo "Building and pushing multi-architecture Docker image..."
IMAGE_TAG=$(git rev-parse --short HEAD)

if docker buildx inspect mybuilder > /dev/null 2>&1; then
    echo "Builder 'mybuilder' already exists. Using it."
    docker buildx use mybuilder
else
    echo "Creating new builder 'mybuilder'."
    docker buildx create --name mybuilder --use
fi

docker buildx inspect --bootstrap

docker buildx build --platform linux/amd64,linux/arm64 \
  -t gcr.io/${PROJECT_ID}/${IMAGE_NAME}:${IMAGE_TAG} \
  -t gcr.io/${PROJECT_ID}/${IMAGE_NAME}:latest \
  --push .

echo "Applying Terraform configuration..."
cd $TERRAFORM_DIR
terraform init -reconfigure
terraform apply -auto-approve

DB_CONNECTION_NAME=$(terraform output -raw database_connection_name)
cd -

echo "Connecting to GKE cluster..."
gcloud container clusters get-credentials $CLUSTER_NAME --zone $ZONE --project $PROJECT_ID

kubectl rollout status deployment/misinformation-mitigation-api -n misinformation-mitigation

echo "Deployment completed successfully!"
echo "You can access your API via the URL configured in the Ingress."
