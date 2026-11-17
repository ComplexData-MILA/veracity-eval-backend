# Changing prompts without a redeploy

Any prompt in `AnalysisPrompt` ([prompts.py](../app/core/llm/prompts.py)) can be replaced on a running cluster. The change is live in about 2 minutes, with no build, deploy or restart. `prompts.py` stays the default, and git stays the record of every change.

## Quick start: try a prompt change on dev

**You need:** `gcloud` logged in with access to the `misinformation-mitigation` project, `kubectl`, and Python.

1. **Switch to the dev branch:**
   ```
   git switch dev-env && git pull
   ```
   Work on `dev-env`. Every dev deploy re-applies `dev.json` from this branch, so a change pushed anywhere else is overwritten by the next deploy.
2. **Edit [dev.json](../infrastructure/prompt-overrides/dev.json).** It holds the live combined prompt (`CLARIFY_AND_PLAN` and `CLARIFY_AND_PLAN_INPUT`). See [The file](#the-file) for the format.
3. **Check it.** It should print `OK`:
   ```
   python -m app.core.llm.prompt_overrides check infrastructure/prompt-overrides/dev.json
   ```
4. **Commit and push it.** The apply script refuses files that are uncommitted or unpushed.
   ```
   git add infrastructure/prompt-overrides/dev.json
   git commit -m "Try new clarify prompt on dev"
   git push
   ```
5. **Apply it.** This also switches your `kubectl` context to the dev cluster.
   ```
   DEPLOY_ENV=dev bash infrastructure/apply-prompt-overrides.sh infrastructure/prompt-overrides/dev.json
   ```
6. **After about 2 minutes, confirm it loaded:**
   ```
   kubectl -n misinformation-mitigation logs deploy/misinformation-mitigation-api -c misinformation-mitigation-api | grep "Prompt overrides"
   ```
   The latest line should say `applied`. If it says `rejected`, it gives the reasons, and dev keeps its previous prompts.
7. **Try it** on the dev site or at `https://api-dev.veri-fact.ai`.

**To undo,** revert your edit to `dev.json`, then repeat steps 4–5.

**Once a change works,** move the text into `prompts.py` in a normal pull request, so it reaches prod through code review.

**Before trying a clarification prompt on dev,** you can also score it offline. Add it as a variant under `TUNED` in [candidate_prompts.py](../tests/eval/candidate_prompts.py), then run [multiturn_eval.py](../tests/eval/multiturn_eval.py); see [multiturn-eval.md](multiturn-eval.md).

## The file

The file maps prompt names to their text. Each prompt can be one string, or a list of lines joined back together with nothing in between:
```json
{"CLARIFY_AND_PLAN": [
  "You are the first step of a fact-checking service. Your only job is to find out WHICH claim the ",
  "user wants checked, then prepare it and plan its first web search.\n",
  "..."
]}
```
- **Line breaks:** a `\n` at the end of a line is a real line break in the prompt. A line without one runs straight into the next, so keep its trailing space.
- **Template fields:** a template prompt must keep exactly the same `{fields}`. For example, `CLARIFY_AND_PLAN_INPUT` must keep `{claim}`, `{date}`, `{turns}` and `{rules}`. Literal braces in a template are written `{{ }}`.
- **Adding a prompt:** this adds a prompt at its current text, ready to edit:
  ```
  python -m app.core.llm.prompt_overrides sync infrastructure/prompt-overrides/dev.json GET_VERACITY
  ```
- **Removing a prompt:** a name that isn't in the file uses its text from `prompts.py`, and `{}` restores them all.

**What can be overridden:**
- **Allowed:** any `AnalysisPrompt` text. Each override takes effect on the next request.
- **Protected, so the file is rejected:** the injection and harmful-request defences, which change only through code review:
  - `UNTRUSTED_SOURCES(_FR)`
  - `FOLLOWUP_RULES`
  - `FOLLOWUP_REMINDER`
  - `FOLLOWUP_ROUTER`
  - `HARM_CHECK`
  - `CLARIFY_HARMFUL_REFUSAL(_FR)`
- **Accepted but no effect:** nothing calls these, so overriding them changes nothing:
  - `CLAIM_ANALYSIS(_FRENCH)`
  - `CLAIM_DETECTION`
  - `GET_ANTH_CONFIDENCE(_MOD)`
  - `IDEAL_PROMPT`
  - `REMOVE_SOURCES`
  - `SUMMARIZE_SEARCH`
- **Cache:** overriding a fact-check or verdict prompt (`ORCHESTRATOR_PROMPT`, `GET_VERACITY`) starts a fresh verdict cache, as a code change would.
- **Size:** each prompt is capped at 20,000 characters.

## How dev.json stays in sync with prompts.py

- **In git:** a pre-commit hook copies `prompts.py` changes into `dev.json` whenever `prompts.py` is committed. An entry you have edited is kept, and the hook prints a note. Install the hooks once with `pre-commit install`.
  - A prompt change committed without the hooks leaves `dev.json` behind.
  - To catch up, run `python -m app.core.llm.prompt_overrides sync infrastructure/prompt-overrides/dev.json`.
- **On the cluster:** `DEPLOY_ENV=dev bash infrastructure/deploy.sh` re-applies `dev.json` after every deploy, so the cluster never keeps an older copy over the new prompts.

## Prod

`prod.json` stays `{}`, and prompt changes reach prod through `prompts.py`. If prod ever needs an override, the steps are the same with `prod.json` and `DEPLOY_ENV=prod`. The script only applies prod from a commit on `main`.

## How it works

- **Storage:** the file is stored in the `veracity-prompt-overrides` ConfigMap and mounted read-only into the pod at `/app/prompt-overrides/`. Terraform creates it as `{}` and then leaves its contents alone.
- **Reloading:** the app ([prompt_overrides.py](../app/core/llm/prompt_overrides.py)) checks the file every 30 seconds and applies it when it changes. With several pods, each picks up a change within the same 30-second window.
- **Bad files:**
  - A file that fails validation is ignored as a whole, and the pod keeps its last good prompts.
  - If the pod restarts while a bad file is in place, it starts on the shipped prompts.
  - Deleting the ConfigMap also restores the shipped prompts.
- **Audit:** the apply script records the source commit on the ConfigMap. The pod logs the sha of every file it applies or rejects.
- **Flags are separate:** feature flags such as `USE_COMBINED_MULTI_PROMPT` are env vars, changed with `kubectl set env`, which restarts the pod.
