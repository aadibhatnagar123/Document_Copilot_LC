# Semantic_Comparator

**Role**: Resolves ambiguous field pairs via LLM semantic comparison, classifies severity on all discrepancies, and generates an approve/reject recommendation. 3 LLM calls max, each with a deterministic fallback.

---

## How it works

Receives ambiguous fuzzy-match pairs (score 40–92) from Internal_Checker plus all accumulated issues. Queries ChromaDB for UCP/ISBP rule context per pair, then makes 3 sequential Groq LLM calls: (1) resolve pairs as match/mismatch, (2) classify every issue as critical/major/minor, (3) generate approve/reject recommendation with reasoning. Each call has a deterministic fallback — the graph never crashes.

**Pipeline**:
```
rag_lookup → resolve_pairs → (fallback?) → merge_issues → classify_severity → (fallback?) → generate_recommendation → (fallback?) → apply_final
```

---

## Inputs

- **`ambiguous_pairs`** — `list[dict]` of fuzzy matches in 40–92 band from Internal_Checker
- **`issues`** — all issues accumulated so far (from Internal_Checker)
- **`schema`** — loaded `schema.json` config
- **Env vars** — `GROQ_API_KEY` (required), `GROQ_MODEL` (optional)

---

## Project Structure

```
Semantic_Comparator/
├── agent.yaml             # Agent spec (v1.0, 3 LLM calls max, dependencies)
├── config.py              # GROQ_API_KEY, GROQ_MODEL, load_schema()
├── tools.py               # 3 LLM call functions + 3 deterministic fallbacks + citations
├── state.py               # SemanticState TypedDict (9 fields)
├── graph.py               # LangGraph StateGraph (8 nodes, 3 conditional edges)
├── __init__.py            # Package marker
└── nodes/
    ├── __init__.py        # Package marker
    └── pipeline.py        # 8 node functions (uses optional RAG retriever)
```

**External prompts**: `Prompts/semantic_comparator_prompts.py` → `build_semantic_prompt()`, `build_severity_prompt()`, `build_recommendation_prompt()`

---

## Processing

| Node | What it does |
|---|---|
| `rag_lookup` | Queries ChromaDB for UCP/ISBP rules per ambiguous pair as context for LLM |
| `resolve_pairs` | **LLM Call 1** — judges each pair as `match`/`mismatch` with rule context |
| `deterministic_fallback` | Fallback for Call 1 — rapidfuzz at stricter `75` threshold → `fuzzy_mismatch` or `needs_manual_review` |
| `merge_issues` | Combines Internal_Checker issues + new resolved semantic issues. Stamps RAG citations on new issues |
| `classify_severity` | **LLM Call 2** — classifies every issue as `critical`/`major`/`minor` |
| `default_severity` | Fallback for Call 2 — deterministic kind→severity map (`missing_doc` → critical, `missing_field` → minor, etc.) |
| `generate_recommendation` | **LLM Call 3** — approve/reject with 3–5 sentence reasoning. Non-`approve` defaults to `reject` |
| `apply_default_recommendation` | Fallback for Call 3 — severity-count-based decision (any critical → reject, only minor → approve) |
| `apply_final` | Clears `ambiguous_pairs` (all resolved). Pipeline complete |

---

## Tools

| Group | Tools | Purpose |
|---|---|---|
| LLM Call 1 | `call_semantic_compare`, `resolve_verdicts` | Groq JSON call to judge pairs; converts verdicts to `semantic_mismatch` issues |
| Fallback 1 | `fallback_resolve` | rapidfuzz at `75` threshold → `fuzzy_mismatch` or `needs_manual_review` |
| LLM Call 2 | `call_severity_classify`, `apply_severity` | Groq JSON call to classify severity; stamps onto issues |
| Fallback 2 | `apply_default_severity` | Kind→severity map: `missing_doc`/`lc_expired` → critical, `missing_field` → minor, else → major |
| LLM Call 3 | `call_recommendation` | Groq JSON call for approve/reject + summary reasoning |
| Fallback 3 | `default_recommendation` | Severity counts: any critical → reject, any major → reject, only minor → approve |
| Citations | `attach_citations` | Stamps UCP/ISBP article refs on new semantic issues via RAG |

---

## Output

- **`issues`** — `list[dict]` with severity (`critical`/`major`/`minor`) + citations stamped on all issues
- **`recommendation`** — `str`, `"approve"` or `"reject"`
- **`recommendation_summary`** — `str`, 3–5 sentence explanation from LLM (or deterministic fallback)
- **`ambiguous_pairs`** — `[]` (cleared — all pairs resolved)
