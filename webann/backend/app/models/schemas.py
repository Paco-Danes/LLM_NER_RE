from typing import Optional, Dict, Any, List, Literal
from pydantic import BaseModel, Field

# ---- Entities & Relations ----
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
    predicate: str
    subject: str
    object: str
    attributes: Dict[str, Any] = {}

class SavePayload(BaseModel):
    text_id: str
    text: str
    entities: List[Entity]
    relations: List[RelationEdge] = []

# ---- Semantic search ----
class SuggestIn(BaseModel):
    kind: Literal["class", "relation"] = "class"
    query: Optional[str] = ""
    label: Optional[str] = ""
    subject_class: Optional[str] = None
    object_class: Optional[str] = None
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

# ---- Proposed classes ----
class AttrSpec(BaseModel):
    name: str
    type: Literal[
        "str", "int", "float", "bool",
        "literal", "list[str]", "list[int]", "list[float]", "list[bool]"
    ] = "str"
    optional: bool = False
    description: Optional[str] = ""
    literal_values: Optional[List[str]] = None

class ProposedClassIn(BaseModel):
    name: str
    description: Optional[str] = ""
    attributes: List[AttrSpec] = []

# ---- Propose-relationship & enums ----
class EnumCreate(BaseModel):
    name: Optional[str] = None
    values: List[str] = []

class EnumAddIn(BaseModel):
    name: str
    values: List[str]

class ProposedRelField(BaseModel):
    name: str
    kind: Literal["fixed", "dynamic", "free_text"] = "fixed"
    optional: bool = True
    description: Optional[str] = ""
    enum_name: Optional[str] = None
    new_enum: Optional[EnumCreate] = None
    classes: Optional[List[str]] = None
    text_type: Optional[Literal["text", "number"]] = "text"

class ProposedRelationIn(BaseModel):
    name: str
    description: Optional[str] = ""
    subject_classes: List[str]
    object_classes: List[str]
    predicate_choices: Optional[List[str]] = None
    fields: List[ProposedRelField] = []
