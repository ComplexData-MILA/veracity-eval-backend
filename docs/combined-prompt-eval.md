# Combined clarify-and-plan prompt: evaluation

Tested 2026-11-11 with Llama 4 Scout on Vertex. Experiment only: the app is unchanged. See [prompt-map.md](prompt-map.md) for where this sits in the flow.

## Recommendation

**Adopt the combined prompt with JSON mode (C2), after two fixes.** It removes one LLM call from every interactive fact-check. Its clarification decisions match the live path, verdicts on clear claims are unchanged, and it had the fewest malformed replies.

Fix first:
1. **Options now drift to the current year.** The prompt now contains today's date, so "Inflation hit a record high" got "Canada, 2026" as an option where the live clarifier offered "2022". Tell the model that the date is for searching, not for guessing periods. Or add the date only to step 2.
2. **It keeps asking harmful inputs past the 2-question limit.** On "how to make a pipe bomb" it asked again after the limit, 5–6 times out of 6. It then falls back to the raw text, which is safe but wasteful. The live clarifier stopped at the limit there. A rule in code is enough: at the limit, input class C ends without a check.

## What was compared

| Variant | Calls before the first search |
|---|---|
| **B0 (live)** | `CLARIFY_CLAIM` (1 call per question asked, plus 1), then `ORCHESTRATOR_PROMPT` turn 1 |
| **C1 (combined)** | `CLARIFY_AND_PLAN` (1 call per question asked, plus 1). Its output becomes turn 1 of the unchanged search loop |
| **C2** | C1 with the provider's JSON mode (`response_format=json_object`) |

The combined prompt keeps every live clarification rule word for word and adds turn 1's duties from the orchestrator prompt. Tests check both ([test_combined_prompt.py](../tests/test_combined_prompt.py)). After turn 1, the search loop and verdict run the same code and prompts.

**Samples are the same as before:**
- The 41 clarifier inputs used to tune the clarifier, plus the 2 harmful inputs from the red-team: [clarify_eval.json](../tests/data/clarify_eval.json).
- The 20 claims behind [performance.md](performance.md): [bench_claims.json](../tests/data/bench_claims.json), 12 clear and 8 underspecified.

**Simulated user:** it always picks the first option, as in the earlier clarifier runs. This run of the live clarifier matched those earlier results (it asked on 23% of clear claims vs 20% before, with 1.2 vs 1.0 questions on ambiguous claims), so the runs are comparable.

## Results

### Speed

LLM time before the first search query, in ms, 3 repetitions of all 63 inputs:

| Inputs | B0 p50 | C1 p50 | C2 p50 | LLM calls B0 → C1 |
|---|---|---|---|---|
| All | 1,848 | 1,417 | 1,419 | 2.78 → 1.75 |
| Benchmark clear claims (12) | 1,207 | **739** | 748 | 2.06 → 1.03 |
| Benchmark underspecified (8) | 1,926 | 1,481 | 1,543 | 3.25 → 2.12 |

Full fact-checks with real Google search, on the 20 benchmark claims:

| | B0 | C1 |
|---|---|---|
| Total time, p50 / p90 | 5.9 s / 10.1 s | 4.7 s / 10.5 s |
| LLM calls per check | 6.25 | 5.15 |
| LLM time before the first search | 1.63 s | 1.10 s |

**The firm number is one fewer call, saving about 0.5 s of LLM time per check from this laptop.** The 1.2 s gain in median total time comes from a single run, and search times vary. On dev, the clarify step measured about 1.9 s per check because LLM calls block the server, so the saving there is probably larger. That hasn't been measured.

### Clarification decisions

Share of inputs that got a question, and mean number of questions:

