#!/usr/bin/env python3
"""Post-hook for /acs:analyze-ticket — finalizes the run entry in analyze-ticket-state.json and
updates pipeline-state.json, tickets-index.json, and metrics.json.

Result-document `states` this run records for the steps that follow it:
  * ready_for_planning  bool — the analysis is complete enough to plan from;
    false is the `needs_input` arm, and /acs:create-impl-plan is what consumes it.
  * api_surface         bool — the change adds or alters an API surface. Mirrors
    analysis.md's front matter, which is what ship.yaml's `api_surface_changed`
    predicate and the /acs:create-api-contract gate actually read.
  * questions_open      int  — clarifications still unanswered in the ledger.

The two recommendations the analysis may carry (stakes, needs_design) are
applied through their own CLIs (`acs.py stakes recommend` / `acs.py lane
apply`), so they are findings here, not states.

Invoked by the skill's coordinator as its mandatory final step:
  python3 post-analyze-ticket.py --result-file <result.json>     # or JSON on stdin
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_lib import run_post

if __name__ == "__main__":
    run_post("analyze-ticket")
