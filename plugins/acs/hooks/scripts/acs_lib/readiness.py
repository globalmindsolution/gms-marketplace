"""acs_lib.readiness — is this PR mergeable? (MAR-524)

merge-pr/SKILL.md spelled out four readiness dimensions as prose, leaving the
model to re-derive a decision table from `gh pr view --json` on every run. The
table is a pure function of that JSON, and a pure function is exactly the thing
a coordinator should not be re-deriving: two runs over the same PR could reach
different verdicts, and neither would be reviewable.

The judgment that is NOT mechanical stays in the skill: whether to wait for a
reviewer, what to tell the user when a merge is refused, and the ADR-0028
rationale for requiring an approving review at all. What lives here is only the
part with one right answer.

Nothing in this module performs I/O — it takes a parsed `gh pr view` document
and the exit status of `gh pr checks --required`, so a verdict is reproducible
from a recorded fixture with no network.
"""


#: The complete set, in report order. merge-pr's state file records exactly
#: these keys; a fifth dimension would be a schema change, not an addition here
#: (an e2e suite wired as a REQUIRED status check is enforced through `ci`).
DIMENSIONS = ("ci", "approvals", "conflicts", "protections")

#: What the three verdicts mean to the caller:
#:   ready         — all four dimensions pass; merge.
#:   update-branch — only the base being ahead stands in the way, and the other
#:                   three pass: the BEHIND carve-out (Step 1a) applies.
#:   blocked       — at least one dimension fails: a REPORT-ONLY stop.
VERDICTS = ("ready", "update-branch", "blocked")

#: Check conclusions that do not block a merge. NEUTRAL and SKIPPED are
#: successes as far as GitHub's own merge button is concerned.
PASSING_CONCLUSIONS = frozenset({"SUCCESS", "NEUTRAL", "SKIPPED"})
#: StatusContext states that mean "no answer yet", not "failed".
PENDING_STATES = frozenset({"PENDING", "EXPECTED"})
#: CheckRun statuses that mean the run has not finished.
#: The non-terminal check states GitHub reports. `check_state` treats anything
#: that is not COMPLETED as pending, which is the fail-closed reading and the
#: one that matters; this set names the states that reading covers, and is
#: asserted against it so the two cannot drift. (It was previously defined,
#: re-exported, and read by nothing.)
PENDING_STATUSES = frozenset({"QUEUED", "IN_PROGRESS", "WAITING", "PENDING", "REQUESTED"})

#: The `gh pr view --json` fields this module reads. The CLI asks for exactly
#: these, so a fixture recorded by one is complete for the other.
PR_VIEW_FIELDS = ("state", "isDraft", "mergeable", "mergeStateStatus", "reviewDecision",
                  "statusCheckRollup", "baseRefName", "headRefName", "url", "number")

#: The fields a verdict actually rests on. A recording missing any of them
#: cannot support a decision, and the module's own rule -- "an unreadable check
#: is not a passing one" -- was applied to `mergeable` alone: a missing `state`,
#: `isDraft` or `mergeStateStatus` passed OPEN, so a two-field document replayed
#: through `--from` returned "ready" with every dimension "pass". That path is
#: exactly the audit mechanism AC-2 designates, which makes a truncated fixture
#: the most dangerous input this function takes.
DECISION_FIELDS = ("state", "isDraft", "mergeable", "mergeStateStatus",
                   "reviewDecision", "statusCheckRollup")


def check_name(entry):
    """A check's display name. CheckRun uses `name`, StatusContext `context`."""
    return entry.get("name") or entry.get("context") or "<unnamed check>"


