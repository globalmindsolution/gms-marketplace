#!/usr/bin/env python3
"""Run the acs golden dataset's deterministic tier.

Every case names a surface of the acs plugin, an invocation, and the output
that surface produced on the build the dataset was recorded against. The runner
replays each invocation in a throwaway sandbox, redacts run-specific values,
and compares against the recorded expectation.

    python3 runner/run_golden.py                    # run everything
    python3 runner/run_golden.py --list             # list cases, run nothing
    python3 runner/run_golden.py --case LANE-*      # glob-filter by id
    python3 runner/run_golden.py --covers MAR-527   # filter by ticket covered
    python3 runner/run_golden.py --record           # rewrite goldens from this build
    python3 runner/run_golden.py -v                 # show every diff

Exit status is 0 only when every selected case matches.
"""

import argparse
import datetime
import fnmatch
import glob
import json
import os
import re
import socket
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import jsonschema_mini  # noqa: E402
from harness import (DATASET, FIXTURES, BuildError,  # noqa: E402
                     Sandbox, redact, resolve_build)

CASES_DIR = os.path.join(DATASET, "cases")


def RUBRIC_VERDICT(sev_failed):
    """The gate's verdict line, per docs/RUBRIC.md.

    A `minor` failure is drift to triage, not a reason to hold a release; a
    `critical` one is never accepted for a cut. Keeping the rule here — and in
    the exit status — is what stops "356/356" from being the only thing anyone
    reads.
    """
    if sev_failed["critical"]:
        return ("VERDICT: BLOCKED (critical) — do not cut a release from this "
                "build. See docs/RUBRIC.md.")
    if sev_failed["major"]:
        return ("VERDICT: BLOCKED — a documented contract moved. Fix, or "
                "re-record deliberately in its own commit.")
    return ("VERDICT: PASSED (minor drift) — not blocking, but triage each "
            "before the next cut.")


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

def load_cases():
    cases = []
    for path in sorted(glob.glob(os.path.join(CASES_DIR, "*.json"))):
        with open(path) as fh:
            doc = json.load(fh)
        for case in doc["cases"]:
            case.setdefault("profile", doc.get("profile", "bare"))
            case.setdefault("covers", doc.get("covers", []))
            case.setdefault("surface", doc.get("surface", ""))
            # An unclassified assertion is assumed to matter: the failure mode
            # of the opposite default is a critical case counted as noise.
            case.setdefault("severity", doc.get("severity", "major"))
            case["_file"] = path
            cases.append(case)
    return cases


def select(cases, args):
    out = cases
    if args.case:
        out = [c for c in out if any(fnmatch.fnmatch(c["id"], p) for p in args.case)]
    if args.covers:
        out = [c for c in out
               if any(t in c.get("covers", []) for t in args.covers)]
    if args.profile:
        out = [c for c in out if c["profile"] in args.profile]
    return out


# --------------------------------------------------------------------------
# Matching
# --------------------------------------------------------------------------

def is_subset(expected, actual, path="$"):
    """Recursive containment: every key/value in `expected` appears in `actual`.

    Lists must match element for element — a golden list that silently tolerated
    extra entries would stop catching an added check, which is most of what the
    gate and readiness cases are for.
    """
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return ["%s: expected an object, got %s" % (path, type(actual).__name__)]
        errs = []
        for key, value in expected.items():
            if key not in actual:
                errs.append("%s.%s: missing" % (path, key))
            else:
                errs.extend(is_subset(value, actual[key], "%s.%s" % (path, key)))
        return errs
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return ["%s: expected a list, got %s" % (path, type(actual).__name__)]
        if len(expected) != len(actual):
            return ["%s: expected %d entries, got %d"
                    % (path, len(expected), len(actual))]
        errs = []
        for i, value in enumerate(expected):
            errs.extend(is_subset(value, actual[i], "%s[%d]" % (path, i)))
        return errs
    if expected != actual:
        return ["%s: expected %r, got %r" % (path, expected, actual)]
    return []


