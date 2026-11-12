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

## Limits

- **Latency was measured from a laptop to Vertex**, one request at a time, not on dev. The relative difference holds; the absolute numbers will differ.
- **The verdict comparison is small:** 20 claims, one run per variant, plus one control run.
- **There are no false claims in the benchmark set,** so it can't show whether false claims are still caught. The clear claims are all true.
- **The simulated user always picks the first option,** which differs between variants, so underspecified claims often end up as different claims.

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
```

Raw results are in `tests/eval/results/`.
