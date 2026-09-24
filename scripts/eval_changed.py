#!/usr/bin/env python3
"""Run the evals a change affects -- locally, on your subscription quota.

The `acs-evals` pre-commit hook runs this on `git push` (and on demand with
`pre-commit run acs-evals --hook-stage manual`). It reads the branch's diff
against `origin/main`, finds the skills it changed, and runs only those skills'
eval cases, three times each, with `claude plugin eval`. It never runs the full
suite: that is the release gate's job. Nothing about the eval suite runs in CI
(ADR-0022, ADR-0108), and this refuses to run there.

**On by default.** Runs draw on the Claude subscription `claude` is logged in
with, so there is no per-run bill to guard. Turn it off, or skip it:

    git config acs.evals false         # this clone, from now on
    ACS_EVALS=0 git push                # this push only
    SKIP=acs-evals git push             # skip it once (pre-commit's own switch)

Without `claude` on PATH it says so and lets the push through.

**Only a changed skill selects anything** (`select()` below). A skill is
changed when a file under `plugins/acs/skills/<skill>/` changes, or a file it
alone owns (`OWNED`: the setup wizard and the CI templates it installs). For
each changed skill:

* if its frontmatter changed (`description`, `when_to_use`, ... -- the only
  part of a skill routing reads): its own routing cases, and the cases that
  name it as the skill a request could be stolen by or leak to -- a
  `confusable` case whose description names `/acs:<skill>` as its neighbour, a
  `negative` or `control` case whose description names it, and a `negative`
  guarding it;
* whatever the file: its behaviour suite, if it has one (`setup`,
  `create-ticket`, `code`).

Nothing else selects anything: not an edited eval case, a fixture, the shared
hook library, or the two controls that name no skill (`ignores-regex-request`,
`ignores-unrelated-request`). Those are covered by the release gate, which runs
the whole suite; the hook lists the edited cases it did not run, with the
command that runs one. `explicit` cases never run here: a typed `/acs:<skill>`
is not reliably observable (plugins/acs/evals/README.md).

**What blocks the push** -- the release gate's own rules (ADR-0107), applied to
the skills this change touches:

* a `negative` or `control` case that misroutes in any run -- a must-never;
* a skill whose selected description cases, pooled, route less than 2/3 of
  their runs (`--min-skill-rate`);
* a run that could not happen -- the plugin directory not trusted yet, a usage
  limit or auth failure, a case that failed to load, a run with no score, or a
  gated case the budget guard stopped before it ran.

`explicit` and behaviour (setup, artifact) cases below 1.0 are REPORTED, not
blocking: the first is unobservable, and the behaviour graders have not been
piloted yet.

**Runs** default to 3 (`--runs`, or `git config acs.evalsRuns`), in parallel
within a case. **Budget** is a runaway guard, not a bill: the CLI's computed
cost, capped at $25 per push (`--budget`, or `git config acs.evalsBudget`).
Must-never cases run first and behaviour cases last, so a guard that trips
usually skips only the costly behaviour cases, which is reported. If it stops a
gated routing case, the push is blocked: an unmeasured case is not a pass.

**Trust**: the CLI asks, once per plugin directory, whether you trust it, and a
hook cannot answer. Run any case once in a terminal, e.g.
`claude plugin eval plugins/acs --case ignores-regex-request --runs 1 --ablation none`.
This script never passes `--trust-plugin`.
"""

import argparse
import fractions
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
DEFAULT_BUDGET_USD = 25.0
DEFAULT_RUNS = 3

#: Skills with a behaviour suite, and the cases that exercise them.
BEHAVIOUR = {
    "setup": ("group", "setup"),
    "create-ticket": ("case", "create-ticket-artifacts"),
    "code": ("case", "resume-and-verify"),
}
#: Files outside a skill's directory that only that skill uses.
OWNED = (
    (re.compile(r"^plugins/acs/hooks/scripts/setup_wizard[^/]*\.py$"), "setup"),
    (re.compile(r"^plugins/acs/templates/ci/"), "setup"),
)
SKILL_FILE = re.compile(r"^plugins/acs/skills/([^/]+)/")
CASE_FILE = re.compile(r"^plugins/acs/evals/([^/]+)/([^/]+)/")
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

def touched_skills(paths):
    """The skills a change touches: a file in the skill's directory, or one it owns."""
    skills = set()
    for path in paths:
        m = SKILL_FILE.match(path)
        if m:
            skills.add(m.group(1))
        skills.update(skill for rx, skill in OWNED if rx.match(path))
    return skills


def names_skill(case, skill):
    """Whether a case's description names `/acs:<skill>` (not a longer name)."""
    return re.search(r"/acs:%s(?![\w-])" % re.escape(skill), case.fm.get("description", "")) is not None


