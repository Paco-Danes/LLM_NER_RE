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
import re
import textwrap


DATA_DIR = Path(__file__).parent / "data"
CLASSES_FILE = DATA_DIR / "classes.json"
TEXTS_FILE = DATA_DIR / "texts.json"
ANNOT_FILE = DATA_DIR / "annotations.jsonl"
PROPOSED_FILE = DATA_DIR / "proposed_classes.py"

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

class AttrSpec(BaseModel):
    name: str
    type: Literal[
        "str", "int", "float", "bool",
        "literal", "list[str]", "list[int]", "list[float]", "list[bool]"
    ] = "str"
    optional: bool = False
    description: Optional[str] = ""
    literal_values: Optional[List[str]] = None  # required if type == literal

class ProposedClassIn(BaseModel):
    name: str
    description: Optional[str] = ""
    attributes: List[AttrSpec] = []

def _ensure_proposed_file():
    """Create proposed_classes.py with a minimal header if missing."""
    if PROPOSED_FILE.exists():
        return
    
    PROPOSED_FILE.parent.mkdir(parents=True, exist_ok=True)
    header = textwrap.dedent("""\
        # Auto-generated proposed classes
        from __future__ import annotations
        from typing import Optional, List, Literal
        from pydantic import BaseModel, Field

        # If you already define NamedEntity elsewhere, keep this stub or replace it.
        class NamedEntity(BaseModel):
            \"\"\"Base type for all proposed entities.\"\"\"
            pass

        """)
    PROPOSED_FILE.write_text(header, encoding="utf-8")

def _render_type_and_default(a: AttrSpec) -> tuple[str, str]:
    """Return (annotation, default_expr) e.g. ('Optional[int]', 'None') or ('Literal[\"A\",\"B\"]', '...')."""
    t = a.type
    if t == "str": base = "str"
    elif t == "int": base = "int"
    elif t == "float": base = "float"
    elif t == "bool": base = "bool"
    elif t == "list[str]": base = "List[str]"
    elif t == "list[int]": base = "List[int]"
    elif t == "list[float]": base = "List[float]"
    elif t == "list[bool]": base = "List[bool]"
    elif t == "literal":
        vals = a.literal_values or []
        if not vals:
            raise HTTPException(400, f'Field "{a.name}" is Literal but has no values.')
        # quote safely
        qvals = ", ".join(json.dumps(v) for v in vals)
        base = f"Literal[{qvals}]"
    else:
        raise HTTPException(400, f"Unsupported type: {t}")

    if a.optional:
        return (f"Optional[{base}]", "None")
    else:
        return (base, "...")
    
def _sanitize_docstring(s: str) -> str:
    # avoid breaking the triple quotes
    return (s or "").replace('"""', '\\"""')

def _render_class_code(payload: ProposedClassIn) -> str:
    lines = []
    lines.append(f"class {payload.name}(NamedEntity):")
    doc = _sanitize_docstring(payload.description or "")
    if doc.strip():
        lines.append('    """')
        for ln in doc.splitlines():
            lines.append(f"    {ln}")
        lines.append('    """')
    else:
        lines.append('    """No description provided."""')

    for a in payload.attributes:
        if not re.match(r"^[a-z_][a-z0-9_]*$", a.name):
            raise HTTPException(400, f'Invalid field name: "{a.name}" (use snake_case).')
        ann, default = _render_type_and_default(a)
        desc_json = json.dumps(a.description or "")
        lines.append(f"    {a.name}: {ann} = Field({default}, description={desc_json})")

    return "\n".join(lines) + "\n"

@app.post("/api/proposed-classes")
async def propose_class(payload: ProposedClassIn):
    # Validate class name
    if not re.match(r"^[A-Z][A-Za-z0-9_]*$", payload.name):
        raise HTTPException(400, "Invalid Python class name (use CamelCase).")
    _ensure_proposed_file()
    txt = PROPOSED_FILE.read_text(encoding="utf-8")
    # Prevent duplicates
    if re.search(rf"^\s*class\s+{re.escape(payload.name)}\s*\(", txt, flags=re.M):
        raise HTTPException(409, f'Class "{payload.name}" already exists in proposed_classes.py')
    # Generate and append
    code = "\n" + _render_class_code(payload)
    with PROPOSED_FILE.open("a", encoding="utf-8") as f:
        f.write(code)
    return {"ok": True, "file": str(PROPOSED_FILE), "bytes_written": len(code)}

# ---------- Dev convenience ----------
@app.get("/")
async def root():
    return {"status": "ok", "message": "Backend is running"}
