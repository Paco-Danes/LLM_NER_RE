from __future__ import annotations
import json, os, re, textwrap, importlib, tempfile
from functools import lru_cache
from pathlib import Path
from typing import List, Dict, Any

from fastapi import HTTPException

from app.core.paths import PROPOSED_FILE, PROPOSED_REL_FILE
from app.core.config import get_settings
from app.services.enums import list_enums_from_module, append_new_enums, load_field_descriptions, upsert_relation_specific_field_descriptions
from app.services.io import write_json_atomic
from app.models.schemas import AttrSpec, ProposedClassIn, ProposedRelationIn

# ---- Proposed classes ----

def ensure_proposed_classes_file():
    if PROPOSED_FILE.exists():
        return
    PROPOSED_FILE.parent.mkdir(parents=True, exist_ok=True)
    header = textwrap.dedent("""\
        # Auto-generated proposed classes
        from __future__ import annotations
        from typing import Optional, List, Literal
        from pydantic import BaseModel, Field

        class NamedEntity(BaseModel):
            \"\"\"Base type for all proposed entities.\"\"\" 
            pass
        """)
    PROPOSED_FILE.write_text(header, encoding="utf-8")

def render_type_and_default(a: AttrSpec) -> tuple[str, str]:
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
        qvals = ", ".join(json.dumps(v) for v in vals)
        base = f"Literal[{qvals}]"
    else:
        raise HTTPException(400, f"Unsupported type: {t}")

    if a.optional:
        return (f"Optional[{base}]", "None")
    else:
        return (base, "...")

def sanitize_docstring(s: str) -> str:
    return (s or "").replace('"""', '\\"""')

def render_class_code(payload: ProposedClassIn) -> str:
    lines = []
    lines.append(f"class {payload.name}(NamedEntity):")
    doc = sanitize_docstring(payload.description or "")
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
        ann, default = render_type_and_default(a)
        desc_json = json.dumps(a.description or "")
        lines.append(f"    {a.name}: {ann} = Field({default}, description={desc_json})")

    return "\n".join(lines) + "\n"

def propose_class(payload: ProposedClassIn):
    if not re.match(r"^[A-Z][A-Za-z0-9_]*$", payload.name):
        raise HTTPException(400, "Invalid Python class name (use CamelCase).")
    ensure_proposed_classes_file()
    txt = PROPOSED_FILE.read_text(encoding="utf-8")
    if re.search(rf"^\s*class\s+{re.escape(payload.name)}\s*\(", txt, flags=re.M):
        raise HTTPException(409, f'Class "{payload.name}" already exists in proposed_classes.py')
    code = "\n" + render_class_code(payload)
    with PROPOSED_FILE.open("a", encoding="utf-8") as f:
        f.write(code)
    return {"ok": True, "file": str(PROPOSED_FILE), "bytes_written": len(code)}

# ---- Proposed relations ----

def ensure_proposed_rel_file():
    if PROPOSED_REL_FILE.exists():
        return
    PROPOSED_REL_FILE.parent.mkdir(parents=True, exist_ok=True)
    header = textwrap.dedent(
        """
        # Auto-generated proposed relationships
        from __future__ import annotations
        from relcode.utils.relation_utils import RelationshipSpec, FixedChoiceField, FreeTextField, DynamicEntityField
        from relcode.utils.my_enums import *
        """
    )
    PROPOSED_REL_FILE.write_text(header + "\n\n", encoding="utf-8")

def camel_to_const_name(s: str) -> str:
    import re as _re
    s1 = _re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", s)
    s2 = _re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    return s2.upper()

def sanitize_py_str(s: str) -> str:
    return json.dumps(s or "")

def render_relationship_code(*,
    rel_name: str,
    description: str,
    subject_classes: list[str],
    object_classes: list[str],
    predicate_choices: list[str] | None,
    compiled_fields: list[dict],  # {name, kind, optional, enum_name?, text_type?, classes?}
) -> str:
    const_var = camel_to_const_name(rel_name)

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
            fixed_lines.append(f"        FixedChoiceField({json.dumps(nm)}, {enum_name}, optional={opt})")
        elif f["kind"] == "free_text":
            kw = ", typ=float" if f.get("text_type") == "number" else ""
            fixed_lines.append(f"        FreeTextField({json.dumps(nm)}, optional={opt}{kw})")
        elif f["kind"] == "dynamic":
            classes = f.get("classes") or []
            fixed_lines.append(
                f"        DynamicEntityField({json.dumps(nm)}, classes={fmt_list(classes)}, optional={opt})"
            )
        else:
            raise HTTPException(400, f"Unsupported field kind: {f['kind']}")

    parts: list[str] = []
    parts.append(f"{const_var} = RelationshipSpec(")
    parts.append(f"    name={json.dumps(rel_name)},")
    parts.append(f"    description={sanitize_py_str(description)},")
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

def propose_relation(payload: ProposedRelationIn, known_classes: set[str]):
    if not re.match(r"^[A-Z][A-Za-z0-9_]*$", payload.name):
        raise HTTPException(400, "Invalid relation name (use CamelCase, e.g., ChemicalAffectsGene)")

    if not payload.subject_classes or not all(c in known_classes for c in payload.subject_classes):
        raise HTTPException(400, f"Unknown subject class in {payload.subject_classes}")
    if not payload.object_classes or not all(c in known_classes for c in payload.object_classes):
        raise HTTPException(400, f"Unknown object class in {payload.object_classes}")

    existing_enums = list_enums_from_module()
    to_create: dict[str, list[str]] = {}
    compiled: list[dict] = []

    fd = load_field_descriptions()
    general = set((fd.get("general_qualifiers") or {}).keys())
    rel_specific_added = {}

    def gen_enum_name(default_rel: str, field_name: str) -> str:
        base = f"{camel_to_const_name(default_rel)}_{field_name.upper()}_ENUM"
        candidate = base
        i = 2
        while candidate in existing_enums or candidate in to_create:
            candidate = f"{base}_{i}"
            i += 1
        return candidate

    for f in payload.fields:
        if not re.match(r"^[a-z_][a-z0-9_]*$", f.name):
            raise HTTPException(400, f"Invalid field name '{f.name}' (use snake_case)")

        item: dict = {"name": f.name, "kind": f.kind, "optional": bool(f.optional)}

        if f.kind == "fixed":
            enum_name = f.enum_name
            if f.new_enum and f.new_enum.values:
                new_name = (f.new_enum.name or gen_enum_name(payload.name, f.name)).upper()
                if not new_name.endswith("_ENUM"):
                    new_name += "_ENUM"
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

        compiled.append(item)

        if f.description and f.name not in general:
            rel_specific_added[f.name] = f.description

    created_names = append_new_enums(to_create)
    if rel_specific_added:
        upsert_relation_specific_field_descriptions(payload.name, rel_specific_added)

    ensure_proposed_rel_file()
    existing = PROPOSED_REL_FILE.read_text(encoding="utf-8") if PROPOSED_REL_FILE.exists() else ""
    if f"name=\"{payload.name}\"" in existing:
        raise HTTPException(409, f"A proposed relation named '{payload.name}' already exists in proposed_rel.py")

    code = render_relationship_code(
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
