from fastapi import APIRouter, HTTPException
from app.services.embeddings import load_index, load_rel_index, load_embedder, encode_query
from app.core.config import get_settings
from app.models.schemas import SuggestIn, SuggestOut, SuggestItem

router = APIRouter()

@router.get("/semantic/status")
async def semantic_status(kind: str = "class"):
    idx = load_rel_index() if kind == "relation" else load_index()
    ok = idx is not None
    return {
        "ready": bool(ok),
        "size": (len(idx["labels"]) if ok else 0),
        "model": get_settings().EMBED_MODEL_NAME,
        "has_embedder": load_embedder() is not None
    }

@router.post("/semantic/suggest", response_model=SuggestOut)
async def semantic_suggest(payload: SuggestIn):
    idx = load_rel_index() if payload.kind == "relation" else load_index()
    if idx is None:
        raise HTTPException(503, "Semantic index missing. Run the embedding builder first.")

    query = " ".join([payload.query or "", payload.label or ""]).strip()
    if not query:
        return {"ready": True, "total": len(idx["labels"]), "items": []}

    qvec = encode_query([query])[0]
    sims = idx["embeddings"] @ qvec

    import numpy as np
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
        items.append(SuggestItem(class_name=name, score=s, description=meta.get("description")))
    return {"ready": True, "total": len(idx["labels"]), "items": items}
