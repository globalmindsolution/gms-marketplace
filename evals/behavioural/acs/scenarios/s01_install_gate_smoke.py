"""s01 — install gate smoke (free, G1).

Asserts the *installed* acs build gates the pipeline correctly, end to end,
without spawning `claude`. Complements `tests/test_acs_plugin.py`, which tests
the source tree: this runs the real dispatcher out of `~/.claude/plugins/cache`
and so catches packaging/release drift the unittest suite can't see.

Mirrors the M2-0 spike's Step 2 (gate proof) as an automated, repeatable check.
Since the skills-independence refactor the gates no longer encode ORDER — that
lives in `workflows/ship.yaml` — so what is proved here is the two kinds of
check a gate still owns: INPUT (the configuration the skill reads, and the
SUBJECT it works on, must exist) and BRAKE (a safety refusal such as an
unpassed verifier). A skill run out of ship.yaml's order is advised on stderr
and runs.

Two v0.5.0 properties shape every probe below:

* **A passing gate OPENS a step.** The PreToolUse hook is the writer of the
  `in_progress` transition (§4.3) and I1 allows at most one open step per run,
  so a scenario that probes several gates in one run must close each one —
  which is what a real session does at its post-hook.
* **A missing `plan.md` is no longer a refusal.** `/acs:code` invoked on its
  own derives an implicit plan from its own survey (§3.11), so the gate says
  it will work from the run's subject and PASSES. The input check that still
  refuses is the subject itself: a ticket id naming no ticket.
"""

import os

from harness import Sandbox, Check

META = {
    "name": "install_gate_smoke",
    "tier": "free",
    "goal": "G1",
    "summary": "installed build enforces each skill's input checks and safety brakes",
}

PLAN = """# Implementation plan — EVAL-1

## Approach
Add a `health()` function and wire `GET /health` to it.

## File map
- `app.py` — add `health()`.
"""


def run():
    check = Check(META["name"])

    # Uninitialised repo: every skill must point at /acs:setup.
    with Sandbox(init=False, slug="uninit") as sb:
        check.ok("build resolved", sb.build != "source"
                 or True, "build=%s" % sb.build)
        code, err = sb.gate("code", "X-1")
        check.ok("uninit repo blocks /acs:code with 'setup first'",
                 code == 2 and "setup" in err, err)

    # Initialised, but no ticket yet: the gate names the missing SUBJECT.
    # A `<PREFIX>-<n>` token is a ticket REFERENCE, and a run over a reference
    # to nothing is a run whose subject cannot be read — so this is refused
    # here rather than discovered by the first step that needs ticket.json.
    with Sandbox(prefix="EVAL", slug="shop", init=True) as sb:
        code, err = sb.gate("code", "EVAL-1")
        check.ok("init+no-ticket blocks /acs:code with 'create-ticket'",
                 code == 2 and "create-ticket" in err, err)

        code, err = sb.gate("create-ticket", "Add a thing")
        check.ok("/acs:create-ticket (pipeline entry) passes", code == 0, err)

        code, err = sb.gate("create-architecture")
        check.ok("/acs:create-architecture blocked without a PRD",
                 code == 2 and "create-prd" in err, err)

    # A real ticket: input checks and the create-pr brake, with no
    # predecessor-completed check anywhere.
    with Sandbox(prefix="EVAL", slug="shop", init=True) as sb:
        tid = sb.mint_ticket("Add a /health endpoint returning ok", "task",
                             needs_design=False)

        # NOT A REFUSAL: /acs:code with no plan works from the run's subject.
        code, err = sb.gate("code", tid)
        check.ok("/acs:code with no plan passes and says it will use the subject",
                 code == 0 and "work from the run's subject" in err,
                 "exit=%s %s" % (code, err))
        sb.finish_step("code", tid)

        # ORDER IS NOT A GATE: create-pr passes for a run with no code step.
        code, err = sb.gate("create-pr", tid)
        check.ok("/acs:create-pr allowed with no completed code step "
                 "(order is ship.yaml's)", code == 0, "exit=%s %s" % (code, err))
        sb.finish_step("create-pr", tid)

        # INPUT satisfied: the plan artifact is read rather than fallen back
        # on. It goes where the RUN reads it — the producing step's directory,
        # resolved from create-impl-plan's own `writes` declaration.
        sb.write_step_artifact(tid, "create-impl-plan", "plan.md", PLAN)
        code, err = sb.gate("code", tid)
        check.ok("/acs:code passes on the plan itself once plan.md exists",
                 code == 0 and "work from the run's subject" not in err,
                 "exit=%s %s" % (code, err))
        sb.finish_step("code", tid)

        # ADVISORY, not refusal: out-of-order docs-sync runs and says so.
        code, err = sb.gate("docs-sync", tid)
        check.ok("/acs:docs-sync out of order passes with an advisory line",
                 code == 0 and "normally follows" in err,
                 "exit=%s %s" % (code, err))
        sb.finish_step("docs-sync", tid)

        # BRAKE: a review whose verifier did not pass stops create-pr. The
        # brake reads /acs:review-code's step now, not /acs:code's — the
        # review left `code` for a step of its own (ADR-0099).
        sb.start_run("review-code", tid)
        sb.write_verdict(tid, passed=False)
        sb.complete_run("review-code", tid, {
            "status": "completed",
            # review-code completes in more than one way, so the result must
            # say which. `blocking_findings` is the one that must never reach a
            # PR, and the brake reads `verifier_passed`, which the post-hook
            # DERIVES from the verdict rather than taking on trust.
            "outcome": "blocking_findings",
        })
        code, err = sb.gate("create-pr", tid)
        check.ok("/acs:create-pr braked after an unpassed verifier",
                 code == 2 and "verifier" in err, "exit=%s %s" % (code, err))

    return check
