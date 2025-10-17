from fastapi import APIRouter, HTTPException, Query
from app.core.paths import ANNOT_FILE
from app.services.io import read_annotations_jsonl, write_annotations_jsonl
from app.services.relations import validate_and_normalize_relations
from app.models.schemas import SavePayload

router = APIRouter()

@router.get("/annotations/{text_id}/exists")
async def annotations_exists(text_id: str):
    items = read_annotations_jsonl(ANNOT_FILE)
    return {"exists": any(it.get("text_id") == text_id for it in items)}

@router.get("/annotations/{text_id}")
async def get_annotation(text_id: str):
    items = read_annotations_jsonl(ANNOT_FILE)
    for it in items:
        if it.get("text_id") == text_id:
            return it
    raise HTTPException(404, "No saved annotation for this text_id")

@router.post("/annotations")
async def save_annotations(payload: SavePayload, overwrite: bool = Query(False)):
    for ent in payload.entities:
        if not (0 <= ent.span.start <= ent.span.end <= len(payload.text)):
            raise HTTPException(400, f"Invalid span for entity {ent.id}")

    normalized_relations = validate_and_normalize_relations(payload)

    obj = payload.model_dump(by_alias=True)
    obj.pop("text", None)
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
