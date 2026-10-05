"""Calibration plays for analyze-requirements-cursor-pagination.

IDEAL does what /acs:analyze-requirements' coordinator does, through the
plugin's own writers where they exist: `acs step start`, `clarify.py add` for
each answer the prompt relayed, the draft FOLDER in the step directory (a
README plus one file per bounded context -- ADR-0133; here one context,
customer-listing.md, as the prompt names it), the Publish copy into
docs/development/customer-listing/EVAL-1/analysis/ left uncommitted on main (no
branch, no commit -- ADR-0127), then result.json with `files` and the
post-hook. The analyst's and impact reviewer's own phase files are workspace
detail no grader reads, so only the draft is played.
"""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
STEP = ".git/acs/state-machine/example-shop/runs/EVAL-1/steps/analyze-requirements"
BRANCH = "story/EVAL-1-cursor-pagination-for-get-customers"
PUBLISHED = "docs/development/customer-listing/EVAL-1/analysis"
DRAFT = STEP + "/iter-1/analysis"

README = """---
ticket: EVAL-1
ready_for_planning: true
needs_design_recommendation: false
---

# Analysis — EVAL-1: Cursor pagination for GET /customers

## Scope and summary

Offset paging on GET /customers skips or repeats customers when rows are
inserted between page requests. Clients need an opaque cursor that walks every
customer exactly once, while existing offset clients keep working.

## Contexts

| Context | File | Purpose |
|---|---|---|
| Customer listing | [customer-listing.md](customer-listing.md) | how a client pages through customers |

## Refined acceptance criteria

The three criteria on the ticket are confirmed as written.

## Cross-cutting risks and decisions

- Interface change: GET /customers, a documented public endpoint, gains `cursor`,
  `next_cursor` and `invalid_cursor` -- design it with /acs:create-api-contract.

## Questions and assumptions

- C-1 cursor encoding — answered: URL-safe base64 of the last customer id.
- C-2 offset compatibility — answered: kept, deprecated; cursor wins.
- C-3 limit bounds — answered: default 20, maximum 100.
- C-4 malformed cursor — answered: HTTP 400, `invalid_cursor`.

No assumptions.

## Verdict

Ready for planning; no design needed.
"""

CONTEXT = """---
context: customer-listing
---

# Customer listing

## Impact map

| Path | Component | Change | Evidence |
|---|---|---|---|
| src/shop/__init__.py | shop | `list_customers` gains `cursor`, returns `next_cursor` | src/shop/__init__.py:8 |
| tests/test_customers.py | tests | new unit tests for cursor paging | tests/ holds only test_health.py |
| README.md | docs | API section documents `cursor` and `next_cursor` | README.md:7 |

## Rules and edge cases

- `cursor` wins when both `cursor` and `offset` are given.

## Risks

- Public API: GET /customers is documented in README.md and called by
  clients; `offset` must keep working (src/shop/__init__.py, README.md).

## Open questions

_None._

## API notes

- GET /customers gains `cursor`; responses carry `next_cursor`; a malformed
  cursor is HTTP 400 `invalid_cursor`.
"""

ANALYSIS = {"README.md": README, "customer-listing.md": CONTEXT}


def _draft_and_publish(ws, files, target=PUBLISHED):
    """The draft folder, then the publish copy: every file, byte for byte."""
    for name, text in files.items():
        ws.write(DRAFT + "/" + name, text)
    ws.sh('mkdir -p "%s" && cp "%s"/*.md "%s"/' % (target, DRAFT, target))


ANSWERS = [
    ("How is the cursor encoded?", "URL-safe base64 of the last customer id"),
    ("Does offset keep working?", "Yes, deprecated; cursor wins when both are given"),
    ("What are the limit bounds?", "Default 20, maximum 100"),
    ("What does a malformed cursor return?", "HTTP 400 with error code invalid_cursor"),
]


def _written(ws):
    """What the run records in `states.files`: the repo paths it wrote and
    left uncommitted for /acs:create-pr (ADR-0127)."""
    return [p for p in ws.created() if not p.startswith(".acs/")]


