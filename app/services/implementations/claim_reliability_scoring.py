def factuality_scorer(atomic_verdicts: list[str]) -> float:
    """
    A simple claim scorer that counts the number of true, false and unverifiable atomic 
    verdicts and returns a score between 0 and 1. It measure the factuality percentage of
    the input
    """
    if not atomic_verdicts or len(atomic_verdicts) == 0:
        raise ValueError("Atomic verdicts list cannot be empty.")
    score = 0.0
    for verdict in atomic_verdicts:
        if verdict not in ["true", "false", "unverifiable"]:
            raise ValueError(f"Invalid atomic verdict: {verdict}. Allowed values are 'true', 'false', 'unverifiable'.")
        if verdict == "true":
            score += 1.0
        elif verdict == "false":
            score += 0.0
        else:  # unverifiable
            score += 0.5
    return score / len(atomic_verdicts)
