import os
import json
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")


def load_schema(path="configs/lc/schema.json"):
    """Load the LC field schema config."""
    with open(path) as f:
        return json.load(f)


def load_report_template(path="configs/lc/report_template.json"):
    """Load the report section template config."""
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
