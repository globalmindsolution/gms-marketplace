"""acs_lib.step — the STEP machine: `runs/<run-id>/steps/<skill>/state.json`.

The second of the two state machines (§4.4). `acs_lib.run` tracks a workflow's
progress; this tracks one skill's progress inside it.

The shape carried over from `<skill>-state.json` because it was sound: a
`states` object, `findings`, `errors`, and one record per invocation with its
session id, transcript path, checkout id, tokens, cost, role/model usage,
guard events, gate enforcement, status and stop reason. Four things changed:

  1. **`runs[]` became `invocations[]`.** Once the partition is
     `runs/<run-id>/`, a `runs` array inside a step means the wrong thing. An
     invocation is one session's attempt at this step.
  2. **`ticket_id` became `run_id`.**
  3. **`skill` validates against the skill directories, not an enum.** The
     33-name list left the schema with the other three copies of it.
  4. **The `states` keys are declared PER SKILL**, in
     `skills/<name>/state.schema.json`. The central schema validates the
     envelope only. That is the same move as the run machine's I5: a new skill
     is a directory, not a central edit — and it is how a skill becomes
     standalone in its state as well as in its invocation.

**Derived, never asserted** (MAR-523, MAR-527) carries over and extends:
`verifier_passed` is computed by the post-hook from `review-code`'s
`verdict.json`, `tests` from the gate's own run, and `outcome` is read from
`result.json` and checked against the skill's fragment. A skill that writes a
value the kernel derives is overwritten and the disagreement recorded in
`errors` -- the skill's self-report is evidence, never the verdict.
"""

import os

from ._common import GateError, now_iso, read_json, write_json
from . import schemasubset
from . import skills as skills_registry
from .run import STEP_STATUSES, STOP_REASONS, step_dir

STATE_FILENAME = "state.json"
RESULT_FILENAME = "result.json"
#: The per-skill schema fragment: its `states` keys and its `outcome` values.
STATE_FRAGMENT_FILENAME = "state.schema.json"
STEP_STATE_SCHEMA_FILENAME = "step-state.schema.json"
RESULT_SCHEMA_FILENAME = "result.schema.json"


def state_path(rdir, step):
    return os.path.join(step_dir(rdir, step), STATE_FILENAME)


def result_path(rdir, step):
    return os.path.join(step_dir(rdir, step), RESULT_FILENAME)


def fragment_path(skill, root=None):
    return os.path.join(skills_registry.skill_dir(skill, root), STATE_FRAGMENT_FILENAME)


def load_fragment(skill, root=None):
    """`skills/<skill>/state.schema.json`, or None when the skill declares no
    `states` keys and no `outcome` vocabulary -- which is the right answer for
    a step with only one way to complete."""
    path = fragment_path(skill, root)
    if not os.path.isfile(path):
        return None
    doc = read_json(path)
    return doc if isinstance(doc, dict) else None


def outcome_vocabulary(skill, root=None):
    """The `outcome` values this step may record, or [] when it has none. A
    step with only one way to complete records no outcome at all."""
    fragment = load_fragment(skill, root) or {}
    node = ((fragment.get("properties") or {}).get("outcome") or {})
    return list(node.get("enum") or [])


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def empty_state(skill, run_id):
    return {"skill": skill, "run_id": run_id, "states": {},
            "findings": [], "errors": [], "invocations": []}


def load_state(rdir, step, run_id=None):
    doc = read_json(state_path(rdir, step))
    if not isinstance(doc, dict) or not isinstance(doc.get("invocations"), list):
        return empty_state(step, run_id or os.path.basename(rdir))
    return doc


def save_state(rdir, step, doc):
    os.makedirs(step_dir(rdir, step), exist_ok=True)
    write_json(state_path(rdir, step), doc)
    return doc


def last_invocation(doc):
    invocations = doc.get("invocations") or []
    return invocations[-1] if invocations else None


def last_status(rdir, step):
    entry = last_invocation(load_state(rdir, step))
    return (entry or {}).get("status")


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

def append_invocation(rdir, step, run_id, session=None, gate=None):
    """Open a new invocation. One session's attempt at this step -- a resumed
    step gets a second entry rather than overwriting the first, so the cost and
    the session trail of an interrupted attempt survive it."""
    doc = load_state(rdir, step, run_id)
    entry = {"started_at": now_iso(), "status": "in_progress"}
    if session:
        for key in ("session_id", "transcript_path", "checkout_id"):
            if session.get(key):
                entry[key] = session[key]
    if gate:
        entry["gate_enforcement"] = gate
    doc.setdefault("invocations", []).append(entry)
    return save_state(rdir, step, doc)


