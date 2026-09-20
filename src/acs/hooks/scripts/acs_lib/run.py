"""acs_lib.run — the RUN machine: `runs/<run-id>/run.json`.

One of the two state machines the redesign makes explicit (§4.3 of
docs/REDESIGN-IMPLEMENTATION-PIPELINE.md). This one tracks a workflow's
progress over a subject; `acs_lib.step` tracks one skill's progress inside it.

What changed from `pipeline-state.json`, and why:

  * **The partition is a RUN, not a ticket.** A ticket id, when supplied, is
    the run's *subject*; a run may equally be started from a prompt or a
    document, which is what makes the pipeline usable for the common case of
    a developer with an idea and a repo.
  * **`steps` is OPEN.** The 18-name enum is gone. Step names validate
    against the *resolved workflow*; skill and leg names against the *skill
    directories* (`acs_lib.skills`); the JSON schema validates shape only. So
    a new workflow is a YAML file and a new skill is a directory — neither
    touches a schema or a central list.
  * **`cursor`, not a ready-set.** With no `needs:` graph there is nothing to
    traverse: the cursor is the first step in workflow order that is not
    `completed`.
  * **`skipped` and `handed_off` are gone.** The first recorded a workflow
    predicate's answer, which no longer exists — a step that had nothing to do
    is `completed` with an `outcome` saying so. The second named a *reason*,
    which now lives in `stop_reason` on the single resumable state,
    `interrupted`.

**Every transition has exactly one writer, and it is never an agent.** The
functions here are those writers; the `acs run` / `acs step` verbs are how the
hooks reach them. A skill that writes `run.json` with its own `Write` tool is
overwritten by the post-hook and the disagreement recorded — the same
derived-never-asserted discipline as MAR-523/527.
"""

import os
import re

from ._common import GateError, now_iso, read_json, write_json
from . import skills as skills_registry
from . import workflow as workflow_mod

RUN_FILENAME = "run.json"
RUNS_DIRNAME = "runs"
STEPS_DIRNAME = "steps"
SUBJECT_DIRNAME = "subject"
RUNS_INDEX_FILENAME = "runs-index.json"

#: The run's own states. `abandoned` is the human escape hatch; there is no
#: `paused` because an unfinished run is simply one whose cursor has not moved.
RUN_STATUSES = ("in_progress", "completed", "failed", "abandoned")
TERMINAL_RUN_STATUSES = ("completed", "failed", "abandoned")

#: A step's states. A step absent from `steps` is pending; there is no
#: `pending` value, because recording "has not happened" is not a transition.
STEP_STATUSES = ("in_progress", "completed", "failed", "interrupted")

#: Why an `interrupted` step stopped. Replaces the `handed_off` status.
STOP_REASONS = ("session_end", "needs_input", "context_pressure")

#: What a run can be about.
SUBJECT_KINDS = ("ticket", "prompt", "document", "branch")

_SLUG_STOP = re.compile(r"[^a-z0-9]+")


# ---------------------------------------------------------------------------
# Paths and ids
# ---------------------------------------------------------------------------

def runs_dir(repo_dir_path):
    return os.path.join(repo_dir_path, RUNS_DIRNAME)


def run_dir(repo_dir_path, run_id):
    return os.path.join(runs_dir(repo_dir_path), run_id)


def run_path(rdir):
    return os.path.join(rdir, RUN_FILENAME)


def steps_dir(rdir):
    return os.path.join(rdir, STEPS_DIRNAME)


def step_dir(rdir, step):
    return os.path.join(steps_dir(rdir), step)


def iteration_dir(rdir, step, iteration):
    """`steps/<step>/iter-<n>/` — the AUDIT TRAIL. The step root holds the
    CURRENT artifacts; this holds the ones there were. A reader who wants the
    plan reads `steps/create-impl-plan/plan.md`; a reader who wants the plans
    lists these directories. That is what replaces the `iter-<n>-<phase>` and
    `plan-superseded-<n>` filename prefixes, whose "current" artifact was
    whichever file happened to sort last."""
    return os.path.join(step_dir(rdir, step), "iter-%d" % iteration)


def subject_dir(rdir):
    return os.path.join(rdir, SUBJECT_DIRNAME)


def runs_index_path(repo_dir_path):
    return os.path.join(repo_dir_path, RUNS_INDEX_FILENAME)


def slug(text, words=6):
    """The first `words` words of `text`, lowercased and hyphenated. The same
    shape `acs slug` renders a branch name with."""
    parts = [p for p in _SLUG_STOP.sub("-", (text or "").lower()).split("-") if p]
    return "-".join(parts[:words])


