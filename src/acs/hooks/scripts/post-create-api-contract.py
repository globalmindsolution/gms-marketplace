#!/usr/bin/env python3
"""Post-hook for /acs:create-api-contract — finalizes the run entry in create-api-contract-state.json and
updates pipeline-state.json, tickets-index.json, and metrics.json.

Result-document `states` this run records for the steps that follow it:
  * contract_path  str  — where api-contract.md was written.
  * items          int  — endpoints/commands/messages the contract declares.
  * traced_acs     list — the acceptance-criteria ids each item traces to.

The machine-readable contract files under settings.contracts_path (when the
repo keeps them) are committed on the ticket branch, not recorded here.

Invoked by the skill's coordinator as its mandatory final step:
  python3 post-create-api-contract.py --result-file <result.json>     # or JSON on stdin
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_lib import run_post

if __name__ == "__main__":
    run_post("create-api-contract")
