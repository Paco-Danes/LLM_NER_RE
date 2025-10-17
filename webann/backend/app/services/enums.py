from __future__ import annotations
import importlib, json, re, tempfile, os
from typing import Dict, List
from fastapi import HTTPException
from pathlib import Path

from app.core.config import get_settings
from app.core.paths import FIELD_DESC_FILE
from app.services.io import write_json_atomic

def list_enums_from_module() -> dict:
    """Return {NAME: [values,...]} from relcode.utils.my_enums."""
    modname = get_settings().ENUMS_IMPORT
    try:
        mod = importlib.import_module(modname)
        try:
            mod = importlib.reload(mod)  # dev convenience
        except Exception:
            pass
    except Exception as e:
        print(f"WARN: cannot import {modname}: {e}")
        return {}

    out = {}
    for k, v in vars(mod).items():
        if not isinstance(k, str) or not k.isupper() or k.startswith("_"):
            continue
        if isinstance(v, (list, tuple, set)):
            out[k] = [str(x) for x in list(v)]
    return out

def append_new_enums(new_enums: Dict[str, List[str]]) -> List[str]:
    """Append enums to my_enums.py. Returns list of names written."""
    if not new_enums:
        return []
    modname = get_settings().ENUMS_IMPORT
    try:
        mod = importlib.import_module(modname)
        enum_file = Path(getattr(mod, "__file__", ""))
    except Exception as e:
        raise HTTPException(500, f"Could not locate my_enums.py via {modname}: {e}")

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

def load_field_descriptions() -> dict:
    if not FIELD_DESC_FILE.exists():
        return {"general_qualifiers": {}}
    try:
        return json.loads(FIELD_DESC_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"general_qualifiers": {}}

def upsert_relation_specific_field_descriptions(relation_name: str, new_items: dict):
    if not new_items:
        return
    cur = load_field_descriptions()
    cur.setdefault(relation_name, {})
    cur[relation_name].update(new_items)
    write_json_atomic(FIELD_DESC_FILE, cur)
