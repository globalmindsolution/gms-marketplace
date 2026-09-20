"""s05 — SessionEnd safety net (free).

When a session ends mid-skill, the installed SessionEnd hook must finalize the
in-flight step as `interrupted` with `stop_reason: session_end` and release
the run lock — otherwise the
next session is blocked by a stale lock and state lies about what happened.
Seeds an in-progress run via the installed helper CLIs, fires the installed
session-end hook, and asserts the transition against the shipped build
(`tests/` covers the same logic on the source tree).
"""

import os

from harness import Sandbox, Check

META = {
    "name": "session_end_safety_net",
    "tier": "free",
    "goal": "cleanup",
    "summary": "SessionEnd finalizes an interrupted run and releases the lock",
}


def run():
    check = Check(META["name"])
    with Sandbox(prefix="EVAL", slug="shop", init=True) as sb:
        tid = sb.mint_ticket("Add a /health endpoint returning ok", "task",
                             needs_design=False)
        sb.start_run("code", tid)  # in_progress + lock + session pointer

        check.eq("seed: code is in_progress",
                 sb.last_status(tid, "code"), "in_progress")
        check.ok("seed: run lock held", os.path.exists(sb.lock_path(tid)))

        rc, err = sb.session_end()
        check.eq("session-end exits 0", rc, 0)

        check.eq("step finalized as interrupted",
                 sb.last_status(tid, "code"), "interrupted")
        check.eq("and the stop reason says why",
                 (sb.step_json(tid, "code")["invocations"][-1]
                  .get("stop_reason")), "session_end")
        check.ok("lock released", not os.path.exists(sb.lock_path(tid)), err)

    return check
