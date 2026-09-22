"""acs_lib.verdict — `/acs:review-code`'s verdict, as a document the kernel reads.

`verifier_passed` — the single field the `/acs:create-pr` gate turns on — was
asserted by the COORDINATOR. The reviewer is the only role that knows the
verdict, and it already writes a full report; the coordinator was transcribing
a conclusion it did not reach. The gate therefore checked whether a model had
written `true`, not whether a review had passed (MAR-523/527).

The verdict is now a document `/acs:review-code` writes and the kernel
validates, with one rule that makes it a finding rather than a claim:

    passed == (the verdict carries no confirmed blocking finding)

`validate_verdict` enforces that. A document asserting `passed: true` alongside
a blocking finding is REJECTED, not believed — which is the whole difference
between a verdict and a self-report.

**What changed with the v0.5.0 redesign (§2.3).** The sixteen-dimension table
went with the verifier it belonged to. A verdict is now a list of *findings*,
because a finding is what crosses the loop: `/acs:code` reads this document on
iteration n+1 and answers every confirmed id. Three fields carry that loop and
the dimension-era verdict had none of them:

  * `id` — stable across iterations, so the next review can close one
  * `evidence` — so `/acs:code` does not re-derive what the review established
  * `resolved_when` — the adjudicator's refutation criterion, restated as what
    a fix must make true

A refuted finding is NOT here: it stays in `iter-<n>/adjudication.json` as an
audit trail. What reaches `/acs:code` is what survived adjudication.

No I/O beyond reading the file it is asked for: the shape rules are a pure
function, so the hooks, the CLI and the tests all reach the same answer.
"""

import json
import os

from ._common import read_json

#: The five review lenses (§3.6). Lens B fans out across the diff, so several
#: findings may carry `B`; the letter names the lens, not the instance.
LENSES = ("A", "B", "C", "D", "E")

#: Only `blocking` decides the verdict. `advisory` findings are reported and
#: carried, and never gate -- `needs-context` adjudications land here.
SEVERITIES = ("blocking", "advisory")

#: A finding's standing in THIS verdict. `refuted` is absent by construction:
#: refuted findings never reach the verdict (§2.3, "what must not cross").
#: `resolved` is how a previous iteration's finding is closed, so the trail
#: shows closure rather than the finding simply vanishing.
FINDING_STATUSES = ("confirmed", "advisory", "resolved")

#: What a finding is about. `gate` is stage 3's channel: a build, lint, suite
#: or coverage failure is a finding with the failing command as its evidence,
#: which is why the gate needs no separate report to the loop.
FINDING_KINDS = ("defect", "acceptance", "contract", "regression", "craft", "gate")

#: The adjudicator's ruling on a candidate finding (§3.6 stage 2).
ADJUDICATIONS = ("confirmed", "refuted", "needs-context")


def verdict_filename(iteration, lens=None):
    # The iteration is the DIRECTORY now, so the file no longer carries it.
    return "verdict.json" if lens is None else "verdict-lens-%s.json" % lens


def verdict_path(rdir, skill, iteration, lens=None):
    """`steps/<skill>/iter-<n>/verdict.json` (§4.2). The step ROOT holds the
    current verdict; this is the one that iteration wrote."""
    from .run import iteration_dir
    return os.path.join(iteration_dir(rdir, skill, int(iteration)),
                        verdict_filename(iteration, lens))


def load_verdict(rdir, skill, iteration, lens=None):
    doc = read_json(verdict_path(rdir, skill, iteration, lens))
    return doc if isinstance(doc, dict) else None


def findings_of(doc):
    if not isinstance(doc, dict):
        return []
    return [f for f in (doc.get("findings") or []) if isinstance(f, dict)]


def blocking_findings(doc):
    """The findings that gate: blocking AND still standing.

    A `resolved` finding is carried so the trail shows closure -- reading it as
    blocking would make a verdict that records its own fixes permanently red.
    """
    return [f for f in findings_of(doc)
            if f.get("severity") == "blocking" and f.get("status") != "resolved"]


def derived_passed(doc):
    """The verdict the DOCUMENT supports, whatever it claims in `passed`."""
    return not blocking_findings(doc)


def open_findings(doc):
    """Confirmed findings `/acs:code` owes an answer to, by id (§2.3)."""
    return [f for f in findings_of(doc) if f.get("status") == "confirmed"]


def unanswered(doc, result):
    """Confirmed finding ids the `code` result does not answer.

    `review-code`'s pre-hook runs this on iteration 2+: every confirmed id is
    answered `fixed` or `disputed`, and there is no third option.
    """
    answered = set()
    if isinstance(result, dict):
        for entry in (result.get("resolutions") or []):
            if isinstance(entry, dict) and entry.get("id"):
                answered.add(entry["id"])
    return [f.get("id") for f in open_findings(doc) if f.get("id") not in answered]


