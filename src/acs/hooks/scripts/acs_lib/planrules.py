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

PLAN_REQUIRED_SECTIONS = [
    "Spec analysis",
    "Executor tasks & file map",
    "Test strategy",
    "Documentation map",
    "Risks",
    "Verifier checklist",
]

PLAN_FOLD_SECTIONS = [
    "Scope",
    "Approach",
    "API/data changes",
    "Test plan",
    "Out of scope",
]

PLAN_FOLD_CLAUSES = [
    "no separate /acs:create-spec invocation and no separate create-spec "
    "planner subagent",
    "every ticket.acceptance_criteria entry maps to at least one test the "
    "folded plan will write",
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


def plan_approval_eligible(plan_text, settings, fold_active=True):
    """Structural conformance of the plan artifact to code/SKILL.md's own
    contract -- the deterministic half of plan approval (never an LLM
    self-assertion). Pure: plain values in, plain values out, no I/O/clock.

    Returns (eligible, evaluation) where evaluation = {"inputs", "checks",
    "failures"}; eligible is `not failures`. The digest is computed here
    (not by the caller) so a verdict can never be paired with a digest of
    different bytes.
    """
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

    lines = text.split("\n")
    headings = _plan_headings(text)
    by_name = {}
    for i, (_lineno, _level, htext) in enumerate(headings):
        by_name.setdefault(htext, []).append(i)

    def _scan(names):
        # Mirrors structure_lint.lint_structure's `ambiguous` safeguard
        # (structure_lint.py:72-81): a name repeated in the declared list, or
        # matching more than one heading in the doc, is flagged so the order
        # check below can exclude it -- an ambiguous name must never
        # false-block a conforming doc (structure_lint.py:19-23).
        unique_names = list(dict.fromkeys(names))
        ambiguous = {n for n in unique_names if names.count(n) > 1}
        for n in unique_names:
            if len(by_name.get(n, [])) > 1:
                ambiguous.add(n)
        out = {}
        for name in names:
            occs = by_name.get(name, [])
            if not occs:
                out[name] = (False, False, None, name in ambiguous)
                continue
            i = occs[0]
            own_level = headings[i][1]
            end_line = len(lines) + 1
            for j in range(i + 1, len(headings)):
                if headings[j][1] <= own_level:
                    end_line = headings[j][0]
                    break
            body = lines[headings[i][0]:end_line - 1]
            out[name] = (True, any(l.strip() for l in body), i, name in ambiguous)
        return out

    required_scan = _scan(PLAN_REQUIRED_SECTIONS)
    required_ok = True
    for name in PLAN_REQUIRED_SECTIONS:
        present, non_empty, _idx, _ambiguous = required_scan[name]
        if not present:
            failures.append("missing-section: %s" % name)
            required_ok = False
        elif not non_empty:
            failures.append("empty-section: %s" % name)
            required_ok = False
    checks["required_sections_ok"] = required_ok

    if fold_active:
        fold_scan = _scan(PLAN_FOLD_SECTIONS)
        fold_ok = True
        for name in PLAN_FOLD_SECTIONS:
            present, non_empty, _idx, _ambiguous = fold_scan[name]
            if not present:
                failures.append("missing-section: %s" % name)
                fold_ok = False
            elif not non_empty:
                failures.append("empty-section: %s" % name)
                fold_ok = False
        checks["fold_sections_ok"] = fold_ok

        ordered_ok = True
        present_seq = [(name, fold_scan[name][2]) for name in PLAN_FOLD_SECTIONS
                        if fold_scan[name][0] and not fold_scan[name][3]]
        for k in range(len(present_seq) - 1):
            name_a, idx_a = present_seq[k]
            name_b, idx_b = present_seq[k + 1]
            if idx_a > idx_b:
                failures.append("section-order: %s before %s" % (name_b, name_a))
                ordered_ok = False
        checks["fold_sections_ordered"] = ordered_ok

        clauses_ok = True
        for clause in PLAN_FOLD_CLAUSES:
            if re.sub(r"\s+", " ", clause) not in norm_text:
                failures.append("missing-clause: %s" % clause)
                clauses_ok = False
        checks["mandatory_clauses_ok"] = clauses_ok
    else:
        checks["fold_sections_ok"] = True
        checks["fold_sections_ordered"] = True
        checks["mandatory_clauses_ok"] = True

    coverage_stated = _coverage_target_stated(norm_text, coverage_target)
    checks["coverage_target_stated"] = coverage_stated
    if not coverage_stated:
        failures.append("coverage-target-not-stated: %s" % coverage_target)

    inputs = {
        "plan_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "plan_chars": len(text),
        "fold_active": bool(fold_active),
        "coverage_target": coverage_target,
        "required_sections": list(PLAN_REQUIRED_SECTIONS),
        "fold_sections": list(PLAN_FOLD_SECTIONS),
        "mandatory_clauses": list(PLAN_FOLD_CLAUSES),
    }
    evaluation = {"inputs": inputs, "checks": checks, "failures": failures}
    return not failures, evaluation
