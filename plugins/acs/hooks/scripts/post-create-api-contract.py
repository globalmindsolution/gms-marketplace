#!/usr/bin/env python3
"""Post-hook for /acs:create-api-contract — finalizes the run entry in create-api-contract-state.json and
updates run.json and tickets-index.json.

Result-document `states` this run records for the steps that follow it:
  * contract_path  str  — where api-contract.md was written.
  * items          int  — endpoints/commands/messages the contract declares.
  * traced_acs     list — the acceptance-criteria ids each item traces to.
  * files          list — repo-relative paths this run wrote and left
    uncommitted in the working tree (ADR-0127); /acs:create-pr commits them.

The repo's machine-readable contract files (when it keeps them) are among
`files`: like the contract, they stay uncommitted until /acs:create-pr.

Invoked by the skill's coordinator as its mandatory final step:
  python3 post-create-api-contract.py --result-file <result.json>     # or JSON on stdin
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_lib import run_post

if __name__ == "__main__":
    run_post("create-api-contract")
