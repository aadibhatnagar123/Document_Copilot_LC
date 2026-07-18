"""
Manual query tool for the RAG store.

Run from Backend/:
    ./.venv/bin/python -m scripts.ask                  # interactive
    ./.venv/bin/python -m scripts.ask "bill of lading" # single query

Commands inside the prompt:
    :ucp  <question>  — search only UCP 600
    :isbp <question>  — search only ISBP 821
    :k 5              — change number of results shown (default 3)
    :q  or  Ctrl-D    — quit
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag import query


def show(text, k=3, corpus=None):
    results = query(text, k=k, corpus=corpus)
    if not results:
        print("  (no results)\n")
        return
    for r in results:
        tag = f"[{corpus}] " if corpus else ""
        print(f"  {r['distance']:.3f}  {tag}{r['source']} — {r['ref']}")
        preview = " ".join(r["text"].split())[:200]
        print(f"        {preview}...\n")


def run_one(raw, k):
    """Parse one line of input and return the (possibly updated) k."""
    raw = raw.strip()
    if not raw:
        return k
    if raw in (":q", ":quit", ":exit"):
        raise EOFError
    if raw.startswith(":k"):
        parts = raw.split()
        if len(parts) == 2 and parts[1].isdigit() and int(parts[1]) >= 1:
            k = int(parts[1])
            print(f"  → showing {k} results per query\n")
        else:
            print("  usage: :k <positive integer>\n")
        return k

    corpus = None
    if raw.startswith(":ucp"):
        corpus, raw = "ucp", raw[4:].strip()
    elif raw.startswith(":isbp"):
        corpus, raw = "isbp", raw[5:].strip()

    if not raw:
        print("  (type a question after the filter)\n")
        return k

    show(raw, k=k, corpus=corpus)
    return k


def main():
    if len(sys.argv) > 1:
        show(" ".join(sys.argv[1:]), k=3)
        return

    print("RAG query tool. Type a question, or :q to quit. (:ucp / :isbp to filter)\n")
    k = 3
    while True:
        try:
            raw = input("query> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        try:
            k = run_one(raw, k)
        except EOFError:
            break


if __name__ == "__main__":
    main()
