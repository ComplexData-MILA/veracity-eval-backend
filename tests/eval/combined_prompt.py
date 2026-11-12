"""Experimental single call that replaces two live ones: the clarify step and turn 1 of the fact-check search loop.

Not imported by app/: production keeps CLARIFY_CLAIM followed by ORCHESTRATOR_PROMPT. The combined prompt is built
from the live clarify rules (verbatim, so they stay in sync), plus the turn-1 duties of the orchestrator prompt. On the
"search" path, `orchestrator_turn` turns the plan into the exact assistant message the orchestrator would have written,
so the rest of the search loop and the verdict run unchanged.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple

from app.core.llm.prompts import AnalysisPrompt
from app.core.text_safety import clean_unicode_text, extract_json_candidate, wrap_untrusted
from app.services.claim_extraction_service import (
    CLARIFY_ASK,
    MAX_CLARIFY_ROUNDS,
    MAX_STATEMENT_CHARS,
    parse_clarification_response,
)

PLAN_ASK = CLARIFY_ASK
PLAN_SEARCH = "search"
MAX_QUERY_CHARS = 500

# Skipped-answer text, identical to ClaimExtractionService._build_clarify_prompt (checked by a test).
SKIPPED = (
    "(skipped: choose the most likely reading, or failing that the most common claim on the subject, "
    "and state it as an assumption)"
)
SKIPPED_FR = (
    "(ignorée : choisissez l'interprétation la plus probable, ou à défaut l'affirmation la plus courante "
    "sur le sujet, et indiquez-la comme hypothèse)"
)


def _rules(template: str, start: str, end: str) -> str:
    """The rules block of a live clarify prompt, verbatim."""
    return template.split(start, 1)[1].split(end, 1)[0]


CLARIFY_RULES = _rules(AnalysisPrompt.CLARIFY_CLAIM, "Rules:\n", "\n\nReturn ONLY")
CLARIFY_RULES_FR = _rules(AnalysisPrompt.CLARIFY_CLAIM_FR, "Règles :\n", "\n\nRenvoyez UNIQUEMENT")

CLARIFY_AND_PLAN = (
    """You are the first step of a fact-checking system. Today is {date}.
In one reply, choose the path for the user's input:
- "ask": a clarifying question is needed first, so ask it (the multi-turn path).
- "search": the claim is good enough to fact-check, so prepare it and start the fact-check by planning its first web search.

## Step 1: decide whether to ask
Rules:
"""
    + CLARIFY_RULES
    + """

## Step 2: start the fact-check (status "search" only)
You have access to a search engine tool. The fact-check analyzes the factuality of the claim (for today's date) and states a score from 0 to 100, where 0 represents definitively false and 100 represents definitively true. That score comes in later turns, after the search results, so do not give it here.
- You must invoke the search tool at least once before any score; do not rely on prior knowledge alone. Status "search" therefore always includes exactly one search.
- "reason": explain your reasoning for invoking search, in one or two sentences.
- "query": the web search query for the self-contained claim. Only one search in this reply.

## Output
Return ONLY minified JSON in exactly one of these shapes, with no prose, no markdown and no code fences:
{{"input": "A, B or C", "status": "ask", "question": "<question>", "options": ["<option>", "<option>"]}}
{{"input": "A, B or C", "status": "search", "claim": "<self-contained claim>", "assumptions": ["<assumption>"], "reason": "<why this search>", "query": "<search query>"}}

Claim:
{claim}

Previous clarifying questions and the user's answers:
{turns}

If the last answer above is a complete claim, the user has chosen: return it with status "search" and ask nothing more. {ask_rule}"""
)

CLARIFY_AND_PLAN_FR = (
    """Vous êtes la première étape d'un système de vérification des faits. Aujourd'hui, nous sommes le {date}.
En une seule réponse, choisissez le chemin de l'entrée de l'utilisateur :
- "ask" : une question de clarification est d'abord nécessaire, posez-la (le chemin à plusieurs tours).
- "search" : l'affirmation est assez précise pour être vérifiée, préparez-la et lancez la vérification en planifiant sa première recherche Web.

## Étape 1 : décider s'il faut poser une question
Règles :
"""
    + CLARIFY_RULES_FR
    + """

## Étape 2 : lancer la vérification (statut "search" uniquement)
Vous avez accès à un moteur de recherche. La vérification consiste à analyser la véracité de l'affirmation (pour la date d'aujourd'hui) et à indiquer un index de 0 à 100, où 0 représente définitivement faux et 100 représente définitivement vrai. Cet index vient dans les tours suivants, après les résultats de recherche : ne le donnez pas ici.
- Vous devez invoquer le moteur de recherche au moins une fois avant tout index ; ne vous fiez pas uniquement à vos connaissances. Le statut "search" comprend donc toujours exactement une recherche.
- "reason" : expliquez votre raisonnement pour lancer la recherche, en une ou deux phrases.
- "query" : la requête de recherche Web pour l'affirmation autonome. Une seule recherche dans cette réponse.

## Sortie
Renvoyez UNIQUEMENT du JSON minifié dans exactement l'une de ces formes, sans texte supplémentaire, sans markdown et sans balises de code :
{{"input": "A, B ou C", "status": "ask", "question": "<question>", "options": ["<option>", "<option>"]}}
{{"input": "A, B ou C", "status": "search", "claim": "<affirmation autonome>", "assumptions": ["<hypothèse>"], "reason": "<raison de cette recherche>", "query": "<requête de recherche>"}}

Affirmation :
{claim}

Questions de clarification précédentes et réponses de l'utilisateur :
{turns}

Si la dernière réponse ci-dessus est une affirmation complète, l'utilisateur a choisi : renvoyez-la avec le statut "search" et ne posez plus de question. {ask_rule}"""
)


