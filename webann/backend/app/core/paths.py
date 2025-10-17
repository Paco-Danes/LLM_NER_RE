from pathlib import Path

# Root is this file's parent two levels up (the "backend" folder)
ROOT_DIR = Path(__file__).resolve().parents[2]

DATA_DIR = ROOT_DIR / "data"

# Files (migrated from your constants)
CLASSES_FILE        = DATA_DIR / "classes.json"
TEXTS_FILE          = DATA_DIR / "texts.json"
ANNOT_FILE          = DATA_DIR / "annotations.jsonl"
PROPOSED_FILE       = DATA_DIR / "proposed_classes.py"

# Propose-relationship
FIELD_DESC_FILE     = DATA_DIR / "field_descriptions.json"
PROPOSED_REL_FILE   = DATA_DIR / "proposed_rel.py"

# Relations meta cache (static fallback)
RELATIONS_FILE      = DATA_DIR / "relations.json"

# Embedding indices
REL_EMBED_INDEX_FILE = DATA_DIR / "rel_index.npz"
REL_EMBED_META_FILE  = DATA_DIR / "rel_index_meta.json"
EMBED_INDEX_FILE     = DATA_DIR / "class_index.npz"
EMBED_META_FILE      = DATA_DIR / "class_index_meta.json"
