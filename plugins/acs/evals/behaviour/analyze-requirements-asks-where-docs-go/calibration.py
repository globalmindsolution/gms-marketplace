"""Calibration plays for analyze-requirements-asks-where-docs-go.

IDEAL does what /acs:analyze-requirements' coordinator does on the first run
in a repo with no saved document choice (ADR-0132), through the plugin's own
CLIs: `acs step start`, `acs.py docs where --doc analysis.md` (which must
report both questions open, proposing the built-in default folder),
`clarify.py add` for every relayed answer, `acs.py docs decide` with the
team's answers, then the draft folder, the publish into the folder `decide` resolved,
and result.json with `files` and the post-hook. The real `where`/`decide`
calls are the point: a change to their keys or to what `decide` writes fails
here, for free.
"""

import json
import os

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
STEP = ".git/acs/state-machine/example-shop/runs/EVAL-1/steps/analyze-requirements"
PUBLISHED = "docs/changes/customer-listing/EVAL-1/analysis"
DEFAULT = "docs/development/customer-listing/EVAL-1/analysis"
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

DOC_ANSWERS = [
    ("Share run documents in the repo, or keep them local?", "Shared in the repo"),
    ("Save that for you or for the team?", "For the team (.acs/settings.json)"),
    ("Where do the Development documents go?", "docs/changes"),
]


def _written(ws):
    """What the run records in `states.files`: the repo documents it wrote and
    left uncommitted for /acs:create-pr (ADR-0127) -- not the settings."""
    return [p for p in ws.created() if p.startswith("docs/")]


def _start(ws):
    ws.skill("analyze-requirements")
    started = ws.acs("step", "start", "--step", "analyze-requirements", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr
    where = ws.acs("docs", "where", "--doc", "analysis.md")
    assert where.returncode == 0, where.stderr
    info = json.loads(where.stdout)
    # Nothing saved and no folder: both questions are open, nothing is a target yet.
    assert sorted(info["needs"]) == ["location", "share"], info
    assert info["location_source"] == "default", info
    assert info["proposed_path"] == "docs/development", info
    assert info["path"] is None, info


def _record_answers(ws):
    for question, answer in ANSWERS + DOC_ANSWERS:
        ws.sh('python3 "%s/clarify.py" add --skill analyze-requirements --ticket EVAL-1 '
              '--question "%s" --answer "%s"' % (SCRIPTS, question, answer))


def _decide(ws, *args):
    decided = ws.acs("docs", "decide", *(list(args) + ["--doc", "analysis.md"]))
    assert decided.returncode == 0, decided.stderr
    return json.loads(decided.stdout)


def _publish(ws, target):
    """The draft folder, then the publish copy of every file (ADR-0133)."""
    for name, text in ANALYSIS.items():
        ws.write(DRAFT + "/" + name, text)
    ws.sh('mkdir -p "%s" && cp "%s"/*.md "%s"/' % (target, DRAFT, target))


def _finish(ws):
    result = {"status": "completed", "summary": "calibration",
              "states": {"ready_for_planning": True, "questions_open": 0, "files": _written(ws)},
              "findings": [], "errors": []}
    ws.write(STEP + "/result.json", json.dumps(result))
    ws.sh('python3 "%s/post-analyze-requirements.py" --result-file "%s/result.json"'
          % (SCRIPTS, STEP))


def IDEAL(ws):
    _start(ws)
    _record_answers(ws)
    info = _decide(ws, "--share", "yes", "--scope", "team", "--location", "development=docs/changes")
    assert info["needs"] == [] and info["share"] is True, info
    assert info["path"] == PUBLISHED, info
    shown = json.loads(ws.acs("artifacts", "show").stdout)
    assert shown["paths"]["analysis.md"].replace(os.sep, "/").endswith(
        PUBLISHED + "/README.md"), shown
    _publish(ws, PUBLISHED)
    _finish(ws)
    ws.reply = ("## /acs:analyze-requirements · EVAL-1 · completed\n\n"
                "- **Results**: ready for planning; analysis shared to %s (team default, "
                "saved now with the folder docs/changes)" % PUBLISHED)


def _started_only(ws):
    _start(ws)


def _published_to_the_default(ws):
    """Never asked: wrote into the built-in default folder acs only proposed."""
    _start(ws)
    _record_answers(ws)
    _publish(ws, DEFAULT)
    _finish(ws)


def _saved_for_this_machine(ws):
    """Saved the share choice in the user scope the user did not ask for."""
    _start(ws)
    _record_answers(ws)
    _decide(ws, "--share", "yes", "--scope", "user", "--location", "development=docs/changes")
    _publish(ws, PUBLISHED)
    _finish(ws)


def _hand_written_settings(ws):
    """Hand-wrote the settings file instead of `docs decide`, losing a key."""
    _start(ws)
    _record_answers(ws)
    ws.write(".acs/settings.json", json.dumps(
        {"docs": {"share_run_documents": True, "development_dir": "docs/changes"}}, indent=2))
    _publish(ws, PUBLISHED)
    _finish(ws)


def _kept_local_despite_the_answer(ws):
    """Saved "keep local" although the user said share: nothing in the repo."""
    _start(ws)
    _record_answers(ws)
    info = _decide(ws, "--share", "no", "--scope", "team")
    _publish(ws, info["abs_path"])
    _finish(ws)


BAD = {
    "fired the skill, started the step, wrote nothing": _started_only,
    "published to the built-in default folder without asking": _published_to_the_default,
    "saved the share choice for this machine only": _saved_for_this_machine,
    "hand-wrote the settings and lost the ticket prefix": _hand_written_settings,
    "kept the analysis local despite the answer": _kept_local_despite_the_answer,
}