@dataclass
class Plan:
    status: str
    claim: str
    question: Optional[str] = None
    options: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    reason: str = ""
    query: str = ""
    input_class: str = ""


def allow_ask(turns: List[Tuple[str, Optional[str]]]) -> bool:
    """Same cap as ClaimExtractionService.clarify: 2 questions, and a skipped question ends clarification."""
    return len(turns) < MAX_CLARIFY_ROUNDS and all(answer for _, answer in turns)


def build_prompt(text: str, language: str, turns: List[Tuple[str, Optional[str]]], date: Optional[str] = None) -> str:
    french = language == "french"
    claim = clean_unicode_text(text).strip()
    skipped = SKIPPED_FR if french else SKIPPED
    lines = [f"Q: {question}\nA: {answer if answer else skipped}" for question, answer in turns]
    if allow_ask(turns):
        ask_rule = ""
    else:
        ask_rule = (
            'Vous devez maintenant renvoyer le statut "search".' if french else 'You must now return status "search".'
        )
    template = CLARIFY_AND_PLAN_FR if french else CLARIFY_AND_PLAN
    return template.format(
        date=date or datetime.now().isoformat(),
        claim=wrap_untrusted(claim),
        turns=wrap_untrusted("\n".join(lines) or "(none)"),
        ask_rule=ask_rule,
    )


def parse_plan(raw_text: str, original_claim: str, can_ask: bool) -> Tuple[Plan, List[str]]:
    """The live clarify parser decides ask vs claim (same fail-open rules); the search fields are read on top.

    Returns the plan and the problems found, for error tracking. Any problem fails open to checking the claim.
    """
    errors: List[str] = []
    original = clean_unicode_text(original_claim).strip()
    try:
        data = json.loads(extract_json_candidate(raw_text))
    except (json.JSONDecodeError, TypeError, ValueError):
        data = None
        errors.append("json_parse")
    if data is not None and not isinstance(data, dict):
        errors.append("not_object")
        data = None

    if data is not None:
        status = data.get("status")
        if status not in (PLAN_ASK, PLAN_SEARCH):
            errors.append("bad_status" if status != "ready" else "status_ready_used")
        if data.get("input") not in ("A", "B", "C"):
            errors.append("bad_input_class")
        if status == PLAN_ASK and not can_ask:
            errors.append("ask_past_cap")
        if status == PLAN_ASK and not (data.get("question") or "").strip():
            errors.append("ask_without_question")
        if status == PLAN_ASK and data.get("input") == "B" and len(data.get("options") or []) < 2:
            errors.append("b_ask_few_options")
        if status == PLAN_SEARCH and not (data.get("claim") or "").strip():
            errors.append("search_without_claim")
        if status == PLAN_SEARCH and not (data.get("query") or "").strip():
            errors.append("search_without_query")

    result = parse_clarification_response(raw_text, original, can_ask)
    input_class = str((data or {}).get("input") or "")
    if result.status == CLARIFY_ASK:
        plan = Plan(PLAN_ASK, original, result.question, result.options, input_class=input_class)
        return plan, errors

    query = clean_unicode_text((data or {}).get("query") or "").strip()[:MAX_QUERY_CHARS]
    reason = clean_unicode_text((data or {}).get("reason") or "").strip()[:MAX_STATEMENT_CHARS]
    plan = Plan(
        PLAN_SEARCH,
        result.claim,
        assumptions=result.assumptions,
        # Fail open the way the live loop treats a turn without a query: search for the claim itself.
        query=" ".join(query.split()) or result.claim,
        reason=" ".join(reason.split()) or "Search for evidence about the claim.",
        input_class=input_class,
    )
    return plan, errors


def orchestrator_turn(plan: Plan, language: str) -> str:
    """The turn-1 assistant message the live orchestrator would write, in the format its parser expects."""
    if language == "french":
        return f"REASON : {plan.reason}\nSEARCH : {plan.query}"
    return f"REASON: {plan.reason}\nSEARCH: {plan.query}"