def routes_for(case, skill):
    """Whether a routing case measures a change to `skill`'s frontmatter."""
    if case.group != "routing" or case.kind == "explicit":
        return False
    if case.skill == skill:
        return True
    if case.kind in MUST_NEVER or "confusable" in case.tags:
        return names_skill(case, skill)
    return False


def select(paths, described, cases=None):
    """The cases for the skills this change touches, in run order: must-never
    first, behaviour last. Nothing but a changed skill selects a case."""
    cases = cases if cases is not None else eval_cases.all_cases()
    chosen = set()
    for skill in described:
        chosen.update(c.name for c in cases if routes_for(c, skill))
    for skill in touched_skills(paths) & set(BEHAVIOUR):
        kind, target = BEHAVIOUR[skill]
        chosen.update(c.name for c in cases
                      if (c.group if kind == "group" else c.name) == target)

    by_name = {c.name: c for c in cases}

    def order(name):
        c = by_name[name]
        rank = (0 if c.kind in MUST_NEVER else 1 if c.group == "routing" else 2)
        return (rank, c.group, name)
    return [by_name[n] for n in sorted(chosen, key=order)]


def edited_cases(paths, selected, cases=None):
    """Eval cases this change edits that the selection does not run."""
    cases = cases if cases is not None else eval_cases.all_cases()
    known = {c.name for c in cases}
    running = {c.name for c in selected}
    edited = {m.group(2) for m in (CASE_FILE.match(p) for p in paths) if m}
    return sorted(edited & known - running)


# --------------------------------------------------------------------------
# Running and judging

def command(case, runs, budget_left, json_path):
    return (["claude", "plugin", "eval", PLUGIN_REL, "--case", case.name,
             "--runs", str(runs), "-j", str(min(runs, 8)),
             "--threshold", "0", "--json", json_path, "--no-publish",
             "--max-cost-usd", "%.2f" % max(budget_left, 0.01)]
            + GROUP_ARGS[case.group])


def rerun_hint(case):
    return " ".join(["claude", "plugin", "eval", PLUGIN_REL, "--case", case.name]
                    + GROUP_ARGS[case.group])


