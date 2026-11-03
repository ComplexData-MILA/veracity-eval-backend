"""Vocabulary trimming for the semantic cache verifier (Ushio et al., "An Efficient Multilingual Language Model
Compression through Vocabulary Trimming", EMNLP Findings 2023).

The multilingual NLI model spends 193M of its 279M parameters on a 251k-token vocabulary. Keeping only the pieces that
English and French text uses (app/services/data/verifier_vocab_enfr.json, made by tests/build_verifier_vocab.py) cuts
its loaded memory from ~1.27 GB to ~0.37 GB with the same calibration results. The trimmed model is built from the
original checkpoint at image build time (app/preload_model.py), or on first use if it is missing.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import List

VOCAB_FILE = Path(__file__).parent / "data" / "verifier_vocab_enfr.json"


def trimmed_model_dir(source_model: str, vocab_file: Path = VOCAB_FILE) -> str:
    from huggingface_hub import constants

    digest = hashlib.sha256(vocab_file.read_bytes()).hexdigest()[:12]
    return os.path.join(constants.HF_HOME, "semcache-verifier", f"{source_model.replace('/', '__')}-{digest}")


def build_trimmed_model(source_model: str, keep_ids: List[int], out_dir: str) -> str:
    """Save a copy of source_model whose vocabulary and embedding matrix only contain keep_ids (old ids, in order)."""
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer, PreTrainedTokenizerFast

    tok = AutoTokenizer.from_pretrained(source_model)
    model = AutoModelForSequenceClassification.from_pretrained(source_model)
    remap = {old: new for new, old in enumerate(keep_ids)}

    spec = json.loads(tok.backend_tokenizer.to_str())
    vocab = spec["model"]["vocab"]
    spec["model"]["vocab"] = [vocab[i] for i in keep_ids if i < len(vocab)]
    spec["model"]["unk_id"] = remap[spec["model"]["unk_id"]]
    for token in spec["added_tokens"]:
        token["id"] = remap[token["id"]]
    for special in spec["post_processor"].get("special_tokens", {}).values():
        special["ids"] = [remap[i] for i in special["ids"]]

    os.makedirs(out_dir, exist_ok=True)
    tokenizer_file = os.path.join(out_dir, "tokenizer.json")
    with open(tokenizer_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(spec, ensure_ascii=False))
    special_tokens = ("bos_token", "eos_token", "unk_token", "sep_token", "pad_token", "cls_token", "mask_token")
    fast = PreTrainedTokenizerFast(tokenizer_file=tokenizer_file, **{k: getattr(tok, k) for k in special_tokens})
    fast.model_max_length = tok.model_max_length
    fast.save_pretrained(out_dir)

    old = model.get_input_embeddings()
    new = torch.nn.Embedding(len(keep_ids), old.embedding_dim, padding_idx=remap.get(old.padding_idx))
    new.weight.data = old.weight.data[keep_ids].clone()
    model.set_input_embeddings(new)
    model.config.vocab_size = len(keep_ids)
    model.config.pad_token_id = remap.get(model.config.pad_token_id, model.config.pad_token_id)
    model.save_pretrained(out_dir, safe_serialization=True)
    return out_dir


def ensure_trimmed_model(source_model: str, vocab_file: Path = VOCAB_FILE) -> str:
    out_dir = trimmed_model_dir(source_model, vocab_file)
    if not os.path.exists(os.path.join(out_dir, "config.json")):
        build_trimmed_model(source_model, json.loads(vocab_file.read_text()), out_dir)
    return out_dir
