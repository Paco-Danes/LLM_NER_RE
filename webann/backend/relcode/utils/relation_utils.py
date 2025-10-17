from __future__ import annotations
from dataclasses import dataclass, field
from typing import (
    Annotated, Optional, Sequence, Union, Literal, Type, Iterable, Callable, Dict, Tuple
)
from enum import Enum
import re, keyword, hashlib

from pydantic import BaseModel, Field, create_model
from pydantic import TypeAdapter  # for producing a JSON Schema with $defs/$refs

from . import my_enums as enum_mod  # your module with enum lists

# ============================================================
# Utilities
# ============================================================

def dedup_preserve(seq: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(x for x in seq if isinstance(x, str) and x))

def Lit(values: Sequence[str]):
    # Python 3.11+: unpack a tuple into Literal[…]
    return Literal[*tuple(values)]

def extract_labels(ner_output: dict) -> dict[str, list[str]]:
    """Extracts labels per NER class, preserving the first occurrence order."""
    by_class: dict[str, list[str]] = {}
    for cls_name, items in ner_output.items():
        if not isinstance(items, list):
            continue
        labels: list[str] = []
        for it in items:
            if isinstance(it, dict) and isinstance(it.get("label"), str):
                labels.append(it["label"])
            elif isinstance(it, str):
                labels.append(it)
        labels = dedup_preserve(labels)
        if labels:
            by_class[cls_name] = labels
    return by_class

def _optional(typ):
    from typing import Optional as _Opt
    return _Opt[typ]

def _union_labels(classes: Sequence[str], labels_by_class: dict[str, list[str]]) -> list[str]:
    vals: list[str] = []
    for cls in classes:
        vals.extend(labels_by_class.get(cls, []))
    return dedup_preserve(vals)

def _normalize_values(values):
    # same normalization you use for keys in EnumRegistry
    return tuple(dedup_preserve(list(values)))

# Build a map: (normalized tuple of strings) -> variable name from utils.my_enums
ENUM_NAME_BY_VALUES: dict[tuple[str, ...], str] = {}
def _index_enum_module(mod=enum_mod):
    for name, val in vars(mod).items():
        if isinstance(val, (list, tuple)) and all(isinstance(x, str) for x in val):
            key = _normalize_values(val)
            # keep the first seen as the canonical name
            ENUM_NAME_BY_VALUES.setdefault(key, name)

_index_enum_module()

# ============================================================
# Relationship spec DSL (unchanged API)
# ============================================================

@dataclass(frozen=True)
class FixedChoiceField:
    name: str
    choices: Sequence[str]
    optional: bool = True
    schema_name: str | None = None  # preferred reusable $defs name (if dedupbed)

@dataclass(frozen=True)
class FreeTextField:
    name: str
    optional: bool = True
    typ: type = str

@dataclass(frozen=True)
class DynamicEntityField:
    """
    Field whose allowed strings come from the union of the listed NER classes.
    If the union is empty for the current document, this field is omitted entirely.
    """
    name: str
    classes: Sequence[str]
    optional: bool = True
    schema_name: str | None = None  # preferred reusable $defs name (if dedupbed)

@dataclass(frozen=True)
class RelationshipSpec:
    name: str
    description: str # useless in this code, helpful for defining the spec and LLM 
    subject_classes: Sequence[str]
    object_classes: Sequence[str]
    predicate_choices: Sequence[str]
    fixed_fields: Sequence[FixedChoiceField | FreeTextField] = field(default_factory=list)
    dynamic_fields: Sequence[DynamicEntityField] = field(default_factory=list)

# ============================================================
# Enum registry: turns repeated long enums into shared Python Enum types
# so Pydantic will emit $defs/$refs; otherwise uses inline Literal[…]
# ============================================================

EnumKey = Tuple[str, ...]  # order-preserving, deduped

def _sanitize_member(name: str) -> str:
    raw = re.sub(r"\W+", "_", name).upper() or "EMPTY"
    if raw[0].isdigit():
        raw = f"V_{raw}"
    if keyword.iskeyword(raw):
        raw = f"{raw}_"
    return raw

def _stable_enum_name(values: Sequence[str]) -> str:
    # short, stable, content-based name if caller didn't provide one
    h = hashlib.sha1(("|".join(values)).encode("utf-8")).hexdigest()[:8]
    base = _sanitize_member(values[0]) if values else "ENUM"
    return f"{base}_ENUM_{h}"

