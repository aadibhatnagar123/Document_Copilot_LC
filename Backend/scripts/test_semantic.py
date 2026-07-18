"""
Full Agent 3 (Semantic_Comparator) verification script.
Run from Backend/:  ./.venv/bin/python -m scripts.test_semantic

Mirrors scripts/test_rag.py: a flat check() harness, sectioned output, and a
non-zero exit if anything fails.

The three real LLM calls (resolve / severity / recommendation) are monkeypatched
so the core suite is deterministic and offline. The graph's whole reason to exist
is that it degrades gracefully when those calls fail, so most of the value is in
exercising the fallback routes without a network. One final section (guarded by
GROQ_API_KEY) runs the graph end-to-end against real Groq.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

passed = 0
failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  {name}")
        passed += 1
    else:
        print(f"  {name} — {detail}")
        failed += 1


from Agents.Semantic_Comparator import tools
from Agents.Semantic_Comparator.nodes import pipeline
from Agents.Semantic_Comparator.graph import build_semantic_comparator_subgraph

# Agent 2's real tools — used to prove the cross-agent contract, not mocks.
from Agents.Internal_Checker import tools as checker_tools


# ── shared fixtures: issues/pairs in Agent 2's exact output shape ──

def agent2_issue(doc_type, field, kind, message):
    """Produce an issue the way Agent 2 actually does (via its own make_issue)."""
    return checker_tools.make_issue(doc_type, field, kind, message)


def agent2_ambiguous_pair(field, doc_a, doc_b, val_a, val_b, score=70.0):
    """An ambiguous pair in the exact shape Agent 2's _compare_field emits."""
    return {
        "field": field,
        "doc_a": doc_a,
        "doc_b": doc_b,
        "val_a": str(val_a),
        "val_b": str(val_b),
        "score": score,
    }


def base_state(ambiguous_pairs=None, issues=None):
    return {
        "ambiguous_pairs": ambiguous_pairs or [],
        "issues": issues or [],
        "schema": {},
    }


# every test controls the LLM + RAG surface; save originals to restore between tests
_ORIG = {
    "call_semantic_compare": tools.call_semantic_compare,
    "call_severity_classify": tools.call_severity_classify,
    "call_recommendation": tools.call_recommendation,
    "pipeline_rag_query": pipeline.rag_query,
}


def restore():
    tools.call_semantic_compare = _ORIG["call_semantic_compare"]
    tools.call_severity_classify = _ORIG["call_severity_classify"]
    tools.call_recommendation = _ORIG["call_recommendation"]
    pipeline.rag_query = _ORIG["pipeline_rag_query"]


def raise_(*a, **k):
    raise RuntimeError("forced LLM failure")


# ── 1. imports & subgraph builds ────────────────────────────────
print("\n═══ 1. build ═══")

g = build_semantic_comparator_subgraph()
check("subgraph compiles", g is not None)
check("resolve_verdicts is callable", callable(tools.resolve_verdicts))
check("default_recommendation is callable", callable(tools.default_recommendation))


# ── 2. Agent 2 → Agent 3 data contract ──────────────────────────
# The single most likely thing to silently break: Agent 2 renames a key and
# Agent 3 KeyErrors at runtime. Lock the shape in.
print("\n═══ 2. Agent2→Agent3 contract ═══")

# 2a. ambiguous pair shape — build a REAL one through Agent 2's comparator
f_spec = {"compare": "fuzzy", "fuzzy_high": 92, "fuzzy_low": 40}
_issue, real_pair = checker_tools._compare_field(
    f_spec, "beneficiary_name",
    "ACME Corporation Ltd", "ACME Corp Limited",  # ~ambiguous band
    "invoice", "bill_of_lading",
)
check("Agent 2 emits an ambiguous pair for near-match strings", real_pair is not None,
      f"got {real_pair}")
