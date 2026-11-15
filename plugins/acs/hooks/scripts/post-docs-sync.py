#!/usr/bin/env python3
"""Post-hook for /acs:docs-sync — finalizes the run entry in docs-sync-state.json and
updates run.json and tickets-index.json.

Invoked by the skill's coordinator as its mandatory final step:
  python3 post-docs-sync.py --result-file <result.json>     # or JSON on stdin

`states.implemented` (ADR-0137) lists the living LLD documents the run moved
from `approved` to `implemented` with `acs.py design status --set implemented`.
It is derived, never asserted: each listed document's own front matter is read
and only one that says `status: implemented` is kept; a path listed but not
flipped is dropped, and the disagreement is recorded on the invocation's
`derived_states` and printed. `states.files` (every doc docs-sync edited or
bumped) is recorded as written.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_lib import run_post

if __name__ == "__main__":
    run_post("docs-sync")
