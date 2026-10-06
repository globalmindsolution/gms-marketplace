"""Calibration plays for create-api-contract-cursor-pagination (see
tests/evals/check_grader_calibration.py).

IDEAL does what /acs:create-api-contract's coordinator and its subagents do as
a Design skill (ADR-0134), through the plugin's own writers where they exist:
`acs step start` (no plan, none needed), the `clarify.py add` answers the
prompt relayed, the survey notes, ONE gap analyst for the feature's existing
interface document (no gap: it matches src/shop/__init__.py), ONE un-sliced
writer revising api/customers.md in place and bumping it through `acs.py
design bump`, the derived preamble joined with the writer's fragment by
`acs.py notes merge --no-markers`, the $0 checks, the three reviewer slices,
the Publish copy of the run record, then result.json with outcome
contract_written and every written path in states.files, and the real
post-hook. Nothing is committed and no machine-readable file is written.
"""

import json
import os
import subprocess
import sys

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-api-contract"
L = "docs/architecture/lld/customer-listing"
DOC = L + "/api/customers.md"
README = L + "/README.md"
RECORD = L + "/EVAL-1/api-contract.md"

BODY = """# Customers API -- REST

## Scope

The shop service's customer listing, consumed by the admin UI and partner
clients (hld/integration-map.md), following hld/cross-cutting.md's API
conventions. Implemented by `list_customers` in src/shop/__init__.py:8.

## Surface

### GET /customers

- **Kind and status**: endpoint, CHANGED.
- **Request**: `cursor` (optional opaque string, NEW (planned)); `limit`
  (optional integer 1-100, default 20); `offset` (optional integer >= 0,
  default 0; deprecated, ignored when `cursor` is given). Today:
  `list_customers(offset=0, limit=PAGE_SIZE)` (src/shop/__init__.py:8).
- **Response**: 200 `{"items": [...], "limit": 20, "next_cursor": "Y3VzdC0yMA"}`;
  `next_cursor` (NEW (planned)) is `null` on the last page.
- **Errors**: 400 `{"error": "invalid_cursor"}` when `cursor` is not one this
  API issued.
- **Traces**: AC-1, AC-2, AC-3.

## Error model

| Code | HTTP | When | New or existing |
|---|---|---|---|
| `invalid_cursor` | 400 | `cursor` is not a cursor this API issued | new |

## Compatibility & versioning

Backward compatible, in place (C-1): `offset` clients keep working,
deprecated (C-2); `cursor` wins when both are given.

## Examples

`GET /customers?cursor=Y3VzdC0yMA&limit=20` -> 200 with the next page.
`GET /customers?cursor=%%%` -> 400 `{"error": "invalid_cursor"}`.

## Traceability

| Item | Criterion |
|---|---|
| GET /customers `cursor` | AC-1 |
| GET /customers `next_cursor` | AC-2 |
| `invalid_cursor` | AC-3 |
"""

FRAGMENT = """## Scope & sources

GET /customers gains a cursor (EVAL-1). Sources: requirements.md,
docs/development/customer-listing/EVAL-1/analysis/README.md, src/shop/__init__.py.

## Interfaces

| Document | Version | Status | Items |
|---|---|---|---|
| docs/architecture/lld/customer-listing/api/customers.md | 2 | proposed | GET /customers CHANGED |

## Compatibility & versioning

Backward compatible, in place (C-1, C-2).

## Traceability

| Item | Criterion |
|---|---|
| GET /customers `cursor` | AC-1 |
| GET /customers `next_cursor` | AC-2 |
| `invalid_cursor` | AC-3 |

## Gaps

None: api/customers.md matched the code (iter-1/gaps.md).
"""

PREAMBLE = ('---\nticket: EVAL-1\nitems: 1\n'
            'interfaces: ["docs/architecture/lld/customer-listing/api/customers.md"]\n---\n\n'
            "# API contract — EVAL-1: Cursor pagination for GET /customers\n")

ANSWERS = [
    ("Is the change versioned or in place?", "Backward compatible and in place; no new version"),
    ("What happens to offset?", "Kept, deprecated; cursor wins when both are given"),
    ("What is a malformed cursor?", "HTTP 400 with error code invalid_cursor"),
]

SLICES = ("surface", "trace", "form")


