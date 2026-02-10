import pandas as pd
import numpy as np
import logging
import os

logger = logging.getLogger(__name__)

# Global variable to hold data in RAM
_REFERENCE_SCORES = np.array([])
_IS_LOADED = False


def load_distribution(csv_path: str):
    """Loads CSV into the global variable. Fails gracefully."""
    global _REFERENCE_SCORES, _IS_LOADED

    if not os.path.exists(csv_path):
        logger.warning(f"Distribution file not found at {csv_path}. Skipping preload.")
        return  # App continues running, just without normalization

    try:
        logger.info(f"Loading distribution from {csv_path}...")
        df = pd.read_csv(csv_path, usecols=["confidence_score"])
        _REFERENCE_SCORES = df["confidence_score"].dropna().values
        _REFERENCE_SCORES.sort()
        _IS_LOADED = True
        logger.info("Distribution loaded into RAM.")
    except Exception as e:
        logger.error(f"ERROR: Failed to load distribution: {e}")
        # We catch the error so the app doesn't crash


def get_percentile(score: float) -> float:
    """Calculates percentile. Returns 0 if data isn't loaded."""
    if not _IS_LOADED or len(_REFERENCE_SCORES) == 0:
        return 0.0

    # Fast binary search
    idx = np.searchsorted(_REFERENCE_SCORES, score, side="left")
    return (idx / len(_REFERENCE_SCORES)) * 100
