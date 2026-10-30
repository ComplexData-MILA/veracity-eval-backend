# Semantic cache

Repeated or paraphrased claims reuse earlier analyses instead of re-running the full search + LLM loop.

## How it works

This runs on every analysis, both the interactive stream and `/claims/batch`. No LLM is called during a lookup. Entries
are filtered by language, by expiry (7 days), and by a hash of `default`, `preferred_domains`, the model and the analysis
prompts.

1. **Exact match.** The SHA-256 of the normalized claim (case, punctuation and whitespace removed) is looked up. A match is
   a **full hit**, with no embedding or model call.
2. **Candidates.** The claim is embedded with Vertex `text-multilingual-embedding-002`. pgvector returns the top
   `SEMCACHE_TOP_K` entries with cosine ≥ `SEMCACHE_T_RECALL`. Similarity only *proposes* candidates, because embeddings
   score "X", "not X" and "X in 2015" almost identically (0.94–0.97 in our tests).
3. **Verification** ([app/services/claim_matching.py](../app/services/claim_matching.py)), per candidate:

| Check | Result |
|---|---|
| Multilingual NLI cross-encoder (`SEMCACHE_VERIFIER_MODEL`): A entails B **and** B entails A, with min probability ≥ `SEMCACHE_ENTAIL_T` | **Full hit.** The cached verdict, analysis and sources are copied to the new claim and replayed as a normal SSE stream. |
| Same wording once numbers are masked, but different numbers (e.g. "legalized in 2018" vs "in 2015") | **Evidence hit.** The search loop is skipped. The verdict is re-run on the cached sources at temperature `SEMCACHE_VERDICT_TEMPERATURE`. |
| Anything else (negations, entity swaps, role swaps, related claims) | **Miss.** The normal pipeline runs and the result is stored in the cache. |

Only fresh, completed analyses are stored, so an entry never outlives the evidence it was based on. Any cache error is
logged and falls back to the normal pipeline. Each candidate's similarity, entailment and decision is logged as
`Semantic cache candidate: ...`.

**Why these checks.**
- Mutual entailment is the standard test for semantic equivalence (Kuhn et al., *Semantic Uncertainty*, ICLR 2023).
- Retrieve-then-verify is the leading approach for matching previously fact-checked claims (SemEval-2025 Task 7).
- Calibrating for zero wrong answers served, rather than for ranking quality, follows GroundedCache (arXiv 2605.27494) and
  Redis's calibration paper (arXiv 2606.19719).
- NLI "contradiction" is *not* used to pick evidence reuse, because NLI models also label entity swaps (Canada→Mexico) as
  contradictions.

**Calibration** (`python tests/calibrate.py`, with the 0.92 threshold):
- 47 curated claim pairs (`tests/data/claim_pairs.json`): 0 wrong full hits, 0 wrong evidence hits, 10/15 full-reuse
  recall. The pairs cover paraphrases, negations, number and date changes, entity swaps, role swaps, related claims and
  French.
- 600 XNLI neutral and contradiction pairs (EN and FR): 0 false full hits.
- PAWS-X adversarial near-duplicates: 68 of 350 non-paraphrases still pass. These are long Wikipedia sentences where one
  modifier moved. They're a stress test, not typical claims.

**Costs measured on CPU.**
- The verifier model is about 1.06 GB in memory (279M parameters, 193M of them its multilingual vocabulary).
- A lookup with candidates adds about 150 ms on a 16-core machine, or about 260 ms with 2 threads (e2-medium).
- The model is loaded in the background at startup (`app/main.py`), since a cold load takes about 13 s.
- Int8 quantization was tested and rejected: no speed-up, and recall dropped to 2/15.

### API

- **`analysis_complete` event:** now includes `cached` (bool). On a hit it also includes `cache_tier` (`full` or `evidence`)
  and `cached_at` (ISO time of the original check).
- **`GET /v1/analysis/claim/{id}/stream?bypass_cache=true`:** "Re-check". Skips the lookup, runs fresh, and replaces the entry.
- **`?eval_mode=true`:** for benchmarks. It is accepted on the stream endpoint and on `POST /v1/claims/batch`. The cache is
  never read or written, so cache timing doesn't affect benchmark runs and benchmark runs don't fill the cache.
- **Experiment endpoint:** `/analysis/experiment/...` (Together) is never cached.

### Frontend (separate repo)

When `analysis_complete.content.cached` is true, show a disclaimer such as: *"This claim was previously checked on
{cached_at}. Results may be up to a week old and may not reflect newer developments."* Next to it, add a **Re-check**
button that reopens the stream with `bypass_cache=true`.

The disclaimer is only sent in the live stream event. It is not stored on the analysis, so reopening a past claim won't
show it. Batch results (`/claims/batch/results`) don't include it either.

### Settings (`app/core/config.py`, all have defaults)