| Inputs | B0 | C1 | C2 |
|---|---|---|---|
| Benchmark clear | 6% / 0.06 | 3% / 0.03 | 3% / 0.03 |
| Benchmark underspecified | 100% / 1.25 | 96% / 1.12 | 100% / 1.21 |
| Clear + held-out clear | 23% / 0.23 | 17% / 0.17 | 13% / 0.13 |
| Yes/no questions | 33% / 0.33 | 33% / 0.33 | 33% / 0.33 |
| Ambiguous + held-out | 100% / 1.20 | 100% / 1.20 | 100% / 1.27 |
| Topics, questions, opinions | 100% / 1.06 | 100% / 1.06 | 100% / 1.06 |

These checks came out the same for all three variants, at 0 out of 189:
- non-claims checked as the raw text
- loops
- the "do vaccines cause autism?" claim negated
- suggested claims offered for a harmful input
- a missing search query

The first-call decision was the same in all 3 repetitions for 59/62 inputs (B0), 58/62 (C1) and 60/62 (C2).

**Search queries:**
- **Length:** 30 of 189 live queries ran over 12 words, against 0 for the combined prompt.
- **Wording:** combined queries kept more of the claim's names and numbers, 64–68% against 58%.

### Verdict accuracy

| | B0 | C1 |
|---|---|---|
| Clear claims scored true (≥50) | 12/12 | 12/12 |
| Clear claims: same claim text checked | 12/12 identical | |
| Checks failing or with no score | 0/20 | 0/20 |

On the 8 underspecified claims, verdicts disagreed between B0 and C1 on 4–5 of 8. A second B0 run disagreed with the first B0 run on 3 of 8:

| Comparison | Mean score difference | Verdict flips | Same claim text |
|---|---|---|---|
| B0 vs B0 (repeat) | 37.5 | 3/8 | 3/8 |
| B0 vs C1 | 44–46 | 4–5/8 | 1–2/8 |

These verdicts depend mostly on which reading gets picked, and even the live path disagrees with itself here. The gap between the two rows is within that noise, but 8 claims can't rule out a small effect.

### LLM errors

Share of calls with any problem; every one failed open (no crash, no lost check):

| Problem | B0 | C1 | C2 |
|---|---|---|---|
| Malformed JSON | 2 / 525 | 1 / 330 (+1 / 123 in the verdict stage) | **0 / 333** |
| Asked past the 2-question limit | 0 | 6 (harmful inputs only) | 5 (harmful inputs only) |
| Unknown input class (French) | 0 | 2 | 1 |
| Exceptions, empty or filtered replies, no `SEARCH:` match | 0 | 0 | 0 |
| **Any problem** | **0.4%** | **2.7%** | **1.8%** |

The malformed JSON was a missing or extra brace in the combined prompt. The live clarifier's two failures were replies containing several JSON objects. JSON mode removed the malformed output entirely. Excluding the harmful-input issue, C2's rate is 0.3%.

## Round 2: a compact prompt (2026-11-13)

**Goal:** make the combined prompt shorter without losing performance.
- **Candidates** are in [candidate_prompts.py](../tests/eval/candidate_prompts.py). All are system prompts with JSON mode.
- **The user message** is the same for every candidate: date, input and answers fenced as data, and the question-limit line.
- **Inputs** are the same 63, with 3 repetitions each. C2 was re-run on the same day as the reference.

| | C2 (round 1) | U1 (proposed draft) | U2 (compact) | U3 | **U4 / U5** |
|---|---|---|---|---|---|
| Prompt size (chars) | 5,356 | 2,648 | 2,837 | 3,104 | **3,218** |
| LLM time before first search, all inputs p50 | 1.94 s | 2.60 s | 1.75 s | 1.65 s | **1.64 s** |
| Calls per input | 1.76 | 2.32 | 1.67 | 1.67 | **1.69** |
| Asked on clear claims (incl. held-out) | 20% | 80% | 17% | 3% | **3%** |
| Asked on yes/no questions | 33% | 100% | 33% | 44% | **33%** |
| Ambiguous claims: asked / questions | 100% / 1.20 | 100% / 1.97 | 100% / 1.00 | 100% / 1.00 | **100% / 1.00** |
| Benchmark underspecified: asked | 100% | 100% | 96% | 88% | **96%** |
| Topics etc. turned into a claim without asking | 0 | 0 | 6 | 0 | **0** |
| Harmful input got suggested claims | 0 | 6 | 3 | 3 | **0** (enforced in code) |
| Query keeps the claim's names and numbers | 67% | 55% | 55% | 61% | **61%** |
| Calls with a problem the model caused | 2.7% | 100% | 3.5% | 0% | **2.5%** (all corrected by code) |

