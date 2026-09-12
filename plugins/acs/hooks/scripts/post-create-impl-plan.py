#!/usr/bin/env python3
"""Post-hook for /acs:create-impl-plan — finalizes the run entry in create-impl-plan-state.json and
updates pipeline-state.json, tickets-index.json, and metrics.json.

Result-document `states` this run records for the steps that follow it:
  * plan_path      str  — where plan.md was written (the ticket docs folder, or
    the partition when artifacts.tickets_path is null). The /acs:code gate
    resolves the file itself; this records which path the run chose.
  * plan_approved  bool — whether plan approval ran and passed (STANDARD/COMPLEX
    lanes only; TRIVIAL/SMALL plans are coordinator-authored and unapproved).
  * file_map       obj  — the declared executor file map (`acs.py filemap set`),
    recorded so a later run can see what scope the plan claimed.

/acs:code REQUIRES the plan artifact, not these keys: a plan written by hand
still opens its gate.

Invoked by the skill's coordinator as its mandatory final step:
  python3 post-create-impl-plan.py --result-file <result.json>     # or JSON on stdin
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_lib import run_post

if __name__ == "__main__":
    run_post("create-impl-plan")
