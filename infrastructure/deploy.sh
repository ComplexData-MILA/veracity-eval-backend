#!/bin/bash

# Stop the script if any command fails
set -euo pipefail

# Run from the repository root regardless of where the script is called from
cd "$(dirname "$0")/.."

# Load environment variables from .env file
if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    . ./.env
    set +a
fi

# Configure variables
PROJECT_ID="misinformation-mitigation"
REGION="northamerica-northeast1"
ZONE="${REGION}-a"
CLUSTER_NAME="misinformation-mitigation-gke-cluster"
IMAGE_NAME="misinformation-mitigation-api"
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/misinformation-mitigation"
TERRAFORM_DIR="./infrastructure/terraform"
HEALTH_URL="https://api.veri-fact.ai/v1/health"

# Dev environment overrides. Usage: DEPLOY_ENV=dev ./infrastructure/deploy.sh (from the dev-env branch)
DEPLOY_ENV="${DEPLOY_ENV:-prod}"
if [ "$DEPLOY_ENV" = "dev" ]; then
    CLUSTER_NAME="misinformation-mitigation-dev-cluster"
    TERRAFORM_DIR="./infrastructure/terraform-dev"
    HEALTH_URL="https://api-dev.veri-fact.ai/v1/health"
    # Dev has its own database; give it its own password when DEV_DB_PASSWORD is set
    export TF_VAR_db_password="${DEV_DB_PASSWORD:-${TF_VAR_db_password:-}}"
elif [ "$DEPLOY_ENV" != "prod" ]; then
    echo "ERROR: DEPLOY_ENV must be 'prod' or 'dev', not '$DEPLOY_ENV'."
    exit 1
fi

# Fall back to the app's own variable names so the same keys need not be duplicated in .env
export TF_VAR_serper_api_key="${TF_VAR_serper_api_key:-${SERPER_API_KEY:-}}"
export TF_VAR_together_api_key="${TF_VAR_together_api_key:-${TOGETHER_API_KEY:-}}"
export TF_VAR_google_search_api_key="${TF_VAR_google_search_api_key:-${GOOGLE_SEARCH_API_KEY:-}}"
export TF_VAR_google_search_engine_id="${TF_VAR_google_search_engine_id:-${GOOGLE_SEARCH_ENGINE_ID:-}}"
# export TF_VAR_auth0_client_id="${TF_VAR_auth0_client_id:-${AUTH0_CLIENT_ID:-}}"
# export TF_VAR_auth0_client_secret="${TF_VAR_auth0_client_secret:-${AUTH0_CLIENT_SECRET:-}}"

# Check if required environment variables are set (Terraform variables without defaults)
missing=0
for var in TF_VAR_db_password TF_VAR_serper_api_key TF_VAR_together_api_key TF_VAR_google_search_api_key \
           TF_VAR_google_search_engine_id; do
    if [ -z "${!var:-}" ]; then
        echo "ERROR: $var is not set. Please set this environment variable in your .env file."
        missing=1
    fi
done
[ "$missing" -eq 0 ] || exit 1

# Dev creates its vertex-ai-credentials secret from this file after Terraform applies; fail before changing anything
if [ "$DEPLOY_ENV" = "dev" ] && [ ! -f service-account.json ]; then
    echo "ERROR: service-account.json not found in the repository root. Dev deploys need it to create the vertex-ai-credentials secret."
    exit 1
fi

