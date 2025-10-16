from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Literal
from functools import lru_cache
import importlib
import inspect
from dataclasses import is_dataclass
import numpy as np
from pathlib import Path
import json
import tempfile
import os
import re
import textwrap
from relcode.utils.relation_utils import RelationshipSpec, FixedChoiceField, FreeTextField, DynamicEntityField

DATA_DIR = Path(__file__).parent / "data"
CLASSES_FILE = DATA_DIR / "classes.json"
TEXTS_FILE = DATA_DIR / "texts.json"
ANNOT_FILE = DATA_DIR / "annotations.jsonl"
PROPOSED_FILE = DATA_DIR / "proposed_classes.py"

# ---------- NEW: files/paths for propose-relationship ----------
FIELD_DESC_FILE = DATA_DIR / "field_descriptions.json"
PROPOSED_REL_FILE = DATA_DIR / "proposed_rel.py"
ENUMS_IMPORT = "relcode.utils.my_enums"

# ---------- Files ----------
RELATIONS_FILE = DATA_DIR / "relations.json"
RELATION_SPECS_IMPORT = "relcode.relationship_specs" #should be a "module" name
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

    # ---- ADD: pydantic models ----
class SuggestIn(BaseModel):
    kind: Literal["class", "relation"] = "class"   # <--- ADD
    query: Optional[str] = ""
    label: Optional[str] = ""
    subject_class: Optional[str] = None            # <--- ADD
    object_class: Optional[str] = None            # <--- ADD
    top_k: int = 10
    threshold: float = 0.5

class SuggestItem(BaseModel):
    class_name: str
    score: float
    description: Optional[str] = None

class SuggestOut(BaseModel):
    ready: bool
    total: int
    items: List[SuggestItem]

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

# ---------- NEW: models for propose-relationship ----------
class EnumCreate(BaseModel):
    name: Optional[str] = None                # if not provided, we'll generate
    values: List[str] = []

class EnumAddIn(BaseModel):
    name: str
    values: List[str]

class ProposedRelField(BaseModel):
    name: str
    kind: Literal["fixed", "dynamic", "free_text"] = "fixed"
    optional: bool = True
    description: Optional[str] = ""
    # fixed
    enum_name: Optional[str] = None           # choose an existing enum
    new_enum: Optional[EnumCreate] = None     # or create a new one
    # dynamic
    classes: Optional[List[str]] = None
    # free-text
    text_type: Optional[Literal["text", "number"]] = "text"

class ProposedRelationIn(BaseModel):
    name: str
    description: Optional[str] = ""
    subject_classes: List[str]
    object_classes: List[str]
    predicate_choices: Optional[List[str]] = None
    fields: List[ProposedRelField] = []

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

def _normalize_free_text_type(py_type: type) -> str:
    # Frontend treats everything not 'number' as 'text'
    return "number" if py_type in (int, float) else "text"

def _relation_spec_to_meta(spec) -> dict:
    """
    Convert a RelationshipSpec into the JSON structure the frontend expects.
    Shape:
    {
      name: {
        description: str,
        subject: [class,...],
        object:  [class,...],
        attributes: {
          field_name: {
             kind: "enum" | "text" | "number" | "entity",
             enum?: [..],
             classes?: [..],
             nullable: bool,
          }, ...
        }
      }
    }
    """
    attrs: dict[str, dict] = {}

    # Turn predicate_choices into a normal enum attribute to avoid name collision with the edge's
    # 'predicate' property (which stores the relation type name in your UI).
    if getattr(spec, "predicate_choices", None):
        attrs["edge_predicate"] = {
            "kind": "enum",
            "enum": list(spec.predicate_choices),
            "nullable": False
        }

    for f in getattr(spec, "fixed_fields", []) or []:
        if isinstance(f, FixedChoiceField):
            attrs[f.name] = {
                "kind": "enum",
                "enum": list(f.choices),
                "nullable": bool(getattr(f, "optional", True))
            }
        elif isinstance(f, FreeTextField):
            kind = _normalize_free_text_type(getattr(f, "typ", str))
            attrs[f.name] = {
                "kind": kind,
                # keep 'type' only for number; text is implicit
                **({"type": kind} if kind == "number" else {}),
                "nullable": bool(getattr(f, "optional", True))
            }

    for d in getattr(spec, "dynamic_fields", []) or []:
        attrs[d.name] = {
            "kind": "entity",
            "classes": list(d.classes),
            "nullable": bool(getattr(d, "optional", True))
        }

    return {
        "description": getattr(spec, "description", "") or "",
        "subject": list(getattr(spec, "subject_classes", []) or []),
        "object":  list(getattr(spec, "object_classes", []) or []),
        "attributes": attrs
    }