class EnumRegistry:
    """
    Decide for each value-set whether to inline as Literal[...] or reuse a shared Enum type.
    policy:
      - 'auto'   : share iff used >1 AND len(values) > threshold
      - 'never'  : always inline (Literal)
      - 'always' : always share if used >1 OR len(values) > threshold
    """
    def __init__(self, policy: Literal["auto","never","always"]="auto", threshold: int = 4):
        self.policy = policy
        self.threshold = int(threshold)
        self._usage: Dict[EnumKey, int] = {}
        self._values: Dict[EnumKey, list[str]] = {}
        self._preferred_name: Dict[EnumKey, str] = {}
        self._shared_types: Dict[EnumKey, Enum] = {}

    @staticmethod
    def _key(values: Sequence[str]) -> EnumKey:
        return tuple(dedup_preserve(values))

    def register(self, values: Sequence[str], preferred_schema_name: str | None = None) -> None:
        key = self._key(values)
        if not key:
            return
        self._usage[key] = self._usage.get(key, 0) + 1
        if key not in self._values:
            self._values[key] = list(key)
        # if any field gives a nice reusable name, remember the first one
        if preferred_schema_name and key not in self._preferred_name:
            self._preferred_name[key] = preferred_schema_name

    def _should_share(self, key: EnumKey) -> bool:
        if self.policy == "never":
            return False
        n_uses = self._usage.get(key, 0)
        n_vals = len(key)
        if self.policy == "always":
            return (n_uses > 1) or (n_vals > self.threshold)
        # auto
        return (n_uses > 1) and (n_vals > self.threshold)

    def _make_enum_type(self, key: EnumKey) -> Enum:
        values = self._values[key]
        # name preference: provided schema_name, else stable content name
        name = self._preferred_name.get(key) or _stable_enum_name(values)
        # create unique member names, preserving value order
        used: set[str] = set()
        members: Dict[str, str] = {}
        for v in values:
            m = _sanitize_member(v)
            i = 2
            base = m
            while m in used:
                m = f"{base}_{i}"
                i += 1
            used.add(m)
            members[m] = v
        enum_type = Enum(name, members)
        enum_type.__module__ = "shared_enums"  # helps pydantic give a nicer $defs name
        return enum_type

    def finalize(self) -> None:
        """Create Enum classes for all value-sets that should be shared."""
        for key in list(self._usage.keys()):
            if self._should_share(key) and key not in self._shared_types:
                self._shared_types[key] = self._make_enum_type(key)

    def type_for(self, values: Sequence[str]):
        """Return either a shared Enum type (for $ref) or an inline Literal[…]."""
        key = self._key(values)
        if not key:
            return str  # shouldn't happen for Enumerations; safe default
        shared = self._shared_types.get(key)
        if shared is not None:
            return shared
        return Lit(list(key))
    

# ============================================================
# Candidate realization (NER filter) and ranking hook
# ============================================================

@dataclass(frozen=True)
class RealizedDynamic:
    field: DynamicEntityField
    choices: list[str]  # resolved from NER (union of classes)

@dataclass(frozen=True)
class CandidateSpec:
    spec: RelationshipSpec
    subject_choices: list[str]
    object_choices: list[str]
    dynamic_realized: list[RealizedDynamic]  # only those with non-empty choices

def realize_candidates_via_ner(
    specs: Sequence[RelationshipSpec],
    labels_by_class: dict[str, list[str]],
) -> list[CandidateSpec]:
    candidates: list[CandidateSpec] = []
    for spec in specs:
        subj_opts = _union_labels(spec.subject_classes, labels_by_class)
        obj_opts  = _union_labels(spec.object_classes, labels_by_class)
        if not subj_opts or not obj_opts:
            continue  # drop the whole relation if either side is missing

        realized_dyn: list[RealizedDynamic] = []
        for d in spec.dynamic_fields:
            opts = _union_labels(d.classes, labels_by_class)
            if opts:
                realized_dyn.append(RealizedDynamic(d, opts))

        candidates.append(CandidateSpec(spec, subj_opts, obj_opts, realized_dyn))
    return candidates

def rank_and_select_candidates(
    candidates: Sequence[CandidateSpec],
    top_k: Optional[int] = 10,
    scorer: Optional[Callable[[CandidateSpec], float]] = None,
) -> list[CandidateSpec]:
    """
    Placeholder for your dual-encoder ranking.
    Provide `scorer` that returns a higher-is-better score; we sort desc and take top_k.
    If no scorer is given, preserve original order. If candidates < top_k, return all.
    """
    if len(candidates) <= (top_k or 0):
        return list(candidates)
    if not scorer:
        return list(candidates[: (top_k or len(candidates))])
    scored = sorted(((scorer(c), c) for c in candidates), key=lambda x: x[0], reverse=True)
    keep = scored[: (top_k or len(scored))]
    return [c for _, c in keep]

# ============================================================
# Model builder (with enum sharing policy)
# ============================================================

def _add_fixed_fields(
    fields: dict,
    spec: RelationshipSpec,
    enum_reg: EnumRegistry,
):
    for f in spec.fixed_fields:
        if isinstance(f, FixedChoiceField):
            t = enum_reg.type_for(f.choices)
            if f.optional:
                t = _optional(t)
                fields[f.name] = (t, Field(default=None))
            else:
                fields[f.name] = (t, Field(...))
        elif isinstance(f, FreeTextField):
            t = f.typ
            if f.optional:
                t = _optional(t)
                fields[f.name] = (t, Field(default=None))
            else:
                fields[f.name] = (t, Field(...))
        else:
            raise TypeError(f"Unsupported fixed field spec: {f}")