def check_state(entry):
    """'pass' | 'fail' | 'pending' for one statusCheckRollup entry.

    Two shapes come back in the same list. A CheckRun carries `status` plus
    `conclusion` and is only judged once status is COMPLETED; a StatusContext
    carries `state` alone. An entry with neither is `pending` rather than
    `pass`: an unreadable check is not a passing one.
    """
    status = (entry.get("status") or "").upper()
    conclusion = (entry.get("conclusion") or "").upper()
    state = (entry.get("state") or "").upper()
    if status:
        if status != "COMPLETED":
            return "pending"
        return "pass" if conclusion in PASSING_CONCLUSIONS else "fail"
    if state:
        if state in PENDING_STATES:
            return "pending"
        return "pass" if state in PASSING_CONCLUSIONS else "fail"
    return "pending"


def classify_checks(rollup):
    """Split a statusCheckRollup into required/optional x pass/fail/pending.

    `isRequired` is what GitHub reports for the PR's base-branch protection.
    An entry without it counts as NOT required — the `gh pr checks --required`
    exit code is the second, independent signal for that case, and the `ci`
    dimension consults both.
    """
    out = {"required": {"pass": [], "fail": [], "pending": []},
           "optional": {"pass": [], "fail": [], "pending": []}}
    for entry in rollup or []:
        if not isinstance(entry, dict):
            continue
        bucket = "required" if entry.get("isRequired") is True else "optional"
        out[bucket][check_state(entry)].append(check_name(entry))
    return out


#: What `gh pr checks --required` says when the --required filter selects
#: nothing. Both strings are present in the shipped gh binary. A repo with no
#: branch protection is explicitly supported (/acs:setup documents enforcement
#: as advisory until an admin enables it, and ADR-0048 says
#: /acs:standardize-project never wires protection itself), so treating this
#: exit as a CI FAILURE made every PR on such a repo permanently unmergeable,
#: with a reason naming no check and carrying no gh output.
NO_REQUIRED_CHECKS_MARKERS = ("no required checks reported on the",
                              "no checks reported on the")


def _ci(pr, required_checks_ok):
    checks = classify_checks(pr.get("statusCheckRollup"))
    if checks["required"]["fail"]:
        return "fail: required check(s) failing: %s" % ", ".join(sorted(checks["required"]["fail"])), checks
    if checks["required"]["pending"]:
        return "fail: required check(s) still running: %s" % ", ".join(sorted(checks["required"]["pending"])), checks
    # required_checks_ok is a tri-state plus an explanation: True (green),
    # None (not run / not applicable), or a (False, detail) pair.
    if isinstance(required_checks_ok, tuple):
        ok, detail = required_checks_ok
    else:
        ok, detail = required_checks_ok, ""
    if ok is False:
        lowered = (detail or "").lower()
        if any(marker in lowered for marker in NO_REQUIRED_CHECKS_MARKERS):
            return "pass", checks  # nothing required is not something failing
        return ("fail: `gh pr checks --required` exited non-zero: %s"
                % (detail.strip().splitlines()[0] if detail.strip() else "no output")), checks
    return "pass", checks


def _approvals(pr):
    """ADR-0028: an approving review is required for EVERY merge, which is
    stricter than the branch protection /acs:setup offers. The skill carries
    the rationale; this only reports which of the three not-approved states
    applies, because "no review required by the repo" and "changes requested"
    read very differently to whoever has to act on the refusal."""
    decision = (pr.get("reviewDecision") or "").upper()
    if decision == "APPROVED":
        return "pass"
    if decision == "CHANGES_REQUESTED":
        return "fail: CHANGES_REQUESTED — a reviewer has requested changes"
    if decision == "REVIEW_REQUIRED":
        return "fail: REVIEW_REQUIRED — no approving review yet"
    return ("fail: no approving review (this repo requires none, but an "
            "agent-invoked merge must carry one — ADR-0028)")