@lru_cache(maxsize=1)
def _build_relations_meta():
    """Import DEFAULT_SPECS and convert to JSON. Return None if import fails."""
    if RelationshipSpec is None:
        return None
    try:
        mod = importlib.import_module(RELATION_SPECS_IMPORT)
    except Exception as e:
        print(f"WARN: could not import {RELATION_SPECS_IMPORT}: {e}")
        return None

    # Preferred: DEFAULT_SPECS = [RelationshipSpec,...]
    specs = getattr(mod, "DEFAULT_SPECS", None)

    # Fallback: scan module symbols for RelationshipSpec instances
    if not specs:
        specs = []
        for name, obj in vars(mod).items():
            try:
                if isinstance(obj, RelationshipSpec):
                    specs.append(obj)
            except Exception:
                pass

    if not specs:
        print("WARN: No RelationshipSpec instances found.")
        return None

    out = {}
    for spec in specs:
        out[spec.name] = _relation_spec_to_meta(spec)
    return out

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
    meta = _build_relations_meta()
    if meta:
        # save to a static json file just for insepection/debugging
        with RELATIONS_FILE.open("w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
        return meta
    # Fallback to static file if import failed
    print('FAILED TO IMPORT RELATION SPECS, FALLING BACK TO STATIC FILE')
    return load_json(RELATIONS_FILE)

@app.post("/api/relations/refresh")
async def refresh_relations():
    try:
        _build_relations_meta.cache_clear()
        meta = _build_relations_meta()
        if not meta:
            raise HTTPException(500, "Could not rebuild relations meta; check RELATION_SPECS_IMPORT")
        return {"ok": True, "count": len(meta)}
    except Exception as e:
        raise HTTPException(500, str(e))

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

def _validate_and_normalize_relations(payload: SavePayload) -> list[dict]:
    """
    Returns a cleaned list of relation dicts ready to persist.
    - Validates subject/object IDs & classes
    - Swaps (subject, object) if the reverse orientation is the valid one
    - Validates attributes per spec; drops unknown attrs
    """
    meta = _build_relations_meta() or load_json(RELATIONS_FILE)
    if not meta:
        raise HTTPException(500, "No relation metadata available.")

    # id -> Entity (pydantic model)
    ent_map = {e.id: e for e in payload.entities}

    cleaned = []
    for rel in payload.relations:
        if rel.predicate not in meta:
            raise HTTPException(400, f"Unknown relation type '{rel.predicate}' in relation {rel.id}")

        if rel.subject not in ent_map or rel.object not in ent_map:
            raise HTTPException(400, f"Relation {rel.id} refers to unknown entity id(s).")

        spec = meta[rel.predicate]
        subj = ent_map[rel.subject]
        obj  = ent_map[rel.object]

        subj_ok = subj.class_ in set(spec.get("subject", []))
        obj_ok  = obj.class_  in set(spec.get("object",  []))
        if not (subj_ok and obj_ok):
            # Try reverse
            subj_ok_rev = subj.class_ in set(spec.get("object", []))
            obj_ok_rev  = obj.class_  in set(spec.get("subject", []))
            if subj_ok_rev and obj_ok_rev:
                # auto-swap to canonical orientation
                rel.subject, rel.object = rel.object, rel.subject
                subj, obj = obj, subj
            else:
                raise HTTPException(
                    400,
                    f"Relation {rel.id} pair ({subj.class_} → {obj.class_}) not allowed for '{rel.predicate}'"
                )

        # Validate attributes (preserve incoming order)
        want_attrs = spec.get("attributes", {}) or {}
        keep: dict[str, any] = {}   # type: ignore , insertion order preserved in Py3.7+

        given = rel.attributes or {}

        # First pass: validate and keep only known attributes in the PROVIDED order
        for name in given.keys():
            aspec = want_attrs.get(name)
            if not aspec:
                # Unknown attribute → ignore (drop), mirroring previous behavior
                continue

            nullable = bool(aspec.get("nullable", True))
            kind = aspec.get("kind", "text")
            val = given.get(name, None)

            # Required check for an explicitly-present-but-empty value
            if (val is None or val == "") and not nullable:
                raise HTTPException(400, f"Relation {rel.id}: missing required attribute '{name}'")

            if val in (None, ""):
                keep[name] = None
                continue

            if kind == "enum":
                allowed = set(aspec.get("enum", []))
                if val not in allowed:
                    raise HTTPException(
                        400,
                        f"Relation {rel.id}: invalid value '{val}' for '{name}'. Allowed: {sorted(allowed)}"
                    )
                keep[name] = val

            elif kind == "number":
                try:
                    keep[name] = float(val)
                except Exception:
                    raise HTTPException(400, f"Relation {rel.id}: '{name}' must be numeric")

            elif kind == "entity":
                target = ent_map.get(str(val))
                if (not target) or (target.class_ not in set(aspec.get("classes", []))):
                    raise HTTPException(
                        400,
                        f"Relation {rel.id}: attribute '{name}' must reference an entity with class in {aspec.get('classes')}"
                    )
                keep[name] = target.id

            else:
                # text (or unknown) → string
                keep[name] = str(val)

        # Second pass: ensure all required attributes exist (even if client didn't include them at all)
        for name, aspec in want_attrs.items():
            if not aspec.get("nullable", True) and name not in keep:
                raise HTTPException(400, f"Relation {rel.id}: missing required attribute '{name}'")


        cleaned.append({
            "id": rel.id,
            "predicate": rel.predicate,
            "subject": rel.subject,
            "object": rel.object,
            "attributes": keep
        })

    return cleaned

@app.post("/api/annotations")
async def save_annotations(payload: SavePayload, overwrite: bool = Query(False)):
    # sanity check spans
    for ent in payload.entities:
        if not (0 <= ent.span.start <= ent.span.end <= len(payload.text)):
            raise HTTPException(400, f"Invalid span for entity {ent.id}")

    # NEW: validate & normalize relations (raises on error)
    normalized_relations = _validate_and_normalize_relations(payload)

    obj = payload.model_dump(by_alias=True)
    obj.pop("text", None)  # don't persist raw text
    # NEW: use cleaned relations
    obj["relations"] = normalized_relations

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

# ---------- NEW: helpers for propose-relationship ----------

def _ensure_proposed_rel_file():
    """Create proposed_rel.py with a minimal header if missing."""
    if PROPOSED_REL_FILE.exists():
        return
    PROPOSED_REL_FILE.parent.mkdir(parents=True, exist_ok=True)
    header = textwrap.dedent(
        """
        # Auto-generated proposed relationships
        from __future__ import annotations
        from relcode.utils.relation_utils import RelationshipSpec, FixedChoiceField, FreeTextField, DynamicEntityField
        # your enums live here
        from relcode.utils.my_enums import *
        """
    )
    PROPOSED_REL_FILE.write_text(header + "\n\n", encoding="utf-8")


def _camel_to_const_name(s: str) -> str:
    import re as _re
    s1 = _re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", s)
    s2 = _re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    return s2.upper()


def _sanitize_py_str(s: str) -> str:
    return json.dumps(s or "")  # ensures proper quoting/escaping


def _load_field_descriptions() -> dict:
    if not FIELD_DESC_FILE.exists():
        return {"general_qualifiers": {}}
    try:
        return json.loads(FIELD_DESC_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"general_qualifiers": {}}


def _write_json_atomic(path: Path, obj: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tmp:
        json.dump(obj, tmp, ensure_ascii=False, indent=2)
        tmp_path = tmp.name
    os.replace(tmp_path, path)


def _list_enums_from_module() -> dict:
    """Return {NAME: [values,...]} from relcode.utils.my_enums."""
    try:
        mod = importlib.import_module(ENUMS_IMPORT)
        # reload so new appends are visible during dev
        try:
            mod = importlib.reload(mod)  # type: ignore
        except Exception:
            pass
    except Exception as e:
        print(f"WARN: cannot import {ENUMS_IMPORT}: {e}")
        return {}

    out = {}
    for k, v in vars(mod).items():
        if not isinstance(k, str) or not k.isupper() or k.startswith("_"):
            continue
        if isinstance(v, (list, tuple, set)):
            out[k] = [str(x) for x in list(v)]
    return out


def _append_new_enums(new_enums: dict[str, list[str]]) -> list[str]:
    """Append simple list-style enums to my_enums.py. Returns list of names written."""
    if not new_enums:
        return []
    try:
        mod = importlib.import_module(ENUMS_IMPORT)
        enum_file = Path(getattr(mod, "__file__", ""))
    except Exception as e:
        raise HTTPException(500, f"Could not locate my_enums.py via {ENUMS_IMPORT}: {e}")

    lines = ["\n\n# ---- Auto-added via propose_relation ----\n"]
    for name, vals in new_enums.items():
        lines.append(f"# {name}\n")
        lines.append(f"{name} = [\n")
        for v in vals:
            lines.append(f"    {json.dumps(str(v))},\n")
        lines.append("]\n")
    with enum_file.open("a", encoding="utf-8") as f:
        f.write("".join(lines))
    return list(new_enums.keys())


def _render_relationship_code(
    *,
    rel_name: str,
    description: str,
    subject_classes: list[str],
    object_classes: list[str],
    predicate_choices: list[str] | None,
    compiled_fields: list[dict],  # each: {name, kind, optional, enum_name?, text_type?, classes?}
) -> str:
    """Return a complete RelationshipSpec definition block as a string."""
    const_var = _camel_to_const_name(rel_name)

    def fmt_list(items: list[str]) -> str:
        return "[" + ", ".join(json.dumps(s) for s in items) + "]"

    fixed_lines: list[str] = []
    dyn_lines: list[str] = []

    for f in compiled_fields:
        nm = f["name"]
        opt = bool(f.get("optional", True))
        if f["kind"] == "fixed":
            enum_name = f.get("enum_name")
            if not enum_name:
                raise HTTPException(400, f"Field '{nm}' is fixed but missing enum_name")
            args = [json.dumps(nm), enum_name]
            kwargs = [f"optional={str(opt)}"]
            fixed_lines.append(f"        FixedChoiceField({', '.join(args + kwargs)})")
        elif f["kind"] == "free_text":
            args = [json.dumps(nm)]
            kwargs = [f"optional={str(opt)}"]
            if f.get("text_type") == "number":
                kwargs.append("typ=float")
            fixed_lines.append(f"        FreeTextField({', '.join(args + kwargs)})")
        elif f["kind"] == "dynamic":
            classes = f.get("classes") or []
            args = [json.dumps(nm), f"classes={fmt_list(classes)}"]
            kwargs = [f"optional={str(opt)}"]
            dyn_lines.append(f"        DynamicEntityField({', '.join(args + kwargs)})")
        else:
            raise HTTPException(400, f"Unsupported field kind: {f['kind']}")

    parts: list[str] = []
    parts.append(f"{const_var} = RelationshipSpec(")
    parts.append(f"    name={json.dumps(rel_name)},")
    parts.append(f"    description={_sanitize_py_str(description)},")
    parts.append(f"    subject_classes={fmt_list(subject_classes)},")
    parts.append(f"    object_classes={fmt_list(object_classes)},")
    if predicate_choices:
        parts.append(f"    predicate_choices={fmt_list(predicate_choices)},")
    if fixed_lines:
        parts.append("    fixed_fields=[")
        parts.extend(fixed_lines)
        parts.append("    ],")
    if dyn_lines:
        parts.append("    dynamic_fields=[")
        parts.extend(dyn_lines)
        parts.append("    ],")
    parts.append(")\n")

    return "\n" + "\n".join(parts)

# ---------- NEW: endpoints for propose-relationship ----------
@app.get("/api/enums")
async def get_enums():
    return _list_enums_from_module()

import re as _re

@app.post("/api/enums")
async def create_enum(payload: EnumAddIn):
    # normalize & validate name
    raw = (payload.name or "").strip()
    name = _re.sub(r"[^A-Za-z0-9_]+", "_", raw).upper()
    if not name.endswith("_ENUM"):
        name = name + "_ENUM"
    if not _re.match(r"^[A-Z_][A-Z0-9_]*$", name):
        raise HTTPException(400, f"Invalid enum name after normalization: {name}")

    values = [str(v).strip() for v in (payload.values or []) if str(v).strip()]
    if not values:
        raise HTTPException(400, "At least one value is required.")

    # de-dup, preserve order
    seen = set()
    uniq_vals = []
    for v in values:
        if v not in seen:
            uniq_vals.append(v)
            seen.add(v)

    existing = _list_enums_from_module()
    if name in existing:
        raise HTTPException(409, f"Enum '{name}' already exists.")

    created = _append_new_enums({name: uniq_vals})
    if not created:
        raise HTTPException(500, "Failed to append enum to my_enums.py")

    # return fresh map (handy for the UI)
    return {"ok": True, "name": name, "values": uniq_vals}


@app.get("/api/field-descriptions")
async def get_field_descriptions():
    return _load_field_descriptions()


@app.post("/api/proposed-relations")
async def propose_relation(payload: ProposedRelationIn):
    # Validate relation name (CamelCase)
    if not re.match(r"^[A-Z][A-Za-z0-9_]*$", payload.name):
        raise HTTPException(400, "Invalid relation name (use CamelCase, e.g., ChemicalAffectsGene)")

    # Validate subject/object classes (must be known)
    classes_meta = load_json(CLASSES_FILE)
    known_classes = set(classes_meta.keys())
    if not payload.subject_classes or not all(c in known_classes for c in payload.subject_classes):
        raise HTTPException(400, f"Unknown subject class in {payload.subject_classes}")
    if not payload.object_classes or not all(c in known_classes for c in payload.object_classes):
        raise HTTPException(400, f"Unknown object class in {payload.object_classes}")

    # Prepare enums and compile field specs
    existing_enums = _list_enums_from_module()
    to_create: dict[str, list[str]] = {}
    compiled: list[dict] = []

    # For relation-specific field descriptions update
    fd = _load_field_descriptions()
    general = set((fd.get("general_qualifiers") or {}).keys())
    rel_specific_added = {}

    def gen_enum_name(default_rel: str, field_name: str) -> str:
        base = f"{_camel_to_const_name(default_rel)}_{field_name.upper()}_ENUM"
        # Avoid collision with existing or to-be-created
        candidate = base
        i = 2
        while candidate in existing_enums or candidate in to_create:
            candidate = f"{base}_{i}"
            i += 1
        return candidate

    for f in payload.fields:
        if not re.match(r"^[a-z_][a-z0-9_]*$", f.name):
            raise HTTPException(400, f"Invalid field name '{f.name}' (use snake_case)")

        item: dict = {
            "name": f.name,
            "kind": f.kind,
            "optional": bool(f.optional),
        }

        if f.kind == "fixed":
            enum_name = f.enum_name
            if f.new_enum and f.new_enum.values:
                # generate or use provided name
                new_name = (f.new_enum.name or gen_enum_name(payload.name, f.name)).upper()
                # normalize suffix
                if not new_name.endswith("_ENUM"):
                    new_name = new_name + "_ENUM"
                vals = [str(v).strip() for v in (f.new_enum.values or []) if str(v).strip()]
                if not vals:
                    raise HTTPException(400, f"New enum for field '{f.name}' has no values")
                to_create[new_name] = vals
                enum_name = new_name

            if not enum_name:
                raise HTTPException(400, f"Field '{f.name}': choose an existing enum or create a new one")

            item["enum_name"] = enum_name

        elif f.kind == "dynamic":
            if not f.classes:
                raise HTTPException(400, f"Field '{f.name}' is dynamic but has no classes")
            item["classes"] = list(dict.fromkeys([str(c) for c in f.classes]))

        elif f.kind == "free_text":
            item["text_type"] = f.text_type or "text"
        else:
            raise HTTPException(400, f"Unsupported field kind: {f.kind}")

        compiled.append(item)

        # Track relation-specific descriptions (only for non-general names)
        if f.description and f.name not in general:
            rel_specific_added[f.name] = f.description

    # Write enums first (so names exist in the spec file for human copy/paste)
    created_names = _append_new_enums(to_create)

    # Append / update field_descriptions.json
    if rel_specific_added:
        cur = _load_field_descriptions()
        cur.setdefault(payload.name, {})
        cur[payload.name].update(rel_specific_added)
        _write_json_atomic(FIELD_DESC_FILE, cur)

    # Render spec block and append to proposed_rel.py
    _ensure_proposed_rel_file()
    existing = PROPOSED_REL_FILE.read_text(encoding="utf-8") if PROPOSED_REL_FILE.exists() else ""
    # avoid duplicate by name=
    if f"name=\"{payload.name}\"" in existing:
        raise HTTPException(409, f"A proposed relation named '{payload.name}' already exists in proposed_rel.py")

    code = _render_relationship_code(
        rel_name=payload.name,
        description=payload.description or "",
        subject_classes=list(payload.subject_classes),
        object_classes=list(payload.object_classes),
        predicate_choices=(payload.predicate_choices or None),
        compiled_fields=compiled,
    )
    with PROPOSED_REL_FILE.open("a", encoding="utf-8") as f:
        f.write(code)

    return {
        "ok": True,
        "proposed_file": str(PROPOSED_REL_FILE),
        "enums_created": created_names,
        "relation_specific_fields_added": list(rel_specific_added.keys()),
        "bytes_written": len(code),
    }

# ---------- Dev convenience ----------
@app.get("/")
async def root():
    return {"status": "ok", "message": "Backend is running"}
