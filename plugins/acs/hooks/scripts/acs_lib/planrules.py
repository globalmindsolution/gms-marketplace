"""acs_lib.planrules — the rules a plan is judged by.

Extracted from acs_lib.py by MAR-522 as `lanes`, when it also held the
size x stakes routing grid. ADR-0095 retired that grid: the delivery path is
judged from the plan by /acs:ship and recorded, so there is no lane to derive,
no verify depth to look up, no ceiling table, and no escalation to clamp. What
is left is what the name now says -- the deterministic half of plan approval,
and the additive-only diff classifier that D6 Option A's verifier uses.
"""


import fnmatch
import hashlib
import re
import markdown_headings  # noqa: E402

from .settings import DEFAULT_SETTINGS



def classify_additive_diff(diff_output, allowlist_globs):
    """Pure additive-only classifier for `git diff --name-status` text (D6 Option A
    verifier half): returns [] when compliant, else a list of {status, path, reason}
    violation dicts — A always compliant, M compliant only inside allowlist_globs,
    R/D always violate, any unrecognized status token fails closed.
    """
    globs = list(allowlist_globs or [])
    violations = []
    for line in (diff_output or "").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        status = parts[0]
        prefix = status[0] if status else ""
        if prefix == "A":
            continue
        if prefix == "M":
            path = parts[1] if len(parts) > 1 else ""
            if any(fnmatch.fnmatch(path, pattern) for pattern in globs):
                continue
            violations.append({"status": status, "path": path, "reason": "modify-outside-allowlist"})
        elif prefix == "R":
            path = parts[2] if len(parts) > 2 else (parts[1] if len(parts) > 1 else "")
            violations.append({"status": status, "path": path, "reason": "rename"})
        elif prefix == "D":
            path = parts[1] if len(parts) > 1 else ""
            violations.append({"status": status, "path": path, "reason": "delete"})
        else:
            path = parts[-1] if len(parts) > 1 else (parts[0] if parts else "")
            violations.append({"status": status, "path": path, "reason": "unrecognized-status"})
    return violations


# ---------------------------------------------------------------------------
# Plan-approval predicate
# ---------------------------------------------------------------------------

#: The ONE heading the predicate requires by name. 3.2: a plan is written for
#: a human to approve in one read, not filled into a template with a section
#: per heading whether or not that heading has content -- so the structural
#: floor is the machine-readable minimum and nothing else. This heading is kept
#: verbatim because the file-map guard already keys on it.
PLAN_FILE_MAP_HEADING = "Executor tasks & file map"

#: Retired with the template they enforced. Named here rather than deleted
#: silently: `plan-approval.json` records written before the change carry them
#: in their `inputs`, and a reader of an older record needs to know what they
#: were.
RETIRED_PLAN_SECTIONS = [
    "Spec analysis", "Test strategy", "Documentation map", "Risks",
    "Verifier checklist", "Scope", "Approach", "API/data changes",
    "Test plan", "Out of scope",
]

#: Kept as an alias: the regex is named in this module's own tests and in the
#: plan-approval prose. markdown_headings owns the pattern now (MAR-522).
_PLAN_HEADING_RE = markdown_headings.HEADING_RE

#: The one heading scanner. markdown_headings imports `re` and nothing else, so
#: plan_approval_eligible stays as pure as it was when this was a local copy.
_plan_headings = markdown_headings.headings


def _coverage_target_stated(norm_text, target):
    """`target` appears as a standalone numeric token within 200 characters
    of a case-insensitive "coverage" occurrence in `norm_text`."""
    if target is None:
        return False
    if isinstance(target, float) and target.is_integer():
        target_str = str(int(target))
    else:
        target_str = str(target)
    token_re = re.compile(r"(?<!\d)" + re.escape(target_str) + r"(?!\d)")
    for m in re.finditer(r"(?i)coverage", norm_text):
        window = norm_text[max(0, m.start() - 200):m.end() + 200]
        if token_re.search(window):
            return True
    return False


def plan_approval_eligible(plan_text, settings, fold_active=None):
    """Structural conformance of the plan artifact to the contract 3.2 leaves
    it -- the deterministic half of plan approval (never an LLM
    self-assertion). Pure: plain values in, plain values out, no I/O/clock.

    What it checks is the MACHINE-READABLE MINIMUM, not a template. A plan is
    written for a human to approve in one read, so requiring six named
    headings graded a document on its shape rather than its content: a plan
    with a `## Risks` heading and "none" under it passed, and a two-paragraph
    plan that said exactly what would change did not. Three things downstream
    code reads must still be findable without parsing prose, and those are
    what the floor is:

      * the `## Contract` block parses, and what it declares is admissible
        (`delivery_path` one of the four, `owes` a mapping of known keys);
      * `### Executor tasks & file map` exists and is non-empty -- the
        file-map guard enforces it on every Write, so an empty one is an
        unguarded run;
      * the coverage target is stated, because the plan is what states it.

    `fold_active` is accepted and ignored: the spec fold has no separate
    section set any more, because the plan IS the spec content.

    Returns (eligible, evaluation) where evaluation = {"inputs", "checks",
    "failures"}; eligible is `not failures`. The digest is computed here
    (not by the caller) so a verdict can never be paired with a digest of
    different bytes.
    """
    from . import plan_contract

    text = plan_text or ""
    settings = settings or {}
    coverage_target = settings.get("test_coverage_percent", DEFAULT_SETTINGS["test_coverage_percent"])
    norm_text = re.sub(r"\s+", " ", text)

    failures = []
    checks = {}

    plan_non_empty = bool(text.strip())
    checks["plan_non_empty"] = plan_non_empty
    if not plan_non_empty:
        failures.append("empty-plan")

    contract = plan_contract.parse(text)
    checks["contract_present"] = bool(contract)
    if not contract:
        failures.append("missing-section: Contract")
    else:
        contract_errors = plan_contract.errors(contract)
        checks["contract_admissible"] = not contract_errors
        for message in contract_errors:
            failures.append("contract: %s" % message)
        path_declared = plan_contract.delivery_path(contract) is not None
        checks["delivery_path_declared"] = path_declared
        if not path_declared:
            failures.append("contract: delivery_path is not declared")

    lines = text.split("\n")
    headings = _plan_headings(text)
    file_map_body = None
    for i, (lineno, level, htext) in enumerate(headings):
        if htext != PLAN_FILE_MAP_HEADING:
            continue
        end_line = len(lines) + 1
        for j in range(i + 1, len(headings)):
            if headings[j][1] <= level:
                end_line = headings[j][0]
                break
        file_map_body = lines[lineno:end_line - 1]
        break
    checks["file_map_present"] = file_map_body is not None
    if file_map_body is None:
        failures.append("missing-section: %s" % PLAN_FILE_MAP_HEADING)
    else:
        file_map_non_empty = any(l.strip() for l in file_map_body)
        checks["file_map_non_empty"] = file_map_non_empty
        if not file_map_non_empty:
            failures.append("empty-section: %s" % PLAN_FILE_MAP_HEADING)

    coverage_stated = _coverage_target_stated(norm_text, coverage_target)
    checks["coverage_target_stated"] = coverage_stated
    if not coverage_stated:
        failures.append("coverage-target-not-stated: %s" % coverage_target)

    inputs = {
        "plan_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "plan_chars": len(text),
        "coverage_target": coverage_target,
        "file_map_heading": PLAN_FILE_MAP_HEADING,
        "contract_keys": sorted(contract) if contract else [],
    }
    evaluation = {"inputs": inputs, "checks": checks, "failures": failures}
    return not failures, evaluation
