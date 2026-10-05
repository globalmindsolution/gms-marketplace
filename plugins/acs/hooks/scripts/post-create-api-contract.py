#!/usr/bin/env python3
"""Post-hook for /acs:create-api-contract — finalizes the run entry in create-api-contract-state.json and
updates run.json and tickets-index.json.

A Design skill (ADR-0134): it documents interfaces and writes nothing else --
the repo's machine-readable contract files (OpenAPI, JSON Schema, proto,
AsyncAPI) are created by /acs:code from the approved contract, as plan items.

`outcome` is `contract_written`, or `type_disabled` when the `api-contract`
LLD type is off in `design.lld_types` (completed, nothing written).

Result-document `states` this run records:
  * contract_path  str  — where the run record api-contract.md went:
    repo-relative under `<architecture_dir>/lld/<feature>/<key>/` when the
    run's documents are shared, the run partition's path when kept local
    (ADR-0132).
  * feature        list — the feature slugs designed.
  * files          list — EVERY repo-relative path this run wrote and left
    uncommitted in the working tree (ADR-0127): the living api docs, the lld
    READMEs and the shared run record. /acs:create-pr commits them in its
    `design` layer.
  * types          list — the owned LLD types written: `["api-contract"]` or `[]`.
  * interfaces     list — the living `lld/<feature>/api/<interface>.md` docs
    written or bumped, one per interface, repo-relative.
  * items          int  — operations, commands or messages specified across them.
  * traced_acs     list — the acceptance-criteria ids the items trace to.
  * gaps           dict — {unimplemented, undocumented, drifted} counts from
    the gap analyst (ADR-0122).

Invoked by the skill's coordinator as its mandatory final step:
  python3 post-create-api-contract.py --result-file <result.json>     # or JSON on stdin
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_lib import run_post

if __name__ == "__main__":
    run_post("create-api-contract")
