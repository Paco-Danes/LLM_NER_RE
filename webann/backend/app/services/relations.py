from __future__ import annotations
from functools import lru_cache
from typing import Any, Dict, List
from fastapi import HTTPException
import importlib, json

from app.core.config import get_settings
from app.core.paths import RELATIONS_FILE
from app.models.schemas import SavePayload
from app.services.io import load_json
from relcode.utils.relation_utils import RelationshipSpec, FixedChoiceField, FreeTextField, DynamicEntityField

def _normalize_free_text_type(py_type: type) -> str:
    return "number" if py_type in (int, float) else "text"

def relation_spec_to_meta(spec) -> dict:
    attrs: dict[str, dict] = {}

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
def build_relations_meta() -> Dict[str, Any] | None:
    """Import DEFAULT_SPECS and convert to JSON. Return None if import fails."""
    modname = get_settings().RELATION_SPECS_IMPORT
    try:
        mod = importlib.import_module(modname)
    except Exception as e:
        print(f"WARN: could not import {modname}: {e}")
        return None

    specs = getattr(mod, "DEFAULT_SPECS", None)
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
        out[spec.name] = relation_spec_to_meta(spec)
    return out

def validate_and_normalize_relations(payload: SavePayload) -> list[dict]:
    """
    Returns a cleaned list of relation dicts ready to persist.
    - Validates subject/object IDs & classes
    - Swaps (subject, object) if the reverse orientation is the valid one
    - Validates attributes per spec; drops unknown attrs
    """
    meta = build_relations_meta() or load_json(RELATIONS_FILE)
    if not meta:
        raise HTTPException(500, "No relation metadata available.")

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
            subj_ok_rev = subj.class_ in set(spec.get("object", []))
            obj_ok_rev  = obj.class_  in set(spec.get("subject", []))
            if subj_ok_rev and obj_ok_rev:
                rel.subject, rel.object = rel.object, rel.subject
                subj, obj = obj, subj
            else:
                raise HTTPException(
                    400,
                    f"Relation {rel.id} pair ({subj.class_} → {obj.class_}) not allowed for '{rel.predicate}'"
                )

        want_attrs = spec.get("attributes", {}) or {}
        keep: dict[str, any] = {} # type: ignore
        given = rel.attributes or {}

        for name in given.keys():
            aspec = want_attrs.get(name)
            if not aspec:
                continue

            nullable = bool(aspec.get("nullable", True))
            kind = aspec.get("kind", "text")
            val = given.get(name, None)

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
                keep[name] = str(val)

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