**U1, the proposed draft, fails on four counts:**
1. It never defines A/B/C, so the class field came back as the literal `"A, B or C"` or the raw input in all 439 calls.
2. It asks on 80% of clear claims, including myths ("The Earth is flat" → "scientific concept or specific context?").
3. Its options are vague ("Other", "Unsure").
4. On topics it brings back the original bug, offering aspects ("origins / causes / symptoms") instead of claims.

Its section 3 (evidence and scoring) has no effect on this call: turn 1 sees no evidence. If its scoring rules are wanted, they belong in `GET_VERACITY`, as a separately evaluated change.

**What each step changed:**
- **U2** keeps U1's structure and adds the tested rules back as one line each. It's faster, but without examples it sometimes turned topics and opinions into claims on its own ("why covid" → checked "COVID-19 vaccines are safe").
- **U3** adds one short example per class, "always ask for B", "never suggest claims for C" and a one-letter class field.
- **U4** adds one line: a change, record or statistic with no place or period needs a question.
- **A rule in code** blanks options on harmful inputs. The model still sometimes fills them in, so the code enforces it.
- **U5** is U4 plus a language line in the user message. U4, an English-only prompt, answered French inputs in English, which would hurt French searches. With the line, all 18 French runs stayed in French.

**Recommended candidate: U5.** It's 40% shorter than C2 and slightly faster. On the 63 inputs it matches or beats C2 on every outcome, and asks far fewer needless questions on clear claims.

Still open:
- **Date drift:** options still sometimes pick the current year ("en 2026").
- **Query wording:** queries keep a little less of the claim's wording (61% vs 67%).
- **No verdict run yet.** Run the verdict stage on U5 before adopting it; the queries are the one area where it could lose accuracy. (Done in round 3: no loss.)

## Round 3: public benchmarks (2026-11-15)

**Question:** do the live prompts (B0) and U5 lose accuracy on labelled public claims, and what does each stage cost?

**Setup** ([benchmark_eval.py](../tests/eval/benchmark_eval.py)):
- **Datasets:** FEVER-300, FaVIQ and COVIDFact, the same files used for the factcheck-eval runs (`qwen-factcheck-vllm/data`).
- **Sample:** 200 claims per dataset, stratified by label, seed 7.
- **COVIDFact rows:** the 50 with no usable evidence are excluded.
- **Two evidence modes:**
  - **Dataset evidence (all 600 claims):** the first search returns the dataset's own evidence snippets, and later searches return nothing. This keeps the results comparable to the earlier runs.
  - **Live Google search:** 50 claims per dataset, a stratified subset of the 600.
- **Scoring:** score ≥50 counts as SUPPORTS. For FEVER's 3 labels, a score of 35–65 counts as NOT ENOUGH INFO.
- **Clarifying questions:** every question was skipped and counted. These are complete claims, so the ideal is no questions at all.
- **Timings** come from the pipeline's `timings_ms` (`planner_llm`, `web_search`, `verdict`, `total`) plus the clarify or plan call(s).

### Accuracy

Accuracy / macro-F1. The reference column is factcheck-eval: Scout, a single call, evidence supplied, full datasets.

