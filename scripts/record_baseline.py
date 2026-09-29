#!/usr/bin/env python3
"""Record the reference transcript a behaviour case's `baseline` grader compares against.

A `baseline` grader (plugin-evals reference) has a judge decide whether a run
satisfies the case's criteria at least as well as a reference transcript,
`baseline_file`, a `.jsonl` in the case directory. The CLI refuses a case whose
`baseline_file` is missing, so the grader and its transcript arrive together,
and only this script writes either:

1. run the case ONCE with the plugin under test (`--runs 1 --keep-temp`);
2. refuse the run unless it is clean -- every grader passed, and no error but
   the turn limit -- because a reference that failed its own graders would
   teach the judge the wrong answer;
3. copy the run's trace to `<case>/baseline.jsonl`;
4. write `<case>/graders/matches-baseline.md`: `type: baseline`,
   `baseline_file: baseline.jsonl`, and the case's `baseline.criteria.md` as
   the criteria.

Behaviour runs need Claude Code's Bash sandbox, which needs user namespaces:
record on a host where `claude plugin eval` can run Bash (a Mac, or Linux with
bubblewrap, socat and unprivileged user namespaces). Nothing here runs in CI
(ADR-0108). Read the trace before committing it: it is a real session.

    python3 scripts/record_baseline.py create-prd-new-product
    python3 scripts/record_baseline.py --missing      # every case without one yet
    python3 scripts/record_baseline.py --missing --dry-run

Stdlib only. Run from the repo root.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "tests", "evals"))
import eval_cases as ec  # noqa: E402

PLUGIN_REL = "plugins/acs"
BASELINE_FILE = "baseline.jsonl"
CRITERIA_FILE = "baseline.criteria.md"
GRADER_FILE = "matches-baseline.md"
#: The groups whose cases grade what a skill DID; routing grades a route, with
#: one free grader per case, and takes no baseline (evals/README.md).
BEHAVIOUR_GROUPS = ("behaviour", "setup", "artifacts")
#: How a recording run is made: one arm (the reference is the plugin's own
#: run), the case's scaffold, and the shell and file tools a skill needs.
RUN_ARGS = ["--scaffold", "--allow-tools", "Bash", "Write", "Edit",
            "--ablation", "none", "--judge-model", "sonnet",
            "--runs", "1", "-j", "1", "--threshold", "0", "--no-publish", "--keep-temp"]
#: See scripts/eval_changed.py: the sandbox's memory directory is always empty.
EVAL_ENV = {"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"}
TURN_LIMIT = re.compile(r"(?i)max(?:imum)? (?:number of )?turns")


class RecordError(Exception):
    """This case's run cannot be a reference."""


def behaviour_cases():
    return sorted((c for c in ec.all_cases() if c.group in BEHAVIOUR_GROUPS),
                  key=lambda c: c.name)


def has_baseline(case):
    return os.path.isfile(os.path.join(case.path, BASELINE_FILE))


def grader_text(criteria):
    return ("---\ntype: baseline\nbaseline_file: %s\n---\n\n%s\n"
            % (BASELINE_FILE, criteria.strip()))


def read_criteria(case):
    path = os.path.join(case.path, CRITERIA_FILE)
    if not os.path.isfile(path):
        raise RecordError("%s has no %s" % (case.name, CRITERIA_FILE))
    with open(path, encoding="utf-8") as fh:
        text = fh.read().strip()
    if not text:
        raise RecordError("%s: %s is empty" % (case.name, CRITERIA_FILE))
    return text


def clean_run(case, result):
    """The one run of `case` in a `--json` result, if it can be a reference."""
    runs = next((c.get("arms", {}).get("with") or [] for c in result.get("cases") or []
                 if c.get("name") == case.name), [])
    if len(runs) != 1:
        raise RecordError("%s: expected one run, got %d" % (case.name, len(runs)))
    run = runs[0]
    error = run.get("error")
    if error and not TURN_LIMIT.search(error):
        raise RecordError("%s: the run errored (%s)" % (case.name, error))
    failed = [g.get("name") for g in run.get("graders") or []
              if g.get("scored", True) and not g.get("passed")]
    if failed:
        raise RecordError("%s: graders failed on the run: %s" % (case.name, ", ".join(failed)))
    trace = run.get("tracePath")
    if not trace or not os.path.isfile(trace):
        raise RecordError("%s: the run's trace is gone (%s)" % (case.name, trace))
    return trace


def record(case, dry_run=False):
    criteria = read_criteria(case)
    if dry_run:
        print("would record %s" % case.name)
        return
    tmp = tempfile.mkdtemp(prefix="record-baseline-")
    kept = []
    try:
        out = os.path.join(tmp, "result.json")
        cmd = ["claude", "plugin", "eval", PLUGIN_REL, "--case", case.name, "--json", out] + RUN_ARGS
        proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True,
                              env=dict(os.environ, **EVAL_ENV))
        if not os.path.isfile(out):
            raise RecordError("%s: no result (%s)" % (case.name, (proc.stderr or proc.stdout)[-300:]))
        with open(out, encoding="utf-8") as fh:
            result = json.load(fh)
        kept = kept_dirs(result)
        trace = clean_run(case, result)
        shutil.copyfile(trace, os.path.join(case.path, BASELINE_FILE))
        gdir = os.path.join(case.path, "graders")
        os.makedirs(gdir, exist_ok=True)
        with open(os.path.join(gdir, GRADER_FILE), "w", encoding="utf-8") as fh:
            fh.write(grader_text(criteria))
        print("recorded %s" % case.name)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        for path in kept:
            # --keep-temp leaves the run's directory with closed modes; open
            # them, then remove only what THIS run kept.
            subprocess.run(["chmod", "-R", "u+rwX", path], capture_output=True)
            shutil.rmtree(path, ignore_errors=True)


def kept_dirs(result):
    """The per-run directories --keep-temp left: the parent of each run's
    `out/`, when it is a `claude-eval-*` directory."""
    out = []
    for case in result.get("cases") or []:
        for run in (case.get("arms") or {}).get("with") or []:
            trace = run.get("tracePath") or ""
            root = os.path.dirname(os.path.dirname(trace))
            if os.path.basename(root).startswith("claude-eval-") and root not in out:
                out.append(root)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("cases", nargs="*", help="case names to record")
    parser.add_argument("--missing", action="store_true", help="every behaviour case without a baseline")
    parser.add_argument("--dry-run", action="store_true", help="say what would be recorded; run nothing")
    args = parser.parse_args(argv)
    known = {c.name: c for c in behaviour_cases()}
    names = list(args.cases)
    if args.missing:
        names += [n for n, c in sorted(known.items()) if not has_baseline(c) and n not in names]
    unknown = [n for n in names if n not in known]
    if unknown:
        print("not a behaviour case: %s" % ", ".join(unknown))
        return 2
    if not names:
        print("nothing to record")
        return 0
    failures = []
    for name in names:
        try:
            record(known[name], dry_run=args.dry_run)
        except RecordError as exc:
            failures.append(str(exc))
            print("NOT recorded: %s" % exc)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
