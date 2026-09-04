"""acs_lib.lanes — extracted from acs_lib.py by MAR-522."""


import fnmatch
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
import markdown_headings  # noqa: E402

from .settings import DEFAULT_SETTINGS



# ---------------------------------------------------------------------------
# Classification routing
# ---------------------------------------------------------------------------

def derive_lane(size, stakes, needs_design, ticket_type):
    """Deterministic lane routing: maps size x stakes axes + flags to a pipeline lane.

    Rule evaluation order (fixed, per design.md:553-565):
      Rule 1 (type override):     epic -> COMPLEX
      Rule 2 (size=large):        large -> COMPLEX
      Rule 3 (high-stakes floor): stakes=high -> STANDARD (size<=standard floor)
      Rule 4 (size dispatch):     standard->STANDARD, small->SMALL, trivial->TRIVIAL
      Rule 5 (default):           STANDARD (conservative fallback for absent/unknown)

    Returns one of: 'TRIVIAL', 'SMALL', 'STANDARD', 'COMPLEX'.
    Pure function; no side effects; stdlib only.
    """
    if ticket_type == "epic":
        return "COMPLEX"
    if size == "large":
        return "COMPLEX"
    if stakes == "high":
        return "STANDARD"
    if size == "standard":
        return "STANDARD"
    if size == "small":
        return "SMALL"
    if size == "trivial":
        return "TRIVIAL"
    return "STANDARD"  # conservative fallback for absent/unknown size


def verify_depth(lane, stakes):
    """Return "light" or "full" verify depth for the ticket's lane and stakes.

    Truth table (design.md D4 / C-9):
      lane=TRIVIAL,  stakes=low    -> "light"
      lane=TRIVIAL,  stakes=normal -> "light"
      lane=SMALL,    stakes=low    -> "light"
      lane=SMALL,    stakes=normal -> "light"
      lane=STANDARD, stakes=*      -> "full"
      lane=COMPLEX,  stakes=*      -> "full"
      any lane,      stakes=high   -> "full"  (stakes floor, AC-2)
      lane=None/unknown/absent     -> "full"  (conservative default, invariant c)

    Check stakes == "high" FIRST (floor cannot be bypassed by lane value).
    Only the exact string "high" triggers the floor; None and other strings do not.
    Only exact uppercase lane values TRIVIAL/SMALL/STANDARD/COMPLEX are recognized;
    any other string (including lowercase) is treated as unknown -> "full".

    Pure function; no I/O, no side effects; stdlib only.
    """
    # Stakes floor: high stakes always yields full regardless of lane (AC-2)
    if stakes == "high":
        return "full"
    # Lane dispatch: recognized fast-lane values
    if lane in ("TRIVIAL", "SMALL"):
        return "light"
    # Recognized full-lane values (conservative for absent/unknown lane too)
    return "full"


VERIFY_ITERATION_CAP: dict = {"light": 1, "full": 3}


# ---------------------------------------------------------------------------
# Lane-rank primitives (MAR-57 / ADR 0030)
# ---------------------------------------------------------------------------

LANE_ORDER: list = ["TRIVIAL", "SMALL", "STANDARD", "COMPLEX"]


def lane_rank(lane):
    """Return the integer rank of *lane* in LANE_ORDER (0=TRIVIAL … 3=COMPLEX).

    Rule evaluation order:
      - Recognized uppercase lane value ('TRIVIAL', 'SMALL', 'STANDARD', 'COMPLEX')
        -> its index in LANE_ORDER.
      - Absent (None), empty, or any unrecognized string (including lowercase)
        -> 2 (STANDARD rank, conservative floor — design.md invariant (c) / AC-7).

    This function is a *comparison helper* only: it never produces a lane value.
    The single authoritative producer remains derive_lane() (ADR 0030:56-61).
    Pure function; no I/O, no side effects; stdlib only.
    """
    try:
        return LANE_ORDER.index(lane)
    except (ValueError, TypeError):
        return LANE_ORDER.index("STANDARD")  # conservative floor for absent/unknown


