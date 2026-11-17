# Changing prompts without a redeploy

Any prompt in `AnalysisPrompt` ([prompts.py](../app/core/llm/prompts.py)) can be replaced at runtime from a Kubernetes ConfigMap. The pod picks up a change within about 1–2 minutes, with no image build, deploy or restart. The texts in `prompts.py` stay the defaults, and git remains the record of what shipped.

## How it works

1. **The ConfigMap.** It is called `veracity-prompt-overrides` and holds one file, `prompts.json`, that maps prompt names to their text. Terraform creates it with `{}` (no overrides) and then ignores its contents, so terraform never undoes a change.
2. **The mount.** The file is mounted as a directory at `/app/prompt-overrides/`, and `PROMPT_OVERRIDES_PATH` points to it. A directory mount is required: kubelet only updates files in place when the mount is not a `sub_path`.
3. **Reloading.** The app checks the file every 30 seconds and applies it when it changes ([prompt_overrides.py](../app/core/llm/prompt_overrides.py)).
4. **Restoring a prompt.** A name that is not in the file uses its shipped text from `prompts.py`. Removing a name, or setting the file back to `{}`, restores the shipped text.
5. **Bad files.** A file that fails validation is ignored as a whole, and the last good prompts stay in place. The pod logs `Prompt overrides <sha> rejected` with the reasons.
6. **The cache.** The semantic cache key reads the prompts when it's computed. Overriding a fact-check or verdict prompt therefore starts a fresh cache, just as a code change would.

Validation checks three things:
- Every name is an existing prompt.
- Every value is a non-empty string.
- A prompt that is a format template keeps exactly the same `{fields}`. For example, `CLARIFY_CLAIM` must keep `{claim}`, `{turns}` and `{ask_rule}`. Literal braces in a template are written `{{ }}`. Prompts that aren't templates, such as `CLARIFY_AND_PLAN`, take any text.

## Changing a prompt

1. **Edit the file for the environment:** [infrastructure/prompt-overrides/dev.json](../infrastructure/prompt-overrides/dev.json) or `prod.json`. A value is the prompt text, or a list of strings joined with nothing between them, so long prompts can be wrapped:
   ```json
   {"CLARIFY_AND_PLAN": [
     "You are the first step of a fact-checking service. Your only job is to find out WHICH claim the ",
     "user wants checked, then prepare it and plan its first web search.\n",
     "..."
   ]}
   ```
   Line breaks in the prompt are the `\n` at the end of a string. A string that ends without one carries on into the next string.

   **`dev.json` mirrors the combined prompt** (`CLARIFY_AND_PLAN` and `CLARIFY_AND_PLAN_INPUT`) from `prompts.py`, so it shows what is live and is the place to try a change. Edit the text there to test a new version.
   - **Keeping it in sync:** a pre-commit hook runs `sync` whenever `prompts.py` is committed, and copies the new shipped text into `dev.json`. An entry you have changed is kept, and the hook says so. Install the hooks once with `pre-commit install`. The hook compares against the last commit, so a prompt change committed without the hooks leaves `dev.json` behind; run the command below by hand to fix it.
   - **Keeping the cluster in sync:** `DEPLOY_ENV=dev deploy.sh` re-applies `dev.json` after every deploy, so the ConfigMap never pins an older copy over the new image's prompts.
   - **Adding another prompt** at its shipped text, ready to edit:
     ```
     python -m app.core.llm.prompt_overrides sync infrastructure/prompt-overrides/dev.json GET_VERACITY
     ```
   - **Once a change has proven itself,** move it into `prompts.py`. The hook then sees the entry match the shipped text again.

   `prod.json` stays `{}` unless prod needs an override.

   **Which prompts can be overridden:** any attribute of `AnalysisPrompt` except the protected ones listed under Security. Every caller reads the prompt when it runs, so an override takes effect on the next request. `CLAIM_ANALYSIS(_FRENCH)`, `CLAIM_DETECTION`, `GET_ANTH_CONFIDENCE(_MOD)`, `IDEAL_PROMPT`, `REMOVE_SOURCES` and `SUMMARIZE_SEARCH` are accepted but have no effect, because nothing calls them.
2. **Check it locally:**
   ```
   python -m app.core.llm.prompt_overrides check infrastructure/prompt-overrides/dev.json
   ```
3. **Evaluate clarification prompts first.** Add the text as a variant in [candidate_prompts.py](../tests/eval/candidate_prompts.py) under `TUNED`, then run [multiturn_eval.py](../tests/eval/multiturn_eval.py) against the shipped prompt. See [multiturn-eval.md](multiturn-eval.md).
4. **Commit and push the file.** For prod, merge it to `main` first. Then apply it:
   ```
   DEPLOY_ENV=dev bash infrastructure/apply-prompt-overrides.sh infrastructure/prompt-overrides/dev.json
   ```
   Like `deploy.sh`, the script refuses files that are uncommitted or unpushed, and refuses prod from any branch other than `main`. It validates the file, applies it, and records the commit on the ConfigMap.
5. **Confirm it within about 2 minutes:**
   ```
   kubectl -n misinformation-mitigation logs deploy/misinformation-mitigation-api -c misinformation-mitigation-api | grep "Prompt overrides"
   ```
   It should show `Prompt overrides <sha> applied: [...]`. A rejected file logs `rejected` with the reasons.
6. **To roll back,** remove the entry, then re-add it at its shipped text with the `sync` command above if `dev.json` should keep mirroring it. Commit and apply the file. `{}` restores every shipped prompt.

## Security

**Failure behaviour.**
- **A bad file** is rejected as a whole, and the running pod keeps its last good prompts.
- **A restart with a bad file in place** starts on the shipped prompts, not the last good overrides, and logs the rejection.
- **Deleting the ConfigMap** restores the shipped prompts.
- **Partial updates can't happen.** A reload swaps every prompt in one step on the event loop, so no request sees half of an update.
- **More than one pod:** each pod reloads on its own schedule, so pods can disagree for up to about 30 seconds.

## Things to know

- **Save tested prompts in git.** Once an override has proven itself, move the text into `prompts.py` and clear the ConfigMap. Overrides live only in the cluster, so a new cluster or a manual ConfigMap deletion would lose them.
- **Every pod checks the file on its own,** so with more replicas each pod picks up a change within the same 30-second window.
- **Flags are separate.** Feature flags such as `USE_COMBINED_MULTI_PROMPT` are still env vars changed with `kubectl set env`, which restarts the pod.
