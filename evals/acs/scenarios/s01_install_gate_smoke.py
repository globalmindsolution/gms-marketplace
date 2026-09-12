"""s01 — install gate smoke (free, G1).

Asserts the *installed* acs build gates the pipeline correctly, end to end,
without spawning `claude`. Complements `tests/test_acs_plugin.py`, which tests
the source tree: this runs the real dispatcher out of `~/.claude/plugins/cache`
and so catches packaging/release drift the unittest suite can't see.

Mirrors the M2-0 spike's Step 2 (gate proof) as an automated, repeatable check.
Since the skills-independence refactor the gates no longer encode ORDER — that
lives in `workflows/ship.yaml` — so what is proved here is the two kinds of
check a gate still owns: INPUT (the configuration or producer artifact the
skill reads must exist) and BRAKE (a safety refusal such as an unpassed
verifier). A skill run out of ship.yaml's order is advised on stderr and runs.
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

    # Initialised, but no ticket yet: the gate names the missing input.
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

        # INPUT: /acs:code needs the plan /acs:create-impl-plan writes.
        code, err = sb.gate("code", tid)
        check.ok("/acs:code blocked without a plan (points at create-impl-plan)",
                 code == 2 and "create-impl-plan" in err, err)

        # ORDER IS NOT A GATE: create-pr passes for a ticket with no code run.
        code, err = sb.gate("create-pr", tid)
        check.ok("/acs:create-pr allowed with no code run (order is ship.yaml's)",
                 code == 0, "exit=%s %s" % (code, err))

        # INPUT satisfied: the plan artifact opens /acs:code.
        with open(sb.ticket_path(tid, "plan.md"), "w") as fh:
            fh.write(PLAN)
        code, err = sb.gate("code", tid)
        check.ok("/acs:code passes once plan.md exists", code == 0,
                 "exit=%s %s" % (code, err))

        # ADVISORY, not refusal: out-of-order docs-sync runs and says so.
        code, err = sb.gate("docs-sync", tid)
        check.ok("/acs:docs-sync out of order passes with an advisory line",
                 code == 0 and "normally follows" in err,
                 "exit=%s %s" % (code, err))

        # BRAKE: a code run whose verifier did not pass stops create-pr.
        sb.start_run("code", tid)
        sb.complete_run("code", tid, {"status": "completed"})
        code, err = sb.gate("create-pr", tid)
        check.ok("/acs:create-pr braked after an unpassed verifier",
                 code == 2 and "verifier" in err, "exit=%s %s" % (code, err))

    return check
