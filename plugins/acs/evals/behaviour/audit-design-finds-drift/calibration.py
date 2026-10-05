"""Calibration plays for audit-design-finds-drift (see
tests/evals/check_grader_calibration.py). The ideal run: `acs step start`
on the run the scaffold opened, `acs design check` over every in-scope
document, one gap analyst (slice `repo`) writing its gap notes, the join
through `acs notes merge`, report.md written from the built-in template, and
the result document through the real post-hook, which checks the report
against the template and derives the counts from it -- no document, code file
or ticket touched."""

import json
import os
import re
import subprocess
import sys

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST = os.path.join(PLUGIN, "hooks", "scripts", "post-audit-design.py")
NEW_TICKET = os.path.join(PLUGIN, "hooks", "scripts", "new-ticket.py")
TEMPLATE = os.path.join(PLUGIN, "templates", "audit-design-report.md")
STEP = (".git/acs/state-machine/example-shop/runs/audit-the-design-against-the-code-9784"
        "/steps/audit-design")
A = "docs/architecture"
DOCS = ["%s/hld/tech-stack.md" % A, "%s/hld/c4-container.md" % A,
        "%s/hld/integration-map.md" % A, "%s/lld/customer-listing/api/customers.md" % A]

UNIMPLEMENTED = ("- **notifier container** -- hld/c4-container.md `Container(notifier, ...)` "
                 "(status implemented) and hld/integration-map.md `shop -->|POST "
                 "/notifications sync| notifier` (status implemented); code: absent -- "
                 "`git log` shows src/notifier deleted in a10cef7, Grep `notify|notifications` "
                 "in src/ finds nothing. A regression: the documents say it is built.\n")
UNDOCUMENTED = ("- **orders API** -- `GET /orders?customer_id=&offset=&limit=`, "
                "src/shop/orders.py:4 `list_orders`; documents: absent from "
                "hld/c4-container.md and hld/integration-map.md.\n")
DRIFTED = ("- **customer page size** -- lld/customer-listing/api/customers.md `## GET "
           "/customers` (status implemented): `limit` defaults to 50; code: "
           "src/shop/__init__.py:1 `PAGE_SIZE = 20` (README says 20 too).\n")
NONE = "_None._\n"

#: The report's entries: one `### ` heading per gap, the fields the template asks for.
R_NOTIFIER = """### notifier container and POST /notifications
- **Design**: `hld/c4-container.md` § C4 container and `hld/integration-map.md` § Integration
  map, status implemented v1
- **Code**: absent -- src/notifier was deleted by the latest commit; Grep
  `notify|notifications` in src/ finds nothing. A regression: the documents say it is built.
- **Handling**: the design (/acs:create-architecture) if the removal was intended, else the code
"""
R_ORDERS = """### orders API -- GET /orders?customer_id=
- **Design**: absent from `hld/c4-container.md` and `hld/integration-map.md` (implemented v1)
- **Code**: `src/shop/orders.py:4` `list_orders`
- **Handling**: the design (/acs:create-architecture)
"""
R_PAGE_SIZE = """### customer page size
- **Design**: `lld/customer-listing/api/customers.md` § GET /customers, status implemented
  v1: `limit` defaults to 50
- **Code**: `src/shop/__init__.py:1` `PAGE_SIZE = 20` (the README says 20 too)
- **Handling**: a person decides which reading is right; then the design or the code
"""
R_SCOPE = """Documents (from `acs.py design check`): hld/tech-stack.md, hld/c4-container.md,
hld/integration-map.md and lld/customer-listing/api/customers.md -- each status implemented,
version 1. Code area: the repository, one gap-analyst slice (`repo`).
"""
R_SUMMARY = """| Kind | Count |
|---|---|
| Unimplemented | 1 |
| Planned | 0 |
| Undocumented | 1 |
| Drifted | 1 |
| Unversioned | 0 |

The notifier is a regression: documents marked implemented describe a container the code no
longer has.
"""


