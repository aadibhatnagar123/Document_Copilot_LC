import os
import json
from dotenv import load_dotenv

from db import DB_PATH  # single source of truth for the sqlite file path

load_dotenv()

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Absolute by default so schema loading doesn't depend on the process's cwd.
# SCHEMA_DIR may still be overridden with a relative path (resolved against
# the backend dir) or an absolute one.
_schema_dir_env = os.environ.get("SCHEMA_DIR")
if _schema_dir_env:
    SCHEMA_DIR = _schema_dir_env if os.path.isabs(_schema_dir_env) else os.path.join(_BACKEND_DIR, _schema_dir_env)
else:
    SCHEMA_DIR = os.path.join(_BACKEND_DIR, "configs")


def load_schema(schema_name="lc"):
    """Load the schema config for a given use case."""
    path = os.path.join(SCHEMA_DIR, schema_name, "schema.json")
    with open(path) as f:
        return json.load(f)