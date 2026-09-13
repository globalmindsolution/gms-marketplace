#!/usr/bin/env python3
"""Seeded defects for the fixture app: green changesets that are wrong in one way.

    python3 runner/defects.py list
    python3 runner/defects.py apply <defect-id> <repo>   # onto a built fixture
    python3 runner/defects.py selftest                   # every defect applies; suites stay green

Each defect in dataset/fixtures/app/defects/ names the code-verifier dimension
that must catch it and the severity it must carry. Every one leaves the
fixture's own test suite green — a defect the tests catch never reaches the
verifier, so it would measure nothing about the verifier. The catch-rate
runner (verifier_catch_rate.py) applies one defect per sandbox and asks the
verifier to judge it; this module only knows how to apply and self-check them.
"""

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fixture_app import build  # noqa: E402

DEFECTS = os.path.join(os.path.dirname(HERE), "dataset", "fixtures", "app", "defects")


def load_all():
    out = []
    for path in sorted(glob.glob(os.path.join(DEFECTS, "DEFECT-*.json"))):
        with open(path) as fh:
            out.append(json.load(fh))
    return out


def load(defect_id):
    with open(os.path.join(DEFECTS, defect_id + ".json")) as fh:
        return json.load(fh)


def apply(defect, repo):
    """Apply one defect's changeset to `repo`; every anchor must match once."""
    for edit in defect.get("patch", []):
        path = os.path.join(repo, edit["file"])
        with open(path) as fh:
            text = fh.read()
        if text.count(edit["before"]) != 1:
            raise RuntimeError("%s: anchor in %s found %d times"
                               % (defect["id"], edit["file"], text.count(edit["before"])))
        with open(path, "w") as fh:
            fh.write(text.replace(edit["before"], edit["after"]))
    for item in defect.get("create", []):
        path = os.path.join(repo, item["file"])
        if os.path.exists(path):
            raise RuntimeError("%s: %s already exists" % (defect["id"], item["file"]))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(item["text"])
    return [e["file"] for e in defect.get("patch", [])] + [c["file"] for c in defect.get("create", [])]


def _run_suite(repo):
    proc = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                          cwd=repo, capture_output=True, text=True)
    return proc.returncode == 0, proc.stderr[-800:]


def _coverage_total(repo):
    subprocess.run([sys.executable, "-m", "coverage", "run", "-m", "unittest", "discover", "-s", "tests"],
                   cwd=repo, capture_output=True, text=True)
    proc = subprocess.run([sys.executable, "-m", "coverage", "report"], cwd=repo,
                          capture_output=True, text=True)
    for line in proc.stdout.splitlines():
        if line.startswith("TOTAL"):
            return int(line.split()[-1].rstrip("%")), proc.returncode
    return None, proc.returncode


def selftest(defects=None, log=print):
    """Each defect applies cleanly and leaves the suite in its declared state."""
    base = tempfile.mkdtemp(prefix="acs-defects-")
    failures = []
    try:
        pristine = os.path.join(base, "pristine")
        build(pristine)
        for defect in defects or load_all():
            repo = os.path.join(base, defect["id"])
            shutil.copytree(pristine, repo)
            try:
                touched = apply(defect, repo)
                green, err = _run_suite(repo)
                want_green = defect.get("tests_after", "green") == "green"
                ok = green == want_green
                detail = "suite %s" % ("green" if green else "red")
                if ok and defect.get("coverage_after") == "below_floor":
                    total, rc = _coverage_total(repo)
                    ok = rc != 0 and total is not None
                    detail += ", coverage %s%% (gate exit %d)" % (total, rc)
                log("  %-42s %s  %s  [%s -> %s]" % (defect["id"], "ok" if ok else "FAILED",
                                                    detail, ", ".join(touched), defect["dimension"]))
                if not ok:
                    failures.append(defect["id"] + (": " + err if not green else ""))
            except RuntimeError as exc:
                log("  %-42s FAILED  %s" % (defect["id"], exc))
                failures.append(str(exc))
    finally:
        shutil.rmtree(base, ignore_errors=True)
    return failures


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["list", "apply", "selftest"])
    ap.add_argument("args", nargs="*")
    a = ap.parse_args()
    if a.command == "list":
        for d in load_all():
            print("%-42s dim %2d %-20s %-8s %s" % (d["id"], d["dimension_id"], d["dimension"],
                                                    d["expected_severity"], d["title"]))
        return 0
    if a.command == "apply":
        if len(a.args) != 2:
            ap.error("apply <defect-id> <repo>")
        print("\n".join(apply(load(a.args[0]), a.args[1])))
        return 0
    failures = selftest()
    print("\n%d defect(s) failed their self-check" % len(failures) if failures else "\nall defects apply and behave as declared")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