def _start(ws):
    ws.skill("create-api-contract")
    started = ws.acs("step", "start", "--step", "create-api-contract", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr
    ws.sh("git status --porcelain > %s/baseline-status.txt" % STEP)
    for question, answer in ANSWERS:
        ws.sh('python3 "%s/clarify.py" add --skill create-api-contract --ticket EVAL-1 '
              '--question "%s" --answer "%s"' % (SCRIPTS, question, answer))
    ws.write(STEP + "/iter-1/authoring.md",
             "## Interface inventory\n\ncustomers: CHANGED, api/customers.md, "
             "src/shop/__init__.py:8, hld/integration-map.md row 1.\n\n"
             "## Item list\n\nGET /customers CHANGED: cursor, next_cursor, invalid_cursor "
             "(AC-1..AC-3).\n")
    ws.write(STEP + "/iter-1/gaps-customers.md",
             "## Unimplemented\n\n_None._\n\n## Undocumented\n\n_None._\n\n"
             "## Drifted\n\n_None._\n\n## Unverified\n\n_None._\n")
    merged = ws.acs("notes", "merge", "--out", STEP + "/iter-1/gaps.md",
                    STEP + "/iter-1/gaps-customers.md")
    assert merged.returncode == 0, merged.stderr


def _revise(ws, body=BODY, bump=True):
    with open(os.path.join(ws.path, DOC), encoding="utf-8") as fh:
        front = fh.read().split("\n---\n", 1)[0] + "\n---\n\n"
    ws.write(DOC, front + body)
    if bump:
        done = ws.acs("design", "bump", "--ticket", "EVAL-1", DOC)
        assert done.returncode == 0, done.stderr
    ws.write(README, "| EVAL-1 | GET /customers gains a cursor |\n", append=True)


def _draft(ws, fragment=FRAGMENT):
    ws.write(STEP + "/iter-1/authoring-write.md", "## Gaps handled\n\nnone\n")
    ws.write(STEP + "/iter-1/contract-author-write.json", json.dumps(
        {"files": [DOC, README], "interfaces": [DOC], "items": 1,
         "traced_acs": ["AC-1", "AC-2", "AC-3"], "breaking": False, "seams": [],
         "problems": [], "clarifications_used": ["C-1", "C-2", "C-3"]}))
    ws.write(STEP + "/api-contract-write.md", fragment)
    ws.write(STEP + "/api-contract-preamble.md", PREAMBLE)
    joined = ws.acs("notes", "merge", "--no-markers", "--out", STEP + "/api-contract.md",
                    STEP + "/api-contract-preamble.md", STEP + "/api-contract-write.md")
    assert joined.returncode == 0, joined.stderr


def _review(ws):
    ws.sh('python3 "%s/acs.py" design check %s' % (SCRIPTS, DOC))
    ws.sh('python3 "%s/structure_lint.py" --sections "Scope; Surface; Error model; '
          'Compatibility & versioning; Examples; Traceability" --ordered %s' % (SCRIPTS, DOC))
    ws.sh('python3 "%s/front_matter_check.py" --require "ticket: str; items: int; '
          'interfaces: list" --ticket EVAL-1 %s/api-contract.md' % (SCRIPTS, STEP))
    for slice_id in SLICES:
        ws.write("%s/iter-1/contract-reviewer-%s.md" % (STEP, slice_id),
                 "## Checks\n\nran\n\n## Findings\n\nnone (slice %s)\n" % slice_id)
    merged = ws.acs("notes", "merge", "--out", STEP + "/iter-1/contract-reviewer.md",
                    *["%s/iter-1/contract-reviewer-%s.md" % (STEP, s) for s in SLICES])
    assert merged.returncode == 0, merged.stderr


def _publish(ws):
    ws.sh('mkdir -p "%s" && cp "%s/api-contract.md" "%s"'
          % (os.path.dirname(RECORD), STEP, RECORD))


def _finish(ws, outcome="contract_written", files=None):
    states = {"contract_path": RECORD, "feature": ["customer-listing"],
              "files": [README, DOC, RECORD] if files is None else files,
              "types": ["api-contract"], "interfaces": [DOC], "items": 1,
              "traced_acs": ["AC-1", "AC-2", "AC-3"],
              "gaps": {"undocumented": 0, "unimplemented": 0, "drifted": 0}}
    if outcome == "type_disabled":
        states = {"feature": [], "files": [], "types": [], "interfaces": [], "items": 0,
                  "traced_acs": [], "gaps": {"undocumented": 0, "unimplemented": 0, "drifted": 0}}
    result = {"status": "completed", "outcome": outcome, "summary": "calibration",
              "states": states, "findings": [], "errors": []}
    ws.write(STEP + "/result.json", json.dumps(result, indent=2))
    done = subprocess.run([sys.executable, os.path.join(SCRIPTS, "post-create-api-contract.py"),
                           "--result-file", STEP + "/result.json"],
                          cwd=ws.path, env=ws.env, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


REPLY = ("## /acs:create-api-contract · EVAL-1 · completed\n\n- **Results**: "
         "docs/architecture/lld/customer-listing/api/customers.md revised -- GET /customers "
         "gains an opaque `cursor` and `next_cursor`, `invalid_cursor` is a 400 -- proposed v2; "
         "backward compatible, offset kept (deprecated); run record shared to "
         "docs/architecture/lld/customer-listing/EVAL-1/api-contract.md; documents only, no "
         "OpenAPI or code; left uncommitted.\n- **Next**: /acs:create-impl-plan EVAL-1")


def IDEAL(ws):
    _start(ws)
    _revise(ws)
    _draft(ws)
    _review(ws)
    _publish(ws)
    _finish(ws)
    ws.reply = REPLY


def _wrote_an_openapi_document(ws):
    """Designed it, then also wrote the machine-readable contract -- /acs:code's
    job, from a plan item, and one the repo does not keep."""
    IDEAL(ws)
    ws.write("docs/api/openapi.yaml", "openapi: 3.0.0\npaths:\n  /customers: {}\n")


def _implemented_the_cursor(ws):
    """Specified the change, then built it."""
    IDEAL(ws)
    ws.write("src/shop/__init__.py",
             "PAGE_SIZE = 20\n\n\ndef health():\n    return \"ok\"\n\n\n"
             "def list_customers(offset=0, limit=PAGE_SIZE, cursor=None):\n"
             "    return {\"items\": [], \"limit\": limit, \"next_cursor\": None}\n")


def _a_second_document(ws):
    """Left the existing interface document alone and wrote a new one beside it."""
    _start(ws)
    ws.write(L + "/api/customers-cursor.md", BODY)
    init = ws.acs("design", "init", "--status", "proposed", "--ticket", "EVAL-1",
                  "--feature", "customer-listing", L + "/api/customers-cursor.md")
    assert init.returncode == 0, init.stderr
    _draft(ws)
    _review(ws)
    _publish(ws)
    _finish(ws, files=[L + "/api/customers-cursor.md", RECORD])


def _no_version_bump(ws):
    """Rewrote the body under the old `implemented` v1 block."""
    _start(ws)
    _revise(ws, bump=False)
    _draft(ws)
    _review(ws)
    _publish(ws)
    _finish(ws)


def _never_published_the_record(ws):
    _start(ws)
    _revise(ws)
    _draft(ws)
    _review(ws)
    _finish(ws, files=[README, DOC])


def _settled_type_disabled(ws):
    """Recorded the type as disabled although the default enables it."""
    _start(ws)
    _finish(ws, outcome="type_disabled")


def _never_finished(ws):
    _start(ws)
    _revise(ws)
    _draft(ws)
    _publish(ws)


def _committed_on_a_branch(ws):
    """Everything right, then a branch and a commit -- only /acs:create-pr
    branches and commits."""
    IDEAL(ws)
    ws.sh('git checkout -q -b story/EVAL-1-x && git add -A && git commit -qm "EVAL-1 design"')


BAD = {
    "fired the skill and did nothing": lambda ws: ws.skill("create-api-contract"),
    "wrote an OpenAPI document": _wrote_an_openapi_document,
    "implemented the cursor in code": _implemented_the_cursor,
    "wrote a second interface document instead of revising": _a_second_document,
    "rewrote the document without a version bump": _no_version_bump,
    "never published the run record": _never_published_the_record,
    "settled type_disabled although enabled": _settled_type_disabled,
    "never ran the post-hook": _never_finished,
    "committed on a new branch": _committed_on_a_branch,
}
