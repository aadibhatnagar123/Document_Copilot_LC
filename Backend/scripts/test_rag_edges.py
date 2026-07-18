"""
Edge-case regression tests for the RAG pipeline.

These lock in the five bug fixes so they can't silently regress. They cover
what scripts/test_rag.py (the happy-path suite) does not:

  Bug 1 — Roman-numeral sub-clauses mis-parsed as lettered clauses
  Bug 2 — retriever used a CWD-relative store path (silent empty results)
  Bug 3 — result key was 'score' but the value is a distance (lower = better)
  Bug 4 — blank query returned junk instead of []
  Bug 5 — every failure was mislabeled "has ingest been run?"

Run from Backend/:  ./.venv/bin/python -m scripts.test_rag_edges
"""

import os
import re
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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


# ── Bug 1: Roman-numeral sub-clauses ────────────────────────────
print("\n═══ Bug 1: no Roman-numeral mis-parsing ═══")

from rag.load_corpus import load_corpus
from rag.chunkers import chunk_ucp

ucp_text = load_corpus(os.path.join(BACKEND_DIR, "rag/corpora/ucp600.txt"))
ucp_chunks = chunk_ucp(ucp_text)

# No lettered-clause ref should end in (i)/(v)/(x) unless it is the real
# sequential clause. After the fix the only way (i) appears is as the 9th
# clause following (h); a bare (v)/(x) never appears in this corpus.
bad_v_x = [c["ref"] for c in ucp_chunks if re.search(r"\((v|x)\)$", c["ref"])]
check("No fake (v)/(x) sub-clause refs", not bad_v_x, f"found: {bad_v_x}")

# Article 7 must NOT be split at Roman numerals: (i) and (v) should be gone,
# and its i.–v. list text should live inside a real lettered clause.
art7_refs = [c["ref"] for c in ucp_chunks if c["ref"].startswith("Article 7(")]
check("Article 7 has no (i) fake clause", "Article 7(i)" not in art7_refs, f"refs: {art7_refs}")
check("Article 7 has no (v) fake clause", "Article 7(v)" not in art7_refs, f"refs: {art7_refs}")
art7_all = "\n".join(c["text"] for c in ucp_chunks if c["ref"].startswith("Article 7"))
check("Article 7 still contains its i.–v. list text",
      "sight payment" in art7_all and "negotiation with a nominated bank" in art7_all)

# Article 14 legitimately runs (a)..(l) — a real (i) must survive.
art14_refs = [c["ref"] for c in ucp_chunks if c["ref"].startswith("Article 14(")]
check("Article 14 keeps its real (i) clause", "Article 14(i)" in art14_refs, f"refs: {art14_refs}")

# No duplicate (source, ref) pairs anywhere (the old bug produced Article 8(a) twice).
pairs = [(c["source"], c["ref"]) for c in ucp_chunks]
dupes = [p for p in set(pairs) if pairs.count(p) > 1]
check("No duplicate (source, ref) pairs", not dupes, f"dupes: {dupes}")

# Within each article, accepted clause letters must be strictly a, b, c, ...
by_art = {}
for c in ucp_chunks:
    m = re.match(r"Article (\d+)\(([a-z])\)$", c["ref"])
    if m:
        by_art.setdefault(m.group(1), []).append(m.group(2))
non_sequential = {a: ls for a, ls in by_art.items()
                  if ls != [chr(ord("a") + i) for i in range(len(ls))]}
check("Every article's clauses are sequential a,b,c,...", not non_sequential,
      f"offenders: {non_sequential}")


# ── Bug 2: store path is CWD-independent ────────────────────────
print("\n═══ Bug 2: retriever works from any directory ═══")

from rag import query

original_cwd = os.getcwd()
try:
    os.chdir("/tmp")
    results_from_tmp = query("standard for examination of documents", k=3)
    check("query() returns results when CWD is /tmp", len(results_from_tmp) > 0,
          f"got {len(results_from_tmp)}")
finally:
    os.chdir(original_cwd)


# ── Bug 3: distance key + direction ─────────────────────────────
print("\n═══ Bug 3: distance semantics ═══")

results = query("standard for examination of documents five banking days", k=3, corpus="ucp")
check("Result uses 'distance' key, not 'score'",
      results and "distance" in results[0] and "score" not in results[0])
# Lower distance = more relevant, so results must be sorted ascending.
distances = [r["distance"] for r in results]
check("Distances are ascending (lower = more relevant)",
      distances == sorted(distances), f"got {distances}")
# The most relevant hit for an examination query should be an Article 14 clause.
check("Closest result for examination query is Article 14",
      results and "Article 14" in results[0]["ref"], f"got {results[0]['ref'] if results else None}")


# ── Bug 4: blank query returns [] ───────────────────────────────
print("\n═══ Bug 4: blank query guard ═══")

check("Empty string returns []", query("", k=3) == [])
check("Whitespace-only returns []", query("   \n ", k=3) == [])


# ── Bug 5: invalid k handled cleanly ────────────────────────────
print("\n═══ Bug 5: invalid k ═══")

check("k=0 returns []", query("bank", k=0) == [])
check("k=-1 returns []", query("bank", k=-1) == [])


# ── Summary ─────────────────────────────────────────────────────
print(f"\n{'═' * 50}")
print(f"  TOTAL: {passed + failed}  |  ✅ PASSED: {passed}  |  ❌ FAILED: {failed}")
print(f"{'═' * 50}")

if failed > 0:
    sys.exit(1)