def derive_run_id(subject, existing=()):
    """A run id that READS like the thing it names (§4.2):

        ticket MAR-590                     -> MAR-590
        prompt "fix the login timeout ..." -> fix-the-login-timeout-3f2a
        document docs/rfcs/0042-retry.md   -> 0042-retry-9c1e

    The four hex characters exist only so two prompts that slug the same do
    not collide. Nobody is expected to remember them, because nobody is
    expected to TYPE a run id: `/acs:ship` with no argument resumes this
    checkout's run, and a subject resumes by subject (§4.9).

    A second run on the same subject appends `-r2`, `-r3`, ...
    """
    kind = subject.get("kind")
    if kind == "ticket":
        base = subject["ticket_id"]
    else:
        import hashlib
        if kind == "document":
            text = os.path.splitext(os.path.basename(subject.get("path") or ""))[0]
            seed = subject.get("sha256") or subject.get("path") or ""
        else:
            text = subject.get("text") or ""
            seed = text
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:4]
        base = "%s-%s" % (slug(text) or "run", digest)
    existing = set(existing)
    if base not in existing:
        return base
    n = 2
    while "%s-r%d" % (base, n) in existing:
        n += 1
    return "%s-r%d" % (base, n)


def existing_run_ids(repo_dir_path):
    base = runs_dir(repo_dir_path)
    if not os.path.isdir(base):
        return []
    return sorted(n for n in os.listdir(base) if os.path.isdir(os.path.join(base, n)))


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def empty_run(run_id, workflow, workflow_version, subject):
    return {
        "run_id": run_id,
        "workflow": workflow,
        "workflow_version": workflow_version,
        "subject": dict(subject),
        "status": "in_progress",
        "cursor": None,
        "steps": {},
        "loops": {},
        "totals": {},
    }


def load_run(rdir):
    """`run.json`, or None when this directory holds no run."""
    doc = read_json(run_path(rdir))
    return doc if isinstance(doc, dict) and isinstance(doc.get("steps"), dict) else None


def require_run(rdir):
    doc = load_run(rdir)
    if doc is None:
        raise GateError("no run recorded at %s" % rdir)
    return doc


def step_entry(doc, step):
    return (doc.get("steps") or {}).get(step) or {}


def step_status(doc, step):
    return step_entry(doc, step).get("status")


def step_completed(doc, step):
    return step_status(doc, step) == "completed"


def in_progress_step(doc):
    """The one step recorded `in_progress`, or None. I1 says there is at most
    one; `check` is what proves it."""
    for step, entry in (doc.get("steps") or {}).items():
        if (entry or {}).get("status") == "in_progress":
            return step
    return None


def loop_iteration(doc, step):
    """How many times the loop ending at `step` has run. 1 on the first pass:
    an iteration count that starts at 0 makes every artifact path off by one."""
    return int(((doc.get("loops") or {}).get(step) or {}).get("iteration") or 1)


def iteration_of(doc, step, wf=None):
    """The iteration number for `step`'s artifacts. For a step inside a
    workflow loop that is the loop's count, so `steps/code/iter-2/` and
    `steps/review-code/iter-2/` are the same round; for a step with its own
    internal cycle it is that cycle's count. Either way: the n-th time this
    step ran its cycle."""
    entry = step_entry(doc, step)
    if "iteration" in entry:
        return int(entry["iteration"])
    if wf is not None:
        for loop in workflow_mod.loops_of(wf):
            if step in (loop["from"], loop["back_to"]):
                return loop_iteration(doc, loop["from"])
    return 1


def cursor(doc, wf):
    """The first step in workflow order that is not `completed`, or None when
    every step is. This is the whole of "what runs next" -- there is no graph
    to traverse and no ready-set to compute."""
    for step in workflow_mod.steps_of(wf):
        if not step_completed(doc, step):
            return step
    return None


# ---------------------------------------------------------------------------
# Writing -- the transitions
# ---------------------------------------------------------------------------

def create_run(repo_dir_path, subject, wf, wf_path, run_id=None):
    """Record a new run and return (run_id, rdir, doc). The caller is
    `acs run new`, reached from the first step's pre-hook when the checkout
    has no current run."""
    kind = subject.get("kind")
    if kind not in SUBJECT_KINDS:
        raise GateError("subject kind %r is not one of %s" % (kind, ", ".join(SUBJECT_KINDS)))
    run_id = run_id or derive_run_id(subject, existing_run_ids(repo_dir_path))
    rdir = run_dir(repo_dir_path, run_id)
    if os.path.isdir(rdir) and load_run(rdir) is not None:
        raise GateError("run %s already exists at %s" % (run_id, rdir))
    os.makedirs(steps_dir(rdir), exist_ok=True)
    os.makedirs(subject_dir(rdir), exist_ok=True)
    doc = empty_run(run_id, workflow_mod.workflow_name(wf_path),
                    wf.get("version"), subject)
    doc["started_at"] = now_iso()
    doc["cursor"] = cursor(doc, wf)
    save_run(rdir, doc)
    index_run(repo_dir_path, doc)
    return run_id, rdir, doc


