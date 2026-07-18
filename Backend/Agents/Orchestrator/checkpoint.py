import os
import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver

from db import DB_PATH

# Shared across calls to build_orchestrator() so a run's state (and its
# paused HITL interrupt) survives between the initial invoke and the later
# resume. Backed by SQLite (not InMemorySaver) so a server restart doesn't
# lose a run that's paused at the HITL step. check_same_thread=False is safe
# here — SqliteSaver serializes access internally, and FastAPI's
# BackgroundTasks may run each request on a different worker thread.
_CHECKPOINT_PATH = os.path.join(os.path.dirname(DB_PATH), "lc_checkpoints.db")
_conn = sqlite3.connect(_CHECKPOINT_PATH, check_same_thread=False)
_checkpointer = SqliteSaver(_conn)
_checkpointer.setup()


def get_checkpointer():
    return _checkpointer
