#!/usr/bin/env python3
"""Post-hook for /acs:create-e2e-tests — finalizes the run entry in create-e2e-tests-state.json and
updates pipeline-state.json, tickets-index.json, and metrics.json.

Result-document `states` this run records for the steps that follow it:
  * suites_written  list — the e2e suite files written under the repo's
    configured e2e location, committed on the ticket branch.
  * cases_covered   list — the TC-n ids from test-cases.md those suites cover.

/acs:run-e2e-tests executes them; it is unhooked and records its own step
through `pipeline-step.py`, not through a post hook.

Invoked by the skill's coordinator as its mandatory final step:
  python3 post-create-e2e-tests.py --result-file <result.json>     # or JSON on stdin
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_lib import run_post

if __name__ == "__main__":
    run_post("create-e2e-tests")