def report(bodies, scope="all", drop=()):
    """The built-in template, filled: its authoring comments out, its count
    markers kept, each section's body from `bodies` (`_None._` when empty)."""
    with open(TEMPLATE, encoding="utf-8") as fh:
        text = re.sub(r"<!--(?!\s*acs:count)[\s\S]*?-->\n?", "", fh.read())
    head, *sections = re.split(r"(?m)^(?=## )", text)
    out = [head.strip().replace("<scope>", scope) + "\n"]
    for section in sections:
        lines = section.strip().splitlines()
        title = lines[0][3:].strip()
        if title in drop:
            continue
        marker = [line for line in lines[1:] if "acs:count" in line]
        out.append("\n".join([lines[0]] + marker) + "\n\n"
                   + (bodies.get(title) or "_None._").strip() + "\n")
    return "\n".join(out)


def _bodies(**kinds):
    """The report's sections; a kind passed as None is empty."""
    bodies = {"Scope": R_SCOPE, "Summary": R_SUMMARY, "Unimplemented": R_NOTIFIER,
              "Undocumented": R_ORDERS, "Drifted": R_PAGE_SIZE, "Tickets": "none"}
    bodies.update(kinds)
    return bodies


def _notes(unimplemented=UNIMPLEMENTED, undocumented=UNDOCUMENTED, drifted=DRIFTED):
    return ("## Unimplemented\n\n%s\n## Undocumented\n\n%s\n## Drifted\n\n%s\n"
            "## Unverified\n\n_None._\n" % (unimplemented, undocumented, drifted))


def _start(ws):
    ws.skill("audit-design")
    started = ws.acs("step", "start", "--step", "audit-design")
    assert started.returncode == 0, started.stderr
    checked = ws.acs("design", "check", *DOCS)
    assert checked.returncode == 0 and json.loads(checked.stdout)["ok"], checked.stdout


def _analyse(ws, notes=None):
    ws.write(STEP + "/iter-1/gaps-repo.md", _notes() if notes is None else notes)
    ws.write(STEP + "/iter-1/gap-analyst-repo.json", json.dumps({
        "commands": [{"run": "git log --stat -3", "outcome": "a10cef7 deletes src/notifier"}],
        "counts": {"unimplemented": 1, "undocumented": 1, "drifted": 1}}, indent=2))
    merged = ws.acs("notes", "merge", "--out", STEP + "/iter-1/gaps.md",
                    STEP + "/iter-1/gaps-repo.md")
    assert merged.returncode == 0, merged.stderr


def _finish(ws, unimplemented=1, planned=0, undocumented=1, drifted=1, tickets=(),
            bodies=None, drop=()):
    """report.md, then the result document through the post-hook -- which may
    refuse (exit 1): a bad play's refusal is part of what it did."""
    ws.write(STEP + "/iter-1/report.md", report(_bodies() if bodies is None else bodies,
                                                drop=drop))
    ws.write(STEP + "/result.json", json.dumps({
        "status": "completed",
        "summary": "audited hld + 1 feature against the code: 3 gaps, 1 a regression",
        "states": {"audit": {"scope": "all", "report": "steps/audit-design/iter-1/report.md",
                             "unimplemented": unimplemented, "planned": planned,
                             "undocumented": undocumented, "drifted": drifted,
                             "unversioned": 0, "tickets": list(tickets)}},
        "findings": [], "errors": []}, indent=2))
    return subprocess.run([sys.executable, POST, "--result-file", STEP + "/result.json"],
                          cwd=ws.path, env=ws.env, capture_output=True, text=True)


def IDEAL(ws):
    _start(ws)
    _analyse(ws)
    posted = _finish(ws)
    assert posted.returncode == 0, posted.stderr
    ws.reply = ("## /acs:audit-design · all · completed\n\n- Unimplemented (regression): the "
                "notifier container and POST /notifications -- hld/c4-container.md, "
                "hld/integration-map.md (implemented); code: absent.\n- Undocumented: the "
                "orders API, src/shop/orders.py:4.\n- Drifted: customer page size, 50 in "
                "lld/customer-listing/api/customers.md vs 20 in src/shop/__init__.py:1.\n"
                "No document or code changed; no ticket created. Next: /acs:create-architecture.")


