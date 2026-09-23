#!/usr/bin/env python3
"""Post-hook for /acs:create-docs — finalizes the run entry in create-docs-state.json and
updates run.json and tickets-index.json for ONE doc set's
delivery ticket.

Invoked by the skill's coordinator as its mandatory final step, once per doc set:
  python3 post-create-docs.py --ticket <id> --result-file <result.json>     # or JSON on stdin
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_lib import run_post

if __name__ == "__main__":
    run_post("create-docs")
