"""Regenerate app/services/data/verifier_vocab_enfr.json: the verifier vocabulary pieces English and French use.

Keeps every piece seen when tokenizing XNLI and PAWS-X training text (EN + FR), every single-character Latin or
punctuation piece (so any EN/FR word can still be segmented), and the special tokens. After regenerating, re-run
tests/calibrate.py and RUN_MODEL_TESTS=1 pytest before deploying.

Usage: python tests/build_verifier_vocab.py [--rows 20000]
"""

import argparse
import json
from concurrent.futures import ThreadPoolExecutor

import requests
from transformers import AutoTokenizer

from app.core.config import settings
from app.services.verifier_trim import VOCAB_FILE

ROWS_API = "https://datasets-server.huggingface.co/rows"


def fetch(dataset: str, config: str, offset: int) -> list:
    params = {"dataset": dataset, "config": config, "split": "train", "offset": offset, "length": 100}
    for _ in range(3):
        try:
            return [r["row"] for r in requests.get(ROWS_API, params=params, timeout=60).json()["rows"]]
        except Exception:
            continue
    raise RuntimeError(f"could not fetch {dataset}/{config} at offset {offset}")


def corpus(rows: int) -> list:
    jobs = []
    for lang in ("en", "fr"):
        jobs += [("facebook/xnli", lang, o, ("premise", "hypothesis")) for o in range(0, rows, 100)]
        jobs += [
            ("google-research-datasets/paws-x", lang, o, ("sentence1", "sentence2")) for o in range(0, rows // 2, 100)
        ]
    with ThreadPoolExecutor(16) as pool:
        batches = list(pool.map(lambda job: fetch(*job[:3]), jobs))
    return [row[key] for batch, job in zip(batches, jobs) for row in batch for key in job[3] if row.get(key)]


def is_latin(ch: str) -> bool:
    o = ord(ch)
    return o < 0x250 or 0x2000 <= o <= 0x206F or 0x20A0 <= o <= 0x20CF or 0x2100 <= o <= 0x22FF or o == 0x2581


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=20000)
    args = parser.parse_args()

    tok = AutoTokenizer.from_pretrained(settings.SEMCACHE_VERIFIER_MODEL)
    texts = corpus(args.rows)
    seen = set()
    for i in range(0, len(texts), 2000):
        for ids in tok(texts[i : i + 2000], add_special_tokens=False)["input_ids"]:
            seen.update(ids)

    spec = json.loads(tok.backend_tokenizer.to_str())
    vocab = spec["model"]["vocab"]
    specials = {t["id"] for t in spec["added_tokens"]}
    single = {i for i, (piece, _) in enumerate(vocab) if len(piece.replace("▁", "")) <= 1 and all(map(is_latin, piece))}
    unigram = sorted((seen | single | specials) & set(range(len(vocab))))
    keep = unigram + sorted(i for i in specials if i >= len(vocab))  # added tokens such as [MASK] come last

    VOCAB_FILE.parent.mkdir(parents=True, exist_ok=True)
    VOCAB_FILE.write_text(json.dumps(keep))
    print(f"{len(texts)} sentences -> kept {len(keep)} pieces -> {VOCAB_FILE}")


if __name__ == "__main__":
    main()
