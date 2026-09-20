#!/usr/bin/env python3
"""Post-hook for /acs:run-e2e-tests — finalizes the invocation and transitions the step.

  python3 post-run-e2e-tests.py --result-file <result.json>     # or JSON on stdin
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_lib import run_post

if __name__ == "__main__":
    run_post("run-e2e-tests")
