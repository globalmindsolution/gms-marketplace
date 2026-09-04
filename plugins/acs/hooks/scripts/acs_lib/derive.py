"""acs_lib.derive — the result-document fields the kernel computes itself (MAR-523).

`run_post` trusted `states.verifier_passed`, `states.tests.*`, `states.pr` and
`states.review.iterations` verbatim from a result document the COORDINATOR
wrote. The `/acs:create-pr` gate therefore checked whether a model had written
`true`, not whether a verifier had passed — and the metrics ledger recorded
whatever number the prose happened to carry.

Each of those four has a recorded source that does not depend on anyone
remembering correctly:

  verifier_passed      the verifier's own verdict.json (MAR-527), whose
                       `passed` is itself derived from its findings
  tests / coverage     the executors' iter-<n>-execute*.json reports, which
                       record the command run and its outcome
  pr                   the forge, through `gh pr list --head <branch>`
  review.iterations    the verify artifacts actually on disk

Derivation WINS over whatever the coordinator supplied, and a disagreement is
recorded rather than silently resolved — the point is not to be strict, it is
to make "the document said X, the artifacts said Y" visible after the fact.

A derivation that CANNOT run (no gh on PATH, no execute report) does not
invent a value: it leaves the coordinator's, and records that it could not be
checked. The single exception is `verifier_passed`, where absence is itself
the answer: no passing verdict means the gate stays shut.
"""

import json
import os
import re
import subprocess

from ._common import read_json
from . import verdict as verdict_mod

#: The keys this module owns. A coordinator may still write them -- SKILL.md
#: prose is a contract with humans too -- but what lands is computed here.
DERIVED_KEYS = ("verifier_passed", "tests", "pr", "review")

#: Only /acs:code has the verifier whose verdict gates /acs:create-pr, so only
#: its result document has a `verifier_passed` to derive.
VERDICT_SKILLS = ("code",)

_EXECUTE_RE = re.compile(r"^iter-(\d+)-execute(?:-\d+)?\.json$")
_VERIFY_RE = re.compile(r"^iter-(\d+)-(?:verify|verdict)")


def _phase_dir(tdir, skill):
    return os.path.join(tdir, "phases", skill)


def _listdir(path):
    try:
        return sorted(os.listdir(path))
    except OSError:
        return []


def execute_reports(tdir, skill):
    """[(iteration, path, doc)] for every readable execute report, ascending."""
    directory = _phase_dir(tdir, skill)
    out = []
    for name in _listdir(directory):
        match = _EXECUTE_RE.match(name)
        if not match:
            continue
        doc = read_json(os.path.join(directory, name))
        if isinstance(doc, dict):
            out.append((int(match.group(1)), os.path.join(directory, name), doc))
    return sorted(out, key=lambda item: item[0])


def review_iterations(tdir, skill):
    """How many iterations actually produced a verify artifact.

    Counted from the files on disk rather than from a number the coordinator
    kept in its head across a loop it may have re-entered."""
    seen = set()
    for name in _listdir(_phase_dir(tdir, skill)):
        match = _VERIFY_RE.match(name)
        if match:
            seen.add(int(match.group(1)))
    return len(seen)


def latest_verdict(tdir, skill):
    """(iteration, doc) for the highest iteration that has a verdict, or (None, None)."""
    best = None
    for name in _listdir(_phase_dir(tdir, skill)):
        match = re.match(r"^iter-(\d+)-verdict\.json$", name)
        if match and (best is None or int(match.group(1)) > best):
            best = int(match.group(1))
    if best is None:
        return None, None
    return best, verdict_mod.load_verdict(tdir, skill, best)


def derive_verifier_passed(tdir, skill):
    """(value, why). Absence is an answer here: no passing verdict, no gate.

    This is the one derivation that refuses to fall back on the coordinator.
    Every other key answers "what happened"; this one answers "may the next
    step run", and the safe answer to that with no evidence is no."""
    iteration, doc = latest_verdict(tdir, skill)
    if doc is None:
        return False, ("no verdict.json in %s -- the verifier writes one per iteration "
                       "(MAR-527); re-run /acs:%s" % (_phase_dir(tdir, skill), skill))
    errors = verdict_mod.validate_verdict(doc)
    if errors:
        return False, ("the iteration-%s verdict is not well formed (%s)"
                       % (iteration, "; ".join(errors)))
    passed = verdict_mod.derived_passed(doc)
    return passed, "iteration-%s verdict: %d blocking finding(s)" % (
        iteration, len(verdict_mod.blocking_findings(doc)))