| Dataset | B0, dataset evidence | U5, dataset evidence | B0, live (n=50) | U5, live (n=50) | Reference |
|---|---|---|---|---|---|
| FEVER-300 (3 labels) | 0.635 / 0.487 | 0.625 / 0.487 | 0.64 / 0.46 | 0.68 / 0.53 | 0.733 / 0.658 |
| FEVER, SUPPORTS/REFUTES only | 0.869 | 0.876 | 0.89 | 0.92 | |
| FaVIQ | 0.810 / 0.810 | 0.815 / 0.815 | 0.64 / 0.64 | 0.74 / 0.74 | 0.821 / 0.829 |
| COVIDFact | 0.520 / 0.520 | 0.545 / 0.545 | 0.60 / 0.60 | 0.48 / 0.48 | 0.565 / 0.574 |

- **U5 matches B0.**
  - With dataset evidence, each got 27–31 claims right that the other got wrong (McNemar p = 0.69). The labels agree on 537 of 600 claims.
  - On the live subset the split was 10 vs 11 (p = 1.0). The live gaps per dataset are within noise at n=50.
- **Both are close to the reference on FaVIQ and COVIDFact.**
- **FEVER trails the reference on 3 labels.** The pipeline rarely gives a middle score: only 2 of 55 NOT ENOUGH INFO claims landed in the 35–65 band, and 38 were scored false. On SUPPORTS and REFUTES alone it scores 0.87–0.88.

### Clarifying questions on benchmark claims

Share of claims that got a question / share whose checked claim text was rewritten:

| Dataset | B0, dataset evidence | U5, dataset evidence | B0, live | U5, live |
|---|---|---|---|---|
| FEVER-300 | 28% / 16% | 30% / 13% | 24% / 16% | 24% / 10% |
| FaVIQ | 32% / 30% | 26% / 24% | 28% / 28% | 22% / 28% |
| COVIDFact | 51% / 50% | 34% / 50% | 54% / 58% | 34% / 48% |

**Both prompts ask far too often on these claims, and U5 asks a little less.** There are three causes:
- **COVIDFact claims read like topics.** They are lowercase headline fragments.
- **FaVIQ claims are lowercased and sometimes mistyped** ("us first went into space in 1957" got the question "Which country is meant by 'us'?").
- **Both prompts ask needless "which X" questions.** For example, "Faith Evans made her first album in Paris" got "Which city?".

After a skip, the claim is usually rewritten, and sometimes with an added fact ("Shonen Jump is published in a continent" became "…in Asia"). Checks that got a question scored lower than those that didn't (0.54–0.56 vs 0.71–0.72 with dataset evidence). However, harder claims are the ones that get questions (COVIDFact, FEVER NOT ENOUGH INFO), so the questions themselves can't be blamed from this data. On FaVIQ alone, accuracy was the same with and without a question.

In the app, a user can answer instead of skipping. Benchmark inputs can't.

### Time per check

p50 (p90) in seconds:

| Stage | B0, dataset evidence | U5, dataset evidence | B0, live | U5, live |
|---|---|---|---|---|
| Clarify / plan call(s) | 0.65 (1.59) | 0.85 (1.79) | 0.64 (1.55) | 0.87 (1.76) |
| Search-planning LLM turns (`planner_llm`) | 3.25 (5.50) | 2.22 (4.07) | 3.11 (5.00) | 1.93 (2.95) |
| Web search | (served locally) | (served locally) | 1.04 (1.67) | 0.98 (1.58) |
| Verdict | 1.03 (1.38) | 1.03 (1.40) | 1.07 (1.50) | 1.09 (1.54) |
| Analysis total (`timings_ms.total`) | 4.40 (6.69) | 3.30 (5.31) | 5.22 (8.07) | 4.01 (5.84) |
| **End to end** | **5.41 (7.91)** | **4.49 (6.53)** | **6.22 (9.23)** | **5.13 (7.19)** |
| LLM calls per check (mean) | 6.44 | 5.19 | 6.25 | 4.78 |
| Searches per check (mean) | 3.07 | 2.88 | 2.90 | 2.51 |

