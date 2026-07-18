# Internal_Checker

**Role**: Deterministic validation gate — checks parsed documents for completeness, date validity, cross-doc consistency, and LC compliance. Zero LLM calls.

---

## How it works

Receives all parsed documents and the schema config. First validates the LC terms sheet (gate check — required fields present, not expired). If the LC passes, runs two verification passes: Pass A checks per-document issues (missing docs, null fields, date rules), Pass B cross-checks documents against each other for consistency and against the LC for compliance. Fuzzy matches scoring 40–92 are queued as `ambiguous_pairs` for the Semantic_Comparator agent.

**Pipeline**:
```
gate → (lc_ok?) → pass_a → pass_b
```

---

## Inputs

- **`run_id`** — unique run identifier (for DB status updates)
- **`parsed_docs`** — `dict[str, dict]` of `doc_type → fields` from Doc_Parser
- **`schema`** — loaded `schema.json` with fields, `gate_requirements`, `date_rules`, and `compare` types
- **`issues`** — starts as `[]`, accumulated through the pipeline

---

## Project Structure

```
Internal_Checker/
├── agent.yaml             # Agent spec (v1.0, 0 LLM calls, dependencies)
├── config.py              # load_schema() for standalone testing
├── tools.py               # 15 tool functions: gate, comparators, date checks, citations
├── state.py               # CheckState TypedDict (8 fields)
├── graph.py               # LangGraph StateGraph (3 nodes, 1 conditional edge)
├── __init__.py            # Package marker
└── nodes/
    ├── __init__.py        # Package marker
    └── pipeline.py        # gate, pass_a, pass_b (uses db + optional RAG)
```

---

## Processing

| Node | What it does |
|---|---|
| `gate` | Validates LC terms via `validate_lc_terms` — checks `gate_requirements` + expiry. If invalid → `blocked=True`, graph ends |
| `pass_a` | Runs 3 checks: `check_required_documents`, `check_completeness`, `check_dates`. Stamps RAG citations |
| `pass_b` | Runs `run_consistency_checks` (docs vs docs) + `run_compliance_checks` (docs vs LC). Updates DB status to `hitl` |

---

## Tools

| Group | Tools | Purpose |
|---|---|---|
| Gate | `validate_lc_terms` | Checks all `gate_requirements` present + `expiry_date` not in past |
| Pass A — Presence | `check_required_documents` | Verifies all LC-required docs exist and are readable |
| Pass A — Completeness | `check_completeness` | Ensures required schema fields are non-null per doc |
| Pass A — Dates | `check_dates`, `_check_not_in_past`, `_check_before_after`, `_check_within_days` | Evaluates `date_rules` from schema |
| Pass B — Comparators | `compare_exact`, `compare_numeric`, `compare_date`, `fuzzy_score` | Individual field comparison functions |
| Pass B — Dispatcher | `_compare_field` | Routes to correct comparator per schema `compare` type |
| Pass B — Cross-doc | `run_consistency_checks` | Compares supporting docs against each other |
| Pass B — Compliance | `run_compliance_checks` | Compares each doc against LC terms |
| Citations | `attach_citations` | Stamps UCP/ISBP article refs via ChromaDB RAG retrieval |
| Helpers | `make_issue`, `_parse_date`, `_get_field_value` | Issue construction, date parsing, field lookup |

---

## Output

- **`issues`** — `list[dict]` of discrepancies, each with `doc_type`, `field`, `kind`, `message`, `citation`
- **`ambiguous_pairs`** — `list[dict]` of fuzzy matches in 40–92 band, forwarded to Semantic_Comparator
- **`lc_ok`** — `bool`, `False` if LC terms are incomplete or expired
- **`blocked`** — `bool`, `True` if the gate check failed (run cannot proceed)
- **`lc_terms`** — `dict` of extracted LC term sheet fields
