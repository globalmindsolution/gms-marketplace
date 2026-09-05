"""acs_lib.verdict — the verifier's verdict, as a document the kernel reads (MAR-527).

`verifier_passed` — the single field the `/acs:create-pr` gate turns on — was
asserted by the COORDINATOR. The verifier is the only role that knows the
verdict, and it already writes a full report; the coordinator was transcribing
a conclusion it did not reach. The gate therefore checked whether a model had
written `true`, not whether a verifier had passed.

The verdict is now a document the verifier writes and the kernel validates,
with one rule that makes it a finding rather than a claim:

    passed == (the verdict carries no blocking finding)

`validate_verdict` enforces that. A document asserting `passed: true` alongside
a blocking finding is REJECTED, not believed — which is the whole difference
between a verdict and a self-report.

No I/O beyond reading the file it is asked for: the shape rules are a pure
function, so the SubagentStop hook, the CLI and the tests all reach the same
answer.
"""

import json
import os

from ._common import read_json

#: The verifier's dimensions, by the numbers the charter uses
#: (plugins/acs/agents/code-verifier.md). Kept in sync by
#: tests/acs/test_verifier_verdict.py, which re-derives them from the charter
#: live rather than trusting this copy.
VERDICT_DIMENSIONS = {
    1: "Acceptance-criteria conformance",
    2: "Tests",
    3: "Coverage",
    4: "Business logic",
    5: "Features",
    6: "Quality",
    7: "Technical standards",
    8: "Architecture",
    9: "System design",
    10: "Security",
    11: "Documentation",
    12: "Simplicity & scope",
    13: "Audience-style",
    14: "Regression-risk (git-history)",
    15: "Plan conformance",
    16: "Approval-audit",
}

#: A dimension's outcome. `n/a` is a real answer, not a missing one: dimension
#: 14 is full-depth only, 15 is inactive without an approved plan, and 2/3 are
#: n/a under `docs_only`.
DIMENSION_RESULTS = ("pass", "fail", "n/a")

#: Only `blocking` decides the verdict. `info` findings are reported and
#: carried, and never gate -- the demoted documentation sub-checks rely on it.
SEVERITIES = ("blocking", "info")

#: The four full-depth review lenses.
LENSES = ("A", "B", "C", "D")

#: Which dimensions each lens owes, fixed literally in agents/code-verifier.md.
#: A lens spawn checks ONLY its subset, so completeness is judged against the
#: subset rather than all sixteen.
LENS_DIMENSIONS = {
    "A": (1, 2, 3, 4, 5),
    "B": (6, 7, 10, 12, 16),
    "C": (8, 9, 11, 13, 15),
    "D": (14,),
}

#: A light-depth spawn checks the 15 base dimensions -- every one except 14,
#: which is full-depth/lens-D only (agents/code-verifier.md).
BASE_DIMENSIONS = tuple(i for i in sorted(VERDICT_DIMENSIONS) if i != 14)


def owed_dimensions(lens=None):
    """The dimension ids this verdict must report on, given its lens."""
    return LENS_DIMENSIONS[lens] if lens in LENS_DIMENSIONS else BASE_DIMENSIONS


def verdict_filename(iteration, lens=None):
    if lens:
        return "iter-%s-verdict-lens-%s.json" % (iteration, lens)
    return "iter-%s-verdict.json" % iteration


def verdict_path(tdir, skill, iteration, lens=None):
    return os.path.join(tdir, "phases", skill, verdict_filename(iteration, lens))


def load_verdict(tdir, skill, iteration, lens=None):
    doc = read_json(verdict_path(tdir, skill, iteration, lens))
    return doc if isinstance(doc, dict) else None


def blocking_findings(doc):
    return [f for f in (doc.get("findings") or [])
            if isinstance(f, dict) and f.get("severity") == "blocking"]


def derived_passed(doc):
    """The verdict the DOCUMENT supports, whatever it claims in `passed`."""
    return not blocking_findings(doc)


