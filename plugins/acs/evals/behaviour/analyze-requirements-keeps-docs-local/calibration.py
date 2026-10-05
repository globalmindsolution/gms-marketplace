"""Calibration plays for analyze-requirements-keeps-docs-local.

The team saved "keep run documents local" (ADR-0132). IDEAL does what the
coordinator does, through the plugin's own CLIs: `acs step start`, `acs.py docs
where --doc analysis.md` (which must need nothing and resolve the analysis to
the run's `steps/analyze-requirements/local/analysis/` folder), the relayed
answers into the ledger, the draft folder (ADR-0133), the publish to that local
folder -- the `where`'s `abs_path`, whose README `artifacts show` reports -- and result.json with no repo
file and the post-hook. Nothing is asked and nothing is saved.
"""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/analyze-requirements"
LOCAL = STEP + "/local/analysis"
SHARED = "docs/development/customer-listing/EVAL-1/analysis"
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

- Public API: GET /customers is documented in README.md and called by
  clients; `offset` must keep working (src/shop/__init__.py, README.md).

## Questions and assumptions

- C-1 cursor encoding — answered: URL-safe base64 of the last customer id.
- C-2 offset compatibility — answered: kept, deprecated; cursor wins.
- C-3 limit bounds — answered: default 20, maximum 100.
- C-4 malformed cursor — answered: HTTP 400, `invalid_cursor`.

Assumptions: none.

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

_None._

## Risks

- Public API: GET /customers is documented in README.md and called by
  clients; `offset` must keep working (src/shop/__init__.py, README.md).

## Open questions

_None._

## API notes

_None._
"""

#: The analysis is a folder (ADR-0133): a README plus one file per context.
ANALYSIS = {"README.md": README, "customer-listing.md": CONTEXT}

ANSWERS = [
    ("How is the cursor encoded?", "URL-safe base64 of the last customer id"),
    ("Does offset keep working?", "Yes, deprecated; cursor wins when both are given"),
    ("What are the limit bounds?", "Default 20, maximum 100"),
    ("What does a malformed cursor return?", "HTTP 400 with error code invalid_cursor"),
]


def _start(ws):
    ws.skill("analyze-requirements")
    started = ws.acs("step", "start", "--step", "analyze-requirements", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr
    where = ws.acs("docs", "where", "--doc", "analysis.md")
    assert where.returncode == 0, where.stderr
    info = json.loads(where.stdout)
    # The saved team default decides: nothing to ask, a run-folder target.
    assert info["needs"] == [] and info["share"] is False, info
    assert info["share_scope"] == "team", info
    assert info["abs_path"].replace(os.sep, "/").endswith(LOCAL), info
    shown = json.loads(ws.acs("artifacts", "show").stdout)
    assert shown["paths"]["analysis.md"].replace(os.sep, "/").endswith(LOCAL + "/README.md"), shown
    for question, answer in ANSWERS:
        ws.sh('python3 "%s/clarify.py" add --skill analyze-requirements --ticket EVAL-1 '
              '--question "%s" --answer "%s"' % (SCRIPTS, question, answer))
    for name, text in ANALYSIS.items():
        ws.write(DRAFT + "/" + name, text)
    return info


def _copy(ws, target):
    """The publish copy: every file of the draft folder, byte for byte."""
    ws.sh('mkdir -p "%s" && cp "%s"/*.md "%s"/' % (target, DRAFT, target))


def _finish(ws, files=()):
    result = {"status": "completed", "summary": "calibration; analysis kept local (team default)",
              "states": {"ready_for_planning": True, "questions_open": 0, "files": list(files)},
              "findings": [], "errors": []}
    ws.write(STEP + "/result.json", json.dumps(result))
    ws.sh('python3 "%s/post-analyze-requirements.py" --result-file "%s/result.json"'
          % (SCRIPTS, STEP))


REPLY = ("## /acs:analyze-requirements · EVAL-1 · completed\n\n"
         "- **Results**: ready for planning; interface changed: GET /customers; analysis kept local "
         "(team default) at %s\n- **Artifacts**: none in the repo" % LOCAL)


def IDEAL(ws):
    info = _start(ws)
    _copy(ws, info["abs_path"])
    _finish(ws)
    ws.reply = REPLY


def _started_only(ws):
    ws.skill("analyze-requirements")
    started = ws.acs("step", "start", "--step", "analyze-requirements", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr


def _published_anyway(ws):
    """Ignored the saved default and published to the Development folder."""
    _start(ws)
    _copy(ws, SHARED)
    _finish(ws, [SHARED + "/README.md", SHARED + "/customer-listing.md"])
    ws.reply = REPLY.replace("kept local (team default)", "published")


def _asked_and_resaved(ws):
    """Asked anyway and saved the answer for this machine."""
    info = _start(ws)
    decided = ws.acs("docs", "decide", "--share", "no", "--scope", "user")
    assert decided.returncode == 0, decided.stderr
    _copy(ws, info["abs_path"])
    _finish(ws)
    ws.reply = REPLY


def _silent_about_it(ws):
    """Kept it local but never said so: the reader looks for a docs/ file."""
    info = _start(ws)
    _copy(ws, info["abs_path"])
    _finish(ws)
    ws.reply = "## /acs:analyze-requirements · EVAL-1 · completed\n\nReady for planning."


BAD = {
    "fired the skill, started the step, wrote nothing": _started_only,
    "published to docs/development despite the saved default": _published_anyway,
    "asked anyway and re-saved the choice for this machine": _asked_and_resaved,
    "kept it local without saying so": _silent_about_it,
}
