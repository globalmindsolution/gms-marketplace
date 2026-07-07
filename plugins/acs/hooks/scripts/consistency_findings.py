#!/usr/bin/env python3
"""consistency_findings.py — shape validator for ADR-0012 consistency findings.

Validates a single finding dict against the fixed shape ADR 0012 defines:
`{kind: "gap"|"staleness", upstream, downstream, description, recommendation}`.
This is a pure shape-validation utility for the test suite (and any future
prose tooling) — it performs no doc-graph detection itself; that stays in the
planner prose per ADR 0012's "no new tooling" decision.

Stdlib-only, Python >= 3.9. No `acs_lib` import, no I/O, no CLI/`main()`, no
hook wiring — mirrors the "Stdlib-only" framing in `codeowners.py`.
"""

VALID_KINDS = ("gap", "staleness")
REQUIRED_STRING_FIELDS = ("upstream", "downstream", "description", "recommendation")


def validate_finding(finding):
    """Validate one ADR-0012 finding dict; returns (ok, errors), never raises."""
    if not isinstance(finding, dict):
        return False, ["finding must be a dict"]

    errors = []

    kind = finding.get("kind")
    if kind not in VALID_KINDS:
        errors.append(
            "kind must be one of %s (got %r)" % (VALID_KINDS, kind)
        )

    for field in REQUIRED_STRING_FIELDS:
        value = finding.get(field)
        if field not in finding or value is None:
            errors.append("%s is required" % field)
        elif not isinstance(value, str) or value.strip() == "":
            errors.append("%s must be a non-empty string" % field)

    return (len(errors) == 0), errors


def validate_findings(findings):
    """Validate a list of finding dicts; returns (ok, per_finding), never raises."""
    if not isinstance(findings, list):
        return False, []

    per_finding = [validate_finding(f) for f in findings]
    ok = all(result[0] for result in per_finding)
    return ok, per_finding