def finalize_invocation(rdir, step, run_id, result):
    """Close the open invocation from the step's result document; returns
    (state, entry).

    Both, because every caller wants the entry it just closed -- to stamp the
    derived-states provenance on it, or to hand it to the metrics roll-up --
    and re-finding it through `invocations[-1]` is an invitation to find the
    wrong one after a concurrent append.

    Appends an invocation when the coordinator never registered a start, so a
    step that crashed before its pre-hook still leaves a record rather than a
    silence."""
    from .metrics import _measure_run_usage

    # No default: this writes the status the next pre-hook reads, so a result
    # document that never stated one must fail here rather than silently
    # finalize the invocation as completed. Refusing only at the CLI boundary
    # would leave the silent default reachable by any in-process caller.
    status = result.get("status")
    if status not in ("completed", "failed", "interrupted"):
        raise ValueError("invalid final invocation status: %r" % status)
    doc = load_state(rdir, step, run_id)
    invocations = doc.setdefault("invocations", [])
    if not invocations or invocations[-1].get("status") != "in_progress":
        invocations.append({"started_at": now_iso()})
    entry = invocations[-1]
    entry["ended_at"] = now_iso()
    entry["status"] = status
    # `in result`, not `is not None`: for the measurement keys, None is an
    # ANSWER -- "unavailable" -- and it is the answer the metrics roll-up folds
    # on (`runs_cost_unavailable`, `runs_api_duration_unavailable`). Skipping a
    # None left the key absent, which reads as a run that was never measured
    # rather than one whose measurement could not be taken.
    if "stop_reason" in result:
        entry["stop_reason"] = result["stop_reason"]
    if "guard_events" in result:
        entry["guard_events"] = result["guard_events"]
    # Tokens, cost and API duration are MEASURED from this invocation's own
    # recorded transcript, never taken from `result`. A coordinator reporting
    # its own spend is the same category of claim as one reporting its own
    # verdict, and the metrics roll-up folds on the measurement's BASIS -- so
    # "unavailable" is written as `None` with a basis beside it rather than
    # left absent, which would read as a run nobody tried to measure.
    _measure_run_usage(entry, rdir, step)
    if result.get("states"):
        doc.setdefault("states", {}).update(result["states"])
    for key in ("findings", "errors"):
        if result.get(key):
            doc.setdefault(key, []).extend(result[key])
    return save_state(rdir, step, doc), entry


def record_error(rdir, step, run_id, message):
    doc = load_state(rdir, step, run_id)
    doc.setdefault("errors", []).append({"at": now_iso(), "message": message})
    return save_state(rdir, step, doc)


def record_guard_event(rdir, step, run_id, event):
    """Append one file-map guard denial to the open invocation. True when it
    landed, False when there was no invocation to land on.

    The denial record is evidence the guard fired, which is why it lives on the
    invocation rather than in a log nobody reads. It NEVER raises and never
    invents an invocation to write to: the guard has already refused the write,
    and a failed append is one extra stderr note, not a second opinion. An
    exception here would let a bookkeeping failure overturn a verdict.
    """
    try:
        doc = load_state(rdir, step, run_id)
        invocations = doc.get("invocations")
        if not isinstance(invocations, list) or not invocations:
            return False
        invocations[-1].setdefault("guard_events", []).append(event)
        save_state(rdir, step, doc)
        return True
    except BaseException:  # noqa: BLE001 -- see the docstring; re-raised below
        raise


# ---------------------------------------------------------------------------
# The result document
# ---------------------------------------------------------------------------

def load_result(rdir, step):
    doc = read_json(result_path(rdir, step))
    return doc if isinstance(doc, dict) else None


def validate_result(doc, skill, root=None):
    """[error, ...] for one result document: the central envelope, then the
    skill's own `outcome` vocabulary. An empty list means it is admissible."""
    errors = []
    # `status` first, and by name: the post-hook refuses a document without one
    # (it would otherwise finalize a step and move the cursor on nothing), so
    # that is the single most useful thing to say about a bad result.
    status = doc.get("status")
    if status is None:
        errors.append("status is absent — the post-hook refuses a result document without one")
    elif status not in STEP_STATUSES:
        errors.append("status %r is not one of %s" % (status, ", ".join(STEP_STATUSES)))
    elif status == "in_progress":
        errors.append("status 'in_progress' does not finalize a step")
    if errors:
        return errors
    schema = skills_registry.load_schema(RESULT_SCHEMA_FILENAME)
    for node, message in schemasubset.schema_errors(schema, doc):
        errors.append("%s: %s" % (schemasubset.pointer(node), message))
    if errors:
        return errors
    outcome = doc.get("outcome")
    vocabulary = outcome_vocabulary(skill, root)
    if outcome is None:
        # A vocabulary of ONE is not a question. §4.5's rule is that a step
        # with only one way to complete has no outcome to state, so filling it
        # in is kinder than demanding the caller repeat the only answer --
        # and it keeps the recorded ledger complete either way.
        if len(vocabulary) == 1:
            doc["outcome"] = outcome = vocabulary[0]
        elif vocabulary:
            errors.append("outcome: %s completes in more than one way (%s) and must say which"
                          % (skill, " | ".join(vocabulary)))
    elif not vocabulary:
        errors.append("outcome: %s declares no outcome vocabulary, so %r means nothing to the "
                      "kernel — add it to skills/%s/state.schema.json or drop the field"
                      % (skill, outcome, skill))
    elif outcome not in vocabulary:
        errors.append("outcome: %r is not one of %s" % (outcome, " | ".join(vocabulary)))
    if doc.get("status") == "interrupted" and doc.get("stop_reason") not in STOP_REASONS:
        errors.append("stop_reason: an interrupted step needs one of %s"
                      % " | ".join(STOP_REASONS))
    return errors


def write_noop_result(rdir, step, run_id, outcome, reason):
    """The evidenced no-op (§2.2): the pre-hook found nothing owed, so the step
    completes with a result that says WHAT it checked and WHY nothing was
    owed, and no coordinator is ever spawned. Milliseconds, zero tokens.

    This is what `status: skipped` could not do. `skipped` recorded that a
    workflow predicate was false, which never distinguished "the plan says
    nothing is owed" from "nobody asked"."""
    doc = {
        "skill": step,
        "run_id": run_id,
        "status": "completed",
        "outcome": outcome,
        "summary": reason,
        "no_op": True,
        "ended_at": now_iso(),
    }
    os.makedirs(step_dir(rdir, step), exist_ok=True)
    write_json(result_path(rdir, step), doc)
    return doc
