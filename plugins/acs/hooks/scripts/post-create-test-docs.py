#!/usr/bin/env python3
"""Post-hook for /acs:create-test-docs — finalizes the run entry in create-test-docs-state.json and
updates pipeline-state.json, tickets-index.json, and metrics.json.

Result-document `states` this run records for the steps that follow it:
  * cases         int  — total TC-n cases in test-cases.md.
  * e2e_cases     int  — of those, the ones typed e2e. /acs:create-e2e-tests
    refuses when this is zero, and its gate counts the file itself.
  * untraced_acs  list — acceptance criteria no case covers; must be empty for a
    completed run.

Both counts mirror test-cases.md, which is the artifact every later step reads.

Invoked by the skill's coordinator as its mandatory final step:
  python3 post-create-test-docs.py --result-file <result.json>     # or JSON on stdin
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_lib import run_post

if __name__ == "__main__":
    run_post("create-test-docs")
