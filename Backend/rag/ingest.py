from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from .load_corpus import load_corpus
from .chunkers import chunk_ucp, chunk_isbp


COLLECTION_NAME = "lc_rules"


def ingest(ucp_path, isbp_path, chroma_path):
    """Build the ChromaDB vector store from UCP and ISBP text files.

    Wipes the existing collection first so re-running doesn't create duplicates.
    """
    ucp_text = load_corpus(ucp_path)
    isbp_text = load_corpus(isbp_path)

    if not ucp_text.strip() and not isbp_text.strip():
        print("WARNING: both corpus files are empty. Nothing to ingest.")
        return

    ucp_chunks = chunk_ucp(ucp_text)
    isbp_chunks = chunk_isbp(isbp_text)
    all_chunks = ucp_chunks + isbp_chunks

    if not all_chunks:
        print("WARNING: no chunks produced. Nothing to ingest.")
        return

    print(f"Chunked {len(ucp_chunks)} UCP + {len(isbp_chunks)} ISBP = {len(all_chunks)} total")

    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    # Wipe old collection so re-running ingest doesn't duplicate chunks
    old_db = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=chroma_path,
    )
    old_db.delete_collection()

    texts = [c["text"] for c in all_chunks]
    metadatas = [{"source": c["source"], "ref": c["ref"], "corpus": c["corpus"]} for c in all_chunks]
    ids = [c["id"] for c in all_chunks]

    Chroma.from_texts(
        texts=texts,
        embedding=embeddings,
        metadatas=metadatas,
        ids=ids,
        collection_name=COLLECTION_NAME,
        persist_directory=chroma_path,
    )

    print(f"Ingested {len(all_chunks)} chunks into '{COLLECTION_NAME}' at {chroma_path}")
