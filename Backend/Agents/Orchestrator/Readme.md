# Orchestrator

**Role**: Main LangGraph graph — routes between all 4 agents, handles HITL pause/resume via `interrupt()`, and persists state to SQLite after every stage. Zero LLM calls.

---

## How it works

Receives a `run_id`, loads the run data + schema from SQLite, then sequences 4 agent subgraphs: Doc_Parser → Internal_Checker → Semantic_Comparator → Report_Generator. After the semantic stage, the graph **pauses** at a HITL interrupt node — the human reviews issues and the AI recommendation, then submits `approve`, `reject`, or `retry`. On retry, the graph loops back to a specified agent. State is checkpointed to SQLite so paused runs survive server restarts.

**Pipeline**:
```
load_run → parse → check → semantic → hitl (interrupt) → reports → done
                                        ↳ retry → parse/check/semantic
```

---

## Inputs

- **`run_id`** — unique run identifier (only input; everything else loaded from DB)
- **DB tables** — `lc_runs`, `raw_documents` (read); `parsed_documents`, `discrepancies`, `hitl_decisions`, `audit_log` (written)
- **Env vars** — `SCHEMA_DIR` (optional, defaults to `configs/`)

---

## Project Structure

```
Orchestrator/
├── agent.yaml             # Agent spec (v1.0, 0 LLM calls, status_flow, agent list)
├── config.py              # DB_PATH, SCHEMA_DIR, load_schema()
├── checkpoint.py          # SqliteSaver checkpointer for HITL pause/resume
├── tools.py               # DB reads/writes: run, docs, discrepancies, decisions, errors
├── state.py               # RunState TypedDict (17 fields — shared bus for all agents)
├── graph.py               # LangGraph StateGraph (8 nodes, 4 conditional edges) + run/resume entry points
├── __init__.py            # Package marker
└── nodes/
    ├── __init__.py        # Package marker
    └── pipeline.py        # 8 node functions (imports + invokes all 4 agent subgraphs)
```

---

## Processing

| Node | What it does |
|---|---|
| `load_run` | Reads run + raw_documents from DB, loads schema config. Sets status `parsing` |
| `parse` | Invokes Doc_Parser subgraph per document. Saves each to DB. All fail → `error` |
| `check` | Invokes Internal_Checker subgraph. Retries once on crash. `blocked` → `rejected` route |
| `semantic` | Invokes Semantic_Comparator subgraph. On crash → applies default severity + recommendation |
| `hitl` | **`interrupt()`** — pauses graph, exposes issues + recommendation to human. Resumes with `approve`/`reject`/`retry` |
| `reports` | Invokes Report_Generator subgraph. Retries once on crash. Sets final status `done` or `rejected` |
| `rejected` | Terminal — marks run as `rejected` in DB |
| `error` | Terminal — marks run as `error` in DB |

---

## Tools

| Group | Tools | Purpose |
|---|---|---|
| DB Reads | `read_run`, `read_raw_documents` | Load run row + raw document rows from SQLite |
| Status | `update_status` | Writes status to `lc_runs` for frontend polling |
| Persistence | `save_parsed_doc`, `save_discrepancy`, `update_discrepancy_severity` | Writes parsed docs + issues to DB |
| Decisions | `save_recommendation`, `save_hitl_decision` | Saves Agent 3 recommendation + human HITL decision |
| Logging | `log_error` | Writes errors to `audit_log` table |
| State | `empty_state` | Returns default values for all 17 RunState keys |

---

## Output

- **`status`** — final run status: `done`, `rejected`, `error`, or `blocked`
- **`mt799_text`** / **`mt799_pdf`** — SWIFT discrepancy notice (text + PDF bytes)
- **`summary_text`** / **`summary_pdf`** — full run summary report (text + PDF bytes)
- All intermediate results persisted to SQLite throughout execution