if real_pair:
    for key in ("field", "doc_a", "doc_b", "val_a", "val_b"):
        check(f"pair has '{key}' (Agent 3 hard-indexes it)", key in real_pair,
              f"keys: {list(real_pair.keys())}")
    # Agent 3 must be able to consume it without crashing
    prompt = tools.build_semantic_prompt([real_pair], [])
    check("build_semantic_prompt consumes a real Agent 2 pair", real_pair["field"] in prompt)

# 2b. issue shape — Agent 2's make_issue must carry every key Agent 3 reads
iss = agent2_issue("invoice", "amount", "numeric_mismatch", "amount differs")
for key in ("doc_type", "field", "kind", "message", "citation"):
    check(f"Agent 2 issue has '{key}'", key in iss, f"keys: {list(iss.keys())}")

# 2c. every kind Agent 2 can emit resolves to a real severity (not silently dropped)
agent2_kinds = {
    "lc_terms_incomplete", "date_invalid", "lc_expired",       # gate
    "missing_doc", "unreadable", "missing_field", "date_rule_violated",  # pass a
    "exact_mismatch", "numeric_mismatch", "date_mismatch", "fuzzy_mismatch",  # pass b
}
mapped = [agent2_issue("d", "f", k, "m") for k in agent2_kinds]
tools.apply_default_severity(mapped)
check("every Agent 2 kind maps to critical/major/minor",
      all(i["severity"] in ("critical", "major", "minor") for i in mapped),
      f"unmapped: {[i for i in mapped if i['severity'] not in ('critical','major','minor')]}")


# ── 3. resolve_verdicts + fallback_resolve ──────────────────────
print("\n═══ 3. resolve logic ═══")

pairs = [
    agent2_ambiguous_pair("beneficiary", "invoice", "bl", "ACME Corp", "ACME Corporation"),
    agent2_ambiguous_pair("port", "invoice", "bl", "Shanghai", "Rotterdam"),
]

# clean "match" produces no issue; anything else is flagged (conservative)
verdicts = {"0": "match", "1": "mismatch"}
out = tools.resolve_verdicts(pairs, verdicts)
check("only the mismatch pair becomes an issue", len(out) == 1, f"got {len(out)}")
check("issue is a semantic_mismatch", out and out[0]["kind"] == "semantic_mismatch")
check("issue starts with severity=None", out and out[0]["severity"] is None)

# missing/garbage verdict defaults to flagging (never silently pass)
out2 = tools.resolve_verdicts(pairs, {"0": "banana"})
check("unknown verdict is treated as mismatch", len(out2) == 2, f"got {len(out2)}")

# fallback_resolve: score<75 => fuzzy_mismatch; else needs_manual_review
fb = tools.fallback_resolve([
    agent2_ambiguous_pair("port", "a", "b", "Shanghai", "Rotterdam"),      # low score
    agent2_ambiguous_pair("name", "a", "b", "ACME Corp", "ACME Corp Ltd"),  # high score
])
kinds = sorted(i["kind"] for i in fb)
check("fallback flags a low-score pair as fuzzy_mismatch", "fuzzy_mismatch" in kinds, kinds)
check("fallback flags a high-score pair for manual review", "needs_manual_review" in kinds, kinds)
check("all fallback issues are severity=major",
      all(i["severity"] == "major" for i in fb))


# ── 4. default severity mapping ─────────────────────────────────
print("\n═══ 4. default severity ═══")

issues = [
    agent2_issue("d", "f", "missing_doc", "m"),        # critical
    agent2_issue("d", "f", "lc_expired", "m"),         # critical
    agent2_issue("d", "f", "missing_field", "m"),      # minor
    agent2_issue("d", "f", "date_invalid", "m"),       # minor
    agent2_issue("d", "f", "exact_mismatch", "m"),     # major (default)
    agent2_issue("d", "f", "semantic_mismatch", "m"),  # major (default)
]
tools.apply_default_severity(issues)
sev = [i["severity"] for i in issues]
check("missing_doc → critical", sev[0] == "critical", sev[0])
check("lc_expired → critical", sev[1] == "critical", sev[1])
check("missing_field → minor", sev[2] == "minor", sev[2])
check("date_invalid → minor", sev[3] == "minor", sev[3])
check("exact_mismatch → major", sev[4] == "major", sev[4])
check("semantic_mismatch → major", sev[5] == "major", sev[5])

