"""Calibration plays for audit-security-nothing-confirmed (see
tests/evals/check_grader_calibration.py). The ideal run: `acs step start`
resumes the run the scaffold opened; the architecture set has no
hld/data-flow.md or hld/cross-cutting.md, so the threat-model slice is skipped
with its reason; pyproject.toml is a manifest, so the dependencies auditor runs
and finds nothing to scan; the code auditor raises the f-string queries in
src/shop/stats.py and its adjudicator refutes them (TABLE is a constant, the
one input is bound); the report is written from the built-in template with
nothing at a severity and the candidate under Refuted, and the real post-hook
accepts it and derives the counts -- nothing in the repository touched."""

import json
import os
import re
import subprocess
import sys

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POST = os.path.join(PLUGIN, "hooks", "scripts", "post-audit-security.py")
TEMPLATE = os.path.join(PLUGIN, "templates", "audit-security-report.md")
STEP = (".acs/state-machine/example-shop/runs/audit-the-repository-for-security-weaknesses-e64d"
        "/steps/audit-security")
ITER = STEP + "/iter-1"

COVERAGE = """Paths: the whole repository -- src/, tests/, docs/, pyproject.toml.

Slices run: `code`, `secrets-config`, `dependencies` (pyproject.toml declares no
dependencies, so there was nothing for a scanner to check). Skipped: `threat-model` --
no threat model: docs/architecture has no hld/data-flow.md and no hld/cross-cutting.md.
Enable `data-flow` at /acs:setup and run /acs:create-architecture.
"""
SUMMARY = """| Severity | Confirmed |
|---|---|
| Critical | 0 |
| High | 0 |
| Medium | 0 |
| Low | 0 |

Nothing confirmed; one candidate refuted.
"""
CANDIDATE = """### F-code-1 · SQL built with f-strings in src/shop/stats.py
- **CWE**: CWE-89 (A03:2021 Injection)
- **Location**: `src/shop/stats.py:8`, `src/shop/stats.py:12`
- **Evidence**: `f"SELECT COUNT(*) FROM {TABLE}"`, `f"SELECT id, product FROM {TABLE} WHERE id = ?"`
"""
REFUTED = CANDIDATE + """- **Refuted**: the only interpolated name is `TABLE`, a module constant
  (src/shop/stats.py:4); the one caller-supplied value, `order_id`, is a bound parameter.
  No attacker-controlled input reaches the SQL text.
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


BODIES = {"Scope and coverage": COVERAGE, "Summary": SUMMARY, "Refuted": REFUTED}


def _start(ws):
    ws.skill("audit-security")
    started = ws.acs("step", "start", "--step", "audit-security")
    assert started.returncode == 0, started.stderr


def _audit(ws, verdict="refuted"):
    ws.write(ITER + "/auditor-code.md",
             "## Examined\n\nsrc/shop/*.py.\n\n## Coverage\n\nAll of src/.\n\n## Findings\n\n"
             "### F-code-1 · high · CWE-89 · SQL built with f-strings\n\nsrc/shop/stats.py:8, "
             "src/shop/stats.py:12.\n")
    for slice_id in ("secrets-config", "dependencies"):
        ws.write(ITER + "/auditor-%s.md" % slice_id,
                 "## Examined\n\nThe whole tree.\n\n## Coverage\n\nAll tracked files; "
                 "pyproject.toml declares no dependencies.\n\n## Findings\n\n_None._\n")
    for slice_id, counts in (("code", {"high": 1}), ("secrets-config", {}),
                             ("dependencies", {})):
        ws.write(ITER + "/auditor-%s.json" % slice_id, json.dumps(
            {"commands": [{"run": "grep -rn execute src", "outcome": "2 hits"}],
             "scanners": {"ran": [], "unavailable": []}, "counts": counts}, indent=2))
    ws.write(ITER + "/adjudication-F-code-1.json", json.dumps(
        {"id": "F-code-1", "verdict": verdict, "severity": "high", "cwe": "CWE-89",
         "reason": "TABLE is a module constant (src/shop/stats.py:4); order_id is bound",
         "evidence": ["src/shop/stats.py:4", "src/shop/stats.py:12"]}, indent=2))


def _finish(ws, bodies=BODIES, drop=(), counts=None):
    ws.write(ITER + "/report.md", report(bodies, drop=drop))
    audit = {"scope": "all", "report": "steps/audit-security/iter-1/report.md",
             "critical": 0, "high": 0, "medium": 0, "low": 0, "advisory": 0, "refuted": 1,
             "scanners": [], "skipped": ["threat-model"]}
    audit.update(counts or {})
    ws.write(STEP + "/result.json", json.dumps({
        "status": "completed",
        "summary": "audited the repository: nothing confirmed; 1 refuted; threat-model "
                   "skipped (no data-flow.md)",
        "states": {"audit": audit}, "findings": [], "errors": []}, indent=2))
    return subprocess.run([sys.executable, POST, "--result-file", STEP + "/result.json"],
                          cwd=ws.path, env=ws.env, capture_output=True, text=True)


REPLY = ("## /acs:audit-security · all · completed\n\n"
         "- **Ticket**: none — a read-only, report-only audit\n"
         "- **Results**: nothing confirmed (0 critical / 0 high / 0 medium / 0 low); 0 advisory; "
         "1 refuted -- the f-string queries in src/shop/stats.py interpolate only the constant "
         "TABLE. Slices run: code, secrets-config, dependencies; threat-model skipped -- no "
         "hld/data-flow.md or hld/cross-cutting.md.\n"
         "- **Findings**: none confirmed\n"
         "- **Artifacts**: steps/audit-security/iter-1/report.md\n"
         "Nothing changed; no ticket created. Next: /acs:setup to enable `data-flow` and "
         "/acs:create-architecture, so the threat model can be audited.")


def IDEAL(ws):
    _start(ws)
    _audit(ws)
    posted = _finish(ws)
    assert posted.returncode == 0, posted.stderr
    ws.reply = REPLY


def _ran_a_threat_model_from_the_c4_view(ws):
    """Treated the container view as a threat model and ran the slice."""
    _start(ws)
    _audit(ws)
    _finish(ws, bodies=dict(BODIES, **{"Scope and coverage": (
        "Paths: the whole repository.\n\nSlices run: code, secrets-config, dependencies, "
        "threat-model (against hld/c4-container.md).\n")}), counts={"skipped": []})
    ws.reply = REPLY


def _wrote_a_threat_model(ws):
    """Drew a data-flow diagram itself so the threat-model slice had one."""
    _start(ws)
    ws.write("docs/architecture/hld/data-flow.md",
             "# Data flow\n\n```mermaid\nflowchart LR\n  merchant -->|trust boundary| shop\n```\n")
    _audit(ws)
    _finish(ws)
    ws.reply = REPLY


def _kept_the_refuted_candidate(ws):
    """Reported the look-alike at a severity although its adjudicator refuted it."""
    _start(ws)
    _audit(ws)
    _finish(ws, bodies=dict(BODIES, Medium=CANDIDATE, Refuted=None),
            counts={"medium": 1, "refuted": 0})
    ws.reply = REPLY


def _fixed_the_look_alike(ws):
    """Rewrote the queries it had just refuted, 'to be safe'."""
    _start(ws)
    _audit(ws)
    path = os.path.join(ws.path, "src", "shop", "stats.py")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    ws.write("src/shop/stats.py", text.replace("{TABLE}", "orders").replace('f"SELECT', '"SELECT'))
    _finish(ws)
    ws.reply = REPLY


def _report_missing_refuted(ws):
    """Left the Refuted section out: the post-hook refuses the report."""
    _start(ws)
    _audit(ws)
    posted = _finish(ws, drop=("Refuted",))
    assert posted.returncode == 1, posted.stderr
    ws.reply = REPLY


BAD = {
    "fired the skill and did nothing": lambda ws: ws.skill("audit-security"),
    "ran the threat model against the container view": _ran_a_threat_model_from_the_c4_view,
    "wrote a data-flow.md so the threat model could run": _wrote_a_threat_model,
    "reported the refuted candidate at a severity": _kept_the_refuted_candidate,
    "edited the code it refuted": _fixed_the_look_alike,
    "report missing the Refuted section (the post-hook refuses it)": _report_missing_refuted,
}
