# Dev environment

A copy of production for end-to-end testing, served at `https://api-dev.veri-fact.ai`.

It lives in the same GCP project (`misinformation-mitigation`). Everything else is separate, with `dev` in each GCP resource name:
- VPC
- GKE cluster
- Cloud SQL instance
- static IP
- certificate
- Terraform state (`gs://misinformation-mitigation-terraform-state/terraform/dev`)

Kubernetes objects inside the dev cluster (namespace, deployment, ingress) keep prod's names, so the same `kubectl` commands work in both.

Shared with prod:
- the `veri-fact.ai` domain. Its DNS is hosted on Cloudflare, where dev has its own `api-dev` A record, added by hand. Terraform also writes an `api-dev` record to the `veri-fact-ai-zone` Cloud DNS zone, but that zone isn't the one the domain uses, so the record has no effect.
- the Artifact Registry, so a commit tested in dev is the exact image that later ships to prod
- the Vertex service-account key (`service-account.json`)

| | Prod | Dev |
|---|---|---|
| Terraform | `infrastructure/terraform` | `infrastructure/terraform-dev` |
| Secrets file | `.env` | the same `.env` (optional `DEV_DB_PASSWORD`) |
| Deployed from | `main` | the `dev-env` branch only |
| Cluster | `misinformation-mitigation-gke-cluster` | `misinformation-mitigation-dev-cluster` |
| API | `api.veri-fact.ai` | `api-dev.veri-fact.ai` |
| Database | prod data | starts empty; migrations run on pod start |

The two Terraform roots are copies of each other. When you change resources in one, make the same change in the other.

## First-time setup

1. **Put `service-account.json` in the repository root.** This is the Vertex key file used for local development. The script stops before changing anything if it is missing.
2. **Optional: give dev its own database password.** Add `DEV_DB_PASSWORD=...` to the same `.env`. If you leave it out, dev uses the prod value of `TF_VAR_db_password`. Dev has its own database instance either way.
3. **Deploy from the `dev-env` branch:**
   ```bash
   git switch dev-env
   DEPLOY_ENV=dev ./infrastructure/deploy.sh
   ```
   - On the first run, Terraform first shows a plan for just the cluster and asks for `yes`. Then the script plans everything else and asks again. Both plans should show only creates.
   - As with prod, Terraform asks for `auth0_client_id` and `auth0_client_secret` unless they are set; the app doesn't use them.
   - The script then creates the `vertex-ai-credentials` secret in the dev cluster from the repo's local `service-account.json`, the same key file used for local development. It does this only when the secret doesn't exist yet.
4. **Add the DNS record in Cloudflare.** Get the dev static IP:
   ```bash
   terraform -chdir=infrastructure/terraform-dev output api_ip_address
   ```
   In the Cloudflare dashboard for `veri-fact.ai`, add an `A` record named `api-dev` pointing to that IP, with proxy status **DNS only** (grey cloud). Google can't issue the certificate while the record is proxied. Check it with `dig +short api-dev.veri-fact.ai`, which should print the static IP and not a Cloudflare `104.x` or `172.x` address.
5. **Wait for the certificate.** Google needs about 15–60 minutes after DNS resolves to issue it. Until then the health check at the end of the script fails. Check progress with:
   ```bash
   kubectl -n misinformation-mitigation describe managedcertificate misinformation-mitigation-cert
   ```
   Once it says `Active`, run the deploy again to confirm the health check passes.

## Day-to-day

- **Deploy dev.** Commit and push to `dev-env`, then run the command below. The script refuses dev deploys from any other branch.
  ```bash
  DEPLOY_ENV=dev ./infrastructure/deploy.sh
  ```
- **Roll back** to an earlier image:
  ```bash
  DEPLOY_ENV=dev DEPLOY_TAG=<sha> ./infrastructure/deploy.sh
  ```
- **Prod is unchanged.** Running `./infrastructure/deploy.sh` without `DEPLOY_ENV` deploys prod exactly as before.

## Dev frontend

The frontend reads `NEXT_PUBLIC_API_URL`, and falls back to `https://api.veri-fact.ai` when it is unset.

1. **Vercel.** On the `dev-env` branch of `veracity-eval-frontend`, set these Preview environment variables, scoped to that branch:
   - `NEXT_PUBLIC_API_URL=https://api-dev.veri-fact.ai`
   - `AUTH0_BASE_URL=<the branch's stable URL>`, for example `https://veracity-eval-frontend-git-dev-env-<team>.vercel.app`
   - All other Auth0 variables stay the same as prod.
2. **Auth0 dashboard.** Add the dev frontend URL to the application's:
   - Allowed Callback URLs (`<url>/api/auth/callback`)
   - Allowed Logout URLs
   - Allowed Web Origins
3. **CORS.** Add the dev frontend's URL to the `allow_origins` list in `app/main.py`, the same way the other Vercel branch URLs are listed, and redeploy dev.

## Costs and teardown

Dev runs one e2-medium node (autoscaling to at most 2), a `db-g1-small` Cloud SQL instance, an HTTPS load balancer and Cloud NAT.

To remove everything, run the command below. Terraform asks for each variable it doesn't find; for a destroy the values aren't used, so any value works. It deletes only dev resources, including the dev database and its data.
```bash
terraform -chdir=infrastructure/terraform-dev destroy
```
Then delete the `api-dev` record in Cloudflare by hand; Terraform doesn't manage it.
