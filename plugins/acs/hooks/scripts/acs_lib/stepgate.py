"""acs_lib.stepgate — the pre-hook gate's generic half.

A gate answers exactly one question: would running now do damage that
re-running cannot undo? It never asks whether this skill is next, and it never
asks whether an upstream artifact exists. Order is `/acs:ship`'s business, via
`acs run next`; inputs are the skill's own business. Each skill is independent:
it reads what it finds and falls back to the run's subject (the ticket's
acceptance criteria, the prompt or the document) when an upstream artifact is
absent, so it runs the same whether `/acs:ship` invoked it or a user did.
Running out of order costs one advisory line on stderr, exit 0.

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
    # The fourth, which the comment above always counted and the table never
    # held. Without it a plan declaring `e2e: false` no-opped create-e2e-tests
    # and then spawned a full run-e2e-tests coordinator to run a suite that
    # was never written -- the exact token cost the evidenced no-op exists to
    # avoid (§2.2).
    "run-e2e-tests": ("e2e", "no_e2e_owed",
                      "the plan declares no e2e impact, so there is no suite to run"),
}


def noop_decision(rdir, step):
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
    plan_path = run_machine.artifact_path(rdir, "plan")
    if not plan_path or not os.path.isfile(plan_path):
        return None
    contract = plan_contract.read(plan_path)
    owes = contract.get("owes") or {}
    if key not in owes:
        return None
    if owes[key]:
        return None
    return outcome, owes.get("reason") or default_reason


def settle_no_op(rdir, step, run_id, wf):
    """Record the evidenced no-op and return its outcome, or None when this
    step has work. The caller (the pre-hook) refuses the invocation when this
    returns a value -- the step is already completed and the coordinator is
    never spawned."""
    decision = noop_decision(rdir, step)
    if decision is None:
        return None
    outcome, reason = decision
    step_machine.write_noop_result(rdir, step, run_id, outcome, reason)
    run_machine.finish_step(rdir, step, wf, status="completed",
                            outcome=outcome, summary=reason)
    return outcome, reason


def check_invariants(rdir, wf, doc=None):
    """I1-I5 before any transition (§4.3). A run that has drifted is refused
    here rather than discovered three steps later, when the artifacts no
    longer say which state was the true one.

    `doc` is the ledger to judge when the caller already holds it -- a
    projected run (`run.projected_run`) has none on disk to load.
    """
    errors, warnings = run_machine.check(rdir, wf, doc=doc)
    if errors:
        raise GateError(
            "this run's ledger is inconsistent and acs will not write to it:\n  %s\n"
            "Inspect it with `acs run check`; `acs run abandon` starts over."
            % "\n  ".join(errors))
    return warnings