def save_run(rdir, doc):
    write_json(run_path(rdir), doc)
    return doc


def start_step(rdir, step, wf, iteration=None):
    """step -> `in_progress`. Writer: `acs step start`, on PreToolUse(Skill).

    Refuses when another step is already `in_progress` (I1): two steps writing
    one changeset is how a run loses track of which one owns a commit.
    """
    doc = require_run(rdir)
    running = in_progress_step(doc)
    if running and running != step:
        raise GateError("step %s is already in_progress in run %s — finish or interrupt it "
                        "first (`acs step finish --step %s --interrupted`)"
                        % (running, doc["run_id"], running))
    entry = dict(step_entry(doc, step))
    entry["status"] = "in_progress"
    entry.setdefault("started_at", now_iso())
    entry.pop("ended_at", None)
    entry.pop("stop_reason", None)
    if iteration is not None:
        entry["iteration"] = int(iteration)
    elif step in (doc.get("loops") or {}):
        entry["iteration"] = loop_iteration(doc, step)
    doc.setdefault("steps", {})[step] = entry
    doc["cursor"] = step
    doc["status"] = "in_progress"
    return save_run(rdir, doc)


def finish_step(rdir, step, wf, status="completed", outcome=None, summary=None,
                stop_reason=None, extra=None):
    """step -> `completed` / `failed` / `interrupted`, then recompute the
    cursor, the loop and the run's own status. Writer: `acs step finish`, from
    the step's `result.json`, on the post-hook.

    This one function owns every consequence of a step ending, which is what
    keeps them consistent: a caller cannot advance the cursor without also
    settling the loop, or fail a step without failing the run.
    """
    if status not in STEP_STATUSES:
        raise GateError("step status %r is not one of %s" % (status, ", ".join(STEP_STATUSES)))
    if status == "interrupted" and stop_reason not in STOP_REASONS:
        raise GateError("an interrupted step needs a stop_reason (%s) — `handed_off` was a "
                        "reason wearing a status, and that is the distinction this replaces"
                        % ", ".join(STOP_REASONS))
    doc = require_run(rdir)
    entry = dict(step_entry(doc, step))
    entry["status"] = status
    entry["ended_at"] = now_iso()
    if outcome is not None:
        entry["outcome"] = outcome
    if summary is not None:
        entry["summary"] = summary
    if stop_reason is not None:
        entry["stop_reason"] = stop_reason
    if extra:
        entry.update(extra)
    doc.setdefault("steps", {})[step] = entry

    exhausted = False
    if status == "completed":
        exhausted = _settle_loop(doc, step, wf, outcome)

    doc["cursor"] = cursor(doc, wf)
    if status == "failed" or exhausted:
        doc["status"] = "failed"
        doc["ended_at"] = now_iso()
    elif doc["cursor"] is None:
        doc["status"] = "completed"
        doc["ended_at"] = now_iso()
    else:
        doc["status"] = "in_progress"
    save_run(rdir, doc)
    _reindex(rdir, doc)
    return doc


def _settle_loop(doc, step, wf, outcome):
    """When `step` closes a loop and its outcome re-enters it, bump the
    iteration and reopen the steps of the cycle. Returns True when the cap is
    reached, which fails the run: a run that exhausted its review loop never
    "passes with findings"."""
    loop = workflow_mod.loop_for(wf, step)
    if loop is None or outcome not in ("blocking_findings",):
        return False
    loops = doc.setdefault("loops", {})
    state = loops.setdefault(step, {"iteration": 1, "max": loop["max_iterations"]})
    state["max"] = loop["max_iterations"]
    if state["iteration"] >= loop["max_iterations"]:
        doc["steps"][step]["outcome"] = "exhausted"
        return True
    state["iteration"] = int(state["iteration"]) + 1
    steps = workflow_mod.steps_of(wf)
    span = steps[steps.index(loop["back_to"]):steps.index(loop["from"]) + 1]
    # Reopen the cycle by FORGETTING it: a step absent from `steps` is
    # pending, so the cursor falls back to `back_to` with no extra vocabulary.
    # Nothing is lost -- `steps/<step>/iter-<n>/` holds what each pass did.
    for name in span:
        doc["steps"].pop(name, None)
    return False