def _add_dynamic_fields(
    fields: dict,
    realized_dyn: list[RealizedDynamic],
    enum_reg: EnumRegistry,
):
    for rd in realized_dyn:
        d = rd.field
        t = enum_reg.type_for(rd.choices)
        if d.optional:
            t = _optional(t)
            fields[d.name] = (t, Field(default=None))
        else:
            fields[d.name] = (t, Field(...))

def _register_all_enums_for_candidates(
    cands: Sequence[CandidateSpec],
    enum_reg: EnumRegistry,
):
    """
    Pass 1: register all value-sets so we can decide which ones become shared $defs.
    We prefer field-provided schema_name where available.
    """
    for c in cands:
        # core triplet
        enum_reg.register(c.subject_choices, preferred_schema_name=f"{c.spec.name}SubjectLabel")
        enum_reg.register(c.spec.predicate_choices, preferred_schema_name=f"{c.spec.name}Predicate")
        enum_reg.register(c.object_choices,  preferred_schema_name=f"{c.spec.name}ObjectLabel")
        # fixed fields
        for ff in c.spec.fixed_fields:
            if isinstance(ff, FixedChoiceField):
                enum_reg.register(ff.choices, preferred_schema_name=ENUM_NAME_BY_VALUES.get(_normalize_values(ff.choices)))
        # dynamic fields always inline otherwise uncomment below
        # for rd in c.dynamic_realized:
        #     enum_reg.register(rd.choices, preferred_schema_name="context_enum")

def build_relationship_models(
    ner_output: dict,
    specs: Sequence[RelationshipSpec],
    *,
    # enum sharing controls
    enum_ref_policy: Literal["auto","never","always"] = "auto",
    enum_share_threshold: int = 4,
    # ranking controls
    top_k: Optional[int] = None,
    scorer: Optional[Callable[[CandidateSpec], float]] = None,
    # schema controls
    ref_template: str = "#/$defs/{model}",
) -> tuple[dict[str, Type[BaseModel]], Annotated, Type[BaseModel], dict]:
    """
    Returns:
      - models_by_name: {rel_name: PydanticModel}
      - RelationshipUnion: Annotated[Union[...], Field(discriminator="rel_type")]
      - RelationshipsContainer: BaseModel with `relationships: list[RelationshipUnion]`
      - relationships_schema: JSON Schema dict for the container, with $defs/$refs
    Steps:
      1) NER filtering → candidate specs
      2) Candidate ranking (top_k)
      3) Enum registry decides inlining vs shared $defs
      4) Build Pydantic models and union container
      5) Emit JSON schema with $defs/$refs (ready for with_structured_output)
    """
    labels_by_class = extract_labels(ner_output)

    # (1) NER filter
    candidates_all = realize_candidates_via_ner(specs, labels_by_class)
    if not candidates_all:
        raise ValueError("No relationships are applicable for this NER output.")

    # (2) Ranking hook (placeholders for your dual-encoder)
    candidates = rank_and_select_candidates(candidates_all, top_k=top_k, scorer=scorer)
    if not candidates:
        raise ValueError("No relationships selected after ranking (top_k).")

    # (3) Enum registry pass — decide which enums become shared refs
    enum_reg = EnumRegistry(policy=enum_ref_policy, threshold=enum_share_threshold)
    _register_all_enums_for_candidates(candidates, enum_reg)
    enum_reg.finalize()

    # (4) Build Pydantic models
    models_by_name: dict[str, Type[BaseModel]] = {}
    for c in candidates:
        spec = c.spec
        fields: dict[str, tuple[type, Field]] = {} # type: ignore

        # Discriminator
        fields["rel_type"] = (Lit([spec.name]), Field(default=spec.name)) # type: ignore

        # Core triplet
        subj_t = enum_reg.type_for(c.subject_choices)
        pred_t = enum_reg.type_for(spec.predicate_choices)
        obj_t  = enum_reg.type_for(c.object_choices)

        fields["subject_label"] = (subj_t, Field(...)) # type: ignore
        fields["predicate"]     = (pred_t, Field(...)) # type: ignore
        fields["object_label"]  = (obj_t, Field(...)) # type: ignore

        # Fixed/dynamic
        _add_fixed_fields(fields, spec, enum_reg)
        _add_dynamic_fields(fields, c.dynamic_realized, enum_reg)

        model = create_model(
            spec.name,
            **fields, # type: ignore
            __base__=BaseModel,
        ) # type: ignore
        models_by_name[spec.name] = model

    # Discriminated union for structured output
    UnionType = Annotated[Union[tuple(models_by_name.values())], Field(discriminator="rel_type")]

    class RelationshipsContainer(BaseModel):
        relationships: list[UnionType] # type: ignore

    # (5) JSON Schema (Pydantic will $ref shared Enum types placed in multiple fields)
    schema = TypeAdapter(RelationshipsContainer).json_schema(ref_template=ref_template)

    return models_by_name, UnionType, RelationshipsContainer, schema