def _fixed_the_design(ws):
    """Found the gaps, then 'fixed' them: dropped the notifier from the
    container view and bumped its version."""
    _start(ws)
    _analyse(ws)
    path = os.path.join(ws.path, A, "hld", "c4-container.md")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    ws.write("%s/hld/c4-container.md" % A, "\n".join(
        line for line in text.split("\n") if "notifier" not in line))
    ws.acs("design", "bump", "--ticket", "EVAL-1", "%s/hld/c4-container.md" % A)
    _finish(ws)


def _added_an_orders_contract(ws):
    """Documented the undocumented API instead of reporting it."""
    _start(ws)
    _analyse(ws)
    ws.write("%s/lld/orders/api/orders.md" % A, "# Orders API\n\n## GET /orders\n")
    _finish(ws)


def _restamped_the_versions(ws):
    """Re-versioned every document it read, as if an audit were a change."""
    _start(ws)
    ws.acs("design", "bump", "--ticket", "EVAL-1", *DOCS)
    _analyse(ws)
    _finish(ws)


def _called_the_regression_planned(ws):
    """Read the removed notifier as the design ahead of the code -- in a
    document marked implemented."""
    _start(ws)
    _analyse(ws)
    _finish(ws, unimplemented=0, planned=1,
            bodies=_bodies(Unimplemented=None, Planned=R_NOTIFIER))


def _drift_as_unimplemented(ws):
    """Filed the page-size disagreement under the wrong kind and counted no
    drift."""
    _start(ws)
    _analyse(ws, notes=_notes(unimplemented=UNIMPLEMENTED + DRIFTED, drifted=NONE))
    _finish(ws, unimplemented=2, drifted=0,
            bodies=_bodies(Unimplemented=R_NOTIFIER + "\n" + R_PAGE_SIZE, Drifted=None))


def _missed_the_orders_api(ws):
    _start(ws)
    _analyse(ws, notes=_notes(undocumented=NONE))
    _finish(ws, undocumented=0, bodies=_bodies(Undocumented=None))


def _report_short_of_the_result(ws):
    """The gap notes have the orders API, the result claims it -- and the
    report left it out. The post-hook counts the report, so the claim does not
    survive."""
    _start(ws)
    _analyse(ws)
    _finish(ws, bodies=_bodies(Undocumented=None))


def _report_missing_a_section(ws):
    """Wrote the report without the sections it had nothing for: the
    post-hook refuses it."""
    _start(ws)
    _analyse(ws)
    posted = _finish(ws, drop=("Planned", "Unversioned"))
    assert posted.returncode == 1, posted.stderr


def _ticketed_the_gaps(ws):
    """Minted a ticket the user declined."""
    _start(ws)
    _analyse(ws)
    ws.sh("python3 %s --title 'Remove the notifier from the HLD' --type task > /dev/null"
          % NEW_TICKET)
    _finish(ws, tickets=("EVAL-2",))


def _never_finished(ws):
    _start(ws)
    _analyse(ws)


BAD = {
    "fired the skill and did nothing": lambda ws: ws.skill("audit-design"),
    "edited a design doc to fix a gap": _fixed_the_design,
    "wrote an LLD contract for the undocumented API": _added_an_orders_contract,
    "bumped the version of every document it read": _restamped_the_versions,
    "wrong classification counts: the regression called planned": _called_the_regression_planned,
    "wrong classification: drift filed as unimplemented": _drift_as_unimplemented,
    "missed the undocumented orders API": _missed_the_orders_api,
    "ticketed the gaps the user declined": _ticketed_the_gaps,
    "never wrote the result document": _never_finished,
    "result claims counts the report does not contain": _report_short_of_the_result,
    "report missing sections (the post-hook refuses it)": _report_missing_a_section,
}
