from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from pathlib import Path
import json

DATA_DIR = Path(__file__).parent / "data"
CLASSES_FILE = DATA_DIR / "classes.json"
TEXTS_FILE = DATA_DIR / "texts.json"
ANNOT_FILE = DATA_DIR / "annotations.jsonl"

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

class SavePayload(BaseModel):
    text_id: str
    text: str
    entities: List[Entity]

# ---------- Helpers ----------

def load_json(path: Path):
    if not path.exists():
        raise HTTPException(500, f"Missing file: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

TEXTS = load_json(TEXTS_FILE)  # list of {id, text}

# ---------- Routes ----------
@app.get("/api/classes")
async def get_classes():
    return load_json(CLASSES_FILE)

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

@app.post("/api/annotations")
async def save_annotations(payload: SavePayload):
    # basic sanity: ensure spans are valid within the provided text
    for ent in payload.entities:
        if not (0 <= ent.span.start <= ent.span.end <= len(payload.text)):
            raise HTTPException(400, f"Invalid span for entity {ent.id}")

    # append to annotations.jsonl
    ANNOT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with ANNOT_FILE.open("a", encoding="utf-8") as f:
        # remove text when saving annotation, just keep text_id
        del payload.text
        f.write(json.dumps(payload.model_dump(by_alias=True), ensure_ascii=False) + "\n")
    return {"ok": True}

# ---------- Dev convenience ----------
@app.get("/")
async def root():
    return {"status": "ok", "message": "Backend is running"}