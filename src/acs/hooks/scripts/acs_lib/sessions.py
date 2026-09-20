"""acs_lib.sessions — `sessions/<checkout-id>/`, one directory per checkout.

Five files related by a filename prefix became one directory:

    sessions/<checkout>.json                 ┐            sessions/<checkout-id>/
    sessions/<checkout>-session.json         │  becomes     pointer.json
    sessions/<checkout>-cost-cursor.json     │              session.json
    sessions/<checkout>-cost-samples.jsonl   │              cost.jsonl
    sessions/<checkout>-claude-version.json  ┘              runtime.json

**`pointer.json` is why nobody types a run id.** Hooks are deterministic
scripts that cannot read a conversation, so something on disk has to say what
this checkout is working on. It already did — it recorded the current ticket
and skill — and it now records the current RUN and STEP. That is the whole
mechanism behind §4.9's table: `/acs:ship` with no argument resumes the run
this pointer names, and `--run` exists only for the rare second run on one
subject.
"""

import os

from ._common import now_iso, read_json, write_json

SESSIONS_DIRNAME = "sessions"
POINTER_FILENAME = "pointer.json"
SESSION_FILENAME = "session.json"
COST_FILENAME = "cost.jsonl"
RUNTIME_FILENAME = "runtime.json"


def sessions_dir(repo_dir_path):
    return os.path.join(repo_dir_path, SESSIONS_DIRNAME)


def checkout_dir(repo_dir_path, ckid):
    return os.path.join(sessions_dir(repo_dir_path), ckid)


def pointer_path(repo_dir_path, ckid):
    return os.path.join(checkout_dir(repo_dir_path, ckid), POINTER_FILENAME)


def session_path(repo_dir_path, ckid):
    return os.path.join(checkout_dir(repo_dir_path, ckid), SESSION_FILENAME)


def cost_path(repo_dir_path, ckid):
    return os.path.join(checkout_dir(repo_dir_path, ckid), COST_FILENAME)


def runtime_path(repo_dir_path, ckid):
    return os.path.join(checkout_dir(repo_dir_path, ckid), RUNTIME_FILENAME)


def load_pointer(repo_dir_path, ckid):
    doc = read_json(pointer_path(repo_dir_path, ckid))
    return doc if isinstance(doc, dict) else None


def save_pointer(repo_dir_path, ckid, run_id=None, step=None, checkout_path=None):
    """Record what this checkout is working on. A `run_id` of None clears it,
    which is what a finished run leaves behind -- better than a pointer at a
    completed run, which would make the next invocation resume something that
    is over."""
    doc = load_pointer(repo_dir_path, ckid) or {}
    doc["checkout_id"] = ckid
    if checkout_path:
        doc["checkout_path"] = checkout_path
    doc["run_id"] = run_id
    doc["step"] = step
    doc["updated_at"] = now_iso()
    os.makedirs(checkout_dir(repo_dir_path, ckid), exist_ok=True)
    write_json(pointer_path(repo_dir_path, ckid), doc)
    return doc


def current_run_id(repo_dir_path, ckid):
    return (load_pointer(repo_dir_path, ckid) or {}).get("run_id")


def current_step(repo_dir_path, ckid):
    return (load_pointer(repo_dir_path, ckid) or {}).get("step")
