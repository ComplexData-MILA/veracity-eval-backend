"""Prompt changes without a redeploy: AnalysisPrompt texts overridden from a JSON file, reloaded when it changes.

The file maps prompt names to their new text, e.g. {"CLARIFY_AND_PLAN": "..."}. In Kubernetes it comes from the
veracity-prompt-overrides ConfigMap, mounted as a directory (kubelet updates the file in about a minute; no pod restart).
Removing a name, or emptying the file to {}, restores the shipped text. The cache key reads prompts at call time, so an
override of a verdict prompt starts a fresh cache, as a code change would.

A value is the text, or a list of strings joined with no separator, so a long prompt can be wrapped across lines.

A file that fails validation is ignored as a whole and the last good overrides stay active, so a typo can't take
prompts down. Validation: every name must be an existing AnalysisPrompt text, every value a non-empty string, and a
prompt that is a format template must keep exactly the same {fields}.

Check a file before applying it:  python -m app.core.llm.prompt_overrides check overrides.json
Copy prompts.py changes into it:  python -m app.core.llm.prompt_overrides sync overrides.json [NAME ...]
"""

import ast
import asyncio
import hashlib
import json
import logging
import os
import re
import string
import subprocess
import sys
from typing import Dict, Optional, Tuple

from app.core.llm.prompts import AnalysisPrompt

logger = logging.getLogger(__name__)

POLL_SECONDS = 30
# Longest shipped prompt is ~5,300 chars; the cap bounds the cost of every call that uses an override
MAX_PROMPT_CHARS = 20_000
# The prompt-injection and harmful-request defences. Changing them needs code review, so no runtime override.
PROTECTED = frozenset(
    {
        "UNTRUSTED_SOURCES",
        "UNTRUSTED_SOURCES_FR",
        "FOLLOWUP_RULES",
        "FOLLOWUP_REMINDER",
        "FOLLOWUP_ROUTER",
        "HARM_CHECK",
        "CLARIFY_HARMFUL_REFUSAL",
        "CLARIFY_HARMFUL_REFUSAL_FR",
    }
)
SHIPPED: Dict[str, str] = {
    name: value for name, value in vars(AnalysisPrompt).items() if name.isupper() and isinstance(value, str)
}
_FIELD = re.compile(r"^\w+$")
_state = {"mtime": None, "sha": None}


def _template_fields(text: str, plain_only: bool = False) -> Optional[set]:
    """The {fields} of a str.format template, or None when the text is not one (e.g. literal JSON braces).

    Field names must be plain identifiers: "{claim.__class__}" or "{claim[0]}" would read objects through the
    template. With plain_only, format specs and conversions are refused too: "{claim:>99999999}" pads every call.
    """
    try:
        parsed = [(name, spec, conversion) for _, name, spec, conversion in string.Formatter().parse(text)]
    except ValueError:
        return None
    fields = {name for name, _, _ in parsed if name is not None}
    if not fields or not all(_FIELD.match(name) for name in fields):
        return None
    if plain_only and any(spec or conversion for name, spec, conversion in parsed if name is not None):
        return None
    return fields


def _joined(value):
    """A value as one text: a list of strings is joined with no separator; anything else is returned as is."""
    if isinstance(value, list) and value and all(isinstance(part, str) for part in value):
        return "".join(value)
    return value


def wrapped(text: str, width: int = 100) -> list:
    """The text split into lines of at most about width chars, breaking after spaces; joining them gives it back."""
    parts = []
    for line in text.splitlines(keepends=True):
        while len(line) > width and line.rfind(" ", 0, width) > 0:
            cut = line.rfind(" ", 0, width) + 1
            parts.append(line[:cut])
            line = line[cut:]
        parts.append(line)
    return parts


def validate(overrides) -> Tuple[Dict[str, str], list]:
    """The usable overrides, as {name: text}, and the problems found; any problem rejects the whole file."""
    if not isinstance(overrides, dict):
        return {}, ["the file must hold a JSON object of {prompt name: text}"]
    overrides = {name: _joined(value) for name, value in overrides.items()}
    problems = []
    for name, text in overrides.items():
        if name not in SHIPPED:
            problems.append(f"{name}: not a prompt name")
        elif name in PROTECTED:
            problems.append(f"{name}: a prompt-injection defence; change it in code, with review")
        elif not isinstance(text, str) or not text.strip():
            problems.append(f"{name}: text must be a non-empty string, or a list of strings")
        elif len(text) > MAX_PROMPT_CHARS:
            problems.append(f"{name}: {len(text)} chars, over the {MAX_PROMPT_CHARS} limit")
        else:
            expected = _template_fields(SHIPPED[name])
            if expected is not None:
                if _template_fields(text, plain_only=True) != expected:
                    problems.append(
                        f"{name}: must keep exactly the fields {sorted(expected)}, written plainly as {{name}}"
                    )
                else:
                    try:
                        text.format(**{field: "" for field in expected})
                    except (ValueError, IndexError, KeyError) as e:
                        problems.append(f"{name}: not a valid template ({e}); write literal braces as {{{{ }}}}")
    return (overrides if not problems else {}), problems