def validate_verdict(doc, lens=None, skill=None, run_id=None, iteration=None):
    """Errors in a verdict document; an empty list means it is well formed.

    Two checks are the point of the module, and neither is expressible in JSON
    Schema -- which is why the shipped schema constrains shape only and this
    function carries the rules:

      * `passed` must agree with the findings. A verdict that claims to pass
        while carrying a blocking finding is not a verdict, and believing it is
        exactly what MAR-527 removes.
      * The document must be ABOUT the run it was read for. `skill`,
        `run_id` and `iteration` are checked against the caller's when the
        caller supplies them, because a verdict is only evidence for the run
        that produced it -- iteration 1's clean verdict copied onto iteration
        3's path is not iteration 3's verdict, and the review loop's fixed
        point depends on that freshness.
    """
    errors = []
    if not isinstance(doc, dict):
        return ["verdict must be a JSON object, got %s" % type(doc).__name__]

    for field in ("skill", "run_id"):
        if not isinstance(doc.get(field), str) or not doc[field].strip():
            errors.append("%s is required and must be a non-empty string" % field)
    if not isinstance(doc.get("iteration"), int) or doc["iteration"] < 1:
        errors.append("iteration is required and must be a positive integer")
    # The commit the review judged. `/acs:code` diffs from here on the next
    # iteration, so a verdict without it cannot say what it reviewed.
    if not isinstance(doc.get("reviewed_sha"), str) or not doc["reviewed_sha"].strip():
        errors.append("reviewed_sha is required and must be a non-empty string -- "
                      "it is the baseline /acs:code diffs from (§2.3)")

    for field, expected in (("skill", skill), ("run_id", run_id),
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

    findings = doc.get("findings")
    if not isinstance(findings, list):
        errors.append("findings is required and must be a list (empty on a pass)")
    else:
        errors.extend(_finding_errors(findings))

    # The rule the whole document exists for.
    if isinstance(doc.get("passed"), bool) and isinstance(findings, list):
        blocking = blocking_findings(doc)
        if doc["passed"] and blocking:
            errors.append(
                "passed is true but the verdict carries %d blocking finding(s) (%s) -- "
                "`passed` is derived from the findings, not asserted alongside them"
                % (len(blocking), "; ".join(str(f.get("id")) for f in blocking)))
        elif not doc["passed"] and not blocking:
            errors.append(
                "passed is false but no finding is `blocking` -- record the blocking "
                "finding that fails the verdict, or report the pass")
    return errors


def _finding_errors(findings):
    """Per-finding shape. The required fields are exactly the ones `/acs:code`
    cannot act without: an id to answer, evidence not to re-derive, and a
    `resolved_when` that says when the answer is good enough."""
    errors = []
    seen = set()
    for finding in findings:
        if not isinstance(finding, dict):
            errors.append("each finding must be an object, got %s" % type(finding).__name__)
            continue
        ident = finding.get("id")
        if not isinstance(ident, str) or not ident.strip():
            errors.append("every finding needs a non-empty string id -- it is what "
                          "/acs:code answers and what the next review closes")
        elif ident in seen:
            errors.append("finding id %r is used twice; an id is the loop's handle "
                          "on one finding" % ident)
        else:
            seen.add(ident)

        status = finding.get("status")
        if status not in FINDING_STATUSES:
            errors.append("finding %r status %r is not one of %s (a refuted finding "
                          "does not belong in the verdict at all)"
                          % (ident, status, ", ".join(FINDING_STATUSES)))
        if finding.get("severity") not in SEVERITIES:
            errors.append("finding %r severity %r is not one of %s"
                          % (ident, finding.get("severity"), ", ".join(SEVERITIES)))
        if finding.get("kind") not in FINDING_KINDS:
            errors.append("finding %r kind %r is not one of %s"
                          % (ident, finding.get("kind"), ", ".join(FINDING_KINDS)))
        finding_lens = finding.get("lens")
        if finding_lens is not None and finding_lens not in LENSES:
            errors.append("finding %r lens %r is not one of %s"
                          % (ident, finding_lens, ", ".join(LENSES)))
        if not str(finding.get("claim") or "").strip():
            errors.append("finding %r needs a non-empty claim" % ident)

        evidence = finding.get("evidence")
        if not isinstance(evidence, list) or not [e for e in evidence if str(e or "").strip()]:
            errors.append("finding %r needs evidence: a non-empty list of what the "
                          "review established, so /acs:code does not re-derive it" % ident)

        traces = finding.get("traces_to")
        if traces is not None and not isinstance(traces, list):
            errors.append("finding %r traces_to must be a list (empty when the lens "
                          "cannot name one)" % ident)

        # `resolved_when` is the adjudicator's refutation criterion restated as
        # an exit criterion. A confirmed finding without one tells /acs:code to
        # fix something without saying when it is fixed.
        if status == "confirmed" and not str(finding.get("resolved_when") or "").strip():
            errors.append("finding %r is confirmed but carries no resolved_when -- "
                          "that field is what /acs:code works to (§2.3)" % ident)

        adjudication = finding.get("adjudication")
        if adjudication is not None:
            if not isinstance(adjudication, dict):
                errors.append("finding %r adjudication must be an object" % ident)
            elif adjudication.get("verdict") not in ADJUDICATIONS:
                errors.append("finding %r adjudication verdict %r is not one of %s"
                              % (ident, adjudication.get("verdict"),
                                 ", ".join(ADJUDICATIONS)))
    return errors


def next_finding_id(iteration, existing=()):
    """`F-<iteration>-<n>`, the first n this iteration has not used."""
    used = set(existing or ())
    n = 1
    while "F-%d-%d" % (int(iteration), n) in used:
        n += 1
    return "F-%d-%d" % (int(iteration), n)


def write_verdict(rdir, skill, iteration, doc, lens=None):
    path = verdict_path(rdir, skill, iteration, lens)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return path
