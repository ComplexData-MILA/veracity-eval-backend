import os
from typing import List, Optional

import httpx
from fastapi import HTTPException, UploadFile

OPENFAKE_API_URL = os.getenv(
    "OPENFAKE_API_URL",
    "https://deepfake-detector.ai4.institute/api/predict",
)

ALLOWED_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "video/mp4",
    "video/quicktime",
    "video/webm",
    "video/x-matroska",
}


def _as_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _verdict_from_score(p_fake: float) -> str:
    if p_fake >= 0.75:
        return "Likely fake"
    if p_fake >= 0.45:
        return "Uncertain"
    return "Likely real"


def _frame_probs_from_frames(frames: object) -> Optional[List[float]]:
    if not isinstance(frames, list):
        return None

    frame_probs = []
    for frame in frames:
        if isinstance(frame, dict) and "p_fake" in frame:
            frame_probs.append(_as_float(frame.get("p_fake")))

    return frame_probs or None


async def verify_media_with_openfake(file: UploadFile) -> dict:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}",
        )

    await file.seek(0)

    files = {
        "file": (
            file.filename,
            file.file,
            file.content_type,
        )
    }

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            OPENFAKE_API_URL,
            files=files,
        )

    if response.status_code != 200:
        detail = "OpenFake detector failed"
        try:
            error_data = response.json()
            detail = error_data.get("detail") or error_data.get("error") or detail
        except ValueError:
            pass

        raise HTTPException(
            status_code=502,
            detail=detail,
        )

    data = response.json()

    p_fake = _as_float(data.get("p_fake"))
    reliability = _as_float(data.get("reliability"), 1 - p_fake)
    frame_probs = data.get("frame_probs") or _frame_probs_from_frames(data.get("frames"))

    return {
        "media_type": data.get("media_type"),
        "p_fake": p_fake,
        "p_real": data.get("p_real"),
        "p_localized": data.get("p_localized"),
        "p_full_synthetic": data.get("p_full_synthetic"),
        "p_fake_max": data.get("p_fake_max"),
        "generators": data.get("generators", []),
        "reliability": reliability,
        "reliability_score": round(reliability * 100),
        "verdict": _verdict_from_score(p_fake),
        "n_frames": data.get("n_frames"),
        "frame_probs": frame_probs,
        "frames": data.get("frames"),
        "mask": data.get("mask"),
        "explanation": (f"The detector estimates a {round(p_fake * 100)}% probability that this media is fake."),
    }
