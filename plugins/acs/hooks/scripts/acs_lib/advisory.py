"""acs_lib.advisory — the out-of-order advisory the pre-hook prints in place
of an order gate.

No gate refuses a skill for running before its neighbours: order lives in
`workflows/ship.yaml` and is `/acs:ship`'s business, which is what makes every
skill independently invocable (§3.11). When a hooked skill runs somewhere
other than the run's cursor, `run_pre_payload` prints ONE stderr line naming
the position and continues with exit 0:

    acs: review-code normally follows code in ship.yaml; the cursor for MAR-590 is code

The version-2 line named the step's unsatisfied `needs`. There are none now —
the list IS the order — so the line names the cursor instead: the one step the
run is actually waiting on. That is more useful as well as shorter, because a
`needs` list never told the reader which of them to go and do.

Suppressed when `settings.workflow.advisories` is false. Never a refusal,
never an exception: a workflow or run that cannot be read yields no line, and
`acs.py workflow validate` is where a broken override is reported.
"""

import os

from . import run as run_machine
from . import workflow
from .repo import repo_dir

#: The substring every advisory line carries; tests filter stderr on it.
ADVISORY_MARK = "normally follows"


def render_advisory(skill, run_id, predecessor, cursor):
    """The one advisory line, exactly:
    'acs: <skill> normally follows <predecessor> in ship.yaml; the cursor for
    <run> is <cursor>'."""
    return ("acs: %s %s %s in ship.yaml; the cursor for %s is %s"
            % (skill, ADVISORY_MARK, predecessor, run_id, cursor))


def workflow_advisory(ctx, skill, run_id, doc=None):
    """The out-of-order advisory for a hooked skill about to run, or None.

    None -- no line at all -- for every ordinary case: the skill IS the
    cursor, the workflow does not name it, advisories are off, or anything
    cannot be read. A line that appeared when nothing was wrong would train
    the reader to ignore it.

    `doc` is the run's ledger when the caller already holds it -- a projected
    run (`run.projected_run`) has none on disk to load, and `acs gate` must
    print the line the hook would print rather than fall silent.
    """
    settings = (ctx.get("settings") or {}).get("workflow") or {}
    if settings.get("advisories") is False:
        return None
    try:
        resolved = workflow.resolve_workflow(ctx.get("checkout_root"))
        wf = workflow.validate_workflow_file(resolved["path"])
    except Exception:  # noqa: BLE001 — an advisory never raises
        return None
    if not workflow.has_step(wf, skill):
        return None
    if doc is None:
        try:
            rdir = run_machine.run_dir(repo_dir(ctx["workspace"], ctx["repo_id"]), run_id)
            doc = run_machine.load_run(rdir)
        except Exception:  # noqa: BLE001
            return None
    if doc is None:
        return None
    cursor = run_machine.cursor(doc, wf)
    if cursor is None or cursor == skill:
        return None
    index = workflow.step_index(wf, skill)
    if index is None or index == 0:
        return None
    predecessor = workflow.steps_of(wf)[index - 1]
    return render_advisory(skill, run_id, predecessor, cursor)