def apply(overrides: Dict[str, str]) -> None:
    """Set the given texts and restore every other prompt to its shipped text."""
    for name, shipped in SHIPPED.items():
        setattr(AnalysisPrompt, name, overrides.get(name, shipped))


def reload_if_changed(path: str) -> None:
    """Apply the file if it changed since the last load. Never raises: errors keep the current prompts."""
    try:
        mtime = os.stat(path).st_mtime if os.path.exists(path) else None
        if mtime == _state["mtime"]:
            return
        _state["mtime"] = mtime
        raw = open(path, encoding="utf-8").read() if mtime is not None else "{}"
        sha = hashlib.sha256(raw.encode()).hexdigest()[:12]
        if sha == _state["sha"]:
            return
        overrides, problems = validate(json.loads(raw or "{}"))
        if problems:
            logger.error(f"Prompt overrides {sha} rejected, keeping the current prompts: {problems}")
            return
        apply(overrides)
        _state["sha"] = sha
        logger.info(f"Prompt overrides {sha} applied: {sorted(overrides) or 'none (shipped prompts)'}")
    except Exception:
        logger.exception("Prompt overrides could not be loaded; keeping the current prompts")


async def watch(path: str) -> None:
    """Background task: load the overrides now, then check the file every POLL_SECONDS."""
    while True:
        reload_if_changed(path)
        await asyncio.sleep(POLL_SECONDS)


def _committed_prompts() -> Dict[str, str]:
    """The AnalysisPrompt texts in the last commit's prompts.py, read without importing it; {} when git can't say."""
    try:
        source = subprocess.run(
            ["git", "show", "HEAD:app/core/llm/prompts.py"], capture_output=True, check=True, encoding="utf-8"
        ).stdout
        cls = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == "AnalysisPrompt")
        return {
            s.targets[0].id: ast.literal_eval(s.value)
            for s in cls.body
            if isinstance(s, ast.Assign) and isinstance(s.targets[0], ast.Name)
        }
    except Exception:
        return {}


def sync(overrides: dict, previous: Dict[str, str], add=()) -> Tuple[dict, list]:
    """Bring a file's copies of shipped prompts up to date with prompts.py.

    An entry still equal to the previous shipped text (`previous`, the last commit's) is a copy, so it takes the
    current text. Any other entry is a deliberate change and is kept. Names in `add` are added at their shipped text.
    Returns the new file contents, wrapped, and notes on what was kept.
    """
    result, notes = {}, []
    for name in [*overrides, *(n for n in add if n not in overrides)]:
        text = _joined(overrides.get(name, ""))
        if name in SHIPPED and (name not in overrides or text in (previous.get(name), SHIPPED[name])):
            text = SHIPPED[name]
        elif text != SHIPPED.get(name):
            notes.append(f"{name}: kept, it differs from prompts.py")
        result[name] = wrapped(text) if isinstance(text, str) else text
    return result, notes


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("check", "sync") or (sys.argv[1] == "check" and len(sys.argv) != 3):
        sys.exit(
            "usage: python -m app.core.llm.prompt_overrides check <overrides.json>\n"
            "       python -m app.core.llm.prompt_overrides sync <overrides.json> [NAME ...]"
        )
    path = sys.argv[2]
    current = json.load(open(path, encoding="utf-8"))
    if sys.argv[1] == "check":
        _, found = validate(current)
        print("\n".join(found) or "OK")
        sys.exit(1 if found else 0)
    synced, notes = sync(current, _committed_prompts(), add=sys.argv[3:])
    print("\n".join(notes))
    text = json.dumps(synced, ensure_ascii=False, indent=2) + "\n"
    if text != open(path, encoding="utf-8").read():
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print(f"Updated {path} from prompts.py")
        sys.exit(1)  # tells pre-commit the file changed, so it is staged with the prompt change
