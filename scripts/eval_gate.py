#!/usr/bin/env python3
"""Judge a routing eval run for the release gate (ADR-0107).

`claude plugin eval` decides pass/fail per CASE: exit 1 if any case scores
below `--threshold`. That is the wrong unit for routing. A case is one prompt,
three runs, and the model is stochastic -- a skill that routes right 90% of
the time scores 3/3 on a prompt only 73% of the time, so a gate at the CLI's
default threshold of 1.0 fails almost every run whether or not anything is
wrong, and a gate nobody can pass is a gate nobody reads.

So the gate runs the CLI with `--threshold 0 --json <file>` and this script
reads the file and applies the policy:

* `negative` and `control` cases are "must never": every run must pass. A
  description that pulls a request onto an internal leg, or a skill that fires
  on a git question answered in prose, is a defect however rarely it happens.
* `description` cases are "should": a skill's runs are pooled across all of
  its prompts, and each skill must route at least `--min-skill-rate` of them
  (no skill is broken) while the suite as a whole routes at least
  `--min-suite-rate` (nothing is broadly degraded).
* `explicit` cases are not gated. A typed `/acs:<skill>` can be expanded before
  any model turn, so no Skill call happens to observe (evals/README.md).

A run counts only if the model answered: one that errored with no turn at all
(a usage limit, an auth failure) is refused, because it makes no Skill call and
a must-never grader would read that as a pass.

A run counts as routed when its score is 1.0 -- every routing case carries
exactly one grader, so a run's score is 1 or 0.

The script refuses, rather than passes, anything it cannot read: a partial run,
a result format it does not know, a case it cannot map to a skill, a gated case
missing from the run, or a file older than `--max-age-hours` (the CLI only
WARNS when it cannot write `--json`, so a stale file from an earlier run could
otherwise be judged in place of this one).

Stdlib only. Run from the repo root:

    python3 scripts/eval_gate.py plugins/acs/evals/results/release-gate-routing.json
"""

import argparse
import datetime
import fractions
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "tests", "acs"))
import eval_cases  # noqa: E402  (the strict case reader the free tests use)

#: The `--json` result schema this script was written against (claude 2.1.x).
SCHEMA_VERSION = 1
GATED_KINDS = ("description", "negative", "control")
MUST_NEVER = ("negative", "control")


class GateError(Exception):
    """The result cannot be judged; the gate fails closed."""


def _fraction(text):
    value = fractions.Fraction(text)
    if not 0 <= value <= 1:
        raise argparse.ArgumentTypeError("%s is not between 0 and 1" % text)
    return value


def load(path, now, max_age_hours):
    try:
        with open(path, encoding="utf-8") as fh:
            result = json.load(fh)
    except (OSError, ValueError) as exc:
        raise GateError("cannot read %s: %s" % (path, exc))
    if result.get("schemaVersion") != SCHEMA_VERSION:
        raise GateError("unknown result format (schemaVersion %r, expected %d)"
                        % (result.get("schemaVersion"), SCHEMA_VERSION))
    if result.get("partial"):
        raise GateError("the run is partial (%s): not every case was measured"
                        % result.get("partialReason", "reason not given"))
    try:
        started = datetime.datetime.fromisoformat(result["startedAt"].replace("Z", "+00:00"))
    except (KeyError, AttributeError, ValueError):
        raise GateError("the result has no readable startedAt")
    age = now - started
    if age > datetime.timedelta(hours=max_age_hours):
        raise GateError("the result started %s ago, more than %s hours: a stale file, "
                        "not this run" % (age, max_age_hours))
    return result


def routing_meta():
    """{case name: (kind, skill)} for every routing case in the repo."""
    return {c.name: (c.kind, c.skill) for c in eval_cases.routing_cases()}


def run_scores(case):
    """The case's run scores. A run that errored before the model answered at
    all (`turns` 0) is refused, not scored: a usage limit or an auth failure
    mid-run scores later runs without marking the run partial, and such a run
    makes no Skill call -- which a `negative` or `control` grader would read as
    a pass. A run that stopped at the one-turn limit has a turn and is scored."""
    runs = (case.get("arms") or {}).get("with")
    if not runs:
        raise GateError("case %s has no runs in the result" % case.get("name"))
    scores = []
    for run in runs:
        if not isinstance(run.get("score"), (int, float)):
            raise GateError("case %s has a run with no numeric score" % case.get("name"))
        if run.get("error") and not run.get("turns"):
            raise GateError("case %s has a run that never reached the model (%s)"
                            % (case.get("name"), run["error"]))
        scores.append(run["score"])
    return scores


def judge(result, meta, min_skill_rate, min_suite_rate):
    """(failures, report lines). An empty failure list is a pass."""
    failures, lines = [], []
    seen, per_skill = set(), {}
    for case in result.get("cases") or []:
        name = case.get("name")
        if name not in meta:
            failures.append("%s is not a routing case in this repo" % name)
            continue
        kind, skill = meta[name]
        seen.add(name)
        if kind not in GATED_KINDS:
            lines.append("  not gated   %s (%s)" % (name, kind))
            continue
        scores = run_scores(case)
        routed = sum(1 for s in scores if s >= 1)
        if kind in MUST_NEVER:
            if routed < len(scores):
                failures.append("%s (%s): %d of %d runs misrouted; must be 0"
                                % (name, kind, len(scores) - routed, len(scores)))
        else:
            hits, runs = per_skill.get(skill, (0, 0))
            per_skill[skill] = (hits + routed, runs + len(scores))

    missing = sorted(n for n, (kind, _) in meta.items() if kind in GATED_KINDS and n not in seen)
    if missing:
        failures.append("gated cases missing from the run: %s" % ", ".join(missing))

    total_hits = total_runs = 0
    for skill in sorted(per_skill):
        hits, runs = per_skill[skill]
        total_hits += hits
        total_runs += runs
        rate = fractions.Fraction(hits, runs)
        ok = rate >= min_skill_rate
        lines.append("  %s %-24s %2d/%-2d routed" % ("ok  " if ok else "FAIL", skill, hits, runs))
        if not ok:
            failures.append("%s routed %d of %d runs, below %s" % (skill, hits, runs, min_skill_rate))
    if total_runs:
        suite = fractions.Fraction(total_hits, total_runs)
        lines.append("  suite: %d/%d routed (%.1f%%)" % (total_hits, total_runs, 100.0 * float(suite)))
        if suite < min_suite_rate:
            failures.append("the suite routed %d of %d runs, below %s"
                            % (total_hits, total_runs, min_suite_rate))
    else:
        failures.append("no description case was measured")
    return failures, lines


def main(argv=None, now=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("result", help="the file `claude plugin eval --json` wrote")
    parser.add_argument("--min-skill-rate", type=_fraction, default=fractions.Fraction(2, 3))
    parser.add_argument("--min-suite-rate", type=_fraction, default=fractions.Fraction(9, 10))
    parser.add_argument("--max-age-hours", type=float, default=6.0)
    args = parser.parse_args(argv)
    now = now or datetime.datetime.now(datetime.timezone.utc)
    try:
        result = load(args.result, now, args.max_age_hours)
        failures, lines = judge(result, routing_meta(), args.min_skill_rate, args.min_suite_rate)
    except GateError as exc:
        print("routing gate: FAIL -- %s" % exc)
        return 1
    print("routing gate (skills >= %s, suite >= %s):" % (args.min_skill_rate, args.min_suite_rate))
    for line in lines:
        print(line)
    if failures:
        print("routing gate: FAIL")
        for failure in failures:
            print("  - %s" % failure)
        return 1
    print("routing gate: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
