# RAG

**Role**: Parses trade finance rulebooks (UCP 600, ISBP 821) into structured chunks and indexes them in a Chroma DB vector store for context retrieval.

**Model**: HuggingFace Embeddings — `all-MiniLM-L6-v2`

---

## How it works

Loads plain-text trade finance regulation documents from `rag/corpora/`. Splitting is performed at the article/sub-clause level for UCP 600 and at the paragraph level for ISBP 821. Converts text chunks to vector embeddings using HuggingFace sentence transformers and persists them to a local Chroma database collection. Exposes a similarity search interface with metadata filtering capabilities to retrieve relevant guidelines.

**Pipeline**:
```
load_corpus → chunk (chunk_ucp / chunk_isbp) → embed (all-MiniLM-L6-v2) → store (Chroma) → query
```

---

## Inputs

- **`text`** — Search query string.
- **`k`** — Number of matching documents to return (default: `3`).
- **`corpus`** — Optional corpus filter string (`"ucp"`, `"isbp"`, or `None` for both).
- **Files** — `rag/corpora/ucp600.txt` (UCP 600 rulebook), `rag/corpora/isbp821.txt` (ISBP 821 rulebook).

---

## Project Structure

```
rag/
├── corpora/
│   ├── isbp821.txt        # Raw ISBP 821 text corpus
│   └── ucp600.txt         # Raw UCP 600 text corpus
├── chunkers.py            # Article/paragraph regex-based splitting rules
├── ingest.py              # Wipes collection and populates Chroma vector store
├── load_corpus.py         # Utility to read raw corpus text files safely
├── retriever.py           # Similarity search interface using ChromaDB
└── __init__.py            # Package entry point
```

---

## Processing

| Step | What it does |
|---|---|
| Ingest | Loads text files, splits into logical chunks, generates vector embeddings, stores them in ChromaDB |
| Chunking | Splits UCP 600 by `Article` / sub-clause (`(a)`, `(b)`); splits ISBP 821 by paragraph (e.g. `A1.`, `B3.`) |
| Querying | Computes similarity of the query against indexed rules, applying optional corpus metadata filters |

---

## Tools

| Group | Tools | Purpose |
|---|---|---|
| Document Loading | `load_corpus` | Reads raw corpus text files with exception protection |
| Chunkers | `chunk_ucp`, `chunk_isbp` | Regex-based rules to split documents into context chunks |
| Storage & Ingestion | `ingest` | Wipes and populates Chroma database collections |
| Search | `query` | Runs cosine/similarity search over embeddings, filtered by corpus |

---

## Output

- **`output`** — `list[dict]` of matching search result chunks.

```json
[
  {
    "text": "Article 14\nStandard for Examination of Documents...",
    "source": "UCP 600",
    "ref": "Article 14(c)",
    "distance": 0.354
  }
]
```
