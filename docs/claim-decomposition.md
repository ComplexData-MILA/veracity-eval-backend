# Claim decomposition and the subclaim cache

A clarified claim is split into atomic subclaims before the search loop. Each subclaim gets its own search. The search
results and snippets are cached per subclaim, so a later, different claim that shares a subclaim reuses that evidence.

**Status:** built and evaluated locally, behind `CLAIM_DECOMPOSITION_ENABLED` (off by default). The decomposer is
`openai/gpt-oss-120b-maas` on the `global` endpoint. Llama 3.1 8B and gpt-oss-20b returned 404 for the project. Not yet
deployed to dev. See [Results](#results) and [GCP](#gcp-what-to-do).

**Recommendation:**
- Ship D1 (the in-prompt Algorithm 1 rule) with decomposition on. It gains accuracy for about +0.6 s median.
- Subclaim searches run concurrently, which saves about 0.4 s per split claim.
- The subclaim cache (`SUBCLAIM_CACHE_ENABLED`, default `true`) is safe, but it saves searches, not time: about +0.3
  s median. Set it to `false` if latency matters more than search quota.
- Don't adopt D2 (separate labelling call) as built: it is less accurate and slower.

## Why

- Splitting a claim into atomic subclaims makes fact-checking more precise and easier to trace. Mitra et al.
  (FactLens, ACL 2025) found this, and CAAFC (Eldifrawi et al., arXiv 2605.12436) builds a pipeline on it.
- CAAFC splits with a small model (quantized Gemma3-27B) and labels each subclaim true, false or unverifiable. Its
  Algorithm 1 then combines the labels: any false subclaim makes the claim false; otherwise any unverifiable one makes it
  unverifiable; otherwise it is true.
- An atomic subclaim is a better cache key than a whole claim. It is short, so the NLI verifier judges it more
  reliably (see [Calibration](#calibration)). Different claims also share subclaims far more often than they repeat
  whole claims.

## How it works

The step runs inside `_generate_analysis`. It comes after clarification, because the client submits the clarified
claim, and after the whole-claim cache lookup, so exact batch repeats still replay without decomposing. The interactive stream,
`/claims/batch` and the eval harnesses all use it. `/clarify`, the API and the frontend are unchanged.

1. **Decompose** ([app/services/claim_decomposition.py](../app/services/claim_decomposition.py)).
   - The prompt is CAAFC's extractor-segmentor (Fig. 4): split only when needed, leave a unit claim whole, and keep
     each subclaim self-contained (names, places, dates, numbers).
   - Output is JSON, temperature 0, at most `DECOMPOSE_MAX_SUBCLAIMS`. The claim is fenced as data.
   - Any failure falls back to checking the claim whole.
2. **Subclaim cache lookup.** The subclaims are embedded in one batched call. Then, for each subclaim:
   - an exact match on the normalized text, or pgvector candidates followed by one batched NLI pass;
   - a hit needs mutual entailment ≥ `SEMCACHE_ENTAIL_T` **and** the same numbers. A different number or date is a
     different fact, so it is a miss.
3. **Evidence per subclaim.**
   - A hit copies the cached search and its sources (title, URL, snippet, credibility) into this analysis.
   - A miss runs a web search with the subclaim as the query. The provider calls for all misses run concurrently
     (`fetch_results`, no DB access). Their sources are then saved one search at a time (`create_sources`), because
     they share the request's DB session.
   - Each search is stored with `summary = "subclaim"`.
4. **Planner.** The first planner message carries each subclaim with its results. The planner searches again for
   anything not covered, or replies READY.
5. **Verdict.** For two or more subclaims, Algorithm 1 is added to the verdict request as a scoring rule:
   - a contradicted subclaim scores ≤ 20;
   - an unsupported one scores 35–65;
   - otherwise it scores > 65.

   It is still one call, with the same `{veracity_score, analysis}` JSON.
6. **Store.** After the verdict, each freshly searched subclaim is cached. A subclaim whose text or evidence has
   injection markers is not stored, matching the rule for the whole-claim cache.

`analysis_complete` gains a `subclaims` field. `timings_ms` gains `decompose`, `n_subclaims`, `subclaim_lookup`,
`subclaim_cache_hits`, `subclaim_searches`, `subclaim_search` (wall time of the concurrent calls), `subclaim_save`,
`subclaim_clone` and `subclaim_store`.

### Storage

Migration `a9d2e4b7c1f3` adds `subclaim_cache_entries`:
- **Columns:** text, hash, language, params hash, `vector(768)` embedding, and a nullable `label`.
- **Evidence:** `search_id` references `searches(id) ON DELETE CASCADE`. The evidence stays in the existing `searches`
  and `sources` rows; nothing is duplicated, and deleting an analysis removes its entries.
- **Cache key:** language, preferred domains, search provider and embedding model only. LLM and prompt changes keep
  cached evidence usable.
- **Pruning:** same TTLs as the claim cache. On write, it deletes entries older than `SEMCACHE_BATCH_TTL_HOURS` and the
  oldest beyond `SUBCLAIM_CACHE_MAX_ENTRIES`.

`label` stays empty in v1. It is filled only if per-subclaim labels (eval variant D2) are adopted.

### Which requests use which cache

| Request | Whole-claim verdict cache | Subclaim evidence cache |
|---|---|---|
| Interactive stream (single user) | never | read and write (NLI matching) |
| `POST /claims/batch` (benchmarks) | read and write, **exact text only** | read and write |

- **Interactive checks always produce a fresh verdict.** An identical repeat runs the full pipeline (about 6–7 s), and
  its score can differ because the verdict is sampled.
- **With `CLAIM_DECOMPOSITION_ENABLED` off, interactive checks are not cached at all.** That is why
  `infrastructure/terraform-dev` sets it to `true`.
- **Batch and interactive subclaim entries don't mix today.** Batch searches with Serper and the stream with Google
  CSE, and the subclaim cache key includes the search provider. Each path reuses its own entries. Batch results depend
  on that cache's state; use `eval_mode=true` for runs that must not.

### Same rules as the claim cache

- `eval_mode` neither reads nor writes either cache. Re-check (`bypass_cache`) skips the read and refreshes the entries.
- Any cache error falls back to a live search.
- With the flag off, the pipeline and the claim-cache key are byte-identical to before. With it on, the claim-cache key
  also covers the decomposition prompts and model, so entries from the two modes never mix.

### Known limitations (v1)

- **The planner can still search after the subclaim searches.** In a smoke run it still spent about 1–3 s in the loop.
- **Copying cached sources is row by row,** as in the claim cache (performance.md, item 4).
- **Duplicate sources.** Two subclaims often find the same page, and `GET /sources/analysis/{id}` doesn't remove
  duplicate URLs, so the page is listed twice.

## Settings (`app/core/config.py`)

| Env var | Default | Notes |
|---|---|---|
| `CLAIM_DECOMPOSITION_ENABLED` | `false` | Turns the whole feature on. `infrastructure/terraform-dev` sets it to `true`. |
| `DECOMPOSE_MODEL_NAME` / `DECOMPOSE_LOCATION` | `openai/gpt-oss-120b-maas` / `global` | Any Vertex MaaS chat model. gpt-oss is served only on `global`: in `us-central1` it returned empty content. |
| `DECOMPOSE_MAX_SUBCLAIMS` | `5` | Upper bound on subclaims, and so on subclaim searches. |
| `SUBCLAIM_CACHE_ENABLED` | `true` | Applies only when decomposition and the semantic cache are both on. `false` keeps decomposition but searches every subclaim (bench config V4). |
| `SUBCLAIM_CACHE_MAX_ENTRIES` | `200000` | Size cap. Entries are small: the evidence lives in `sources`. |

The NLI threshold, candidate count, recall floor and TTLs are shared with the claim cache (`SEMCACHE_*`).

## Calibration

Run `python tests/calibrate.py` with the configured threshold of 0.92. No LLM is involved.

| Pair set | Reuses found | Wrong reuses |
|---|---|---|
| Curated whole claims (`claim_pairs.json`) | 10/15 | 0/32 |
| **Curated subclaims** (`subclaim_pairs.json`: paraphrases, numbers, negations, entity/role swaps, same entity with another fact, scope) | **9/11** | **0/26** |
| **WiCE hard negatives** (two different subclaims of the same claim) | – | **0/300** |
| XNLI neutral/contradiction | – | 0/400 |

- Subclaims are matched more often than whole claims (82% against 67%), and no wrong reuse appeared on either
  subclaim set.
- The two misses are a reworded subject ("spans nine countries" / "nine countries contain parts of", 0.63) and a French
  paraphrase (0.03).
- Missed matches cost speed, not correctness.

## Evaluation

Results go to `tests/eval/results/` and `tests/bench/results/`. To run the scripts, see `docs/dev-environment.md`: run
from outside the repo root with `PYTHONPATH=<repo>` and the `.env` minus `TF_VAR_*`.

| Eval | Command | Compared with |
|---|---|---|
| **(a) Overall accuracy**: FEVER, FaVIQ, COVIDFact; dataset evidence | `benchmark_eval.py --mode dataset --variants B0,D1,D2` (only D1/D2 run, since B0 rows are saved) | Saved B0: FEVER 0.635 / 0.487, FaVIQ 0.810 / 0.810, COVIDFact 0.520 / 0.520 (acc / macro-F1); end to end p50 5.41 s |
| (a) live Google search | `benchmark_eval.py --mode live --live-subset 30 --variants B0,D1` | Saved live B0 on the same 150 claims |
| **(b) Decomposition alone**: WiCE test, 358 claims | `decomposition_eval.py`, then `--report` | The no-split floor and the WiCE reference subclaims |
| **(c) Subclaim cache, live**: 24 overlap groups | `subclaim_cache_eval.py` (throwaway local DB only), then `--report` | The same follow-up without the cache: paired latency, verdict agreement |
| **(d) Deployed latency on dev** | `bash tests/bench/run_all.sh decomposition`, then `compare.py` | Saved V3 (live config): mean 9.84 s, p50 9.75, p95 14.28, first word p50 8.85, Apdex 0.80 |

Notes:
- **D1** is the shipped design. **D2** adds CAAFC's separate per-subclaim labelling call (Fig. 6) and scores with
  Algorithm 1 in code. It lives only in the evals and shows whether explicit labels beat the in-prompt rule.
- **Dataset mode** serves a row's evidence on the first search only. It therefore measures the verdict-side effect of
  decomposition, not per-subclaim retrieval; live mode covers retrieval.
- **WiCE reference subclaims** were split by GPT-3.5 and then annotated by people, so treat them as a reference split.
  The NLI scorer cannot judge long, multi-fact hypotheses (a WiCE claim "entails itself" at p = 0.12). Coverage is
  therefore scored only on reference subclaims that the scorer confirms from the original claim, and the report says
  how many those are.
- **The overlap groups** (`tests/data/subclaim_overlap.json`) pair each seed with a different claim that shares one
  fact, and with a near miss of that fact (a changed number, entity, negation or role). Any reuse on a near miss is a
  wrong reuse.

### Results

All local runs used gpt-oss-120b as the decomposer and Llama 4 Scout for everything else. Each comparison is paired:
the same claim ids, against B0 rows saved earlier. Live Google results change between days, which adds noise to live
comparisons.

#### (a) Accuracy and latency, dataset evidence (600 claims)

| Dataset (200 each) | B0 acc / F1 | **D1** acc / F1 | D2 acc / F1 |
|---|---|---|---|
| FEVER (3-way) | 0.635 / 0.487 | 0.635 / **0.521** | 0.605 / 0.573 |
| FEVER binary | 0.869 | 0.869 | 0.910 |
| FaVIQ | 0.810 / 0.810 | 0.810 / 0.810 | 0.780 / 0.777 |
| COVIDFact | 0.520 / 0.520 | **0.600 / 0.593** | 0.480 / 0.471 |
| Split claims | 0.565 (n=170) | **0.641** | 0.512 (n=172) |
| Unsplit claims | 0.691 (n=430) | 0.698 | 0.666 |
| End to end p50 / p90 | 5.41 / 7.94 s | 6.10 / 8.65 s | 7.12 / 9.69 s |
| Paired difference, median / mean | – | +0.58 / +1.54 s | +1.40 / +2.43 s |
| LLM calls / searches per check | 6.44 / 3.07 | 6.64 / 3.60 | 7.75 / 3.72 |

- **Split rate:** 28% of claims split, 1.32 subclaims on average. The decompose call p50 is 0.89 s.
- **D1:** right on 42 claims where B0 was wrong, wrong on 26 where B0 was right (exact McNemar p = 0.068). The gain is
  where expected, on split claims: +7.6 points. Unsplit claims are flat.
- **D2:** the 15/50/85 scores from Algorithm 1 help FEVER binary and NEI F1. They lose on FaVIQ and COVIDFact, because a
  single "unverifiable" label pulls the claim to 50 (B0 right on 68 / D2 right on 48, p = 0.077).

#### (a) Accuracy and latency, live Google search (150 claims)

| Dataset | B0 acc / F1 | D1 acc / F1 |
|---|---|---|
| FEVER (3-way) | 0.640 / 0.463 | **0.700 / 0.572** |
| FEVER binary | 0.889 | 0.944 |
| FaVIQ | 0.640 / 0.640 | **0.740 / 0.740** |
| COVIDFact | 0.600 / 0.597 | 0.600 / 0.599 |

- **Latency:** end to end p50 6.23 → 6.90 s (paired median +0.75 s). Searches 2.90 → 3.25.
- **Stage p50s, before concurrent searches** (s; "searches" is all claims, "split" only claims with 2+ subclaims):

  | Stage | B0 | D1 |
  |---|---|---|
  | Decompose | – | 0.81 |
  | Subclaim searches (split: 0.79 sequential; about 0.4 now that they run concurrently) | – | 0.42 |
  | Planner LLM (turns 3.9 → 2.9) | 3.12 | 2.68 |
  | Planner searches | 1.04 | 0.67 |
  | Verdict (first token 0.35 / 0.32) | 1.07 | 1.16 |
  | Analysis total | 5.25 | 5.92 |
  | Outside the analysis (request, claim, stream setup) | 0.71 | 0.70 |

  Decomposition costs about 1.2 s up front: the decompose call plus the subclaim searches. The planner recovers about
  0.8 s of that, because it starts with evidence. Concurrent searches should cut about 0.35 s more on split claims;
  that estimate comes from (c), since this table wasn't rerun.
- **Split rate:** 41 of 150 claims split.
- **Where the gain comes from:** split claims 0.659 → 0.683, unsplit 0.615 → 0.679. Part of the gain therefore comes
  from searching the clean subclaim text first, or from drift since B0 ran (17 / 9 discordant, p = 0.17).

#### (b) Decomposition alone: WiCE test (358 claims)

| Metric | No split (floor) | gpt-oss-120b | WiCE reference |
|---|---|---|---|
| Coverage | 1.000 | 0.944 | 0.946 |
| Faithfulness | 1.000 | 0.984 | 0.977 |
| Redundancy | 0.000 | 0.008 | 0.006 |
| Mean subclaims | 1.00 | 2.49 | 2.68 |
| Count error vs reference | 1.676 | 0.550 | 0 |
| Unit claims kept whole | 1.000 | 1.000 | 1.000 |
| Starts with a pronoun | 0.182 | 0.175 | 0.165 |

- **Quality:** the split matches the reference on coverage, faithfulness and redundancy, and splits a little less.
- **Reliability and speed:** 0 parse failures. Latency p50 1.23 s, p95 2.83 s; WiCE claims are longer than the
  benchmark claims.

#### (c) Subclaim cache, live (24 groups, 23 shared-fact and 24 near-miss follow-ups)

This was rerun after two changes: subclaim searches now run concurrently, and interactive checks no longer use the
whole-claim cache. The baseline is the same follow-up with the subclaim cache off, which now means no cache at all.

| | Shared fact | Near miss |
|---|---|---|
| Reused | 20/23 | **0/24** (any reuse here would be wrong) |
| Searches per check, cache off → on | 3.26 → 1.91 | 3.46 → 3.33 |
| Analysis total p50, cache off → on | 5.17 → 5.79 s | 6.08 → 6.51 s |
| Paired difference, median | +0.39 s | +0.24 s |
| Same verdict, cache off vs on | 23/23 | 18/24 (no reuse, so this is run-to-run noise) |

- **Concurrent searches:** across both arms, the provider calls plus saving for checks with 2+ subclaim searches went
  from 1.02 s p50 (sequential, previous run) to about 0.62 s, saving about 0.4 s per check. The concurrent calls take
  0.38–0.43 s, about the time of one search; saving sources takes 0.12–0.22 s.
- **Stage times with the cache on:** lookup 0.48–0.59 s (embedding plus NLI), copying a hit 0.10 s. Now that searches
  run concurrently, a hit saves almost no search time, so the lookup is a net cost of about 0.3–0.4 s.
- **Whole-claim cache:** 0 hits on these follow-ups.
- **Conclusion:** the cache is safe and avoids about 40% of searches on overlapping claims, but it costs time.
  Overlapping the lookup with the searches, instead of running them one after the other, would remove most of that
  cost, at the price of spending the searches that a hit would have saved.

#### (d) Deployed latency on dev

Not run: local only for now. The bench configs (V4, V5, the `overlap` scenario) are ready in `tests/bench/`.

#### Other findings

- **Expired tokens.** Long runs failed with 401 `ACCESS_TOKEN_EXPIRED` after about an hour. The refreshed token was
  written to `client.default_headers`, which the OpenAI client copies at creation, so the new token was never sent.
  This bug was pre-existing. It is fixed in `vertex_ai_llama.py` with `client.with_options(...)`, with a regression
  test.
- **Unterminated verdict JSON.** About 5–10% of verdicts are cut off, at the same rate in B0. The regex fallback still
  recovers the score.

### How close this is to CAAFC

- **Same:**
  - the extractor-segmentor rules (Fig. 4);
  - per-subclaim retrieval;
  - Algorithm 1: as a prompt rule in D1, and in code after a Fig. 6 labelling call in D2.
- **Different:**
  - CAAFC retrieves primary sources with dated, chronological Google AI Mode queries (Fig. 5); we use our Google
    search;
  - CAAFC uses a quantized Gemma3-27B; we use gpt-oss-120b;
  - we have no actionability justifier or revision loop.
- **Datasets:** CAAFC evaluates end to end on AVeriTeC, CoverBench, FACTors, DiaHalu and HaluEval, with no standalone
  decomposition eval. WiCE is used here because it has reference subclaims. Factcheck-Bench, FActScore and ClaimDecomp
  are other options.

## GCP: what to do

1. **Decomposer model:** `openai/gpt-oss-120b-maas` is already enabled for project `misinformation-mitigation` and
   answers on the `global` endpoint. The pod's service account already calls Vertex MaaS.
2. **Deploy to dev:** `DEPLOY_ENV=dev ./infrastructure/deploy.sh`. Migration `a9d2e4b7c1f3` runs on pod start and needs
   pgvector, which is already installed for the claim cache.
3. **Flags:** dev deploys with `CLAIM_DECOMPOSITION_ENABLED=true` (terraform-dev). The decomposition bench toggles
   `SUBCLAIM_CACHE_ENABLED` itself and restores both flags afterwards.
4. **Verify:**
   - `analysis_complete` contains `subclaims`, and `timings_ms.decompose` is set.
   - Submit a claim, then a different claim that shares one of its facts. The second shows `subclaim_cache_hits ≥ 1`.
   - In Cloud Logging, look for `Subclaim cache candidate` and `Decompose timings`.
