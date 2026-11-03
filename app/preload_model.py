# app/preload_model.py
import os
from sentence_transformers import SentenceTransformer

# 1. Force the location to be inside the container structure
os.environ["HF_HOME"] = "/app/hf_cache"

print("⏳ Downloading embedding model to build...")
# 2. This triggers the download
model = SentenceTransformer("all-MiniLM-L6-v2")
print("✅ Model downloaded successfully.")

# 3. Semantic cache claim verifier, vocabulary-trimmed to English/French (see app/services/verifier_trim.py)
from app.core.config import settings  # noqa: E402
from app.services.verifier_trim import ensure_trimmed_model  # noqa: E402

from huggingface_hub import scan_cache_dir  # noqa: E402

print("⏳ Building trimmed semantic cache verifier...")
print(f"✅ Verifier ready at {ensure_trimmed_model(settings.SEMCACHE_VERIFIER_MODEL)}")

# The app only loads the trimmed copy, so drop the ~1 GB original checkpoint from the image (same RUN layer)
cache = scan_cache_dir()
revisions = [
    r.commit_hash for repo in cache.repos if repo.repo_id == settings.SEMCACHE_VERIFIER_MODEL for r in repo.revisions
]
cache.delete_revisions(*revisions).execute()
print(f"🧹 Removed original verifier checkpoint from the image ({len(revisions)} revision(s))")
