# run this once before starting the app:
# python -m scripts.run_ingest

import sys
import os

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BACKEND_DIR)

from rag.ingest import ingest

# Absolute paths so ingest writes to the exact same store retriever.py reads
# from, regardless of the current working directory.
ingest(
    ucp_path=os.path.join(BACKEND_DIR, "rag/corpora/ucp600.txt"),
    isbp_path=os.path.join(BACKEND_DIR, "rag/corpora/isbp821.txt"),
    chroma_path=os.path.join(BACKEND_DIR, "chroma_store"),
)