def _start(ws):
    ws.skill("analyze-requirements")
    started = ws.acs("step", "start", "--step", "analyze-requirements", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr
    # The graders' path is the one the plugin itself resolves for this run.
    shown = ws.acs("artifacts", "show")
    assert shown.returncode == 0, shown.stderr
    target = json.loads(shown.stdout)["paths"]["analysis.md"]
    assert target.replace(os.sep, "/").endswith(PUBLISHED + "/README.md"), target


def _finish(ws, status="completed"):
    result = {"status": status, "summary": "calibration",
              "states": {"ready_for_planning": status == "completed",
                         "questions_open": 0},
              "findings": [], "errors": []}
    result["states"]["files"] = _written(ws)
    ws.write(STEP + "/result.json", json.dumps(result))
    ws.sh('python3 "%s/post-analyze-requirements.py" --result-file "%s/result.json"'
          % (SCRIPTS, STEP))


def IDEAL(ws):
    _start(ws)
    for question, answer in ANSWERS:
        ws.sh('python3 "%s/clarify.py" add --skill analyze-requirements --ticket EVAL-1 '
              '--question "%s" --answer "%s"' % (SCRIPTS, question, answer))
    _draft_and_publish(ws, ANALYSIS)
    _finish(ws)


def _started_only(ws):
    _start(ws)


def _prose_on_main(ws):
    """Wrote an analysis by hand and committed it: no front matter, no impact
    map from the code, and the step never finished."""
    _start(ws)
    ws.write(PUBLISHED + "/README.md", "# Analysis of EVAL-1\n\nAdd a cursor to GET /customers. "
                                     "Low risk; no API change.\n")
    ws.sh("git add docs && git commit -qm 'analysis'")


def _no_interface_named(ws):
    """Ran the whole flow but named no interface change, so nothing points
    the change to /acs:create-api-contract."""
    _start(ws)
    _draft_and_publish(ws, dict(ANALYSIS, **{
        "README.md": README.replace(
            "- Interface change: GET /customers, a documented public endpoint, gains `cursor`,\n"
            "  `next_cursor` and `invalid_cursor` -- design it with /acs:create-api-contract.",
            "- No interface changes.")}))
    _finish(ws)


def _wrote_the_retired_flag(ws):
    """Wrote the `api_surface` front-matter key ADR-0134 retired."""
    _start(ws)
    _draft_and_publish(ws, dict(ANALYSIS, **{
        "README.md": README.replace("ready_for_planning: true\n",
                                    "ready_for_planning: true\napi_surface: true\n")}))
    _finish(ws)


BAD = {
    "fired the skill, started the step, wrote nothing": _started_only,
    "hand-wrote a prose analysis on main": _prose_on_main,
    "named no interface change": _no_interface_named,
    "wrote the retired api_surface key": _wrote_the_retired_flag,
}


def _committed_on_a_ticket_branch(ws):
    """The pre-ADR-0127 publish: everything right, then a ticket branch and a
    commit -- only /acs:create-pr branches and commits now."""
    IDEAL(ws)
    ws.sh('git checkout -q -b "%s" && git add docs && git commit -qm "EVAL-1 Analyze"' % BRANCH)


BAD["committed the analysis on a new ticket branch"] = _committed_on_a_ticket_branch


def _published_to_the_legacy_folder(ws):
    """The pre-ADR-0128 target: everything right, but published to the
    retired ticket docs tree."""
    _start(ws)
    _draft_and_publish(ws, ANALYSIS, "docs/tickets/EVAL-1/analysis")
    _finish(ws)


BAD["published to the legacy docs/tickets folder"] = _published_to_the_legacy_folder


def _one_long_file(ws):
    """The pre-ADR-0133 shape: one analysis.md with every section, no
    folder, no README, no context file."""
    _start(ws)
    ws.write(STEP + "/analysis.md", README + CONTEXT.split("---\n", 2)[2])
    ws.sh('mkdir -p docs/development/customer-listing/EVAL-1 && cp "%s/analysis.md" '
          'docs/development/customer-listing/EVAL-1/analysis.md' % STEP)
    _finish(ws)


BAD["published one long analysis.md instead of a folder"] = _one_long_file


def _context_left_out_of_the_table(ws):
    """A folder whose README does not link its context file."""
    _start(ws)
    _draft_and_publish(ws, dict(ANALYSIS, **{
        "README.md": README.replace("[customer-listing.md](customer-listing.md)",
                                    "customer listing")}))
    _finish(ws)


BAD["README's contexts table does not link the context file"] = _context_left_out_of_the_table
