import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

import os
import sys

load_dotenv()

# Startup validation
if not os.environ.get("GROQ_API_KEY"):
    print("=====================================================================", file=sys.stderr)
    print("WARNING: GROQ_API_KEY is not set in the environment or .env file!", file=sys.stderr)
    print("LLM calls to Groq will fail. Please add it to your environment or .env.", file=sys.stderr)
    print("=====================================================================", file=sys.stderr)

if not os.environ.get("APP_API_KEY"):
    print("=====================================================================", file=sys.stderr)
    print("WARNING: APP_API_KEY is not set — the API is running with NO auth.", file=sys.stderr)
    print("Anyone who can reach this server can upload, view, and decide runs.", file=sys.stderr)
    print("Set APP_API_KEY in .env to require it (see .env.example).", file=sys.stderr)
    print("=====================================================================", file=sys.stderr)

from api.routes.runs import router as runs_router

app = FastAPI(title="Document Copilot API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000","http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(runs_router)


@app.get("/")
def read_root():
    return {"message": "Welcome to Document Copilot API!"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

