from __future__ import annotations
from functools import lru_cache
from typing import List, Optional, TypedDict
import numpy as np
from fastapi import HTTPException

from app.core.paths import (
    EMBED_INDEX_FILE, EMBED_META_FILE,
    REL_EMBED_INDEX_FILE, REL_EMBED_META_FILE
)
from app.core.config import get_settings

class Index(TypedDict):
    labels: list[str]
    embeddings: np.ndarray
    meta: dict

@lru_cache(maxsize=1)
def load_index() -> Optional[Index]:
    if not EMBED_INDEX_FILE.exists():
        return None
    data = np.load(EMBED_INDEX_FILE, allow_pickle=True)
    labels = list(map(str, data["labels"].tolist()))
    embs = data["embeddings"].astype("float32")
    embs /= (np.linalg.norm(embs, axis=1, keepdims=True) + 1e-12)
    meta = {}
    if EMBED_META_FILE.exists():
        try:
            import json
            meta = json.loads(EMBED_META_FILE.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
    return {"labels": labels, "embeddings": embs, "meta": meta}

@lru_cache(maxsize=1)
def load_rel_index() -> Optional[Index]:
    if not REL_EMBED_INDEX_FILE.exists():
        return None
    data = np.load(REL_EMBED_INDEX_FILE, allow_pickle=True)
    labels = list(map(str, data["labels"].tolist()))
    embs = data["embeddings"].astype("float32")
    embs /= (np.linalg.norm(embs, axis=1, keepdims=True) + 1e-12)
    meta = {}
    if REL_EMBED_META_FILE.exists():
        try:
            import json
            meta = json.loads(REL_EMBED_META_FILE.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
    return {"labels": labels, "embeddings": embs, "meta": meta}

@lru_cache(maxsize=1)
def load_embedder():
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer(get_settings().EMBED_MODEL_NAME)
    except Exception:
        # Keep same behavior
        return None

def encode_query(texts: List[str]) -> np.ndarray:
    model = load_embedder()
    if model is None:
        raise HTTPException(501, "Embedding model not installed on server.")
    texts = [("query: " + t.strip()) if t else "query:" for t in texts]
    vecs = model.encode(texts, normalize_embeddings=True)
    return vecs.astype("float32")