# Function to check if a command is available
check_command() {
    if ! command -v "$1" &> /dev/null
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
check_command git

# The image is tagged with the commit SHA, so the build must match that commit exactly
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    echo "ERROR: You have uncommitted changes. Commit or stash them before deploying."
    exit 1
fi
# Dev is only ever deployed from the dev-env branch
if [ "$DEPLOY_ENV" = "dev" ] && [ "$(git rev-parse --abbrev-ref HEAD)" != "dev-env" ]; then
    echo "ERROR: Dev deploys must run from the dev-env branch. Run: git switch dev-env"
    exit 1
fi
IMAGE_TAG=$(git rev-parse --short HEAD)
git fetch --quiet origin
if [ -n "${DEPLOY_TAG:-}" ]; then
    # Rollback: deploy an already-built image with the current Terraform config
    IMAGE_TAG="$DEPLOY_TAG"
    echo "Rolling back to existing image tag ${IMAGE_TAG}."
elif [ -z "$(git branch -r --contains HEAD)" ]; then
    echo "ERROR: Commit $IMAGE_TAG has not been pushed to GitHub. Push it before deploying."
    exit 1
elif [ "$DEPLOY_ENV" = "prod" ] && ! git merge-base --is-ancestor HEAD origin/main; then
    read -r -p "WARNING: $IMAGE_TAG is not on origin/main. Deploy it anyway? Type 'yes' to continue: " answer
    [ "$answer" = "yes" ] || exit 1
fi

# Shell scripts checked out with CRLF line endings cannot run inside the Linux container
crlf_scripts=$(git ls-files --eol -- '*.sh' | awk '$2 == "w/crlf" {printf "%s ", $NF}')
if [ -n "$crlf_scripts" ]; then
    echo "ERROR: These scripts have CRLF line endings in your checkout: $crlf_scripts"
    echo "Fix with: rm $crlf_scripts && git checkout -- $crlf_scripts"
    exit 1
fi
IMAGE_URI="${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"

# Log in to GCP and set up application default credentials (only when not already logged in)
if ! gcloud auth print-access-token > /dev/null 2>&1; then
    echo "Logging in to Google Cloud..."
    gcloud auth login
fi
if ! gcloud auth application-default print-access-token > /dev/null 2>&1; then
    echo "Setting up application default credentials..."
    gcloud auth application-default login
fi
gcloud config set project $PROJECT_ID
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# Reuse the image if this commit was already built (e.g. when rolling back)
if gcloud artifacts docker images describe "${IMAGE_URI}" > /dev/null 2>&1; then
    echo "Image ${IMAGE_URI} already exists. Skipping build."
elif [ -n "${DEPLOY_TAG:-}" ]; then
    echo "ERROR: No image tagged ${DEPLOY_TAG} exists in ${REGISTRY}."
    exit 1
else
    # Enable Docker BuildKit
    export DOCKER_BUILDKIT=1

    # Build and push multi-architecture Docker image
    echo "Building and pushing multi-architecture Docker image ${IMAGE_URI}..."

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
      -t "${IMAGE_URI}" \
      -t "${REGISTRY}/${IMAGE_NAME}:latest" \
      --push .
fi

# Apply Terraform configuration
echo "Planning Terraform changes..."
export TF_VAR_image_uri="${IMAGE_URI}"
cd $TERRAFORM_DIR
# A saved plan contains secrets in plain text; always remove it
trap "rm -f '$PWD/tfplan'" EXIT
terraform init -reconfigure

# kubernetes_manifest resources need a reachable cluster at plan time, so a
# brand-new dev environment creates the cluster first in a separate apply.
if [ "$DEPLOY_ENV" = "dev" ] && ! gcloud container clusters describe "$CLUSTER_NAME" --zone "$ZONE" > /dev/null 2>&1; then
    terraform apply -target=google_container_node_pool.primary_nodes
fi

terraform plan -out=tfplan

# The plan covers the database, networking and ingress as well as the API image,
# so review it before applying.
read -r -p "Apply this plan? Type 'yes' to continue: " answer
if [ "$answer" != "yes" ]; then
    echo "Aborted. Nothing was applied."
    rm -f tfplan
    exit 1
fi
terraform apply tfplan
rm -f tfplan
cd - > /dev/null

echo "Connecting to GKE cluster..."
gcloud container clusters get-credentials $CLUSTER_NAME --zone "$ZONE"

# A new dev cluster has no Vertex key secret yet; create it from the local key file
if [ "$DEPLOY_ENV" = "dev" ] && ! kubectl get secret vertex-ai-credentials -n misinformation-mitigation > /dev/null 2>&1; then
    kubectl -n misinformation-mitigation create secret generic vertex-ai-credentials --from-file=service-account.json
fi

kubectl rollout status deployment/misinformation-mitigation-api -n misinformation-mitigation --timeout=10m

echo "Checking API health at ${HEALTH_URL}..."
curl -fsS --max-time 30 "$HEALTH_URL"
echo

echo "Deployment of ${IMAGE_TAG} completed successfully!"
echo "To roll back, run: DEPLOY_TAG=<previous sha> ./infrastructure/deploy.sh"