| Env var | Default | Notes |
|---|---|---|
| `SEMANTIC_CACHE_MODE` | `on` | `shadow` looks up and logs would-be hits but always runs fresh. `off` disables the cache completely; use it for a dedicated benchmark deployment. |
| `SEMCACHE_TOP_K` / `SEMCACHE_T_RECALL` | `3` / `0.85` | Candidate retrieval. Each candidate costs one verifier pass (both directions). |
| `SEMCACHE_VERIFIER_MODEL` | `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7` | Baked into the image by `app/preload_model.py`; keep the two in sync. |
| `SEMCACHE_ENTAIL_T` | `0.92` | Re-check with `tests/calibrate.py` after changing the model or threshold. |
| `SEMCACHE_TTL_HOURS` | `168` | Weekly refresh. |
| `SEMCACHE_EMBEDDING_MODEL` / `SEMCACHE_EMBEDDING_LOCATION` | `text-multilingual-embedding-002` / `us-central1` | |
| `SEMCACHE_VERDICT_TEMPERATURE` | `0.2` | Used only on evidence hits. |
| `SEMCACHE_REPLAY_DELAY_MS` | `15` | Pause between replayed chunks on a full hit. |

## Local setup

`docker-compose.yml` now uses `pgvector/pgvector:pg13`. The existing data volume is compatible. Run
`docker compose pull && docker compose up -d`, and the app runs the migration (`e7a1c3f9b2d4`) on start.

## GCP: what to do

Do these steps for **dev first**, then prod. The values come from `infrastructure/terraform-dev` and
`infrastructure/terraform`.

1. **Check that pgvector supports HNSW (needs ≥ 0.5).** Cloud SQL Postgres 13 ships pgvector, and the migration runs
   `CREATE EXTENSION vector` itself. The Terraform-created `misinformation_mitigation_user` is a member of
   `cloudsqlsuperuser`, so it's allowed to do that. Make sure the instance is on a recent maintenance version:
   ```sh
   gcloud sql instances describe <instance> --format="value(maintenanceVersion,availableMaintenanceVersions)"
   # if availableMaintenanceVersions is non-empty:
   gcloud sql instances patch <instance> --maintenance-version=<latest>   # short restart
   ```
   `<instance>` is `<name>-db` from Terraform `local.name`. To list instances, run `gcloud sql instances list`.

2. **Check the Vertex service account can call embeddings.** The pod uses the key in the K8s secret
   `vertex-ai-credentials`. It already calls Vertex MaaS, so it most likely has `roles/aiplatform.user`. Check with:
   ```sh
   gcloud projects get-iam-policy misinformation-mitigation \
     --flatten="bindings[].members" --filter="bindings.members:<sa-email>" --format="value(bindings.role)"
   ```
   If it's missing, run:
   `gcloud projects add-iam-policy-binding misinformation-mitigation --member=serviceAccount:<sa-email> --role=roles/aiplatform.user`.
   The Vertex AI API (`aiplatform.googleapis.com`) is already enabled.

3. **Optional: data residency.** Claim text is sent to `us-central1` for embedding, as it already is to `us-east5` for Llama.
   To keep embeddings in Canada, set `SEMCACHE_EMBEDDING_LOCATION=northamerica-northeast1`, provided that region
   offers the model when you deploy.

4. **Optional: env overrides.** Only needed if you want non-default values. Add `env { name = "..." value = "..." }`
   blocks next to `GOOGLE_APPLICATION_CREDENTIALS` in the API container. Do it in **both**
   `infrastructure/terraform/main.tf` and `infrastructure/terraform-dev/main.tf`. Suggested values:
   - First prod rollout: `SEMANTIC_CACHE_MODE=shadow` for a few days. Check the logs, adjust the thresholds, then
     switch to `on`.
   - A benchmark-only deployment: `SEMANTIC_CACHE_MODE=off`. For one-off benchmark runs against a normal
     deployment, pass `eval_mode=true` instead.

5. **Deploy.** Run `DEPLOY_ENV=dev ./infrastructure/deploy.sh`, as described in `docs/dev-environment.md`. The migration
   runs on pod start, and no new GCP resources are needed.

6. **Verify.**
   - Check the migration in the pod logs:
     `kubectl logs deploy/<api-deployment> -c <api-container> | grep -i alembic`.
   - Submit the same claim twice. The second `analysis_complete` should have `"cached": true`. In Cloud Logging, search
     for `Semantic cache`.
   - Submit with `eval_mode=true` and confirm it isn't cached.
   - Check the table:
     `SELECT count(*), sum(hit_count) FROM semantic_cache_entries WHERE NOT invalidated AND expires_at > now();`

7. **Optional: housekeeping.** Expired rows are ignored automatically. To keep the table small, run this periodically,
   for example from a K8s CronJob:
   `DELETE FROM semantic_cache_entries WHERE expires_at < now() - interval '30 days';`
