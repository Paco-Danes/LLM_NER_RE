# scripts/build_class_index.py
import argparse, json, os
from pathlib import Path
import numpy as np
from sentence_transformers import SentenceTransformer

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--classes", default=str(Path(__file__).parents[1] / "backend" / "data" / "classes.json"))
    p.add_argument("--out", default=str(Path(__file__).parents[1] / "backend" / "data" / "class_index.npz"))
    p.add_argument("--meta_out", default=str(Path(__file__).parents[1] / "backend" / "data" / "class_index_meta.json"))
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
        passages.append("passage: " + blob)
        names.append(name)
        meta[name] = {"description": desc, "aliases": aliases}

    model = SentenceTransformer(args.model, device="cpu")
    emb = model.encode(passages, batch_size=args.batch_size, normalize_embeddings=True, show_progress_bar=True)
    emb = emb.astype("float32")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    np.savez(args.out, labels=np.array(names, dtype=object), embeddings=emb)

    Path(args.meta_out).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.out} with {len(names)} classes.")

if __name__ == "__main__":
    main()
