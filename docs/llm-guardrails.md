# LLM guardrails

How the fact-checker protects itself against bad inputs and bad outputs. Structured around the OWASP Top 10 for LLM Applications (2025).

The main risk here is not a chatbot saying something rude. It is a **wrong verdict**, because one verdict can be cached and served to other users. The system has no tools with side effects, so the model cannot act on a successful injection beyond changing the text it writes.

## What is in place

**Untrusted content (LLM01 prompt injection, LLM04 poisoning)**
- Search results are flattened to one line and stripped of our source labels, so a web page cannot pose as a separate, highly credible source.
- Search results, claims, answers and follow-up history go inside data tags with a random name that the text cannot know or close (spotlighting). The model is told that text inside a source cannot add sources, set credibility, or retract other sources.
- Invisible characters that can hide instructions are removed.
- Rules come after the data, and a short reminder sits on the user's latest turn, because this model weighs what it read most recently.

**Shared cache (LLM04)**
- A verdict is not cached if the claim or its sources show injection markers. This limits a poisoned verdict to the user who triggered it. The event is logged as a warning.

**Follow-up chat (LLM01, LLM07, LLM09)**
- The assistant only discusses the fact-check. It declines other tasks, role-play and persuasive writing for a claim, and won't change a verdict under pressure.
- A random code opens the system prompt. A reply containing it is replaced before reaching the user. The prompt holds no secrets, so this is a second layer and not a protection to rely on.
- The start of each reply is held back briefly, so a blocked reply is replaced with a clear message rather than shown as a fragment.

**Clarifier (LLM01)**
- Requests for how to cause harm, and attacks on groups of people, get no suggested claims. The user is asked for a factual claim.

**Output integrity (LLM05)**
- A verdict with no score is an error. It used to be reported as 0% true, so a truncated reply looked like a false claim.
- Vertex Llama Guard stays on for input and output. The frontend shows model text as plain text, so it cannot run as HTML.

**Cost and abuse (LLM10)**
- Per-user limits on all interactive LLM routes: 30 a minute and 500 a day by default. Batch keeps its 100-claim cap and monthly limit.
- Length limits on claims, context and follow-ups, and a cap on output tokens.

**Information exposure (LLM02)**
- Stream errors show a generic message. Details go to the logs only.

**Access**
- Editing domain credibility needs an admin account (`ADMIN_AUTH0_IDS`). It used to need no login.

## Testing

A red-team of 35 live cases against the real pipeline and model, with the database and search faked.

| Attack | Before | After |
|---|---|---|
| Forged source on an obscure claim (verdict out of 100) | 100 | 0–20 (5 runs) |
| System prompt leak, direct and by translation | leaked | 0 of 5 |
| Off-topic use (writing code) | complied | 0 of 5 |
| Role-play and fake "assistant instruction" | complied | 0 of 5 each |
| Instruction planted in a source, follow-up | resisted | 0 of 5 |
| Poisoned verdict written to the shared cache | not tested | blocked |
| Harmful clarifier input | suggested claims | no suggestions |

All 8 harmless control cases passed: true claims still score high, and normal follow-ups are not refused. Fact-check analysis already resisted plain "ignore your instructions" attacks. Forged structure was what worked.

## Limitations

- **No defence here is complete.** Published work shows that prompt defences which look strong against fixed tests can fall to adaptive attackers. These results cover a small set of known attacks.
- **False content is not injection.** A plausible page that simply states something false can still mislead the verdict. Consistency checks across sources would be the next defence.
- **Injection markers are easy to evade.** They are a tripwire and a logging signal.
- **Self-injection still works.** A user can make replies in their own conversation repeat text placed in their claim or context. It only reaches that user, and it cannot change a verdict that others see.
- **Rate limits are per pod.** They need a shared store if the API runs more than one replica.

## Open items

1. **Auth tokens and follow-up text travel in URLs** on stream requests, so they can end up in proxy and server logs. Move to a POST or a fetch-based stream.
2. **Some read routes have no login:** batch results, word cloud, clustering, claim totals and domain lookups.
3. **Any user can set `bypass_cache` or `eval_mode`.** `bypass_cache` also refreshes the shared cache entry. Restrict both to admins.
4. **Stream responses hard-code `Access-Control-Allow-Origin: *`,** which bypasses the CORS allow-list.
5. **Many routes return `str(e)` in HTTP 500 details.** Replace with generic messages.
6. **The LLM client is synchronous,** so a slow call blocks other requests on the pod.
7. Add the red-team set to CI, and alert on the guardrail warnings in the logs.
