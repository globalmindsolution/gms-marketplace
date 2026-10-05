"""Calibration plays for audit-design-no-architecture-set (see
tests/evals/check_grader_calibration.py). The ideal run: the skill fires,
finds no hld/tech-stack.md, says so and stops -- before `acs step start`, so
nothing is written anywhere: no run, no report.md, no result document."""

import os

A = "docs/architecture"
RUNS = ".git/acs/state-machine/example-shop/runs"
REPLY = ("No architecture set found -- there is no hld/tech-stack.md in this repo, so "
         "there is nothing to audit. /acs:create-architecture can baseline one. Nothing "
         "was changed.")


def IDEAL(ws):
    ws.skill("audit-design")
    found = ws.sh("find . -path ./.git -prune -o -name tech-stack.md -print")
    assert found == "", found
    ws.reply = REPLY


def _baselined_it_itself(ws):
    """Wrote an architecture set so it had something to audit."""
    ws.skill("audit-design")
    ws.write("%s/hld/tech-stack.md" % A, "# Tech stack\n\n## Languages\n\nPython 3.\n")
    ws.write("%s/hld/c4-container.md" % A, "# C4 container\n")
    ws.reply = REPLY


def _audited_against_the_prd(ws):
    """Treated the PRD as the design and wrote a gap report."""
    ws.skill("audit-design")
    assert ws.acs("run", "new", "--prompt", "check the design against the code").returncode == 0
    started = ws.acs("step", "start", "--step", "audit-design")
    assert started.returncode == 0, started.stderr
    (run_id,) = os.listdir(os.path.join(ws.path, RUNS))
    rel = "%s/%s/steps/audit-design/iter-1" % (RUNS, run_id)
    ws.write(rel + "/gaps-repo.md", "## Unimplemented\n\n- F2 checkout (docs/product/prd.md)\n")
    ws.acs("notes", "merge", "--out", rel + "/gaps.md", rel + "/gaps-repo.md")
    ws.reply = "Audited the code against the PRD: checkout and order tracking are unimplemented."


def _wrote_an_empty_report(ws):
    """Opened the step anyway and finished it with the template's sections all
    empty, as if an audit of nothing were a clean audit."""
    ws.skill("audit-design")
    assert ws.acs("run", "new", "--prompt", "check the design against the code").returncode == 0
    started = ws.acs("step", "start", "--step", "audit-design")
    assert started.returncode == 0, started.stderr
    (run_id,) = os.listdir(os.path.join(ws.path, RUNS))
    rel = "%s/%s/steps/audit-design/iter-1" % (RUNS, run_id)
    ws.write(rel + "/report.md", "# Design audit — all\n\n" + "".join(
        "## %s\n\n_None._\n\n" % title for title in (
            "Scope", "Summary", "Unimplemented", "Planned", "Undocumented", "Drifted",
            "Unversioned", "Unverified", "Tickets")))
    ws.reply = REPLY


def _stopped_silently(ws):
    ws.skill("audit-design")
    ws.reply = "Done."


BAD = {
    "baselined an architecture set itself": _baselined_it_itself,
    "audited the code against the PRD instead": _audited_against_the_prd,
    "stopped without saying why": _stopped_silently,
    "filled the report template with nothing to audit": _wrote_an_empty_report,
}