def escalate_lane(current_lane, size, stakes, needs_design, ticket_type, settings=None):
    """Return the higher of (current_lane, candidate) as a (lane, depth, ceiling) triple.

    The candidate lane is computed exclusively via derive_lane(size, stakes,
    needs_design, ticket_type) — never hand-set (ADR 0030:56-61 / AC-4).

    Clamp semantics (upward-only, AC-1 / AC-3 / AC-7):
      - candidate rank > current rank -> escalate: return candidate lane.
      - candidate rank <= current rank -> hold: return current_lane unchanged.
      - current_lane is None/unknown -> treated as STANDARD rank (2) for comparison,
        conservative floor: a COMPLEX candidate still fires; TRIVIAL/SMALL do not.

    The returned triple is always consistent:
      lane    — the higher of current_lane or candidate (string)
      depth   — verify_depth(lane, stakes)
      ceiling — VERIFY_ITERATION_CAP[depth]

    Pure function: no file I/O, no state mutations, no side effects.
    Mirrors recommend_stakes() (acs_lib.py: "Pure function — never writes
    stakes to ticket.json or any state file").
    """
    candidate_lane = derive_lane(size, stakes, needs_design, ticket_type)
    if lane_rank(candidate_lane) > lane_rank(current_lane):
        result_lane = candidate_lane
    else:
        # Hold at current; for None/unknown current_lane fall back to the STANDARD
        # floor (the conservative default, not the candidate — AC-7 invariant (c)).
        result_lane = current_lane if current_lane in LANE_ORDER else "STANDARD"
    depth = verify_depth(result_lane, stakes)
    ceiling = VERIFY_ITERATION_CAP[depth]
    return result_lane, depth, ceiling


# Axis ordering for guard_axes (MAR-57 Spec 03 / design.md:29 invariant (e)).
_SIZE_ORDER: list = ["trivial", "small", "standard", "large"]
_STAKES_ORDER: list = ["low", "normal", "high"]


def guard_axes(current_size, current_stakes, proposed_size, proposed_stakes):
    """Return (effective_size, effective_stakes) taking the higher of each axis.

    Axis orderings (from lowest to highest rigor):
      size:   trivial < small < standard < large
      stakes: low < normal < high

    Rules (axis-level realization of design.md:29 invariant (e)):
      - None current  -> treated as the lowest known rank; any explicit proposed wins.
      - None proposed -> effective = current (absent signal leaves current unchanged).
      - Unrecognized string -> treated as the lowest known rank for that axis
        (conservative: never block an upward proposal due to an unknown value).
      - effective rank >= current rank for both axes (upward-only, never lower).

    This function is the axis-guard step in the in-loop escalation sequence:
    it must be called BEFORE escalate_lane so the axis values passed in are
    already monotone-clamped.  No automatic/unattended code path may write a
    size or stakes value that is strictly lower than the current confirmed value
    without first passing through guard_axes.

    Pure function: no I/O, no side effects; stdlib only.
    """
    def _rank(value, order):
        try:
            return order.index(value)
        except (ValueError, TypeError):
            return -1  # None / unrecognized -> below the lowest recognized value

    def _pick_higher(current, proposed, order):
        if proposed is None:
            # No new signal: leave current unchanged (or fall back to lowest if
            # current is also unknown, since there is nothing to preserve).
            return current if current is not None else order[0]
        c_rank = _rank(current, order)
        p_rank = _rank(proposed, order)
        if p_rank > c_rank:
            return proposed
        # current rank >= proposed rank (or current is None/-1): return whichever
        # is a recognized value; prefer current when both are known.
        if current is None or c_rank < 0:
            # current unknown: proposed is known and >= current rank (both -1), take it
            return proposed
        return current

    eff_size = _pick_higher(current_size, proposed_size, _SIZE_ORDER)
    eff_stakes = _pick_higher(current_stakes, proposed_stakes, _STAKES_ORDER)
    return eff_size, eff_stakes


def recommend_stakes(paths, settings):
    """Match a collection of file paths against high_stakes_paths globs from settings.

    Returns 'high' if any path matches any glob; returns 'normal' otherwise.
    Pure function — never writes stakes to ticket.json or any state file.

    Arguments:
      paths    -- iterable of file path strings (changed files, owned paths, surveyed paths).
                  Empty collection -> 'normal'.
      settings -- the merged settings dict; high_stakes_paths resolved from it
                  (falls back to DEFAULT_SETTINGS seed list if absent or settings is None).

    Returns 'high' or 'normal'. This is a RECOMMENDATION only; the caller (SKILL.md planner)
    presents it to the user. The function never silently floors a previously-confirmed value.
    """
    globs = (settings or {}).get("high_stakes_paths", DEFAULT_SETTINGS["high_stakes_paths"])
    for path in (paths or []):
        for pattern in globs:
            if fnmatch.fnmatch(path, pattern):
                return "high"
    return "normal"


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
