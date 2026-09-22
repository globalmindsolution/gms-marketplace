#!/usr/bin/env python3
"""Measure the code-verifier's catch rate on the seeded defects (PAID).

    python3 runner/verifier_catch_rate.py --dry-run           # the plan, no spending
    python3 runner/verifier_catch_rate.py --defect DEFECT-*   # a subset
    python3 runner/verifier_catch_rate.py                     # all seven, once each

Protocol, per defect: build an `app-ticketed` sandbox (the fixture app with
TKT-1 minted), create the ticket branch /acs:code will reuse, commit the
defect's green-but-wrong changeset on it, then run one headless `/acs:code
TKT-1` session. The verifier judges `git diff main...HEAD`, which carries the
seeded commit alongside the executor's own work, so the question this answers
is exactly the one the plan asks: does the owning dimension produce a finding
of the expected severity? The verdict is read from the partition's
`phases/code/iter-*-verdict.json` — the verifier's own document, never the
session's prose.

Output: results/verifier-catch-rate.json with one record per defect (caught,
the findings seen, cost, seconds) and a per-dimension catch rate. One run per
defect is a screen, not a statistic; `--runs 3` is the number to quote.
"""

import argparse
import datetime
import glob
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from defects import apply, load_all  # noqa: E402
from harness import BuildError, Sandbox, _GIT_ENV, resolve_build  # noqa: E402
from measure_skills import session_once  # noqa: E402

PROMPT = ("Run the /acs:code skill for ticket TKT-1. Determine everything you need from the "
          "acs workspace state and the ticket. Do not ask me anything. Complete the code TDD "
          "cycle including the verifier.")


def judge(defect, verdicts):
    """(caught, matched_findings) — pure, so the rule is testable.

    A defect is caught when any verdict carries a finding whose dimension names
    the expected one (case-insensitive prefix match on the charter name) at the
    expected severity or stricter (a blocking finding satisfies an expected
    info; the reverse does not).
    """
    want = defect["dimension"].lower()
    want_sev = defect["expected_severity"]
    matched = []
    for doc in verdicts:
        for f in doc.get("findings") or []:
            dim = str(f.get("dimension") or "").lower()
            sev = f.get("severity")
            if not (dim.startswith(want) or want.startswith(dim.split(" ")[0] if dim else "\0")):
                continue
            if want_sev == "blocking" and sev != "blocking":
                continue
            matched.append({"severity": sev, "dimension": f.get("dimension"),
                            "detail": str(f.get("detail") or "")[:300]})
    return bool(matched), matched


def _git(repo, *args):
    subprocess.run(("git",) + args, cwd=repo, check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, env=dict(os.environ, **_GIT_ENV))


def seed_branch(sb, defect):
    """Create the branch /acs:code will reuse and commit the defect on it."""
    sys.path.insert(0, sb.build.scripts)
    import acs_lib  # noqa: E402  (the build under test's own slugify)
    with open(os.path.join(sb.ticket_dir(), "ticket.json")) as fh:
        ticket = json.load(fh)
    branch = "%s/%s-%s" % (ticket["type"], sb.ticket_id, acs_lib.slugify(ticket["title"]))
    _git(sb.repo, "checkout", "-q", "-b", branch)
    touched = apply(defect, sb.repo)
    _git(sb.repo, "add", "-A")
    _git(sb.repo, "commit", "-qm", "%s groundwork for %s" % (sb.ticket_id, defect["ticket_context"][:40].lower()))
    _git(sb.repo, "checkout", "-q", "main")
    return branch, touched


def read_verdicts(sb):
    docs = []
    for path in sorted(glob.glob(os.path.join(sb.ticket_dir(), "phases", "code", "iter-*-verdict*.json"))):
        try:
            with open(path) as fh:
                docs.append(json.load(fh))
        except (OSError, ValueError):
            pass
    return docs


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--defect", action="append", help="defect id glob (repeatable)")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--timeout", type=int, default=2400)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default=os.path.join(REPO_ROOT, "results", "verifier-catch-rate.json"))
    args = ap.parse_args()

    defects = load_all()
    if args.defect:
        import fnmatch
        defects = [d for d in defects if any(fnmatch.fnmatch(d["id"], g) for g in args.defect)]
    print("verifier catch rate — %d defect(s) x %d run(s) = %d /acs:code session(s), up to %ds each"
          % (len(defects), args.runs, len(defects) * args.runs, args.timeout))
    for d in defects:
        print("  %-42s expects %-8s on %s" % (d["id"], d["expected_severity"], d["dimension"]))
    if args.dry_run:
        print("\ndry run — nothing executed, nothing spent.")
        return 0
    try:
        build = resolve_build()
    except BuildError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    env = dict(os.environ)
    started = time.time()
    records = []
    for d in defects:
        runs = []
        for _ in range(args.runs):
            with Sandbox(build, profile="app-ticketed") as sb:
                branch, touched = seed_branch(sb, d)
                run = session_once(PROMPT.replace("TKT-1", sb.ticket_id), sb.repo, args.timeout, env)
                verdicts = read_verdicts(sb)
                caught, matched = judge(d, verdicts)
                run.update({"branch": branch, "seeded_files": touched, "verdicts": len(verdicts),
                            "caught": caught, "matched": matched,
                            "all_findings": [{"severity": f.get("severity"), "dimension": f.get("dimension")}
                                             for v in verdicts for f in (v.get("findings") or [])]})
                runs.append(run)
                print("  %-42s %s  (%d verdict(s), %d finding(s), %.0fs, $%s)"
                      % (d["id"], "CAUGHT" if caught else "missed", len(verdicts),
                         len(run["all_findings"]), run["seconds"], run.get("cost_usd")))
        records.append({"id": d["id"], "dimension": d["dimension"], "dimension_id": d["dimension_id"],
                        "expected_severity": d["expected_severity"], "runs": runs,
                        "catch_rate": sum(1 for r in runs if r["caught"]) / len(runs)})
    by_dim = {}
    for r in records:
        by_dim.setdefault(r["dimension"], []).append(r["catch_rate"])
    doc = {"schema": "acs-evals/verifier-catch-rate/1",
           "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "build": {"version": build.version, "root": build.root}, "runs_per_defect": args.runs,
           "defects": records,
           "by_dimension": {k: sum(v) / len(v) for k, v in by_dim.items()},
           "seconds": round(time.time() - started, 1)}
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")
    print("\nper-dimension catch rate:")
    for k, v in sorted(doc["by_dimension"].items()):
        print("  %-22s %.0f%%" % (k, 100 * v))
    print("written to %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