def compare(expect, observed):
    """Every way the observed run differs from the recorded expectation."""
    errs = []
    if "present" in expect:
        if expect["present"] != observed.get("present"):
            errs.append("present: expected %s, got %s"
                        % (expect["present"], observed.get("present")))
            return errs
        front = observed.get("manifest", {})
        for key, value in expect.get("frontmatter", {}).items():
            if front.get(key) != value:
                errs.append("frontmatter.%s: expected %r, got %r"
                            % (key, value, front.get(key)))
        for key in expect.get("frontmatter_absent", []):
            if key in front:
                errs.append("frontmatter.%s: present, expected absent (%r)"
                            % (key, front[key]))
        for key in expect.get("frontmatter_nonempty", []):
            if not (front.get(key) or "").strip():
                errs.append("frontmatter.%s: missing or empty" % key)
        for needle in expect.get("description_contains", []):
            if needle not in (front.get("description") or ""):
                errs.append("description_contains: %r not in description" % needle)
        return errs
    if "valid" in expect:
        if expect["valid"] != observed.get("valid"):
            errs.append("valid: expected %s, got %s (%s)"
                        % (expect["valid"], observed.get("valid"),
                           "; ".join(observed.get("errors", [])) or "no errors"))
        for needle in expect.get("errors_contain", []):
            if not any(needle in e for e in observed.get("errors", [])):
                errs.append("errors_contain: %r not reported" % needle)
        return errs
    if "exit_code" in expect and expect["exit_code"] != observed["exit_code"]:
        errs.append("exit_code: expected %s, got %s"
                    % (expect["exit_code"], observed["exit_code"]))
    for key, stream in (("stdout_contains", "stdout"), ("stderr_contains", "stderr")):
        for needle in expect.get(key, []):
            if needle not in observed[stream]:
                errs.append("%s: %r not in %s" % (key, needle, stream))
    for key, stream in (("stdout_excludes", "stdout"), ("stderr_excludes", "stderr")):
        for needle in expect.get(key, []):
            if needle in observed[stream]:
                errs.append("%s: %r unexpectedly in %s" % (key, needle, stream))
    for want in expect.get("after", []):
        seen = (observed.get("after") or {}).get(want["path"], {})
        if "exists" in want and seen.get("exists") != want["exists"]:
            errs.append("after[%s].exists: expected %s, got %s"
                        % (want["path"], want["exists"], seen.get("exists")))
            continue
        if want.get("json_subset") is not None:
            if "json" not in seen:
                errs.append("after[%s]: not readable as JSON (%s)"
                            % (want["path"], seen.get("error", "absent")))
            else:
                errs.extend("after[%s] %s" % (want["path"], e)
                            for e in is_subset(want["json_subset"], seen["json"]))
    if "stdout_json" in expect or "stdout_json_subset" in expect:
        try:
            actual = json.loads(observed["stdout"])
        except ValueError:
            errs.append("stdout is not JSON: %s" % observed["stdout"][:200])
        else:
            if "stdout_json" in expect:
                if expect["stdout_json"] != actual:
                    errs.extend(is_subset(expect["stdout_json"], actual)
                                or ["stdout_json: extra keys present"])
            if "stdout_json_subset" in expect:
                errs.extend(is_subset(expect["stdout_json_subset"], actual))
    return errs


# --------------------------------------------------------------------------
# Execution
# --------------------------------------------------------------------------

def expand(token, sb):
    """Substitute sandbox-relative tokens into one argv entry."""
    if not isinstance(token, str):
        return str(token)
    if token.startswith("{{fixture:") and token.endswith("}}"):
        return os.path.join(FIXTURES, token[len("{{fixture:"):-2])
    out = (token.replace("{{repo}}", sb.repo)
                .replace("{{ws}}", sb.partition)
                .replace("{{ticket_dir}}", sb.ticket_dir())
                .replace("{{ticket}}", sb.ticket_id or ""))
    if "{{checkout_id}}" in out:
        out = out.replace("{{checkout_id}}", _checkout_id(sb))
    return out