def run_case(case, runs, budget_left, workdir):
    """{"status": ok|budget|error, "scores": [per run], "cost", "failed_graders", "message"}."""
    json_path = os.path.join(workdir, case.name + ".json")
    proc = subprocess.run(command(case, runs, budget_left, json_path), cwd=REPO_ROOT,
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
    arm = ((entry or {}).get("arms") or {}).get("with") or []
    if not arm:
        return {"status": "error", "cost": cost, "message": "the result has no run for this case"}
    for run in arm:
        if run.get("error") and not run.get("turns"):
            return {"status": "error", "cost": cost,
                    "message": "a run never reached the model: %s" % run["error"]}
        score = run.get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            return {"status": "error", "cost": cost, "message": "a run has no score"}
    failed = sorted({g.get("name") for run in arm for g in run.get("graders") or []
                     if not g.get("passed") and g.get("scored", True)})
    return {"status": "ok", "cost": cost, "scores": [run["score"] for run in arm],
            "failed_graders": failed}


def gated(case):
    """Whether a miss on this case can block: must-never and description routing."""
    return case.group == "routing" and (case.kind in MUST_NEVER or case.kind == "description")


def judge(outcomes, min_skill_rate):
    """(blocking, reported) from {case: outcome} for the cases that ran."""
    blocking, reported, pools = [], [], {}
    for case, outcome in outcomes:
        scores = outcome["scores"]
        hits = sum(1 for s in scores if s >= 1)
        detail = ", ".join(outcome["failed_graders"]) or "score %.2f" % (sum(scores) / len(scores))
        if case.kind in MUST_NEVER:
            if hits < len(scores):
                blocking.append("%s (%s) misrouted in %d of %d runs: %s"
                                % (case.name, case.kind, len(scores) - hits, len(scores), detail))
        elif case.group == "routing" and case.kind == "description":
            pool = pools.setdefault(case.skill, [0, 0, []])
            pool[0] += hits
            pool[1] += len(scores)
            pool[2].append(case)
        elif hits < len(scores):
            reported.append("%s: %d of %d runs passed (%s); run it again with:\n      %s"
                            % (case.name, hits, len(scores), detail, rerun_hint(case)))
    for skill in sorted(pools):
        hits, total, cases = pools[skill]
        if fractions.Fraction(hits, total) < min_skill_rate:
            blocking.append("%s routed %d of %d runs across %s, below %s"
                            % (skill, hits, total, ", ".join(c.name for c in cases), min_skill_rate))
    return blocking, reported


def enabled(env):
    flag = env.get("ACS_EVALS")
    if flag is not None:
        return flag.strip().lower() in ("1", "true", "yes", "on")
    try:
        return git("config", "--get", "acs.evals").strip().lower() not in ("false", "0", "no", "off")
    except subprocess.CalledProcessError:
        return True  # unset: on


def configured(key, default, kind):
    try:
        return kind(git("config", "--get", key).strip())
    except (subprocess.CalledProcessError, ValueError):
        return default


def main(argv=None, env=None):
    env = os.environ if env is None else env
    parser = argparse.ArgumentParser(description="Run the evals a change affects, locally.")
    parser.add_argument("--base", default=None, help="ref to diff against (default origin/main)")
    parser.add_argument("--runs", type=int, default=None, help="runs per case (default 3)")
    parser.add_argument("--budget", type=float, default=None,
                        help="runaway guard on the CLI's computed cost (default $25)")
    parser.add_argument("--min-skill-rate", type=fractions.Fraction, default=fractions.Fraction(2, 3),
                        help="a touched skill's pooled description runs must route at least this")
    parser.add_argument("--dry-run", action="store_true", help="print the selection; run nothing")
    args = parser.parse_args(argv)

    if env.get("CI"):
        print("acs-evals: evals never run in CI (ADR-0108); nothing to do.")
        return 0
    if not args.dry_run and not enabled(env):
        print("acs-evals: off (git config acs.evals false, or ACS_EVALS=0).")
        return 0

    head = env.get("PRE_COMMIT_TO_REF") or "HEAD"
    base = base_ref(args.base)
    paths, described = changes(base, head)
    selected = select(paths, described)
    skipped_edits = edited_cases(paths, selected)
    if skipped_edits:
        shown = ", ".join(skipped_edits[:5]) + (" and %d more" % (len(skipped_edits) - 5)
                                                if len(skipped_edits) > 5 else "")
        print("acs-evals: %d edited case(s) not run -- not a skill change: %s.\n"
              "  Run one by hand: claude plugin eval %s --case <name> (each group's flags: "
              "plugins/acs/evals/README.md). The release gate runs them all."
              % (len(skipped_edits), shown, PLUGIN_REL))
    if not selected:
        print("acs-evals: this change touches no skill's routing or behaviour; nothing to run "
              "(diffed against %s)." % base)
        return 0
    runs = max(1, args.runs if args.runs is not None else configured("acs.evalsRuns", DEFAULT_RUNS, int))
    budget = args.budget if args.budget is not None else configured("acs.evalsBudget", DEFAULT_BUDGET_USD, float)
    print("acs-evals: %d case(s) for this change, %d run(s) each, guard $%.2f:"
          % (len(selected), runs, budget))
    for c in selected:
        print("  %-10s %-12s %s" % (c.group, c.kind or "", c.name))
    if args.dry_run:
        return 0
    if shutil.which("claude") is None:
        print("acs-evals: skipped -- `claude` is not on PATH, so nothing can be run.")
        return 0

    errors, outcomes, skipped, spent = [], [], [], 0.0
    workdir = tempfile.mkdtemp(prefix="acs-evals-")
    try:
        for i, case in enumerate(selected):
            if spent >= budget:
                skipped.extend(selected[i:])
                break
            outcome = run_case(case, runs, budget - spent, workdir)
            spent += outcome.get("cost", 0.0)
            if outcome["status"] == "budget":
                skipped.extend(selected[i:])
                break
            if outcome["status"] == "error":
                errors.append("%s: %s" % (case.name, outcome["message"]))
                if "not trusted" in outcome["message"]:
                    break  # every other case would fail the same way
                continue
            hits = sum(1 for s in outcome["scores"] if s >= 1)
            print("  %d/%d %s" % (hits, len(outcome["scores"]), case.name))
            outcomes.append((case, outcome))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    blocking, reported = judge(outcomes, args.min_skill_rate)
    blocking = errors + blocking
    unmeasured = [c.name for c in skipped if gated(c)]
    if unmeasured:
        blocking.append("the $%.2f guard was reached before these gated cases ran: %s. Raise it "
                        "with --budget or git config acs.evalsBudget" % (budget, ", ".join(unmeasured)))
    print("acs-evals: computed cost $%.2f (guard $%.2f)" % (spent, budget))
    for line in reported:
        print("  report: %s" % line)
    if skipped:
        print("  guard reached; not run: %s" % ", ".join(c.name for c in skipped))
    if blocking:
        print("acs-evals: FAIL (skip once with SKIP=acs-evals)")
        for line in blocking:
            print("  - %s" % line)
        return 1
    print("acs-evals: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
