import os
from fastapi import Header, HTTPException

API_KEY = os.environ.get("APP_API_KEY")


def require_api_key(x_api_key: str = Header(default=None)):
    """Require a shared-secret API key on protected routes.

    If APP_API_KEY isn't set in the environment, auth is skipped so local
    development still works without extra setup — main.py warns loudly at
    startup in that case.
    """
    if not API_KEY:
        return
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Missing or invalid API key")