def _conflicts(pr):
    mergeable = (pr.get("mergeable") or "").upper()
    merge_state = (pr.get("mergeStateStatus") or "").upper()
    if merge_state == "DIRTY":
        return "fail: DIRTY — the branch conflicts with its base"
    if mergeable == "MERGEABLE":
        return "pass"
    if mergeable == "CONFLICTING":
        return "fail: CONFLICTING — the branch conflicts with its base"
    # UNKNOWN means GitHub has not finished computing mergeability. Reporting
    # it as a pass would merge on no evidence, so it refuses and says why.
    return ("fail: mergeable is %s — GitHub has not finished computing "
            "mergeability; re-invoke once it settles" % (mergeable or "absent"))


def _protections(pr, others_pass):
    """`state`/`isDraft` live here with BLOCKED and BEHIND because all four are
    reasons GitHub itself would refuse the merge button.

    BEHIND is the one non-flat case: when the other three dimensions pass it
    routes to the update-branch carve-out instead of failing, which is why this
    takes `others_pass` rather than being a function of the PR alone."""
    state = (pr.get("state") or "").upper()
    if state and state != "OPEN":
        return "fail: PR state is %s, not OPEN" % state
    if pr.get("isDraft") is True:
        return "fail: the PR is a draft"
    merge_state = (pr.get("mergeStateStatus") or "").upper()
    if merge_state == "BLOCKED":
        return "fail: BLOCKED — unmet branch protection rules that cannot be auto-resolved"
    if merge_state == "BEHIND":
        if others_pass:
            return "behind: the base is ahead — routes to the update-branch carve-out"
        return "fail: BEHIND"
    return "pass"


def merge_readiness(pr, required_checks_ok=None):
    """The four readiness dimensions and one overall verdict, as data.

    `pr` is the parsed `gh pr view --json <PR_VIEW_FIELDS>` document.
    `required_checks_ok` is the exit status of `gh pr checks --required` as a
    bool, or None when it was not run — the rollup's own `isRequired` flags
    decide on their own in that case.

    Returns {"dimensions", "failed", "verdict", "ready", "behind",
    "stop_reason", "info_findings", "checks"}. `verdict` is one of VERDICTS;
    `ready` is true only for "ready". `stop_reason` is the sentence merge-pr
    puts in its result document, and is None unless the verdict is "blocked".
    """
    missing = [f for f in DECISION_FIELDS if f not in (pr or {})]
    if missing:
        # Fail closed, uniformly. Reporting "ready" from a document that never
        # carried the evidence is worse than refusing: it merges on no evidence,
        # which is the one outcome this module says it will not produce.
        reason = ("the PR recording is missing %s, so readiness cannot be "
                  "judged from it" % ", ".join(missing))
        return {
            "dimensions": {name: "fail: %s" % reason for name in DIMENSIONS},
            "failed": list(DIMENSIONS), "verdict": "blocked", "ready": False,
            "behind": False, "stop_reason": reason, "info_findings": [],
            "checks": classify_checks(None),
        }

    dimensions = {}
    dimensions["ci"], checks = _ci(pr, required_checks_ok)
    dimensions["approvals"] = _approvals(pr)
    dimensions["conflicts"] = _conflicts(pr)
    others_pass = all(dimensions[name] == "pass" for name in ("ci", "approvals", "conflicts"))
    dimensions["protections"] = _protections(pr, others_pass)

    failed = [name for name in DIMENSIONS if dimensions[name].startswith("fail")]
    behind = dimensions["protections"].startswith("behind")
    if failed:
        verdict = "blocked"
    elif behind:
        verdict = "update-branch"
    else:
        verdict = "ready"

    stop_reason = None
    if verdict == "blocked":
        stop_reason = "readiness failed: %s" % "; ".join(
            "%s %s" % (name, dimensions[name].split("fail: ", 1)[-1]) for name in failed)

    info = ["non-required check %s is %s" % (name, state)
            for state in ("fail", "pending")
            for name in sorted(checks["optional"][state])]

    return {
        "dimensions": dimensions,
        "failed": failed,
        "verdict": verdict,
        "ready": verdict == "ready",
        "behind": behind,
        "stop_reason": stop_reason,
        "info_findings": info,
        "checks": checks,
    }