def derive_tests(tdir, skill, settings=None):
    """(value, why) for states.tests, from the executors' recorded runs.

    Only the LAST iteration's reports count -- earlier ones describe a suite
    that has since changed. Within it: `failed` is the maximum any executor
    saw, because a suite that was red for anyone was red; `passed` and
    `coverage_percent` are the maxima, because within one iteration each
    executor runs the suite when its own work is done, so the largest
    observation is the latest state of the tree. `coverage_target` comes from
    settings, which is not a claim at all.
    """
    reports = execute_reports(tdir, skill)
    if not reports:
        return None, "no iter-<n>-execute*.json report to read"
    last = max(iteration for iteration, _path, _doc in reports)
    current = [(path, doc) for iteration, path, doc in reports if iteration == last]

    passed = failed = percent = None
    for _path, doc in current:
        tests = doc.get("tests") if isinstance(doc.get("tests"), dict) else {}
        coverage = doc.get("coverage") if isinstance(doc.get("coverage"), dict) else {}
        for key, value in (("passed", tests.get("passed")), ("failed", tests.get("failed"))):
            if isinstance(value, int):
                if key == "passed":
                    passed = value if passed is None else max(passed, value)
                else:
                    failed = value if failed is None else max(failed, value)
        if isinstance(coverage.get("percent"), (int, float)):
            percent = coverage["percent"] if percent is None else max(percent, coverage["percent"])

    if passed is None and failed is None and percent is None:
        return None, "iteration-%d execute reports record no tests or coverage" % last
    value = {"passed": passed, "failed": failed, "coverage_percent": percent,
             "coverage_target": (settings or {}).get("test_coverage_percent")}
    return value, "iteration-%d execute report(s): %s" % (
        last, ", ".join(os.path.basename(path) for path, _doc in current))


def gh_pr_for_branch(branch, runner=None):
    """The PR for `branch` as the forge reports it, or (None, why).

    `runner` exists for tests; production passes None and gets subprocess."""
    if not branch:
        return None, "no branch to look up"
    run = runner or (lambda argv: subprocess.run(argv, capture_output=True, text=True))
    try:
        proc = run(["gh", "pr", "list", "--head", branch, "--state", "all",
                    "--json", "number,url,headRefName"])
    except FileNotFoundError:
        return None, "gh is not on PATH, so the PR reference could not be verified"
    if proc.returncode != 0:
        return None, ("gh pr list failed (%s), so the PR reference could not be verified"
                      % (proc.stderr or proc.stdout or "").strip().splitlines()[:1])
    try:
        rows = json.loads(proc.stdout or "[]")
    except (ValueError, TypeError):
        return None, "gh pr list returned no parseable JSON"
    if not rows:
        return None, "no PR on the forge for %s" % branch
    row = rows[0]
    return ({"number": row.get("number"), "url": row.get("url"),
             "branch": row.get("headRefName") or branch},
            "gh pr list --head %s" % branch)


def derive_states(tdir, skill, result, settings=None, branch=None, pr_runner=None):
    """(derived, notes) for the four keys this module owns.

    `derived` holds only the keys that could actually be computed; `notes` maps
    every key this module considered to a one-line provenance string, including
    the ones it declined to compute and why. `run_post` merges `derived` over
    the coordinator's `states` and records `notes` on the run entry, so the
    disagreement is auditable rather than silently resolved.
    """
    supplied = (result.get("states") or {}) if isinstance(result, dict) else {}
    derived, notes = {}, {}

    if skill in VERDICT_SKILLS:
        value, why = derive_verifier_passed(tdir, skill)
        derived["verifier_passed"] = value
        notes["verifier_passed"] = why

    tests, why = derive_tests(tdir, skill, settings)
    notes["tests"] = why
    if tests is not None:
        derived["tests"] = tests

    iterations = review_iterations(tdir, skill)
    if iterations:
        review = dict(supplied.get("review") or {})
        review["iterations"] = iterations
        derived["review"] = review
        notes["review"] = "%d iteration(s) with a verify artifact on disk" % iterations
    else:
        notes["review"] = "no verify artifact on disk"

    pr, why = gh_pr_for_branch(branch, runner=pr_runner)
    notes["pr"] = why
    if pr is not None:
        derived["pr"] = pr

    return derived, notes


def disagreements(supplied, derived):
    """[(key, supplied_value, derived_value)] where the two differ.

    Reported, never silently resolved: "the document said X and the artifacts
    said Y" is the finding, and it is worth more than either value alone."""
    out = []
    for key, value in sorted(derived.items()):
        if key in supplied and supplied[key] != value:
            out.append((key, supplied[key], value))
    return out
