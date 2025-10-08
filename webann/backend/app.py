from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Literal
from functools import lru_cache
import numpy as np
from pathlib import Path
import json
import tempfile
import os

DATA_DIR = Path(__file__).parent / "data"
CLASSES_FILE = DATA_DIR / "classes.json"
TEXTS_FILE = DATA_DIR / "texts.json"
ANNOT_FILE = DATA_DIR / "annotations.jsonl"
# ---------- Files ----------
RELATIONS_FILE = DATA_DIR / "relations.json"
# ---- ADD: relation embedding index files (symmetric to class index) ----
REL_EMBED_INDEX_FILE = DATA_DIR / "rel_index.npz"
REL_EMBED_META_FILE  = DATA_DIR / "rel_index_meta.json"
# ---- ADD: class embedding model name and index ----
EMBED_INDEX_FILE = DATA_DIR / "class_index.npz"
EMBED_META_FILE = DATA_DIR / "class_index_meta.json"
EMBED_MODEL_NAME = "BAAI/bge-small-en-v1.5"

app = FastAPI(title="Annotation Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"]
)

# ---------- Models ----------
class Span(BaseModel):
    start: int = Field(..., ge=0, description="0-based start char offset (inclusive)")
    end: int = Field(..., ge=0, description="0-based end char offset (exclusive)")

class Entity(BaseModel):
    id: str
    class_: str = Field(..., alias="class")
    label: str
    span: Span
    attributes: Dict[str, Any] = {}

class RelationEdge(BaseModel):
    id: str
    predicate: str             # relation name
    subject: str               # entity id (e.g., "T3")
    object: str                # entity id
    attributes: Dict[str, Any] = {}

class SavePayload(BaseModel):
    text_id: str
    text: str
    entities: List[Entity]
    relations: List[RelationEdge] = []   # <--- ADD