def validate_verdict(doc, lens=None, skill=None, ticket_id=None, iteration=None):
    """Errors in a verdict document; an empty list means it is well formed.

    Two checks are the point of the module, and neither is expressible in JSON
    Schema -- which is why the shipped schema constrains shape only and this
    function carries the rules:

      * `passed` must agree with the findings. A verdict that claims to pass
        while carrying a blocking finding is not a verdict, and believing it is
        exactly what MAR-527 removes.
      * The document must be ABOUT the run it was read for. `skill`,
        `ticket_id` and `iteration` are checked against the caller's when the
        caller supplies them, because a verdict is only evidence for the run
        that produced it -- iteration 1's clean verdict copied onto iteration
        3's path is not iteration 3's verdict, and the review loop's fixed
        point depends on that freshness.
    """
    errors = []
    if not isinstance(doc, dict):
        return ["verdict must be a JSON object, got %s" % type(doc).__name__]

    for field in ("skill", "ticket_id"):
        if not isinstance(doc.get(field), str) or not doc[field].strip():
            errors.append("%s is required and must be a non-empty string" % field)
    if not isinstance(doc.get("iteration"), int) or doc["iteration"] < 1:
        errors.append("iteration is required and must be a positive integer")

    for field, expected in (("skill", skill), ("ticket_id", ticket_id),
                            ("iteration", iteration)):
        if expected is None:
            continue
        actual = doc.get(field)
        if field == "iteration":
            try:
                same = int(actual) == int(expected)
            except (TypeError, ValueError):
                same = False
        else:
            same = actual == expected
        if not same:
            errors.append(
                "verdict %s is %r but this is %r -- a verdict is evidence only "
                "for the run that produced it" % (field, actual, expected))
    if not isinstance(doc.get("passed"), bool):
        errors.append("passed is required and must be a boolean")

    declared_lens = doc.get("lens")
    if declared_lens is not None and declared_lens not in LENSES:
        errors.append("lens %r is not one of %s" % (declared_lens, ", ".join(LENSES)))
    if lens is not None and declared_lens != lens:
        errors.append("lens %r does not match the %r this verdict was written for"
                      % (declared_lens, lens))

    dimensions = doc.get("dimensions")
    if not isinstance(dimensions, list) or not dimensions:
        errors.append("dimensions is required and must be a non-empty list")
    else:
        seen = set()
        for entry in dimensions:
            if not isinstance(entry, dict):
                errors.append("each dimension must be an object, got %s" % type(entry).__name__)
                continue
            ident = entry.get("id")
            if ident not in VERDICT_DIMENSIONS:
                errors.append("dimension id %r is not one of 1-%d"
                              % (ident, len(VERDICT_DIMENSIONS)))
            elif ident in seen:
                errors.append("dimension %s is reported twice" % ident)
            else:
                seen.add(ident)
            if entry.get("result") not in DIMENSION_RESULTS:
                errors.append("dimension %r result %r is not one of %s"
                              % (ident, entry.get("result"), ", ".join(DIMENSION_RESULTS)))

        # Completeness. "Zero findings" only means a pass if every dimension
        # the verifier OWED was actually reported -- otherwise an unfinished
        # review is indistinguishable from a clean one, and `n/a` is already a
        # valid result, so saying so costs an honest verifier nothing.
        owed = set(owed_dimensions(declared_lens))
        missing = sorted(owed - seen)
        if missing:
            errors.append(
                "dimensions %s are not reported; a verdict must cover every "
                "dimension it owed (use result \"n/a\" where one does not apply)"
                % ", ".join(str(m) for m in missing))

    findings = doc.get("findings")
    if not isinstance(findings, list):
        errors.append("findings is required and must be a list (empty on a pass)")
    else:
        for finding in findings:
            if not isinstance(finding, dict):
                errors.append("each finding must be an object, got %s" % type(finding).__name__)
                continue
            if finding.get("severity") not in SEVERITIES:
                errors.append("finding severity %r is not one of %s"
                              % (finding.get("severity"), ", ".join(SEVERITIES)))
            if not str(finding.get("detail") or "").strip():
                errors.append("every finding needs a non-empty detail")

    # The rule the whole document exists for.
    if isinstance(doc.get("passed"), bool) and isinstance(findings, list):
        blocking = blocking_findings(doc)
        if doc["passed"] and blocking:
            errors.append(
                "passed is true but the verdict carries %d blocking finding(s) (%s) -- "
                "`passed` is derived from the findings, not asserted alongside them"
                % (len(blocking), "; ".join(str(f.get("dimension")) for f in blocking)))
        elif not doc["passed"] and not blocking:
            errors.append(
                "passed is false but no finding is `blocking` -- record the blocking "
                "finding that fails the verdict, or report the pass")

    # A dimension that failed must have produced a finding, or the report and
    # the verdict disagree about what happened.
    failed = [e.get("id") for e in (dimensions if isinstance(dimensions, list) else [])
              if isinstance(e, dict) and e.get("result") == "fail"]
    if failed and isinstance(findings, list) and not blocking_findings(doc):
        errors.append("dimension(s) %s report `fail` with no blocking finding to match"
                      % ", ".join(str(f) for f in failed))
    return errors


def merge_lens_verdicts(docs):
    """One verdict from the four full-depth lens verdicts.

    Mechanical, so the coordinator invokes it rather than authoring it: passed
    is the conjunction, findings are the union in lens order, and a dimension's
    result is the worst any lens reported (`fail` beats `pass` beats `n/a`),
    since the lenses partition the dimensions and only one judges each.
    """
    rank = {"n/a": 0, "pass": 1, "fail": 2}
    merged = {}
    findings = []
    lenses = []
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        if doc.get("lens"):
            lenses.append(doc["lens"])
        findings.extend(f for f in (doc.get("findings") or []) if isinstance(f, dict))
        for entry in (doc.get("dimensions") or []):
            if not isinstance(entry, dict) or entry.get("id") not in VERDICT_DIMENSIONS:
                continue
            current = merged.get(entry["id"])
            if current is None or rank.get(entry.get("result"), -1) > rank.get(current.get("result"), -1):
                merged[entry["id"]] = dict(entry)
    first = next((d for d in docs if isinstance(d, dict)), {})
    out = {
        "skill": first.get("skill"),
        "ticket_id": first.get("ticket_id"),
        "iteration": first.get("iteration"),
        "lens": None,
        "merged_from": sorted(lenses),
        "dimensions": [merged[k] for k in sorted(merged)],
        "findings": findings,
    }
    out["passed"] = derived_passed(out)
    return out


def write_verdict(tdir, skill, iteration, doc, lens=None):
    path = verdict_path(tdir, skill, iteration, lens)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return path