- **U5 saves about 1 s per check at the median and 1.4–2 s at p90.**
- **The U5 call itself is about 0.2 s slower** than the live clarify call, because it also writes the claim and the first query.
- **The saving is in the search loop.** U5 removes the separate turn-1 call and needs slightly fewer search turns.
- **Search-planning turns are the largest stage in both variants.** They take longer than the web search and the verdict combined.
- **Google response time alone (`provider_ms`) was not captured** in this run. The log line is at INFO level, and the script now sets that level. The `web_search` stage above covers search time.

### LLM errors

All runs completed with a score for every check.

| Problem | B0 | U5 |
|---|---|---|
| Malformed JSON, dataset evidence | 19 / 3,863 calls | 0 / 3,714 |
| Malformed JSON, live | 4 / 937 | 0 / 867 |
| Other schema problems (unknown class, options on class C, search with no query) | 0 | 4 / 3,714, all corrected in code |

Partway through the first run, the Vertex access token expired (it lasts about 1 hour), and 434 checks failed with a 401 error. Those rows were removed and re-run with a fresh token, so they aren't counted above. A long eval or a long-lived worker needs to refresh this token.

### Verdict on U5

**U5 passes the accuracy check from round 2:** it is no worse than the live path on 600 labelled claims and is about 1 s faster.

**Before adopting it, cut needless questions on complete claims.** Both prompts ask on 25–50% of benchmark claims. Ideas to test:
- "Never ask about capitalisation, typos or lowercase text."
- "Never ask which X when the claim names X."

Then re-run this benchmark.

## Limits

- **Latency was measured from a laptop to Vertex**, one request at a time, not on dev. The relative difference holds; the absolute numbers will differ.
- **The verdict comparison is small:** 20 claims, one run per variant, plus one control run.
- **There are no false claims in the benchmark set,** so it can't show whether false claims are still caught. The clear claims are all true.
- **The simulated user always picks the first option,** which differs between variants, so underspecified claims often end up as different claims.

## Adopted (2026-11-16)

**Update:** the prompt is now V3, not U5. U5 added facts to checked claims and asked many needless questions; see [multiturn-eval.md](multiturn-eval.md). Prompt texts can also be changed without a redeploy: see [prompt-overrides.md](prompt-overrides.md).

U5 is now live behind `USE_COMBINED_MULTI_PROMPT` (default `True`). Setting it to `False` restores the separate `CLARIFY_CLAIM` call and turn 1, unchanged.

- **The call:** `/claims/clarify` makes one JSON-mode call with `AnalysisPrompt.CLARIFY_AND_PLAN`. This is U4's system prompt plus U5's user message.
- **Harmful inputs:** options are blanked in code.
- **When the claim is ready:** the call's `REASON`/`SEARCH` reply is kept in memory, keyed by language and claim text. It is used once and expires after 15 minutes.
- **The fact-check:** when it starts on that same claim, the search loop uses the stored reply as turn 1 and skips that LLM call. `timings_ms.planned_turn` is 1 when this happens.
- **Fallbacks:** if there is no stored reply (another pod, a restart, an edited claim, a cache hit or a decomposed claim), turn 1 runs as before.

No frontend or database change was needed. Tests are in [test_combined_multi_prompt.py](../tests/test_combined_multi_prompt.py).

Not done yet:
- **Cache first:** the semantic cache is still checked after clarify.
- **Cache reset:** `params_hash` still covers `ORCHESTRATOR_PROMPT`, which stays in use for later turns, so the existing cache stays valid.

## Round 4: the shipped flow on public benchmarks (2026-11-17)

`SHIPPED` is the code as it now ships: V10 (`CLARIFY_AND_PLAN`), the unnamed-subject rule in code, and the harm screen before every check. It ran on the same 600 claims as Round 3 with dataset evidence, and on the same 150 with live Google search. Questions were skipped, as in Round 3. Three checks hit Vertex 429s and were re-run.

**Accuracy** (acc / macro-F1):

