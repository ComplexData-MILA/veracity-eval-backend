import time
from collections import defaultdict, deque
from typing import Deque, Dict
from uuid import UUID

from fastapi import HTTPException, status

from app.core.config import settings

MINUTE = 60
DAY = 86_400

_requests: Dict[UUID, Deque[float]] = defaultdict(deque)


def enforce_llm_rate_limit(user_id: UUID) -> None:
    """Sliding per-user limit on LLM routes. Counts live in this process, so each pod enforces its own limit."""
    now = time.monotonic()
    requests = _requests[user_id]
    while requests and now - requests[0] > DAY:
        requests.popleft()

    per_minute, per_day = settings.LLM_RATE_LIMIT_PER_MINUTE, settings.LLM_RATE_LIMIT_PER_DAY
    last_minute = sum(1 for sent in requests if now - sent <= MINUTE)
    if (per_minute and last_minute >= per_minute) or (per_day and len(requests) >= per_day):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests. Please try again later."
        )
    requests.append(now)
