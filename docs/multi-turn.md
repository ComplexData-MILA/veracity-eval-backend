# Multi-turn fact-checking (v1)

Fact-checking is now a short conversation instead of a single request:

1. **Clarify before checking.** If the input isn't a claim yet, or a claim is missing a detail that would change the verdict, the system asks one question first.
2. **Follow up after the result.** Users can ask questions about a verdict. The system answers from the evidence it already has, runs a new search, or offers to re-check a revised claim.

## How it works

**Clarification (before the check)**
- The system first decides whether the input is a claim at all. A yes/no question counts as one ("is coffee bad for you" becomes "Coffee is bad for you").
- **Topics, open questions and opinions** ("why covid", "climate change") can't be checked, so the system asks which claim the user means and offers 2–4 complete claims on the subject. Picking one ends clarification. If the user answers with a narrower topic instead, it asks once more about that topic.
- **For claims**, the system asks only when the claim could be read in more than one way and those readings would likely get *different* verdicts. Typical gaps: time period, place, which person or organisation, which statistic, or who said a quote. Clear claims, and claims that get the same verdict however they are read, go straight to the check.
- Each question comes with 2–4 concrete options, plus a "Type my own answer" button that moves to the text box. When several details are missing, one question tries to cover them together, to keep the number of questions down.
- The user's answers are written into the claim itself, so it reads on its own (e.g. "Unemployment doubled" becomes "Unemployment doubled in Canada during the COVID-19 pandemic"). Writing the answers into the claim also keeps the semantic cache working correctly.
- If a detail is still missing after 2 questions, the system picks the most likely reading, writes it into the claim, and shows it to the user as an assumption. If there is still no claim, it checks a common claim on the subject and shows that claim first. The API still accepts a skipped answer, which ends the questioning the same way, but the chat no longer offers one.
- Requests for how to cause harm, and attacks on groups of people, get no suggested claims: the user is asked for a factual claim instead.
- The system asks at most 2 questions per claim.
- The clarification step saves nothing. The client sends back the earlier questions and answers on each call, and nothing is stored until the claim is submitted.
- If clarification fails (LLM error or unreadable output), the claim is checked as written, so this step never blocks a fact-check.

**Follow-ups (after the result)**
- Every follow-up is first routed to one of three paths:
  - **Answer:** reply from the analysis and the sources already gathered.
  - **Search:** run one extra web search, then reply. The verdict does not change.
  - **Re-check:** the user changed the claim (different place, period, person or number). The system says a new check is needed and offers a button that starts one on the revised claim, without asking clarifying questions again.
- Replies use the claim, the verdict, the sources and the recent conversation, and cite sources by title. When the sources don't cover something, the reply says so.
- Evidence found during follow-ups is stored under the analysis and marked as follow-up evidence. It is never reused as cached evidence for a future verdict.
- Batch, evaluation-mode and experiment runs skip clarification and work as before.
- `MULTITURN_ENABLED=false` (env var, default `true`) turns both parts off: `/claims/clarify` returns the claim as ready without an LLM call, and follow-ups skip the router and answer from the existing sources. Flip it with `kubectl set env`, which restarts the pod with no redeploy.

**Basis in the literature:** ask only when it matters (CLAM; Zhang & Choi, *Clarify When Necessary*, NAACL 2025); make clarification an explicit step, because LLMs rarely ask on their own (*Knowing but Not Showing*, 2026); check that the input is verifiable first (Claimify; CheckThat! check-worthiness criteria); make each option settle as much as possible, so fewer questions are needed (expected information gain: *Active Task Disambiguation with LLMs*, ICLR 2025); rewrite claims to stand alone (CheckThat! 2025 claim normalization; Claimify); decide whether to answer now or search more (FIRE, NAACL 2025).

## Testing done

- **Unit tests:** clarification parsing, the round cap, skip handling and fail-open behaviour; the follow-up router's three paths and its fallback; the ownership check; excluding follow-up evidence from cache replays.
- **Clarifier tuning** (live, 41 inputs, 12 held out from tuning): all 17 topics and open questions, 5 of them held out, end in a complete claim, nearly always after one question. Before tuning, none of the 12 tested did. Ambiguous claims average 1.0 questions, down from 1.4.
- **Live end-to-end** (Llama 4 Scout, Google Search, a fresh pgvector DB): 31/31 checks pass. The system asked on 8/8 underspecified claims and 1/8 well-specified ones. The three follow-up paths, re-check and cache hits on clarified claims all work.
- **Browser test** of the full UI flow: options, free-text answer, skip, analysis, the three follow-up types, re-check, starting a new claim.

## Assumptions and limitations

- **Ambiguity is judged by a single LLM call**, not by a measured score. It still sometimes asks when every reading gets the same verdict: 2 of 4 held-out clear claims, though none of the 6 used for tuning. Some options can be generic or name guessed people and events.
- **Suggested claims come from the model.** They reflect what it thinks people commonly say on a subject and may be false or dated, which is what the check is for.
- **Assumed defaults are not always sensible.** The "most likely reading" is the model's guess, e.g. "United States" or "the Great Depression" for "Unemployment doubled".
- **Clarification history lives in the client.** It is not stored, so it can't be analysed or resumed later.
- **Routing can be wrong.** A misrouted follow-up gets a weaker answer, not a failure: anything unclear falls back to "answer".
- **Follow-up evidence is mixed in with the original evidence.** Sources from follow-up searches appear in the analysis's source list. The UI does not yet label them.
- **No verdict changes inside the chat.** A changed claim always means a new, separate check.
- **Clarification adds one LLM call** (about 1–3 s) before every interactive check, and each follow-up adds a routing call.
- **English and French only**, like the rest of the pipeline. Re-checks go straight to analysis without clarification.

## Suggested next steps

1. Tune the clarification prompt on a larger labelled set (e.g. AmbiFC and CheckThat 2025 samples). Track how often it asks on ambiguous vs. clear claims and how users respond to questions (skip rate, option vs. free text).
2. Replace the single-call ambiguity judgement with a measured one: sample several readings and ask only when they disagree, reusing the semantic cache's entailment model.
3. Store clarification turns and route decisions, both for analytics and so a conversation can be resumed.
4. Label follow-up sources in the UI, or keep them out of the analysis's source list.

See [LLM guardrails](llm-guardrails.md) for how this feature is protected.
