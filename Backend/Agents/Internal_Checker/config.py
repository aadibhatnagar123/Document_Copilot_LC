import os
import json

_dir = os.path.dirname(os.path.abspath(__file__))
_schema_path = os.path.join(_dir, "..", "..", "configs", "lc", "schema.json")


def load_schema():
    """Load schema config. Only used for standalone testing."""
    with open(_schema_path) as f:
        return json.load(f)