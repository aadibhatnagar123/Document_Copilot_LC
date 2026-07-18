"""
Inspect the ChromaDB vector store.

Run from the Backend directory:
    ./.venv/bin/python -m scripts.inspect_store            # summary + first 10 chunks
    ./.venv/bin/python -m scripts.inspect_store --all      # dump every chunk
    ./.venv/bin/python -m scripts.inspect_store --id ucp600-art14a   # one chunk by id
    ./.venv/bin/python -m scripts.inspect_store --corpus ucp         # only UCP chunks
    ./.venv/bin/python -m scripts.inspect_store --limit 25           # first 25 chunks
"""

import argparse
import os

import chromadb

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BACKEND_DIR, "chroma_store")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="dump every chunk")
    ap.add_argument("--limit", type=int, default=10, help="how many chunks to show")
    ap.add_argument("--id", help="show a single chunk by its id")
    ap.add_argument("--corpus", choices=["ucp", "isbp"], help="filter by corpus")
    ap.add_argument("--full", action="store_true", help="print full text, not a preview")
    args = ap.parse_args()

    client = chromadb.PersistentClient(path=DB_PATH)
    collection = client.get_collection("lc_rules")

    print(f"Collection: lc_rules   Total chunks: {collection.count()}\n")

    where = {"corpus": args.corpus} if args.corpus else None

    if args.id:
        res = collection.get(ids=[args.id], include=["documents", "metadatas"])
    elif args.all:
        res = collection.get(where=where, include=["documents", "metadatas"])
    else:
        res = collection.get(where=where, limit=args.limit, include=["documents", "metadatas"])

    ids = res["ids"]
    if not ids:
        print("No chunks matched.")
        return

    for cid, doc, meta in zip(ids, res["documents"], res["metadatas"]):
        print(f"── {cid}  |  {meta.get('source')} — {meta.get('ref')}  (corpus {meta.get('corpus')})")
        text = doc if args.full else doc[:250].replace("\n", " ")
        print(f"   {text}{'' if args.full else '...'}\n")

    print(f"Shown: {len(ids)} chunk(s)")


if __name__ == "__main__":
    main()
