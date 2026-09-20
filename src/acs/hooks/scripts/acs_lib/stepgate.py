"""acs_lib.stepgate — the pre-hook gate, driven by what the skill declares.

Replaces `GATE_INPUTS` and the seventeen per-skill gate functions that grew
around it. A gate answers exactly two questions, and `INTERNALS.md` has said so
since the skills-independence refactor:

  INPUT         does the artifact this skill READS exist?
  SAFETY BRAKE  would running now do damage that re-running cannot undo?

It never answers a third — *is this skill next?* Order is `/acs:ship`'s
business, via `acs run next`; a skill invoked by hand is never asked whether
it is next, and that is what makes every skill independently invocable
(§3.11). Running out of order costs one advisory line on stderr, exit 0.

**The input half is now generic.** It reads `skills/<name>/acs.yaml`'s
`reads.required` and resolves each artifact through `acs_lib.run.artifact_path`
— the same declaration `acs workflow validate` checks a step list's order
against, so the validator and the gate cannot disagree about what a skill
needs. Adding a skill declares its inputs once, in its own directory, and both
enforcers pick it up.

**Standalone, a missing required read is a FALLBACK, not a refusal.** Every
artifact has a chain that ends at the run's subject (§3.11): the requirement
falls back to the plan's restatement and then to the ticket's acceptance
criteria, the prompt or the document. `reads.required` is therefore a
statement about a WORKFLOW — under `/acs:ship` a required read no earlier step
writes is a validation error, because the author wrote a list that makes a
step run on its fallback when it did not have to. This module refuses only
when the chain bottoms out with no subject at all.

**The no-op decision lives here too** (§2.2). Four of the ten steps owe
nothing on a change that owes nothing, and the pre-hook is where that is
settled: it reads the plan's `## Contract` block, finds `api_contract: false`,
records the step completed with `outcome: no_surface_owed` and the plan's own
reason, and refuses the invocation — so no coordinator is ever spawned.
Milliseconds, zero tokens. That is what `status: skipped` could not do:
`skipped` recorded that a workflow predicate was false, which never
distinguished *the plan says nothing is owed* from *nobody asked*.
"""

import os

from ._common import GateError
from . import plan_contract
from . import run as run_machine
from . import skills as skills_registry
from . import step as step_machine

#: skill -> (artifact-name-in-the-plan's-contract, outcome, what it checked).
#: The four steps that can complete without doing anything, and the `owes` key
#: each consults. Everything else always has work.
NO_OP_STEPS = {
    "create-api-contract": ("api_contract", "no_surface_owed",
                            "no API or data surface in this plan"),
    "create-test-docs": ("test_cases", "no_cases_owed",
                         "the plan's test strategy owes no test cases"),
    "create-e2e-tests": ("e2e", "no_e2e_owed",
                         "the plan declares no e2e impact"),
}


def check_inputs(rdir, step, manifests=None, wf=None, standalone=False):
    """Raise GateError when a required artifact is absent and nothing can
    stand in for it. Returns the list of artifacts that fell back, for the
    caller to report.

    `standalone=True` is a hand invocation: a missing artifact becomes a
    fallback the skill resolves from the subject, and only a run with no
    subject at all is refused.
    """
    manifests = manifests if manifests is not None else skills_registry.load_manifests()
    missing = run_machine.missing_reads(rdir, step, manifests, wf)
    if not missing:
        return []
    if not standalone:
        artifact, producer = missing[0]
        raise GateError(
            "no %s for this run (expected %s) — run /acs:%s first."
            % (artifact, run_machine.artifact_path(rdir, artifact, manifests, wf),
               producer or "<the skill that writes it>"))
    doc = run_machine.load_run(rdir)
    if doc is None or not (doc.get("subject") or {}).get("kind"):
        artifact, producer = missing[0]
        raise GateError(
            "no %s for this run and no subject to derive one from — give %s a ticket id, "
            "a prompt or a document, or run /acs:%s first."
            % (artifact, step, producer or "<the skill that writes it>"))
    return [artifact for artifact, _producer in missing]


def noop_decision(rdir, step, manifests=None, wf=None):
    """(outcome, reason) when this step owes nothing on this run, else None.

    Read from the plan's `## Contract` block -- the plan is where the decision
    belongs, because the plan is what knows the shape of the change. A step
    with no plan to read owes work by default: silence is not permission to
    skip.
    """
    spec = NO_OP_STEPS.get(step)
    if spec is None:
        return None
    key, outcome, default_reason = spec
    plan_path = run_machine.artifact_path(rdir, "plan", manifests, wf)
    if not plan_path or not os.path.isfile(plan_path):
        return None
    contract = plan_contract.read(plan_path)
    owes = contract.get("owes") or {}
    if key not in owes:
        return None
    if owes[key]:
        return None
    return outcome, owes.get("reason") or default_reason


def settle_no_op(rdir, step, run_id, wf, manifests=None):
    """Record the evidenced no-op and return its outcome, or None when this
    step has work. The caller (the pre-hook) refuses the invocation when this
    returns a value -- the step is already completed and the coordinator is
    never spawned."""
    decision = noop_decision(rdir, step, manifests, wf)
    if decision is None:
        return None
    outcome, reason = decision
    step_machine.write_noop_result(rdir, step, run_id, outcome, reason)
    run_machine.finish_step(rdir, step, wf, status="completed",
                            outcome=outcome, summary=reason)
    return outcome, reason


def check_invariants(rdir, wf, manifests=None):
    """I1-I5 before any transition (§4.3). A run that has drifted is refused
    here rather than discovered three steps later, when the artifacts no
    longer say which state was the true one."""
    errors, warnings = run_machine.check(rdir, wf, manifests)
    if errors:
        raise GateError(
            "this run's ledger is inconsistent and acs will not write to it:\n  %s\n"
            "Inspect it with `acs run check`; `acs run abandon` starts over."
            % "\n  ".join(errors))
    return warnings
