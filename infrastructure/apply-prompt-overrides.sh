#!/bin/bash
# Applies a prompt overrides file to the cluster's veracity-prompt-overrides ConfigMap (docs/prompt-overrides.md).
# Same rule as deploy.sh: only committed and pushed text reaches the cluster, and prod only from main, so every
# prompt change is reviewed and recorded in git. The ConfigMap is annotated with the commit it came from.
#
# Usage: DEPLOY_ENV=dev ./infrastructure/apply-prompt-overrides.sh infrastructure/prompt-overrides/dev.json

set -euo pipefail
cd "$(dirname "$0")/.."

FILE="${1:?Usage: DEPLOY_ENV=dev|prod $0 <overrides.json>}"
ZONE="northamerica-northeast1-a"
NAMESPACE="misinformation-mitigation"
DEPLOY_ENV="${DEPLOY_ENV:-prod}"
if [ "$DEPLOY_ENV" = "dev" ]; then
    CLUSTER_NAME="misinformation-mitigation-dev-cluster"
elif [ "$DEPLOY_ENV" = "prod" ]; then
    CLUSTER_NAME="misinformation-mitigation-gke-cluster"
else
    echo "ERROR: DEPLOY_ENV must be 'prod' or 'dev', not '$DEPLOY_ENV'."
    exit 1
fi

if ! git ls-files --error-unmatch "$FILE" > /dev/null 2>&1; then
    echo "ERROR: $FILE is not committed. Commit it so the change is reviewed and recorded."
    exit 1
fi
if [ -n "$(git status --porcelain -- "$FILE")" ]; then
    echo "ERROR: $FILE has uncommitted changes."
    exit 1
fi
COMMIT=$(git rev-parse --short HEAD)
git fetch --quiet origin
if [ -z "$(git branch -r --contains HEAD)" ]; then
    echo "ERROR: Commit $COMMIT has not been pushed. Push it first."
    exit 1
fi
if [ "$DEPLOY_ENV" = "prod" ] && ! git merge-base --is-ancestor HEAD origin/main; then
    echo "ERROR: Prod prompt overrides must come from a commit on main."
    exit 1
fi

# The check needs only the standard library. Use PYTHON if set, else the first launcher that runs: macOS has only
# python3, and on Windows python3 may be a stub that opens the Store, leaving python or py.
PY="${PYTHON:-}"
if [ -z "$PY" ]; then
    for candidate in python3 python py; do
        if "$candidate" -c "" > /dev/null 2>&1; then PY="$candidate"; break; fi
    done
fi
if [ -z "$PY" ]; then
    echo "ERROR: Python not found. Install it, or set PYTHON=/path/to/python."
    exit 1
fi
"$PY" -m app.core.llm.prompt_overrides check "$FILE"

gcloud container clusters get-credentials "$CLUSTER_NAME" --zone "$ZONE"
kubectl -n "$NAMESPACE" create configmap veracity-prompt-overrides --from-file=prompts.json="$FILE" \
    --dry-run=client -o yaml | kubectl apply -f -
kubectl -n "$NAMESPACE" annotate configmap veracity-prompt-overrides --overwrite \
    "veri-fact.ai/source-commit=$COMMIT" "veri-fact.ai/source-file=$FILE"

echo "Applied $FILE at $COMMIT to $DEPLOY_ENV. The pod loads it within about 2 minutes; check with:"
echo "  kubectl -n $NAMESPACE logs deploy/misinformation-mitigation-api -c misinformation-mitigation-api | grep 'Prompt overrides'"
