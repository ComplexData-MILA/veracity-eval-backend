import os

import httpx
from fastapi import HTTPException, UploadFile

OPENFAKE_API_URL = os.getenv(
    "OPENFAKE_API_URL",
    "https://complexdatalab-openfakedemo.hf.space/api/predict",
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


async def verify_media_with_openfake(file: UploadFile) -> dict:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}",
        )

    await file.seek(0)

    # This forwards the uploaded file object to OpenFake
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
        raise HTTPException(
            status_code=502,
            detail="OpenFake detector failed",
        )

    data = response.json()

    p_fake = float(data.get("p_fake", 0))
    reliability = float(data.get("reliability", 1 - p_fake))

    if p_fake >= 0.75:
        verdict = "Likely fake"
    elif p_fake >= 0.45:
        verdict = "Uncertain"
    else:
        verdict = "Likely real"

    return {
        "media_type": data.get("media_type"),
        "p_fake": p_fake,
        "reliability": reliability,
        "reliability_score": round(reliability * 100),
        "verdict": verdict,
        "n_frames": data.get("n_frames"),
        "frame_probs": data.get("frame_probs"),
        "explanation": (f"The detector estimates a {round(p_fake * 100)}% probability " f"that this media is fake."),
    }
