"""
Full RAG pipeline verification script.
Run from Backend/:  .venv/bin/python -m scripts.test_rag
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  ✅ {name}")
        passed += 1
    else:
        print(f"  ❌ {name} — {detail}")
        failed += 1


# ── 1. load_corpus ──────────────────────────────────────────────
print("\n═══ 1. load_corpus ═══")

from rag.load_corpus import load_corpus

ucp_text = load_corpus("rag/corpora/ucp600.txt")
check("UCP file loads", len(ucp_text) > 1000, f"got {len(ucp_text)} chars")
check("UCP contains Article 1", "Article 1" in ucp_text)
check("UCP contains Article 39", "Article 39" in ucp_text)

isbp_text = load_corpus("rag/corpora/isbp821.txt")
check("ISBP file loads", len(isbp_text) > 1000, f"got {len(isbp_text)} chars")
check("ISBP contains A1)", "A1)" in isbp_text)
check("ISBP contains Q11)", "Q11)" in isbp_text)

missing = load_corpus("rag/corpora/nonexistent.txt")
check("Missing file returns empty string", missing == "", f"got: {repr(missing[:50])}")


# ── 2. chunkers ─────────────────────────────────────────────────
print("\n═══ 2. chunk_ucp ═══")

from rag.chunkers import chunk_ucp, chunk_isbp

ucp_chunks = chunk_ucp(ucp_text)
check("UCP produces chunks", len(ucp_chunks) > 0, f"got {len(ucp_chunks)}")
check("UCP chunk count reasonable (>50)", len(ucp_chunks) > 50, f"got {len(ucp_chunks)}")

# check structure of first chunk
first = ucp_chunks[0]
check("Chunk has 'id' key", "id" in first)
check("Chunk has 'text' key", "text" in first)
check("Chunk has 'source' key", "source" in first)
check("Chunk has 'ref' key", "ref" in first)
check("Chunk has 'corpus' key", "corpus" in first)
check("Source is 'UCP 600'", first["source"] == "UCP 600", f"got {first['source']}")
check("Corpus is 'ucp'", first["corpus"] == "ucp", f"got {first['corpus']}")

# check IDs are unique
ucp_ids = [c["id"] for c in ucp_chunks]
check("All UCP IDs unique", len(ucp_ids) == len(set(ucp_ids)),
      f"{len(ucp_ids)} total, {len(set(ucp_ids))} unique")

# check key articles exist
ucp_refs = [c["ref"] for c in ucp_chunks]
check("Article 14 chunked", any("Article 14" in r for r in ucp_refs))
check("Article 20 chunked", any("Article 20" in r for r in ucp_refs))
check("Article 39 chunked", any("Article 39" in r for r in ucp_refs))

# check no chunk has empty text
empty_text_ucp = [c for c in ucp_chunks if not c["text"].strip()]
check("No UCP chunks with empty text", len(empty_text_ucp) == 0,
      f"{len(empty_text_ucp)} empty chunks")

# content-presence: known source text must survive chunking (guards against
# the sub-clause splitter dropping article preambles like Article 2 definitions)
ucp_all_text = "\n".join(c["text"] for c in ucp_chunks)
check("Article 2 'Advising bank' definition preserved",
      "Advising bank means" in ucp_all_text)
check("Article 2 'Nominated bank' definition preserved",
      "Nominated bank means" in ucp_all_text)
check("Article titles carried into sub-clause chunks",
      "Standard for Examination of Documents" in ucp_all_text)

# check empty input
check("Empty text returns []", chunk_ucp("") == [])
check("Whitespace-only returns []", chunk_ucp("   \n  ") == [])


print("\n═══ 3. chunk_isbp ═══")

isbp_chunks = chunk_isbp(isbp_text)
check("ISBP produces chunks", len(isbp_chunks) > 0, f"got {len(isbp_chunks)}")
check("ISBP chunk count reasonable (>100)", len(isbp_chunks) > 100, f"got {len(isbp_chunks)}")

# check structure
first_isbp = isbp_chunks[0]
check("Source is 'ISBP 821'", first_isbp["source"] == "ISBP 821", f"got {first_isbp['source']}")
check("Corpus is 'isbp'", first_isbp["corpus"] == "isbp", f"got {first_isbp['corpus']}")

# check IDs are unique
isbp_ids = [c["id"] for c in isbp_chunks]
check("All ISBP IDs unique", len(isbp_ids) == len(set(isbp_ids)),
      f"{len(isbp_ids)} total, {len(set(isbp_ids))} unique")

# check key paragraphs exist
isbp_refs = [c["ref"] for c in isbp_chunks]
check("Paragraph A1 exists", any("Paragraph A1" == r for r in isbp_refs))
check("Paragraph B1 exists", any("Paragraph B1" == r for r in isbp_refs))
check("Paragraph K1 exists", any("Paragraph K1" == r for r in isbp_refs))
check("Paragraph Q1 exists", any("Paragraph Q1" == r for r in isbp_refs))

# check no chunk has empty text
empty_text_isbp = [c for c in isbp_chunks if not c["text"].strip()]
check("No ISBP chunks with empty text", len(empty_text_isbp) == 0,
      f"{len(empty_text_isbp)} empty chunks")

# check empty input
check("Empty text returns []", chunk_isbp("") == [])

# cross-corpus ID uniqueness
all_ids = ucp_ids + isbp_ids
check("All IDs unique across both corpora", len(all_ids) == len(set(all_ids)),
      f"{len(all_ids)} total, {len(set(all_ids))} unique")


# ── 4. ChromaDB collection ──────────────────────────────────────
print("\n═══ 4. ChromaDB collection ═══")

import chromadb

client = chromadb.PersistentClient(path="./chroma_store")
try:
    collection = client.get_collection("lc_rules")
    count = collection.count()
    check("Collection 'lc_rules' exists", True)
    check(f"Collection has {count} chunks", count > 0)

    expected = len(ucp_chunks) + len(isbp_chunks)
    check(f"Chunk count matches ({count} stored vs {expected} chunked)",
          count == expected, f"stored={count}, expected={expected}")

    # spot-check metadata
    sample = collection.get(limit=1, include=["metadatas", "documents"])
    meta = sample["metadatas"][0]
    check("Metadata has 'source'", "source" in meta, f"keys: {list(meta.keys())}")
    check("Metadata has 'ref'", "ref" in meta)
    check("Metadata has 'corpus'", "corpus" in meta)
    check("Document text is non-empty", len(sample["documents"][0]) > 0)

    # check corpus filter works at chromadb level
    ucp_results = collection.get(where={"corpus": "ucp"}, limit=1)
    check("Corpus filter 'ucp' returns results", len(ucp_results["ids"]) > 0)

    isbp_results = collection.get(where={"corpus": "isbp"}, limit=1)
    check("Corpus filter 'isbp' returns results", len(isbp_results["ids"]) > 0)

except Exception as e:
    check("Collection 'lc_rules' exists", False, str(e))


# ── 5. retriever.query() ────────────────────────────────────────
print("\n═══ 5. retriever.query() ═══")

from rag import query

# basic query — search both corpora
results = query("standard for examination of documents", k=3)
check("query() returns a list", isinstance(results, list))
check("query() returns results", len(results) > 0, f"got {len(results)}")
check(f"query() returns {len(results)} results (asked for 3)", len(results) == 3,
      f"got {len(results)}")

if results:
    r = results[0]
    check("Result has 'text'", "text" in r)
    check("Result has 'source'", "source" in r)
    check("Result has 'ref'", "ref" in r)
    check("Result has 'distance'", "distance" in r)
    check("Result is a plain dict (not LangChain obj)", type(r) == dict, f"got {type(r)}")
    check("Distance is a float", isinstance(r["distance"], float), f"got {type(r['distance'])}")

# filtered query — UCP only
ucp_results = query("bill of lading", k=3, corpus="ucp")
check("UCP-filtered query returns results", len(ucp_results) > 0)
all_ucp = all(r["source"] == "UCP 600" for r in ucp_results)
check("All UCP-filtered results are from UCP 600", all_ucp,
      f"sources: {[r['source'] for r in ucp_results]}")

# filtered query — ISBP only
isbp_results = query("bill of lading", k=3, corpus="isbp")
check("ISBP-filtered query returns results", len(isbp_results) > 0)
all_isbp = all(r["source"] == "ISBP 821" for r in isbp_results)
check("All ISBP-filtered results are from ISBP 821", all_isbp,
      f"sources: {[r['source'] for r in isbp_results]}")

# unfiltered query — should potentially return both
both_results = query("insurance document coverage", k=5)
sources_found = set(r["source"] for r in both_results)
check("Unfiltered query can return both sources", len(sources_found) >= 1,
      f"sources: {sources_found}")

# edge: k=1
one_result = query("article 14", k=1)
check("k=1 returns exactly 1 result", len(one_result) == 1, f"got {len(one_result)}")

# relevance sanity check
art14_results = query("standard for examination of documents five banking days", k=3, corpus="ucp")
art14_refs = [r["ref"] for r in art14_results]
check("Article 14 appears in top results for examination query",
      any("Article 14" in ref for ref in art14_refs),
      f"got refs: {art14_refs}")


# ── 6. Package import ───────────────────────────────────────────
print("\n═══ 6. Package imports ═══")

try:
    from rag import query as q
    check("'from rag import query' works", callable(q))
except ImportError as e:
    check("'from rag import query' works", False, str(e))

try:
    from rag.retriever import query as q2
    check("'from rag.retriever import query' works", callable(q2))
except ImportError as e:
    check("'from rag.retriever import query' works", False, str(e))

try:
    from rag.ingest import ingest
    check("'from rag.ingest import ingest' works", callable(ingest))
except ImportError as e:
    check("'from rag.ingest import ingest' works", False, str(e))

try:
    from rag.load_corpus import load_corpus as lc
    check("'from rag.load_corpus import load_corpus' works", callable(lc))
except ImportError as e:
    check("'from rag.load_corpus import load_corpus' works", False, str(e))

try:
    from rag.chunkers import chunk_ucp as cu, chunk_isbp as ci
    check("'from rag.chunkers import chunk_ucp, chunk_isbp' works", callable(cu) and callable(ci))
except ImportError as e:
    check("'from rag.chunkers import ...' works", False, str(e))


# ── Summary ─────────────────────────────────────────────────────
print(f"\n{'═'*50}")
print(f"  TOTAL: {passed + failed}  |  ✅ PASSED: {passed}  |  ❌ FAILED: {failed}")
print(f"{'═'*50}")

if failed > 0:
    sys.exit(1)
