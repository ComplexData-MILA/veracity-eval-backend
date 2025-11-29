# app/preload_model.py
import os
from sentence_transformers import SentenceTransformer

# 1. Force the location to be inside the container structure
os.environ["HF_HOME"] = "/app/hf_cache"

print("⏳ Downloading embedding model to build...")
# 2. This triggers the download
model = SentenceTransformer('all-MiniLM-L6-v2')
print("✅ Model downloaded successfully.")