def abandon_run(rdir, reason=None):
    """run -> `abandoned`. Writer: `acs run abandon`, a human. The one
    transition no hook makes."""
    doc = require_run(rdir)
    doc["status"] = "abandoned"
    doc["ended_at"] = now_iso()
    if reason:
        doc["abandoned_reason"] = reason
    save_run(rdir, doc)
    _reindex(rdir, doc)
    return doc


# ---------------------------------------------------------------------------
# The index
# ---------------------------------------------------------------------------

def load_index(repo_dir_path):
    doc = read_json(runs_index_path(repo_dir_path))
    return doc if isinstance(doc, dict) and isinstance(doc.get("runs"), list) else {"runs": []}


def index_run(repo_dir_path, doc):
    index = load_index(repo_dir_path)
    row = {
        "run_id": doc["run_id"],
        "workflow": doc.get("workflow"),
        "subject": doc.get("subject"),
        "status": doc.get("status"),
        "started_at": doc.get("started_at"),
        "ended_at": doc.get("ended_at"),
    }
    rows = [r for r in index["runs"] if r.get("run_id") != doc["run_id"]]
    rows.append(row)
    index["runs"] = rows
    write_json(runs_index_path(repo_dir_path), index)
    return index


def _reindex(rdir, doc):
    repo_dir_path = os.path.dirname(os.path.dirname(rdir))
    try:
        index_run(repo_dir_path, doc)
    except OSError:
        pass


def find_runs_for_subject(repo_dir_path, kind, key):
    """Every run whose subject matches, newest last. `key` is the ticket id,
    the prompt text or the document path."""
    field = {"ticket": "ticket_id", "prompt": "text", "document": "path",
             "branch": "branch"}.get(kind)
    out = []
    for row in load_index(repo_dir_path).get("runs") or []:
        subject = row.get("subject") or {}
        if subject.get("kind") == kind and (field is None or subject.get(field) == key):
            out.append(row)
    return out


def latest_open_run(repo_dir_path, kind, key):
    """The newest non-terminal run on this subject, or None -- what
    `/acs:ship MAR-590` resumes (§4.9)."""
    for row in reversed(find_runs_for_subject(repo_dir_path, kind, key)):
        if row.get("status") not in TERMINAL_RUN_STATUSES:
            return row
    return None


# ---------------------------------------------------------------------------
# Invariants -- `acs run check`
# ---------------------------------------------------------------------------

def check(rdir, wf, manifests=None):
    """(errors, warnings) for invariants I1-I5 (§4.3). Every pre-hook calls
    this before allowing a transition, so a run cannot drift silently between
    one step and the next."""
    manifests = manifests if manifests is not None else skills_registry.load_manifests()
    doc = require_run(rdir)
    steps = workflow_mod.steps_of(wf)
    errors, warnings = [], []

    running = [s for s, e in (doc.get("steps") or {}).items()
               if (e or {}).get("status") == "in_progress"]
    if len(running) > 1:
        errors.append("I1: %d steps are in_progress at once (%s); at most one may be"
                      % (len(running), ", ".join(sorted(running))))

    expected = cursor(doc, wf)
    if doc.get("cursor") != expected:
        errors.append("I2: cursor is %r but the first step not completed is %r"
                      % (doc.get("cursor"), expected))
    if running and doc.get("cursor") != running[0]:
        errors.append("I2: %s is in_progress but the cursor is %r"
                      % (running[0], doc.get("cursor")))

    for step, entry in (doc.get("steps") or {}).items():
        if (entry or {}).get("status") != "completed":
            continue
        result = os.path.join(step_dir(rdir, step), "result.json")
        if not os.path.isfile(result):
            errors.append("I3: %s is completed but has no result.json" % step)

    for step, state in (doc.get("loops") or {}).items():
        if int(state.get("iteration") or 1) > int(state.get("max") or 1):
            warnings.append("I4: %s is at iteration %s of a maximum %s — /acs:ship refuses "
                            "to loop past the cap; a hand-driven run may exceed it"
                            % (step, state.get("iteration"), state.get("max")))

    for step in (doc.get("steps") or {}):
        if step not in steps:
            errors.append("I5: %r is not a step of workflow %r" % (step, doc.get("workflow")))
    for step, entry in (doc.get("steps") or {}).items():
        leg = (entry or {}).get("leg")
        if leg and skills_registry.entry_point_of(leg, manifests) != step:
            errors.append("I5: %s recorded leg %r, which is not a leg of it" % (step, leg))
    return errors, warnings