def _checkout_id(sb):
    """The build's own checkout id for the sandbox repo — a session pointer
    is keyed by it, so a case that needs the partition to resolve from cwd
    seeds `sessions/{{checkout_id}}.json`."""
    if sb.build.scripts not in sys.path:
        sys.path.insert(0, sb.build.scripts)
    import acs_lib  # noqa: E402  (the build under test)
    return acs_lib.checkout_id(sb.repo)


_HOURS_AGO = re.compile(r"\{\{hours_ago:(\d+)\}\}")


def _clock(value):
    """Expand relative-time tokens inside a seeded document.

    A lock's staleness is judged against the wall clock, so a fixture carrying
    a fixed ``created_at`` would silently change verdict the day it crossed the
    24-hour timeout. ``{{now}}`` and ``{{hours_ago:N}}`` keep the *relationship*
    fixed instead of the timestamp.
    """
    if isinstance(value, dict):
        return {k: _clock(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clock(v) for v in value]
    if isinstance(value, str):
        if "{{now}}" in value:
            value = value.replace("{{now}}", _iso(0))
        value = _HOURS_AGO.sub(lambda m: _iso(int(m.group(1))), value)
        if value == "{{hostname}}":
            return socket.gethostname()
        if value == "{{live_pid}}":
            return os.getpid()          # the runner itself: alive for the probe
        if value == "{{dead_pid}}":
            return _dead_pid()
    return value


def _dead_pid():
    """A pid that belonged to a process which has already exited."""
    proc = subprocess.Popen(["true"])
    proc.wait()
    return proc.pid


def _iso(hours_ago):
    stamp = datetime.datetime.now(datetime.timezone.utc) - \
        datetime.timedelta(hours=hours_ago)
    return stamp.strftime("%Y-%m-%dT%H:%M:%SZ")


def seed_content(seed):
    """The bytes one seed file should carry.

    ``fixture`` reads a shared document out of dataset/fixtures/ so the same
    recorded artifact can back several cases; ``json``/``text`` inline it.
    """
    if "fixture" in seed:
        with open(os.path.join(FIXTURES, seed["fixture"])) as fh:
            return _clock(json.load(fh))
    return _clock(seed.get("json", seed.get("text", "")))


def execute_schema(case, build):
    """Validate one recorded instance against a schema the plugin ships.

    No sandbox and no subprocess: the schema files are part of the build, and
    the question is only whether they accept what they should and reject what
    they should not.
    """
    path = os.path.join(build.root, "schemas", case["schema"])
    try:
        with open(path) as fh:
            schema = json.load(fh)
    except OSError:
        return {"valid": False, "errors": ["no schema at %s" % case["schema"]],
                "exit_code": 3, "stdout": "", "stderr": ""}
    instance = seed_content(case)
    try:
        errors = jsonschema_mini.validate(instance, schema)
    except jsonschema_mini.UnsupportedKeyword as exc:
        return {"valid": False, "errors": ["UNSUPPORTED: %s" % exc],
                "exit_code": 3, "stdout": "", "stderr": ""}
    return {"valid": not errors, "errors": errors,
            "exit_code": 0, "stdout": "", "stderr": ""}


def _frontmatter(path):
    """The YAML frontmatter of a SKILL.md, as a flat dict of scalars.

    Deliberately not a YAML parser: skill frontmatter is a handful of
    `key: value` lines, and the dataset asserts on exactly those. A block
    scalar or nested mapping would be reported as absent rather than
    mis-parsed.
    """
    with open(path) as fh:
        text = fh.read()
    if not text.startswith("---"):
        return {}
    body = text.split("---", 2)
    if len(body) < 3:
        return {}
    out = {}
    for line in body[1].splitlines():
        if line.startswith((" ", "\t")) or ":" not in line:
            continue
        key, _, value = line.partition(":")
        out[key.strip()] = value.strip()
    return out


def execute_skill_manifest(case, build):
    """Assert one skill's shipped frontmatter — its routing surface.

    What a skill routes on is its `description`, and whether it may be
    model-invoked at all is `disable-model-invocation`. Both live in the
    shipped SKILL.md, so both are checkable without spending a session.
    """
    name = case["skill"]
    path = os.path.join(build.root, "skills", name, "SKILL.md")
    if not os.path.isfile(path):
        return {"manifest": {}, "present": False,
                "exit_code": 3, "stdout": "", "stderr": ""}
    front = _frontmatter(path)
    return {"manifest": front, "present": True,
            "exit_code": 0, "stdout": "", "stderr": ""}


def execute(case, sb):
    for seed in case.get("files", []):
        sb.write(seed.get("base", "ticket"), expand(seed["path"], sb), seed_content(seed))
    invoke = case["invoke"]
    stdin = invoke.get("stdin")
    if isinstance(stdin, (dict, list)):
        stdin = json.dumps(stdin)
    if isinstance(stdin, str):
        # A hook payload names the repo it fires in; the sandbox path is only
        # known at run time, so the same tokens argv gets apply here.
        stdin = expand(stdin, sb)
    raw = sb.run(invoke.get("script", "acs.py"),
                 *[expand(a, sb) for a in invoke["argv"]], stdin=stdin)
    return {"exit_code": raw["exit_code"],
            "stdout": redact(raw["stdout"], sb).strip(),
            "stderr": redact(raw["stderr"], sb).strip(),
            "after": read_after(case, sb)}


def read_after(case, sb):
    """The workspace state an `expect.after` clause asks about.

    Some surfaces are judged by what they LEFT BEHIND, not by what they
    printed: `ticket save` writes a document and says little, and the
    SessionEnd hook is silent by design. A case whose only assertion is
    `exit_code` would pass against a script that did nothing at all, so those
    cases assert on the file instead.
    """
    out = {}
    for want in case.get("expect", {}).get("after", []):
        root = {"repo": sb.repo, "ws": sb.partition,
                "ticket": sb.ticket_dir()}[want.get("base", "ticket")]
        path = os.path.join(root, want["path"])
        entry = {"exists": os.path.exists(path)}
        if entry["exists"] and want.get("json_subset") is not None:
            try:
                with open(path) as fh:
                    entry["json"] = json.load(fh)
            except (OSError, ValueError) as exc:
                entry["error"] = str(exc)
        out[want["path"]] = entry
    return out


def record(case, observed):
    """Rewrite this case's expectation from what the build actually produced.

    Kind-aware, because the three case kinds do not share an observation shape.
    Reducing a schema or skill-manifest case to `{"exit_code": 0}` — which the
    CLI-only version of this function did — leaves a case that asserts nothing
    and can never fail again, which is strictly worse than deleting it.

    It also preserves the SHAPE the case was authored with: a case written
    against `stdout_json_subset` keeps a subset expectation over the same keys,
    rather than being widened to an exact match over every key the surface
    happens to emit today.
    """
    kind = case.get("kind", "cli")
    if kind == "schema":
        expect = {"valid": observed["valid"]}
        if observed["errors"]:
            # Keep the first error as the pinned reason, mirroring how these
            # cases are authored: the rejection must name the constraint.
            expect["errors_contain"] = [observed["errors"][0]]
        case["expect"] = expect
        return
    if kind == "skill_manifest":
        front = observed["manifest"]
        expect = {"present": observed["present"]}
        if observed["present"]:
            keep = {k: front[k] for k in ("name", "disable-model-invocation")
                    if k in front}
            expect["frontmatter"] = keep
            expect["frontmatter_nonempty"] = ["description"]
            if "disable-model-invocation" not in front:
                expect["frontmatter_absent"] = ["disable-model-invocation"]
        case["expect"] = expect
        return

    previous = case.get("expect", {})
    expect = {"exit_code": observed["exit_code"]}
    try:
        parsed = json.loads(observed["stdout"])
    except ValueError:
        parsed = None
    if parsed is not None and "stdout_json_subset" in previous:
        expect["stdout_json_subset"] = _refresh_subset(
            previous["stdout_json_subset"], parsed)
    elif parsed is not None:
        expect["stdout_json"] = parsed
    elif observed["stdout"]:
        expect["stdout_contains"] = [observed["stdout"]]
    if observed["stderr"]:
        expect["stderr_contains"] = [observed["stderr"]]
    case["expect"] = expect


def _refresh_subset(previous, actual):
    """Re-read the keys the case already asserted, and only those.

    A case that deliberately asserts four stable keys out of forty must not
    become a forty-key exact match just because it was re-recorded.
    """
    if isinstance(previous, dict) and isinstance(actual, dict):
        return {k: _refresh_subset(v, actual[k])
                for k, v in previous.items() if k in actual}
    if isinstance(previous, list) and isinstance(actual, list):
        return actual
    return actual


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case", nargs="*", help="glob(s) matched against case ids")
    ap.add_argument("--covers", nargs="*", help="only cases covering these tickets")
    ap.add_argument("--profile", nargs="*", help="only cases on these sandbox profiles")
    ap.add_argument("--list", action="store_true", help="list selected cases and exit")
    ap.add_argument("--record", action="store_true",
                    help="rewrite goldens from this build (review the diff!)")
    ap.add_argument("--keep", action="store_true", help="keep sandbox dirs")
    ap.add_argument("-v", "--verbose", action="store_true", help="show every diff")
    ap.add_argument("--json", metavar="PATH",
                    help="write the full run result as JSON (for runner/report.py)")
    args = ap.parse_args()

    try:
        build = resolve_build()
    except BuildError as exc:
        print("acs golden dataset: %s" % exc, file=sys.stderr)
        return 3

    with open(os.path.join(DATASET, "manifest.json")) as fh:
        manifest = json.load(fh)

    cases = select(load_cases(), args)
    if args.list:
        for case in cases:
            print("%-22s %-8s %-26s %s"
                  % (case["id"], case["profile"], case.get("surface", ""),
                     case["title"]))
        print("\n%d case(s)" % len(cases))
        return 0

    print("acs golden dataset %s  |  build under test: acs %s"
          % (manifest["dataset_version"], build.version))
    print("recorded against: acs %s" % manifest["recorded_against"])
    if build.version != manifest["recorded_against"] and not args.record:
        print("NOTE: build differs from the recorded baseline — differences "
              "below are release-relevant, not necessarily defects.")
    print("build root: %s\n" % build.root)

    failures, passed = [], 0
    records = []
    started = time.time()
    by_profile = {}
    for case in cases:
        by_profile.setdefault(case["profile"], []).append(case)

    touched = set()
    for profile, group in sorted(by_profile.items()):
        for case in group:
            case_started = time.time()
            if case.get("kind") == "schema":
                observed = execute_schema(case, build)
            elif case.get("kind") == "skill_manifest":
                observed = execute_skill_manifest(case, build)
            else:
                # A fresh sandbox per case: several cases mutate workspace state
                # (locks, file maps, verdicts) and must not see each other's
                # writes.
                with Sandbox(build, profile=profile, keep=args.keep) as sb:
                    observed = execute(case, sb)
            if args.record:
                record(case, observed)
                touched.add(case["_file"])
                print("  rec  %-22s %s" % (case["id"], case["title"]))
                continue
            errs = compare(case["expect"], observed)
            records.append({
                "id": case["id"], "title": case["title"],
                "group": os.path.basename(case["_file"])[:-5],
                "surface": case.get("surface", ""), "profile": case["profile"],
                "covers": case.get("covers", []),
                "kind": case.get("kind", "cli"),
                "severity": case["severity"],
                "known_divergence": case.get("known_divergence") or None,
                "note": case.get("note", ""),
                "seconds": round(time.time() - case_started, 3),
                "status": "fail" if errs else "pass",
                "diffs": errs,
            })
            if errs:
                failures.append((case, errs, observed))
                print("  FAIL %-22s %s" % (case["id"], case["title"]))
                if args.verbose:
                    for err in errs:
                        print("         - %s" % err)
            else:
                passed += 1
                print("  ok   %-22s %s" % (case["id"], case["title"]))

    if args.record:
        rewrite(touched, cases)
        print("\nrecorded %d case(s) from acs %s — review the diff before "
              "committing." % (len(cases), build.version))
        return 0

    elapsed = round(time.time() - started, 2)
    if args.json:
        write_results(args.json, manifest, build, records, elapsed)
        print("\nresults written to %s" % args.json)

    sev_failed = {level: len([c for c, _e, _o in failures
                              if c["severity"] == level])
                  for level in ("critical", "major", "minor")}
    print("\n%d passed, %d failed, %d total  (%.1fs)"
          % (passed, len(failures), len(cases), elapsed))
    if failures:
        print("failed by severity: %d critical, %d major, %d minor"
              % (sev_failed["critical"], sev_failed["major"],
                 sev_failed["minor"]))
        print(RUBRIC_VERDICT(sev_failed))
    if failures and not args.verbose:
        print("\nre-run with -v for the diffs, or:")
        for case, _errs, _obs in failures[:5]:
            print("  python3 runner/run_golden.py -v --case %s" % case["id"])
    # docs/RUBRIC.md: critical and major block; minor does not.
    return 1 if (sev_failed["critical"] or sev_failed["major"]) else 0


def write_results(path, manifest, build, records, elapsed):
    """The machine-readable run result runner/report.py renders.

    Deliberately self-contained: it names the build, the dataset and the clock,
    so a report generated from it months later still says what was tested.
    """
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    passed = [r for r in records if r["status"] == "pass"]
    failed = [r for r in records if r["status"] == "fail"]
    by_sev = {}
    for level in ("critical", "major", "minor"):
        group = [r for r in records if r["severity"] == level]
        by_sev[level] = {
            "total": len(group),
            "failed": len([r for r in group if r["status"] == "fail"]),
        }
    doc = {
        "schema": "acs-evals/run-result/1",
        "generated_at": datetime.datetime.now(datetime.timezone.utc)
                                 .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dataset": {
            "version": manifest["dataset_version"],
            "target_release": manifest.get("target_release"),
            "recorded_against": manifest.get("recorded_against"),
            "covers": manifest.get("covers", []),
        },
        "build": {"version": build.version, "root": build.root},
        "baseline_match": build.version == manifest.get("recorded_against"),
        "totals": {
            "total": len(records), "passed": len(passed), "failed": len(failed),
            "known_divergences": len([r for r in records if r["known_divergence"]]),
            "seconds": elapsed,
            "by_severity": by_sev,
        },
        "cases": records,
    }
    with open(path, "w") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")
    return doc


def rewrite(touched, cases):
    """Write recorded expectations back into their case files."""
    by_file = {}
    for case in cases:
        by_file.setdefault(case["_file"], {})[case["id"]] = case
    for path in sorted(touched):
        with open(path) as fh:
            doc = json.load(fh)
        for case in doc["cases"]:
            fresh = by_file.get(path, {}).get(case["id"])
            if fresh:
                case["expect"] = fresh["expect"]
        with open(path, "w") as fh:
            json.dump(doc, fh, indent=2)
            fh.write("\n")


if __name__ == "__main__":
    sys.exit(main())
