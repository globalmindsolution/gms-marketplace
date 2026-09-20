"""acs_lib.brakes — the pre-hook SAFETY brakes, and the two repo-document
preconditions that sit beside them.

Split out of `acs_lib.gates` when it crossed the 800-line budget. The line is
by LAYER, not by size: a brake answers "would running now do damage a re-run
cannot undo?" from the run and the repo alone. It resolves no context, takes
no lock, writes nothing, and never asks whether a skill is next. `gates` does
all of that and then consults this table.

`gates` re-exports every name here, so no caller had to move.
"""

import os

from ._common import GateError, read_json
from .gate_inputs import _refuse_epic
from .repo import find_ticket_partition
from .tickets import load_ticket
from . import run as run_machine
from . import step as step_machine


#: Safety brakes, by skill. Each returns None or raises GateError. These are
#: the checks that are not "does an input exist" -- the ones where running
#: anyway would do damage a re-run could not undo.
def _brake_code(ctx, rdir, doc, wf):
    """On the deep paths the plan must be APPROVED, and the approval must be
    for the plan that is on disk now. An implementer working from a plan the
    human approved a revision ago is the failure this prevents."""
    from . import plan_contract
    plan = run_machine.artifact_path(rdir, "plan", None, wf)
    if not plan or not os.path.isfile(plan):
        return None
    path = plan_contract.delivery_path(plan_contract.read(plan))
    if path not in ("standard", "complex"):
        return None
    approval = os.path.join(run_machine.step_dir(rdir, "create-impl-plan"),
                            "plan-approval.json")
    record = read_json(approval)
    if not isinstance(record, dict) or not record.get("approved"):
        raise GateError(
            "the %s delivery path requires an approved plan, and %s records none. "
            "Run /acs:create-impl-plan and approve its plan first." % (path, approval))
    digest = _sha256_file(plan)
    if record.get("plan_sha256") != digest:
        raise GateError(
            "the approval at %s is for a different revision of the plan (approved "
            "%s, on disk %s). An edited plan is an unapproved plan: re-approve it."
            % (approval, (record.get("plan_sha256") or "?")[:12], digest[:12]))
    return None


def _brake_create_pr(ctx, rdir, doc, wf):
    """A review that did not pass never becomes a PR. `verifier_passed` is
    DERIVED from review-code's verdict by the post-hook (MAR-523/527), so this
    reads what the kernel computed rather than any skill's self-report.

    It reads the STEP's state, not the run's ledger entry. A loop-back forgets
    the cycle's entries on purpose — a step absent from `steps` is pending —
    and that is exactly the moment a PR must be refused: the review ran, found
    something, and sent the changeset back. Reading the ledger let every
    blocking review through the instant it re-entered the loop.
    """
    if not os.path.isfile(step_machine.state_path(rdir, "review-code")):
        return None  # no review has run at all; the order advisory says so
    state = step_machine.load_state(rdir, "review-code", doc["run_id"])
    if state.get("states", {}).get("verifier_passed") is not True:
        raise GateError(
            "/acs:review-code ran for this run and did not pass (verifier_passed is not "
            "true). Fix the findings in its verdict and re-review before opening a PR.")
    return None


def _merge_pr_arg_text(payload):
    """The raw argument string, read the same way subject_from_payload reads
    it. /acs:merge-pr's exempt non-ticket forms (--pr N, #N, a PR URL) are
    parsed from this before any run is resolved: an exempt PR merge is not a
    step of a run and must not create one."""
    tool_input = payload.get("tool_input") or {}
    for key in ("args", "arguments", "argument"):
        if isinstance(tool_input.get(key), str):
            return tool_input[key]
    return ""


def _sha256_file(path):
    import hashlib
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


#: What an epic is refused FOR, per step, in that step's own words.
_EPIC_VERBS = {
    "analyze-requirements": "analyzed for implementation",
    "create-impl-plan": "planned",
    "create-api-contract": "given an API contract",
    "create-test-docs": "given test cases",
    "code": "implemented",
    "review-code": "reviewed as one changeset",
    "create-e2e-tests": "given e2e tests",
    "create-pr": "opened as one pull request",
}


def _brake_no_epics(ctx, rdir, doc, wf):
    """Epics are designed and fanned out, never worked as one ticket.

    A brake rather than an input check: the ticket resolves, the partition is
    live, everything the step needs is there -- and doing the work anyway is
    the damage. An epic implemented as one changeset is not a re-runnable
    mistake, which is what separates a brake from a missing input.
    """
    step = doc.get("__step__")
    subject = doc.get("subject") or {}
    ticket_id = subject.get("ticket_id")
    if not ticket_id or not step:
        return None
    tdir, _archived = find_ticket_partition(ctx["workspace"], ctx["repo_id"], ticket_id)
    ticket = load_ticket(tdir) if os.path.isdir(tdir) else None
    if isinstance(ticket, dict) and ticket.get("type") == "epic":
        _refuse_epic(ticket_id, step, _EPIC_VERBS.get(step, "worked directly"))
    return None


BRAKES = {
    "code": _brake_code,
    "create-pr": _brake_create_pr,
}


def _require_architecture_doc_set(ctx):
    """Shared precondition for the doc-set producer gates: the architecture
    set (hld/tech-stack.md) must exist before a downstream doc set is built.

    The FILE, not the directory: an empty `docs/architecture/` is what a
    half-finished /acs:create-architecture leaves behind, and treating it as
    a doc set is how a downstream producer ends up auditing against nothing."""
    root = ctx["checkout_root"]
    arch = os.path.join(root, ctx["settings"].get("architecture_path", "docs/architecture"))
    tech_stack = os.path.join(arch, "hld", "tech-stack.md")
    if not os.path.isfile(tech_stack):
        raise GateError(
            "no architecture doc set found at %s (expected hld/tech-stack.md) — "
            "run /acs:create-architecture first." % arch)
    return None


def _require_prd(ctx):
    root = ctx["checkout_root"]
    prd = os.path.join(root, ctx["settings"].get("prd_path", "docs/product"), "prd.md")
    if not os.path.isfile(prd):
        raise GateError("no PRD found at %s — run /acs:create-prd first (it also "
                        "baselines existing products)." % prd)
    return None


#: Skills that need the architecture doc set before they can do anything.
#: `project` itself is NOT here: it is an unhooked umbrella, so no pre-hook
#: ever fires for it and the row was dead. Each leg it dispatches to carries
#: the precondition, which is where a refusal can name the leg that needs it.
ARCHITECTURE_GATED = ("create-project", "standardize-project", "create-docs")

#: Skills that need the PRD.
#:
#: These REPO-DOCUMENT inputs are checked here rather than through a skill's
#: `reads` declaration, because they are not run artifacts: a design or product
#: skill is never a step of `ship` (§2.4), so it has no run to read them from.
#: The declaration drives the artifact gate; this drives the document gate; the
#: two do not overlap.
PRD_GATED = ("create-architecture",)
