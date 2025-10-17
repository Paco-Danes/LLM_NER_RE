from functools import lru_cache
from pydantic import BaseModel

class Settings(BaseModel):
    # Imports used at runtime
    RELATION_SPECS_IMPORT: str = "relcode.relationship_specs"
    ENUMS_IMPORT: str = "relcode.utils.my_enums"

    # Embedding model
    EMBED_MODEL_NAME: str = "BAAI/bge-small-en-v1.5"

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
