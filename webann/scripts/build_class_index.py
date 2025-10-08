# scripts/build_class_index.py
import argparse, json
from pathlib import Path
import numpy as np
from sentence_transformers import SentenceTransformer

def main():
    ROOT = Path(__file__).resolve().parents[1]   # repo root
    DATA = ROOT / "backend" / "data"
    default_classes = DATA / "classes.json"
    default_out_ind = DATA / "class_index.npz"
    default_out_meta= DATA / "class_index_meta.json"
    p = argparse.ArgumentParser()
    p.add_argument("--classes", default=default_classes)
    p.add_argument("--out", default=default_out_ind)
    p.add_argument("--meta_out", default=default_out_meta)
    p.add_argument("--model", default="BAAI/bge-small-en-v1.5")
    p.add_argument("--batch_size", type=int, default=16)
    args = p.parse_args()

    classes = json.loads(Path(args.classes).read_text(encoding="utf-8"))

    names, passages, meta = [], [], {}
    for name, cfg in classes.items():
        desc = (cfg or {}).get("description", "")
        aliases = (cfg or {}).get("aliases", [])  # optional: you can add this field to classes.json
        blob = f"{name}. {desc}".strip()
        if aliases:
            blob += ". Aliases: " + ", ".join(aliases)
        passages.append(blob)
        names.append(name)
        meta[name] = {"description": desc, "aliases": aliases}

    model = SentenceTransformer(args.model) # fastest device should be auto-detected
    emb = model.encode(passages, batch_size=args.batch_size, normalize_embeddings=True, show_progress_bar=True)
    emb = emb.astype("float32")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    np.savez(args.out, labels=np.array(names, dtype=object), embeddings=emb)

    Path(args.meta_out).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.out} with {len(names)} classes.")

if __name__ == "__main__":
    main()
