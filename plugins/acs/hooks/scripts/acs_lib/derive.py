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
from datetime import datetime, timedelta, timezone

#: A forge lookup on the post-hook critical path. Unbounded, a hung gh hung
#: every skill's post hook; the repo's other probing call site uses 5s.
GH_TIMEOUT_SECONDS = 10

from ._common import read_json
from .repo import gh_failure_hint
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


def latest_verdict(tdir, skill, since=None):
    """(iteration, doc) for the highest iteration that has a verdict, or (None, None).

    `since` is an ISO timestamp -- the current run's `started_at`. Verdicts
    written before it belong to a PREVIOUS run and are ignored: nothing clears
    phase artifacts between runs, and re-running /acs:code is a documented
    flow, so without this a stale pass at a higher iteration number silently
    beat this run's fail."""
    best = None
    for name in _listdir(_phase_dir(tdir, skill)):
        match = re.match(r"^iter-(\d+)-verdict\.json$", name)
        if not match:
            continue
        iteration = int(match.group(1))
        if since and not _written_since(_phase_dir(tdir, skill), name, since):
            continue
        if best is None or iteration > best:
            best = iteration
    if best is None:
        return None, None
    return best, verdict_mod.load_verdict(tdir, skill, best)


def _written_since(directory, name, since):
    """Was this artifact written at or after `since`? Unreadable mtime = no.

    Fail-closed on purpose: an artifact we cannot date cannot be shown to
    belong to this run, and this is the one derivation where "no evidence"
    must mean "no"."""
    try:
        mtime = datetime.fromtimestamp(os.path.getmtime(os.path.join(directory, name)),
                                       timezone.utc)
    except OSError:
        return False
    try:
        floor = datetime.fromisoformat(str(since).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return True  # no usable floor: do not silently discard every verdict
    if floor.tzinfo is None:
        floor = floor.replace(tzinfo=timezone.utc)
    return mtime >= floor - timedelta(seconds=5)  # filesystem granularity


def derive_verifier_passed(tdir, skill, ticket_id=None, since=None):
    """(value, why). Absence is an answer here: no passing verdict, no gate.

    This is the one derivation that refuses to fall back on the coordinator.
    Every other key answers "what happened"; this one answers "may the next
    step run", and the safe answer to that with no evidence is no.

    Three things have to hold, and each was a way in before:
      * the verdict belongs to THIS run (`since`), not one left behind by a
        previous /acs:code on the same ticket;
      * it is ABOUT this ticket and skill (`ticket_id`) -- only its path was
        ever checked, so a document naming another ticket was accepted;
      * it is COMPLETE -- validate_verdict now requires every owed dimension,
        so a one-dimension document no longer reads as a clean review.
    """
    iteration, doc = latest_verdict(tdir, skill, since=since)
    if doc is None:
        return False, ("no verdict.json for this run in %s -- the verifier writes one "
                       "per iteration (MAR-527); re-run /acs:%s"
                       % (_phase_dir(tdir, skill), skill))
    errors = verdict_mod.validate_verdict(doc, skill=skill, ticket_id=ticket_id,
                                          iteration=iteration)
    if errors:
        return False, ("the iteration-%s verdict is not usable (%s)"
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

    # ONE report supplies the numbers, as a coherent set. Taking the max of
    # each field independently synthesised rows no single run produced (e.g.
    # passed 84 alongside failed 2), and for coverage it simply recorded the
    # most flattering observation -- coverage is not monotonic in time, so
    # "the largest is the latest" does not follow.
    def _sort_key(item):
        path, _doc = item
        try:
            return (os.path.getmtime(path), path)
        except OSError:
            return (0.0, path)

    chosen_path, chosen = sorted(current, key=_sort_key)[-1]
    tests = chosen.get("tests") if isinstance(chosen.get("tests"), dict) else {}
    coverage = chosen.get("coverage") if isinstance(chosen.get("coverage"), dict) else {}

    value, sources = {}, [os.path.basename(chosen_path)]
    if isinstance(tests.get("passed"), int):
        value["passed"] = tests["passed"]
    if isinstance(tests.get("failed"), int):
        value["failed"] = tests["failed"]
    if isinstance(coverage.get("percent"), (int, float)):
        value["coverage_percent"] = coverage["percent"]

    # A suite that was red for ANY executor in this iteration was red, even if
    # the report we took the rest from happened to be green. This is the one
    # cross-report rule, and it can only ever make the answer worse.
    for path, doc in current:
        other = doc.get("tests") if isinstance(doc.get("tests"), dict) else {}
        if isinstance(other.get("failed"), int) and other["failed"] > value.get("failed", 0):
            value["failed"] = other["failed"]
            if os.path.basename(path) not in sources:
                sources.append(os.path.basename(path))

    target = (settings or {}).get("test_coverage_percent")
    if target is not None:
        value["coverage_target"] = target

    if not value:
        return None, "iteration-%d execute reports record no tests or coverage" % last

    # AC-2 asks for numbers from recorded COMMAND OUTPUT. Carrying the command
    # into the provenance is what makes that checkable: a report with numbers
    # and no command is not the same evidence as one backed by a real run.
    commands = []
    for key, holder in (("tests", tests), ("coverage", coverage)):
        recorded = holder.get("commands") or holder.get("command")
        if isinstance(recorded, str) and recorded.strip():
            commands.append("%s: %s" % (key, recorded.strip()))
        elif isinstance(recorded, list) and recorded:
            commands.append("%s: %s" % (key, "; ".join(str(c) for c in recorded)))
    provenance = "iteration-%d execute report(s): %s" % (last, ", ".join(sources))
    provenance += (" [%s]" % " | ".join(commands)) if commands else \
                  " [no command recorded -- numbers are unbacked]"
    return value, provenance


def gh_pr_for_branch(branch, runner=None):
    """The PR for `branch` as the forge reports it, or (None, why).

    `runner` exists for tests; production passes None and gets subprocess."""
    if not branch:
        return None, "no branch to look up"
    run = runner or (lambda argv: subprocess.run(argv, capture_output=True, text=True,
                                                 timeout=GH_TIMEOUT_SECONDS))
    try:
        # baseRefName is requested because states.pr's documented shape is
        # {number, url, branch, base} and this value REPLACES the coordinator's;
        # without it, `base` was silently dropped. state is requested because
        # rows[0] of a --state all answer can be a CLOSED PR.
        proc = run(["gh", "pr", "list", "--head", branch, "--state", "all",
                    "--json", "number,url,headRefName,baseRefName,state"])
    except FileNotFoundError:
        return None, "gh is not on PATH, so the PR reference could not be verified"
    except (OSError, subprocess.SubprocessError) as exc:
        # Every failure mode of the call, not just a missing binary: a
        # non-executable gh raises PermissionError, and a hung one raises
        # TimeoutExpired. Either used to propagate out of a derivation that
        # runs BEFORE finalize_run, stranding the run in_progress with the lock
        # still held and losing the coordinator's result document entirely.
        return None, ("gh pr list could not run (%s), so the PR reference could not "
                      "be verified" % type(exc).__name__)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        first = detail.splitlines()[0] if detail else "no output"
        hint = gh_failure_hint(detail)
        return None, ("gh pr list failed (%s), so the PR reference could not be "
                      "verified%s" % (first, ". %s" % hint if hint else ""))
    try:
        rows = json.loads(proc.stdout or "[]")
    except (ValueError, TypeError):
        return None, "gh pr list returned no parseable JSON"
    if not isinstance(rows, list) or not rows:
        return None, "no PR on the forge for %s" % branch
    # Prefer an OPEN PR. rows[0] of a --state all answer is whatever the forge
    # listed first, which can be a closed PR from an earlier attempt on the
    # same branch -- and that value flows into ticket.status, the pr_created
    # metrics, and gate_merge_pr, which accepts any pr carrying a number.
    open_rows = [r for r in rows if isinstance(r, dict)
                 and str(r.get("state") or "").upper() == "OPEN"]
    row = (open_rows or [r for r in rows if isinstance(r, dict)])[0]
    value = {"number": row.get("number"), "url": row.get("url"),
             "branch": row.get("headRefName") or branch}
    if row.get("baseRefName"):
        value["base"] = row["baseRefName"]
    return value, "gh pr list --head %s (%s)" % (
        branch, "open" if open_rows else "no open PR; reporting %s" % row.get("state"))


def derive_states(tdir, skill, result, settings=None, branch=None, pr_runner=None,
                  ticket_id=None, since=None):
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
        value, why = derive_verifier_passed(tdir, skill, ticket_id=ticket_id, since=since)
        derived["verifier_passed"] = value
        notes["verifier_passed"] = why

    tests, why = derive_tests(tdir, skill, settings)
    notes["tests"] = why
    if tests is not None:
        # MERGED over the supplied dict, not substituted for it. derive_tests
        # returns only the keys it could actually compute, and run_post applies
        # this with states.update(), so replacing wholesale nulled real numbers
        # the coordinator had -- contradicting this module's own contract that
        # a derivation which cannot run leaves the supplied value alone.
        merged = dict(supplied.get("tests") or {})
        merged.update(tests)
        derived["tests"] = merged

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
        # Merged, like `review` above and for the same reason: this value
        # REPLACED the coordinator's dict, so any key the forge query does not
        # return was silently dropped. The sibling review derivation already
        # merges and has a test saying a key this module does not own must
        # survive; `pr` had neither.
        merged = dict(supplied.get("pr") or {})
        merged.update(pr)
        derived["pr"] = merged

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