# a pre-set severity must never be overwritten by the fallback
preset = agent2_issue("d", "f", "missing_doc", "m")
preset["severity"] = "minor"
tools.apply_default_severity([preset])
check("fallback never overwrites an existing severity", preset["severity"] == "minor", preset["severity"])


# ── 5. default recommendation logic ─────────────────────────────
print("\n═══ 5. default recommendation ═══")

def rec_for(severities):
    return tools.default_recommendation([{"severity": s} for s in severities])

check("any critical → reject", rec_for(["critical", "minor"])["recommendation"] == "reject")
check("only major → reject", rec_for(["major", "major"])["recommendation"] == "reject")
check("only minor → approve", rec_for(["minor", "minor"])["recommendation"] == "approve")
check("no issues → approve", rec_for([])["recommendation"] == "approve")
check("clean summary mentions no discrepancies",
      "no discrepancies" in rec_for([])["summary"].lower())


# ── 6. full graph, ALL LLM calls fail → deterministic fallbacks ─
# This is the load-bearing guarantee in agent.yaml: "deterministic fallbacks
# if any call fails". Force all three to raise and prove the graph still
# produces a usable recommendation with every issue severity-stamped.
print("\n═══ 6. full graph, all LLM calls down ═══")

tools.call_semantic_compare = raise_
tools.call_severity_classify = raise_
tools.call_recommendation = raise_
pipeline.rag_query = None  # simulate RAG unavailable too

state = base_state(
    ambiguous_pairs=[
        agent2_ambiguous_pair("port", "invoice", "bl", "Shanghai", "Rotterdam"),
    ],
    issues=[agent2_issue("bill_of_lading", "amount", "numeric_mismatch", "amount differs")],
)
final = g.invoke(state)

check("graph completes despite total LLM outage", final is not None)
check("resolve fell back", final.get("resolve_failed") is True)
check("severity fell back", final.get("severity_failed") is True)
check("recommendation fell back", final.get("recommendation_failed") is True)
check("recommendation is valid", final.get("recommendation") in ("approve", "reject"),
      final.get("recommendation"))
check("recommendation summary is non-empty", bool(final.get("recommendation_summary")))
check("every issue has a severity after fallback",
      all(i.get("severity") in ("critical", "major", "minor") for i in final["issues"]),
      [i.get("severity") for i in final["issues"]])
check("ambiguous_pairs cleared at the end", final.get("ambiguous_pairs") == [])
# a low-score pair with the LLM down must still surface as a mismatch issue
check("failed pair still produced an issue",
      any(i["kind"] in ("fuzzy_mismatch", "needs_manual_review") for i in final["issues"]))
restore()


# ── 7. full graph, mocked happy path + citation ordering ────────
# Verifies the fix: citations are stamped on new semantic issues BEFORE the
# severity call, so the classifier actually sees them.
print("\n═══ 7. full graph, mocked happy path ═══")

seen_citations_at_severity = {}


def fake_rag(text, k=1):
    return [{"ref": "Article 14(d)", "text": "documents must not conflict", "source": "UCP 600"}]


def fake_semantic_compare(pairs, ctx, model, key):
    # flag every pair as a mismatch so there's a new issue to cite
    return {str(i): "mismatch" for i in range(len(pairs))}


def fake_severity(issues, model, key):
    # record, at call time, which new semantic issues already carry a citation
    for i in issues:
        if i.get("kind") == "semantic_mismatch":
            seen_citations_at_severity[i["field"]] = i.get("citation")
    return {str(i): "major" for i in range(len(issues))}


def fake_recommendation(issues, model, key):
    return {"recommendation": "reject", "summary": "Mismatches found across documents."}


