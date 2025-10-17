from fastapi import APIRouter
from app.core.paths import CLASSES_FILE, PROPOSED_FILE
from app.models.schemas import ProposedClassIn
from app.services.io import load_json
from app.services.proposals import propose_class

router = APIRouter()

@router.get("/classes")
async def get_classes():
    return load_json(CLASSES_FILE)

@router.post("/proposed-classes")
async def post_proposed_class(payload: ProposedClassIn):
    return propose_class(payload)
