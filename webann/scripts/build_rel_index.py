import json, numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[1]   # repo root
DATA = ROOT / "backend" / "data"
REL = json.loads((DATA / "relations.json").read_text(encoding="utf-8"))

model = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu")

labels, texts, meta = [], [], {}
for name, spec in REL.items():
    labels.append(name)
    desc = (spec.get("description") or "").strip()
    subj = ", ".join(spec.get("subject", []))
    obj  = ", ".join(spec.get("object", []))
    # put useful context into the embedding text
    texts.append(f"relation: {name}. description: {desc}. subject: {subj}. object: {obj}.")
    meta[name] = {"description": desc, "subject": spec.get("subject", []), "object": spec.get("object", [])}

embs = model.encode(texts, normalize_embeddings=True).astype("float32")
np.savez(DATA / "rel_index.npz", labels=np.array(labels, dtype=object), embeddings=embs)
(DATA / "rel_index_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
print("Built data/rel_index.npz and data/rel_index_meta.json")