tools.call_semantic_compare = fake_semantic_compare
tools.call_severity_classify = fake_severity
tools.call_recommendation = fake_recommendation
pipeline.rag_query = fake_rag

state = base_state(
    ambiguous_pairs=[
        agent2_ambiguous_pair("beneficiary", "invoice", "bl", "ACME Corp", "ACME Corporation"),
    ],
    issues=[agent2_issue("invoice", "amount", "numeric_mismatch", "amount differs")],
)
final = g.invoke(state)

check("no fallback flags set on happy path",
      not final.get("resolve_failed") and not final.get("severity_failed")
      and not final.get("recommendation_failed"))
check("new semantic issue was created", any(i["kind"] == "semantic_mismatch" for i in final["issues"]))
check("recommendation is 'reject' (from mock)", final.get("recommendation") == "reject")
check("all issues severity-stamped to major",
      all(i.get("severity") == "major" for i in final["issues"]))
check("new semantic issue carries a RAG citation",
      any(i["kind"] == "semantic_mismatch" and i.get("citation") == "Article 14(d)"
          for i in final["issues"]))
# the ordering fix: the severity classifier must have seen the citation already
check("citation was present BEFORE severity classification (ordering fix)",
      seen_citations_at_severity.get("beneficiary") == "Article 14(d)",
      f"saw: {seen_citations_at_severity}")
restore()


# ── 8. empty presentation → clean approve ───────────────────────
print("\n═══ 8. empty input ═══")

# no pairs, no issues: LLM calls should be skipped, recommendation clean-approve.
# Force any LLM call to raise so we PROVE they aren't invoked on empty input.
tools.call_semantic_compare = raise_
tools.call_severity_classify = raise_
tools.call_recommendation = fake_recommendation  # only recommendation runs on empty
pipeline.rag_query = None

final = g.invoke(base_state())
check("empty input completes", final is not None)
check("empty input did not fail resolve (skipped)", not final.get("resolve_failed"))
check("empty input did not fail severity (skipped)", not final.get("severity_failed"))
check("empty input yields a recommendation", final.get("recommendation") in ("approve", "reject"))
check("no issues carried through", final.get("issues") == [])
restore()


# ── 9. live Groq end-to-end (guarded) ───────────────────────────
print("\n═══ 9. live Groq (optional) ═══")

from Agents.Semantic_Comparator import config

if not config.GROQ_API_KEY:
    print("  (skipped — GROQ_API_KEY not set)")
else:
    try:
        state = base_state(
            ambiguous_pairs=[
                agent2_ambiguous_pair(
                    "beneficiary_name", "invoice", "bill_of_lading",
                    "ACME Corporation Limited", "ACME Corp Ltd",
                ),
            ],
            issues=[agent2_issue("invoice", "amount", "numeric_mismatch",
                                 "invoice amount 10,000 vs LC 12,000")],
        )
        final = g.invoke(state)
        check("live graph completes", final is not None)
        check("live recommendation is approve/reject",
              final.get("recommendation") in ("approve", "reject"), final.get("recommendation"))
        check("live summary is non-empty", bool(final.get("recommendation_summary")))
        check("live: every issue severity-stamped",
              all(i.get("severity") in ("critical", "major", "minor") for i in final["issues"]),
              [i.get("severity") for i in final["issues"]])
        check("live: no fallback was needed (calls succeeded)",
              not final.get("resolve_failed") and not final.get("severity_failed")
              and not final.get("recommendation_failed"),
              f"resolve={final.get('resolve_failed')} sev={final.get('severity_failed')} "
              f"rec={final.get('recommendation_failed')}")
    except Exception as e:
        check("live graph completes", False, f"{type(e).__name__}: {e}")
    finally:
        restore()


# ── Summary ─────────────────────────────────────────────────────
print(f"\n{'═' * 50}")
print(f"  TOTAL: {passed + failed}  |  PASSED: {passed}  |  FAILED: {failed}")
print(f"{'═' * 50}")

if failed > 0:
    sys.exit(1)
