from fastapi import APIRouter, HTTPException
import json

from app.core.paths import RELATIONS_FILE
from app.services.relations import build_relations_meta

router = APIRouter()

@router.get("/relations")
async def get_relations():
    meta = build_relations_meta()
    if meta:
        with RELATIONS_FILE.open("w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
        return meta
    return json.loads(RELATIONS_FILE.read_text(encoding="utf-8"))

@router.post("/relations/refresh")
async def refresh_relations():
    try:
        build_relations_meta.cache_clear()  # type: ignore[attr-defined]
        meta = build_relations_meta()
        if not meta:
            raise HTTPException(500, "Could not rebuild relations meta; check RELATION_SPECS_IMPORT")
        return {"ok": True, "count": len(meta)}
    except Exception as e:
        raise HTTPException(500, str(e))
