from fastapi import APIRouter, HTTPException
from typing import Optional
from app.core.paths import CLASSES_FILE
from app.services.io import load_json
from app.services.enums import list_enums_from_module, load_field_descriptions
from app.services.proposals import propose_relation
from app.models.schemas import EnumAddIn, ProposedRelationIn
from app.services.enums import append_new_enums

router = APIRouter()

@router.get("/enums")
async def get_enums():
    return list_enums_from_module()

@router.post("/enums")
async def create_enum(payload: EnumAddIn):
    import re
    raw = (payload.name or "").strip()
    name = re.sub(r"[^A-Za-z0-9_]+", "_", raw).upper()
    if not name.endswith("_ENUM"):
        name = name + "_ENUM"
    if not re.match(r"^[A-Z_][A-Z0-9_]*$", name):
        raise HTTPException(400, f"Invalid enum name after normalization: {name}")

    values = [str(v).strip() for v in (payload.values or []) if str(v).strip()]
    if not values:
        raise HTTPException(400, "At least one value is required.")

    existing = list_enums_from_module()
    if name in existing:
        raise HTTPException(409, f"Enum '{name}' already exists.")

    created = append_new_enums({name: values})
    if not created:
        raise HTTPException(500, "Failed to append enum to my_enums.py")
    return {"ok": True, "name": name, "values": values}

@router.get("/field-descriptions")
async def get_field_descriptions():
    return load_field_descriptions()

@router.post("/proposed-relations")
async def post_proposed_relation(payload: ProposedRelationIn):
    classes_meta = load_json(CLASSES_FILE)
    known = set(classes_meta.keys())
    return propose_relation(payload, known_classes=known)
