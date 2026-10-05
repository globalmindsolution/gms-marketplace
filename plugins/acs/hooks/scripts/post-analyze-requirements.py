#!/usr/bin/env python3
"""Post-hook for /acs:analyze-requirements — finalizes the run entry in analyze-requirements-state.json and
updates run.json and tickets-index.json.

Result-document `states` this run records for the steps that follow it:
  * ready_for_planning  bool — the analysis is complete enough to plan from;
    false is the `needs_input` arm, and /acs:create-impl-plan is what consumes it.
  * questions_open      int  — clarifications still unanswered in the ledger.
  * files               list — the ticket docs folder's paths the publish wrote
    and left uncommitted (ADR-0127); /acs:create-pr commits them.

`api_surface` is no longer recorded (ADR-0134): an interface change is
designed with /acs:create-api-contract, a Design skill no step decision reads
it for. The fragment still declares it, deprecated, so older state validates.

The needs_design recommendation the analysis may carry is applied through its
own CLI (`acs.py ticket save`), so it is a finding here, not a state.

Invoked by the skill's coordinator as its mandatory final step:
  python3 post-analyze-requirements.py --result-file <result.json>     # or JSON on stdin
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_lib import run_post

if __name__ == "__main__":
    run_post("analyze-requirements")