# ---------- Helpers ----------
def load_json(path: Path):
    if not path.exists():
        raise HTTPException(500, f"Missing file: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

TEXTS = load_json(TEXTS_FILE)  # list of {id, text}

def read_annotations_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    items = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return items

def write_annotations_jsonl(path: Path, items: List[Dict[str, Any]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tmp:
        for obj in items:
            tmp.write(json.dumps(obj, ensure_ascii=False) + "\n")
        tmp_path = tmp.name
    os.replace(tmp_path, path)

# ---- ADD: lazy loaders ----
@lru_cache(maxsize=1)
def _load_index(): #for classes
    if not EMBED_INDEX_FILE.exists():
        return None
    data = np.load(EMBED_INDEX_FILE, allow_pickle=True)
    labels = list(map(str, data["labels"].tolist()))
    embs = data["embeddings"].astype("float32")
    # ensure normalized
    norms = np.linalg.norm(embs, axis=1, keepdims=True) + 1e-12
    embs = embs / norms
    meta = {}
    if EMBED_META_FILE.exists():
        try:
            meta = json.loads(EMBED_META_FILE.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
    return {"labels": labels, "embeddings": embs, "meta": meta}

@lru_cache(maxsize=1)
def _load_rel_index():
    if not REL_EMBED_INDEX_FILE.exists():
        return None
    data  = np.load(REL_EMBED_INDEX_FILE, allow_pickle=True)
    labels = list(map(str, data["labels"].tolist()))
    embs   = data["embeddings"].astype("float32")
    embs  /= (np.linalg.norm(embs, axis=1, keepdims=True) + 1e-12)
    meta = {}
    if REL_EMBED_META_FILE.exists():
        try:
            meta = json.loads(REL_EMBED_META_FILE.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
    return {"labels": labels, "embeddings": embs, "meta": meta}

@lru_cache(maxsize=1)
def _load_embedder():
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer(EMBED_MODEL_NAME)
    except Exception as e:
        print(f"Failed to load embedder model {EMBED_MODEL_NAME}")
        return None

def _encode_query(texts: List[str]):
    model = _load_embedder()
    if model is None:
        raise HTTPException(501, "Embedding model not installed on server.")
    #BGE_prefix = "Represent this sentence for searching relevant passages:"
    texts = [("query: " + t.strip()) if t else "query:" for t in texts]
    vecs = model.encode(texts, normalize_embeddings=True)
    return vecs.astype("float32")

# ---- ADD: pydantic models ----
class SuggestIn(BaseModel):
    kind: Literal["class", "relation"] = "class"   # <--- ADD
    query: Optional[str] = ""
    label: Optional[str] = ""
    subject_class: Optional[str] = None            # <--- ADD
    object_class: Optional[str] = None            # <--- ADD
    top_k: int = 8
    threshold: float = 0.5

class SuggestItem(BaseModel):
    class_name: str
    score: float
    description: Optional[str] = None

class SuggestOut(BaseModel):
    ready: bool
    total: int
    items: List[SuggestItem]

# ---- ADD: endpoints ----
@app.get("/api/semantic/status")
async def semantic_status(kind: str = "class"):
    idx = _load_rel_index() if kind == "relation" else _load_index()
    ok = idx is not None
    return {
        "ready": bool(ok),
        "size": (len(idx["labels"]) if ok else 0),
        "model": EMBED_MODEL_NAME,
        "has_embedder": _load_embedder() is not None
    }

@app.post("/api/semantic/suggest", response_model=SuggestOut)
async def semantic_suggest(payload: SuggestIn):
    idx = _load_rel_index() if payload.kind == "relation" else _load_index()
    if idx is None:
        raise HTTPException(503, "Semantic index missing. Run the embedding builder first.")

    query = " ".join([payload.query or "", payload.label or ""]).strip()
    if not query:
        return {"ready": True, "total": len(idx["labels"]), "items": []}

    qvec = _encode_query([query])[0]
    sims = idx["embeddings"] @ qvec

    order = np.argsort(-sims)[: max(1, payload.top_k)]
    items = []
    for i in order:
        s = float(sims[i])
        if s < payload.threshold:
            continue
        name = idx["labels"][i]
        meta = (idx["meta"].get(name) or {})

        if payload.kind == "relation":
            subj_ok = True
            obj_ok = True
            if payload.subject_class:
                subj_ok = payload.subject_class in set(meta.get("subject", []))
            if payload.object_class:
                obj_ok = payload.object_class in set(meta.get("object", []))
            if not (subj_ok and obj_ok):
                continue

        items.append({
            "class_name": name,
            "score": s,
            "description": meta.get("description")
        })
    return {"ready": True, "total": len(idx["labels"]), "items": items}

# ---------- Routes ----------
@app.get("/api/classes")
async def get_classes():
    return load_json(CLASSES_FILE)

@app.get("/api/relations")
async def get_relations():
    return load_json(RELATIONS_FILE)

@app.get("/api/texts/next")
async def get_next(cursor: Optional[int] = None):
    if cursor is None:
        cursor = 0
    if cursor < 0 or cursor >= len(TEXTS):
        raise HTTPException(404, "No more texts")
    item = TEXTS[cursor]
    return {"id": item["id"], "text": item["text"], "cursor": cursor, "total": len(TEXTS)}

@app.get("/api/texts/prev")
async def get_prev(cursor: int):
    if cursor < 0:
        cursor = 0
    if cursor >= len(TEXTS):
        cursor = len(TEXTS)-1
    item = TEXTS[cursor]
    return {"id": item["id"], "text": item["text"], "cursor": cursor, "total": len(TEXTS)}

# ADD: does this text_id already have an annotation?
@app.get("/api/annotations/{text_id}/exists")
async def annotations_exists(text_id: str):
    items = read_annotations_jsonl(ANNOT_FILE)
    return {"exists": any(it.get("text_id") == text_id for it in items)}

# ADD: fetch the saved annotation (if any) for this text_id
@app.get("/api/annotations/{text_id}")
async def get_annotation(text_id: str):
    items = read_annotations_jsonl(ANNOT_FILE)
    for it in items:
        if it.get("text_id") == text_id:
            return it
    raise HTTPException(404, "No saved annotation for this text_id")

@app.post("/api/annotations")
async def save_annotations(payload: SavePayload, overwrite: bool = Query(False)):
    # sanity check spans
    for ent in payload.entities:
        if not (0 <= ent.span.start <= ent.span.end <= len(payload.text)):
            raise HTTPException(400, f"Invalid span for entity {ent.id}")

    obj = payload.model_dump(by_alias=True)
    obj.pop("text", None)  # don't persist raw text

    items = read_annotations_jsonl(ANNOT_FILE)
    idx = next((i for i, it in enumerate(items) if it.get("text_id") == payload.text_id), None)

    if idx is not None and not overwrite:
        raise HTTPException(409, "Annotations for this text_id already exist")

    if idx is not None:
        items[idx] = obj
    else:
        items.append(obj)

    write_annotations_jsonl(ANNOT_FILE, items)
    return {"ok": True, "overwritten": idx is not None}
    
# ---------- Dev convenience ----------
@app.get("/")
async def root():
    return {"status": "ok", "message": "Backend is running"}
