# Document Copilot

An AI copilot for checking **Letter of Credit (LC)** document presentations against
UCP 600 and ISBP rules. It runs a multi-agent pipeline over uploaded trade documents,
surfaces discrepancies with a severity level and rule citations, pauses for a human
review, and produces an MT799-formatted notice.

## How it works

The run flows through four agents with a human checkpoint in the middle:

1. **Parser** extracts structured fields from the uploaded PDFs.
2. **Checker** runs gate and completeness checks, flagging missing fields and mismatches.
3. **Semantic** resolves ambiguous field pairs, classifies each discrepancy as
   `critical`, `major`, or `minor`, and makes an approve or reject recommendation.
4. **Human review (HITL)** shows the findings and the AI recommendation, then the
   reviewer approves or rejects.
5. **Report** writes the MT799 notice and a summary report.

Rule context from UCP 600 and ISBP is retrieved from a local vector store (RAG) and
attached to each finding as a citation.

## Tech stack

| Layer | Built with |
| :--- | :--- |
| Backend | FastAPI, LangGraph, SQLite (run state), ChromaDB (RAG), Groq (LLM) |
| Frontend | React, Vite, Tailwind CSS |

## Running locally

### Backend

Requires Python 3.13+ and [uv](https://github.com/astral-sh/uv).

```bash
cd Backend
# create a .env file with:
#   GROQ_API_KEY=your_key_here
#   APP_API_KEY=optional_key_to_require_auth
uv run python main.py
```

Serves the API at `http://localhost:8000`.

### Frontend

```bash
cd Frontend
npm install
npm run dev
```

Serves the app at `http://localhost:5173`.

Open the app, upload the LC term sheet plus supporting documents, and follow the
run through the review checkpoint.

## Notes

- PDF documents only, up to 8 files per check.
- Set `APP_API_KEY` in `Backend/.env` to require an API key on all endpoints.

