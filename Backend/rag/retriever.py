import os

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma


# Use an absolute path so query() works regardless of where the app is launched from
_RAG_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_PATH = os.path.normpath(os.path.join(_RAG_DIR, "..", "chroma_store"))
COLLECTION_NAME = "lc_rules"

# Load once at startup so repeated calls don't reload the model every time
_embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
_db = Chroma(
    collection_name=COLLECTION_NAME,
    embedding_function=_embeddings,
    persist_directory=CHROMA_PATH,
)


def query(text, k=3, corpus=None):
    """Search the vector store for chunks matching the query.

    Args:
        text: the search query
        k: number of results to return (default 3)
        corpus: "ucp", "isbp", or None to search both

    Returns list of dicts: [{text, source, ref, distance}, ...]
    Lower distance = more relevant.
    """
    if not text or not text.strip():
        return []

    if k < 1:
        print(f"WARNING: k must be >= 1, got k={k}. Returning [].")
        return []

    try:
        where = {"corpus": corpus} if corpus is not None else None
        results = _db.similarity_search_with_score(text, k=k, filter=where)

        output = []
        for doc, distance in results:
            output.append({
                "text": doc.page_content,
                "source": doc.metadata.get("source"),
                "ref": doc.metadata.get("ref"),
                "distance": distance,
            })
        return output

    except Exception as e:
        print(f"WARNING: RAG query failed ({type(e).__name__}: {e}). Store path: {CHROMA_PATH}")
        return []