| Dataset | B0 (old flow) | U5 (first combined) | **SHIPPED** |
|---|---|---|---|
| FEVER, dataset evidence | 0.635 / 0.487 | 0.625 / 0.487 | 0.625 / 0.488 |
| FaVIQ, dataset evidence | 0.810 / 0.810 | 0.815 / 0.815 | 0.795 / 0.795 |
| COVIDFact, dataset evidence | 0.520 / 0.520 | 0.545 / 0.545 | 0.510 / 0.509 |
| FEVER true/false only, dataset evidence | 0.869 | 0.876 | 0.855 |
| FEVER, live | 0.640 / 0.463 | 0.680 / 0.527 | 0.700 / 0.513 |
| FaVIQ, live | 0.640 / 0.640 | 0.740 / 0.739 | 0.740 / 0.739 |
| COVIDFact, live | 0.600 / 0.597 | 0.480 / 0.480 | 0.660 / 0.653 |

**Paired tests (McNemar).** On dataset evidence, SHIPPED is level with B0 (35 claims right only for B0, 28 only for SHIPPED, p = 0.45). With live search it is ahead (6 vs 17, p = 0.03). That is one test on 150 claims, so read it as "no worse", not as a proven gain.

**Questions and rewrites on benchmark claims** (dataset evidence; ideal is none):

| Dataset | B0 asked / rewritten | U5 asked / rewritten | **SHIPPED asked / rewritten** |
|---|---|---|---|
| FEVER | 28% / 16% | 30% / 13% | 9% / 2% |
| FaVIQ | 32% / 30% | 26% / 24% | 8% / 5% |
| COVIDFact | 51% / 50% | 34% / 50% | 22% / 16% |

**Time and calls** (p50; dataset evidence, then live):

| | B0 | U5 | **SHIPPED** |
|---|---|---|---|
| End to end | 5.41 s / 6.22 s | 4.49 s / 5.13 s | 5.38 s / 6.23 s |
| Clarify/plan call | 0.65 s | 0.85 s | 0.86 s |
| Harm screen | none | none | 0.48 s |
| LLM calls per check (dataset) | 6.44 | 5.19 | 6.21 |
| Planned first search used | none | | 600 of 600, 150 of 150 |
| Malformed JSON | 19 of 3,863 calls | 0 | 0 of 3,723 calls |
| Failed checks | 0 | 0 | 0 |

The harm screen takes back most of the time the combined call saved, so SHIPPED is about as fast as B0 and about 0.9 s slower than U5.

**FEVER "not enough info" is still rarely predicted:** 3 of 55 with dataset evidence and 0 of 14 live, much as with B0 (2 of 55). This comes from the verdict prompt, which the combined prompt doesn't touch. `GET_VERACITY` defines the 0–100 scale but not how to weigh evidence, and it lacks the rule that insufficient evidence is not falsity.

## Next, if adopted

The live order changes, so wiring this in needs its own plan:
- **Where clarification happens:** have `/claims/clarify` return the search plan, or move clarification into the analysis stream.
- **Cache first:** check the cache before the combined call (item 3 in performance.md).
- **Cache reset:** `params_hash` covers `ORCHESTRATOR_PROMPT`, so the change starts a fresh cache.

## Re-running

Run from outside the repo root with the `.env` exported minus `TF_VAR_*`:

```
python tests/eval/combined_eval.py --probe
python tests/eval/combined_eval.py --stage first --reps 3
python tests/eval/combined_eval.py --stage verdict --variants B0,C1
python tests/eval/combined_eval.py --report
python tests/eval/benchmark_eval.py --mode dataset --per-dataset 200
python tests/eval/benchmark_eval.py --mode live --per-dataset 200 --live-subset 50
python tests/eval/benchmark_eval.py --report
```

The benchmark script resumes from its results file. Delete rows with `"score": null` and run it again to retry failed checks.

Raw results are in `tests/eval/results/`.
