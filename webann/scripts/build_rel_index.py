import argparse
import json
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer

def main():
    ROOT = Path(__file__).resolve().parents[1]   # repo root
    DATA = ROOT / "backend" / "data"
    default_relations = DATA / "relations.json"
    default_out_ind = DATA / "rel_index.npz"
    default_out_meta = DATA / "rel_index_meta.json"

    p = argparse.ArgumentParser()
    p.add_argument("--relations", default=default_relations)
    p.add_argument("--out", default=default_out_ind)
    p.add_argument("--meta_out", default=default_out_meta)
    p.add_argument("--model", default="BAAI/bge-small-en-v1.5")
    args = p.parse_args()

    REL = json.loads(Path(args.relations).read_text(encoding="utf-8"))
    model = SentenceTransformer(args.model)

    labels, texts, meta = [], [], {}
    for name, spec in REL.items():
        labels.append(name)
        desc = (spec.get("description") or "").strip()
        subj = ", ".join(spec.get("subject", []))
        obj = ", ".join(spec.get("object", []))
        texts.append(f"relation: {name}. {desc}. subject: {subj}. object: {obj}.")
        meta[name] = {"description": desc, "subject": spec.get("subject", []), "object": spec.get("object", [])}

    embs = model.encode(texts, normalize_embeddings=True, show_progress_bar=True)
    embs = embs.astype("float32")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    np.savez(args.out, labels=np.array(labels, dtype=object), embeddings=embs)

    Path(args.meta_out).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.out} and {args.meta_out}.")

if __name__ == "__main__":
    main()