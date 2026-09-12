"""acs_lib.advisory — the out-of-order advisory the pre-hook prints in place of
the order gates.

Since the skills-independence refactor no gate refuses a skill for running
before its predecessor; the order lives in workflows/ship.yaml. When a hooked
skill runs out of that declared order -- one of its step's `needs` is not
satisfied for the ticket per pipeline-state.json -- run_pre_payload prints ONE
stderr line naming the position and continues with exit 0:

    acs: <skill> normally follows <needs> in ship.yaml; <need> has not completed for <ID>

`<needs>` are the step's declared needs and `<need>` the ones still pending,
each rendered as a prose list ("a, b and c"); the verb agrees with the pending
count ("has" / "have not completed"). Suppressed when
settings.workflow.advisories is false. Read through acs_lib.workflow.resolve
(the consumer override when present, else the plugin default) and
workflow.pending_needs, which never writes the ledger. Never a refusal, never
an exception: a workflow or ticket that cannot be read yields no line --
`acs.py workflow validate` is where a broken override is reported.
"""

from . import workflow

#: The substring every advisory line carries; tests filter stderr on it.
ADVISORY_MARK = "normally follows"


def _prose_list(names):
    names = list(names)
    if len(names) <= 1:
        return "".join(names)
    return "%s and %s" % (", ".join(names[:-1]), names[-1])


def render_advisory(skill, ticket_id, needs, pending):
    """The one advisory line, exactly:
    'acs: <skill> normally follows <needs> in ship.yaml; <pending> has not completed for <ID>'
    -- `needs` are the step's declared needs, `pending` the ones not satisfied."""
    pending = list(pending)
    verb = "has" if len(pending) == 1 else "have"
    return "acs: %s %s %s in ship.yaml; %s %s not completed for %s" % (
        skill, ADVISORY_MARK, _prose_list(needs), _prose_list(pending), verb, ticket_id)


def _workflow_step(doc, skill):
    """The first ship.yaml step whose skill is `skill` (aliases resolved), or None."""
    skill = workflow.skill_aliases().get(skill, skill)
    for step in doc.get("steps") or []:
        if step.get("skill") == skill:
            return step
    return None


def workflow_advisory(ctx, skill, ticket_id, tdir=None, ticket=None):
    """The out-of-order advisory line for a hooked skill about to run for a
    ticket, or None when the skill is in its declared place (every `needs` of
    its ship.yaml step is satisfied per pipeline-state.json), when the skill is
    not a ship.yaml step at all, or when settings.workflow.advisories is false.

    `tdir`/`ticket` are optional short-cuts for a caller that already loaded
    the partition; otherwise the ticket is resolved through
    workflow.ticket_context (which reads it via the acs_lib facade's
    load_ticket at call time). NEVER raises and never refuses -- see the
    module docstring."""
    settings = ctx.get("settings") or {}
    if not (settings.get("workflow") or {}).get("advisories", True):
        return None
    try:
        if tdir is not None and isinstance(ticket, dict):
            wctx = dict(ctx)
            wctx.update({"ticket_id": ticket_id, "tdir": tdir, "ticket": ticket})
        else:
            wctx = workflow.ticket_context(ctx, ticket_id, tdir=tdir)
        resolved = workflow.resolve_workflow(ctx.get("checkout_root"))
        pending = workflow.pending_needs(wctx, skill, resolved=resolved)
        if not pending:
            return None
        step = _workflow_step(resolved["workflow"], skill)
        needs = list((step or {}).get("needs") or [])
        return render_advisory(skill, ticket_id, needs, [entry["step"] for entry in pending])
    except Exception:  # noqa: BLE001 -- advice only, never a refusal
        return None
