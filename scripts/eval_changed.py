#!/usr/bin/env python3
"""Run the evals a change affects -- locally, opt-in, paid.

The `acs-evals` pre-commit hook runs this on `git push` (and on demand with
`pre-commit run acs-evals --hook-stage manual`). It reads the branch's diff
against `origin/main`, picks the eval cases that diff can move, and runs each
once with `claude plugin eval`. Nothing about the eval suite runs in CI
(ADR-0022, ADR-0108), and this refuses to run there.

**Off unless you turn it on** -- every case is a real, paid session, and a push
must not spend a teammate's money for them:

    git config acs.evals true          # this clone, from now on
    ACS_EVALS=1 git push                # this push only
    SKIP=acs-evals git push             # skip it once (pre-commit's own switch)

**What a change selects** (`select()` below, in order of what runs first):

* a skill's frontmatter (`description`, `when_to_use`, ...) -- the routing
  cases that probe that skill, the `confusable` cases that name it as the
  neighbour they borrow from, and every `negative` and `control` case: a
  description competes with all the others, so a new one can pull a request off
  an internal leg or fire on a question answered in prose;
* any file of a skill that has a behaviour suite (`setup`, `create-ticket`,
  `code`) -- that suite's cases;
* an eval case's files -- that case (a group's `_fixtures/`: the whole group);
* the setup wizard or the CI templates it installs -- the setup suite;
* the hook library the artifact cases play through -- the artifact suite.

`explicit` routing cases run only when their own files change: a typed
`/acs:<skill>` is not reliably observable (plugins/acs/evals/README.md).

**What blocks the push**: a `negative` or `control` case that misroutes (a
must-never, even once), or a run that could not happen -- the CLI missing, the
plugin directory not trusted yet, an auth failure, a case that failed to load.
Everything else is one run, which is not evidence, so a description case that
missed or a behaviour case below 1.0 is REPORTED with the command that runs it
three times, and the push goes ahead.

**Budget**: `--budget` (default $3, or `git config acs.evalsBudget`) caps the
whole run; each case gets what is left as its `--max-cost-usd`. Must-never
cases run first, so a budget that runs out skips the costly behaviour cases,
not the checks that block.

**Trust**: the CLI asks, once per plugin directory, whether you trust it, and a
hook cannot answer. Run any case once in a terminal, e.g.
`claude plugin eval plugins/acs --case ignores-regex-request --runs 1 --ablation none`.
This script never passes `--trust-plugin`.
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
import eval_cases  # noqa: E402  (the strict case reader the local checks use)

PLUGIN_REL = "plugins/acs"
SKILLS_PREFIX = PLUGIN_REL + "/skills/"
EVALS_PREFIX = PLUGIN_REL + "/evals/"
DEFAULT_BUDGET_USD = 3.0

#: Skills with a behaviour suite, and the cases that exercise them.
BEHAVIOUR = {
    "setup": ("group", "setup"),
    "create-ticket": ("case", "create-ticket-artifacts"),
    "code": ("case", "resume-and-verify"),
}
#: Code that a suite plays through without it being a skill's own file.
SUITE_CODE = (
    (re.compile(r"^plugins/acs/hooks/scripts/setup_wizard[^/]*\.py$"), "setup"),
    (re.compile(r"^plugins/acs/templates/ci/"), "setup"),
    (re.compile(r"^plugins/acs/hooks/scripts/(acs\.py|acs_lib/)"), "artifacts"),
)
#: How each group is run. Routing needs no baseline arm (no plugin, no route);
#: the setup suite is scored against one; the artifact cases need shell.
GROUP_ARGS = {
    "routing": ["--ablation", "none"],
    "setup": ["--scaffold", "--allow-tools", "Bash", "Write", "Edit", "--judge-model", "sonnet"],
    "artifacts": ["--scaffold", "--allow-tools", "Write", "Edit", "Bash", "--ablation", "none"],
}
MUST_NEVER = ("negative", "control")


# --------------------------------------------------------------------------
# What changed

def git(*args):
    return subprocess.run(["git"] + list(args), cwd=REPO_ROOT, capture_output=True,
                          text=True, check=True).stdout


def base_ref(preferred):
    for ref in (preferred, "origin/main", "main"):
        if ref and subprocess.run(["git", "rev-parse", "--verify", "-q", ref], cwd=REPO_ROOT,
                                  capture_output=True).returncode == 0:
            return ref
    raise SystemExit("acs-evals: no base to diff against (tried %s, origin/main, main)" % preferred)


def frontmatter(ref, path):
    try:
        text = git("show", "%s:%s" % (ref, path))
    except subprocess.CalledProcessError:
        return None  # absent at that ref
    if not text.startswith("---\n"):
        return ""
    end = text.find("\n---\n", 4)
    return text[4:end] if end >= 0 else text[4:]


def changes(base, head):
    """(changed paths, skills whose SKILL.md frontmatter changed)."""
    merge_base = git("merge-base", base, head).strip()
    paths = [p for p in git("diff", "--name-only", merge_base, head).splitlines() if p]
    described = set()
    for path in paths:
        m = re.match(r"^plugins/acs/skills/([^/]+)/SKILL\.md$", path)
        if m and frontmatter(merge_base, path) != frontmatter(head, path):
            described.add(m.group(1))
    return paths, described


# --------------------------------------------------------------------------
# What that selects

def select(paths, described, cases=None):
    """The cases to run, in run order: must-never first, behaviour last."""
    cases = cases if cases is not None else eval_cases.all_cases()
    by_name = {c.name: c for c in cases}
    chosen = set()

    def group(name):
        chosen.update(c.name for c in cases if c.group == name)

    for skill in described:
        for c in cases:
            if c.group != "routing":
                continue
            if c.kind in MUST_NEVER:
                chosen.add(c.name)
            elif c.skill == skill and c.kind != "explicit":
                chosen.add(c.name)
            elif "confusable" in c.tags and "/acs:%s " % skill in c.fm.get("description", "") + " ":
                chosen.add(c.name)
    for path in paths:
        m = re.match(r"^plugins/acs/skills/([^/]+)/", path)
        if m and m.group(1) in BEHAVIOUR:
            kind, target = BEHAVIOUR[m.group(1)]
            group(target) if kind == "group" else chosen.add(target)
        m = re.match(r"^plugins/acs/evals/([^/]+)/([^/]+)/", path)
        if m:
            group_name, case = m.groups()
            if case == "_fixtures":
                group(group_name)
            elif case in by_name:
                chosen.add(case)
        for rx, suite in SUITE_CODE:
            if rx.match(path):
                group(suite)

    def order(name):
        c = by_name[name]
        rank = (0 if c.kind in MUST_NEVER else 1 if c.group == "routing" else 2)
        return (rank, c.group, name)
    return [by_name[n] for n in sorted(chosen, key=order)]


# --------------------------------------------------------------------------
# Running and judging

def command(case, budget_left, json_path):
    return (["claude", "plugin", "eval", PLUGIN_REL, "--case", case.name, "--runs", "1",
             "--threshold", "0", "--json", json_path, "--no-publish",
             "--max-cost-usd", "%.2f" % max(budget_left, 0.01)]
            + GROUP_ARGS[case.group])


def rerun_hint(case):
    return " ".join(["claude", "plugin", "eval", PLUGIN_REL, "--case", case.name]
                    + GROUP_ARGS[case.group])


def run_case(case, budget_left, workdir):
    """{"status": ok|budget|error, "score", "cost", "failed_graders", "message"}."""
    json_path = os.path.join(workdir, case.name + ".json")
    proc = subprocess.run(command(case, budget_left, json_path), cwd=REPO_ROOT,
                          capture_output=True, text=True)
    out = (proc.stderr or "") + (proc.stdout or "")
    if "not a trusted plugin directory" in out:
        return {"status": "error", "message": "this plugin directory is not trusted yet. Run one "
                "case once in a terminal to trust it:\n      claude plugin eval %s --case "
                "ignores-regex-request --runs 1 --ablation none" % PLUGIN_REL}
    try:
        with open(json_path, encoding="utf-8") as fh:
            result = json.load(fh)
    except (OSError, ValueError):
        tail = out.strip().splitlines()[-3:]
        return {"status": "error", "message": "no result (exit %s): %s" % (proc.returncode, " | ".join(tail))}
    cost = float(result.get("costUsd") or 0)
    if result.get("partial"):
        reason = result.get("partialReason")
        if reason == "cost_ceiling":
            return {"status": "budget", "cost": cost}
        return {"status": "error", "cost": cost, "message": "the run stopped: %s" % reason}
    entry = next((c for c in result.get("cases") or [] if c.get("name") == case.name), None)
    runs = ((entry or {}).get("arms") or {}).get("with") or []
    if not runs:
        return {"status": "error", "cost": cost, "message": "the result has no run for this case"}
    run = runs[0]
    if run.get("error") and not run.get("turns"):
        return {"status": "error", "cost": cost, "message": "the run never reached the model: %s" % run["error"]}
    failed = [g.get("name") for g in run.get("graders") or [] if not g.get("passed") and g.get("scored", True)]
    return {"status": "ok", "cost": cost, "score": run.get("score", 0), "failed_graders": failed}


def enabled(env):
    flag = env.get("ACS_EVALS")
    if flag is not None:
        return flag.strip().lower() in ("1", "true", "yes", "on")
    try:
        return git("config", "--get", "acs.evals").strip().lower() == "true"
    except subprocess.CalledProcessError:
        return False


def configured_budget():
    try:
        return float(git("config", "--get", "acs.evalsBudget").strip())
    except (subprocess.CalledProcessError, ValueError):
        return DEFAULT_BUDGET_USD


def main(argv=None, env=None):
    env = os.environ if env is None else env
    parser = argparse.ArgumentParser(description="Run the evals a change affects (local, opt-in, paid).")
    parser.add_argument("--base", default=None, help="ref to diff against (default origin/main)")
    parser.add_argument("--budget", type=float, default=None, help="USD cap for the whole run")
    parser.add_argument("--dry-run", action="store_true", help="print the selection; run nothing")
    args = parser.parse_args(argv)

    if env.get("CI"):
        print("acs-evals: evals never run in CI (ADR-0108); nothing to do.")
        return 0
    if not args.dry_run and not enabled(env):
        print("acs-evals: off. Turn it on with `git config acs.evals true` "
              "(each case is a paid session).")
        return 0

    head = env.get("PRE_COMMIT_TO_REF") or "HEAD"
    base = base_ref(args.base)
    paths, described = changes(base, head)
    selected = select(paths, described)
    if not selected:
        print("acs-evals: this change moves no eval case (diffed against %s)." % base)
        return 0
    budget = args.budget if args.budget is not None else configured_budget()
    print("acs-evals: %d case(s) for this change, 1 run each, budget $%.2f:" % (len(selected), budget))
    for c in selected:
        print("  %-10s %-12s %s" % (c.group, c.kind or "", c.name))
    if args.dry_run:
        return 0
    if shutil.which("claude") is None:
        print("acs-evals: FAIL -- `claude` is not on PATH. Install Claude Code, or skip this "
              "push with SKIP=acs-evals.")
        return 1

    blocking, reported, skipped, spent = [], [], [], 0.0
    workdir = tempfile.mkdtemp(prefix="acs-evals-")
    try:
        for i, case in enumerate(selected):
            if spent >= budget:
                skipped.extend(c.name for c in selected[i:])
                break
            outcome = run_case(case, budget - spent, workdir)
            spent += outcome.get("cost", 0.0)
            if outcome["status"] == "budget":
                skipped.extend(c.name for c in selected[i:])
                break
            if outcome["status"] == "error":
                blocking.append("%s: %s" % (case.name, outcome["message"]))
                if "not trusted" in outcome["message"]:
                    break  # every other case would fail the same way
                continue
            ok = outcome["score"] >= 1
            print("  %s %s  $%.2f" % ("ok  " if ok else "MISS", case.name, outcome.get("cost", 0.0)))
            if ok:
                continue
            detail = ", ".join(outcome["failed_graders"]) or "score %.2f" % outcome["score"]
            if case.kind in MUST_NEVER:
                blocking.append("%s (%s) misrouted: %s" % (case.name, case.kind, detail))
            else:
                reported.append("%s: %s -- one run is not evidence; run it 3 times:\n      %s"
                                % (case.name, detail, rerun_hint(case)))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    print("acs-evals: spent $%.2f of $%.2f" % (spent, budget))
    for line in reported:
        print("  report: %s" % line)
    if skipped:
        print("  budget reached; not run: %s" % ", ".join(skipped))
    if blocking:
        print("acs-evals: FAIL (skip once with SKIP=acs-evals)")
        for line in blocking:
            print("  - %s" % line)
        return 1
    print("acs-evals: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
