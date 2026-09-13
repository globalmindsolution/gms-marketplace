#!/usr/bin/env python3
"""Tier 3's collector: run the controlled scenario set and record what it cost.

This is the half that needs a real `claude`, real network, and real money. It
produces `results/measurements.json`; `runner/perf_gate.py` is what judges it,
and that half is pure. The split is deliberate and matches tier 1's: recording
and judging are two acts, so a measurement taken once can be re-judged under
new thresholds without paying for it again.

    python3 runner/measure_skills.py --dry-run        # the plan, no spending
    python3 runner/measure_skills.py --routing-only   # cheap tier: 30 probes
    python3 runner/measure_skills.py                  # everything

Two measurement notes that decide how the numbers may be read:

* **Routing probes record time, not cost.** The process is killed the instant
  the first `Skill` tool_use appears — that is what keeps a routing probe to
  time-to-route instead of a whole skill body — and killing it means the
  session never emits its cost envelope. `cost_usd` is recorded as null rather
  than estimated, because an invented number in a cost baseline is worse than
  an absent one.
* **Explicit probes are decided by the CLI, not the model.** A typed
  `/acs:<skill>` is expanded into the prompt and never dispatched through the
  `Skill` tool, so the two `disable-model-invocation` skills can only be
  observed as *registered*: the `init` event's `slash_commands` list. Those
  probes are killed at `init`, before any model turn. Every run records how it
  was decided in `detection`, so a measurement never mixes the two up.
* **The instrument is checked before the plugin is.** Three CONTROL probes in
  `routing.json` have known answers — a registration canary that must hit, an
  unregistered command that must miss, an off-domain request that must route
  nowhere. The free ones (decided at `init`) run as a pre-flight before any
  paid session; if one fails, nothing is spent and no measurement is written,
  because a suite that cannot see the plugin would otherwise report 30 misses
  as if they were routing results.
* **Pipeline cost and quality come from acs's own ledger**, not from this
  script's observations: `<ticket>/<skill>-state.json` is what `/acs:usage`
  reads, so the evaluation and the product cannot disagree about what a run
  cost. Wall clock is measured here because the ledger's own timing is what is
  under test.
"""

import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from harness import DATASET, PROFILES, BuildError, Sandbox, resolve_build  # noqa: E402
from perf_gate import summarize  # noqa: E402

SCENARIOS = os.path.join(DATASET, "scenarios.json")
ROUTING = os.path.join(DATASET, "routing.json")


def set_hashes(scenarios, probes):
    """Content hashes of the two halves of the experiment, so a baseline for
    one half stays comparable when only the other half changes."""
    def digest(obj):
        return hashlib.sha256(json.dumps(obj, sort_keys=True,
                                         separators=(",", ":")).encode()).hexdigest()[:16]
    return {"routing": digest(probes),
            "pipeline": digest({"scenarios": scenarios["pipeline"]["scenarios"],
                                "fixture_hash": scenarios.get("fixture_hash")})}

PIPELINE_TOOLS = ("Bash", "Read", "Write", "Edit", "Glob", "Grep", "Task",
                  "TodoWrite", "Skill")


# --------------------------------------------------------------------------
# Driving claude
# --------------------------------------------------------------------------

def explicit_skill(prompt):
    """The command an explicit `/acs:<skill>` prompt names, else None.

    A user-typed slash command is expanded into the prompt by the CLI and never
    dispatched through the `Skill` tool, so a probe whose prompt *is* the
    command cannot be observed as a tool_use. `install-hooks` and `update` set
    `disable-model-invocation: true`, which makes the explicit command the only
    way to reach them at all.
    """
    text = (prompt or "").strip()
    if not text.startswith("/"):
        return None
    parts = text[1:].split(None, 1)
    return parts[0] if parts else None


def classify(lines, prompt):
    """Decide where a stream-json session routed, from its raw event lines.

    Returns `(routed_to, detection)`. Pure: `lines` is any iterable of
    stream-json lines, so the decision rule is testable without a `claude`,
    and the caller may stop reading the moment a value comes back.

    * A description prompt is routed by the model: `routed_to` is the `skill`
      of the first `Skill` tool_use and `detection` is `skill_tool_use`.
    * An explicit `/acs:<skill>` prompt is routed by the CLI: the `init` event
      lists every registered command in `slash_commands`, so `routed_to` is the
      named command when it is registered and `detection` is `registered`.
      The probe is decided at `init`, before any model turn.
    * An explicit probe whose stream never reports a registration list — an
      `init` without `slash_commands`, or no `init` at all — is `unmeasured`:
      `routed_to` is None, which the gate counts as a miss, never as a pass.
    """
    want = explicit_skill(prompt)
    for line in lines:
        try:
            event = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(event, dict):
            continue
        kind = event.get("type")
        if (want is not None and kind == "system"
                and event.get("subtype") == "init"):
            if "slash_commands" not in event:
                return None, "unmeasured"
            registered = event.get("slash_commands") or []
            return (want if want in registered else None), "registered"
        if kind == "assistant":
            for block in (event.get("message") or {}).get("content") or []:
                if block.get("type") == "tool_use" and block.get("name") == "Skill":
                    return (block.get("input") or {}).get("skill"), "skill_tool_use"
    return None, ("unmeasured" if want is not None else "skill_tool_use")


def route_once(prompt, cwd, timeout, env):
    """Return (routed_to, detection, seconds). Killed at the first decision.

    `routed_to` is None when the model stopped, or the timeout elapsed, without
    invoking any skill — which for a negative probe is the passing outcome, so
    None is a result here and never an error. `detection` says which rule in
    `classify` decided the run.
    """
    cmd = ["claude", "-p", prompt, "--output-format", "stream-json",
           "--verbose", "--permission-mode", "acceptEdits",
           "--allowedTools", "Skill"]
    started = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True,
                            cwd=cwd, env=env)
    deadline = started + timeout

    def until_deadline(stream):
        for line in stream:
            if time.time() > deadline:
                return
            yield line

    try:
        routed, detection = classify(until_deadline(proc.stdout), prompt)
    finally:
        proc.kill()
        proc.wait()
        if proc.stdout:
            proc.stdout.close()
    return routed, detection, round(time.time() - started, 3)


def session_once(prompt, cwd, timeout, env):
    """One full `claude -p` session. Returns the envelope plus wall clock."""
    cmd = ["claude", "-p", prompt, "--output-format", "json",
           "--permission-mode", "acceptEdits",
           "--allowedTools", " ".join(PIPELINE_TOOLS)]
    started = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd,
                              timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return {"ok": False, "seconds": round(time.time() - started, 3),
                "cost_usd": None, "turns": None, "error": "timeout"}
    out = {"ok": proc.returncode == 0, "seconds": round(time.time() - started, 3),
           "cost_usd": None, "turns": None, "error": None}
    try:
        env_doc = json.loads(proc.stdout)
        out["cost_usd"] = env_doc.get("total_cost_usd")
        out["turns"] = env_doc.get("num_turns")
        out["ok"] = proc.returncode == 0 and not env_doc.get("is_error")
        if env_doc.get("is_error"):
            out["error"] = "session reported is_error"
    except (json.JSONDecodeError, TypeError):
        out["ok"] = False
        out["error"] = "unparseable session envelope"
    return out


# --------------------------------------------------------------------------
# Reading acs's own ledger
# --------------------------------------------------------------------------

def read_ledger(sandbox, skill):
    """The quality, cost and reliability signals acs recorded for itself.

    Returns the fields tier 3 compares. Every one is optional: a run that died
    early leaves no ledger, and `None` is the honest answer for a signal that
    was never written. It must never read as a zero — a zero coverage or zero
    iteration count would be a finding, and "we don't know" is not a finding.
    """
    out = {"status": None, "stop_reason": None, "ledger_cost_usd": None,
           "role_usage": [], "quality": {
               "verify_iterations": None, "coverage_percent": None,
               "coverage_target": None, "blocking_findings": None,
               "tests_passed": None}}
    tdir = sandbox.ticket_dir()
    path = os.path.join(tdir, "%s-state.json" % skill.split(":")[-1])
    if not os.path.exists(path):
        return out
    try:
        with open(path) as fh:
            doc = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return out

    runs = doc.get("runs") or []
    if runs:
        last = runs[-1]
        out["status"] = last.get("status")
        out["stop_reason"] = last.get("stop_reason")
        out["ledger_cost_usd"] = last.get("cost_usd")
        out["role_usage"] = last.get("role_usage") or []

    states = doc.get("states") or {}
    review = states.get("review") or {}
    if isinstance(review.get("iterations"), int):
        out["quality"]["verify_iterations"] = review["iterations"]
    tests = states.get("tests") or {}
    if isinstance(tests.get("coverage_percent"), (int, float)):
        out["quality"]["coverage_percent"] = float(tests["coverage_percent"])
    if isinstance(tests.get("coverage_target"), (int, float)):
        out["quality"]["coverage_target"] = float(tests["coverage_target"])
    if isinstance(tests.get("passed"), bool):
        out["quality"]["tests_passed"] = tests["passed"]

    findings = doc.get("findings") or []
    if isinstance(findings, list):
        out["quality"]["blocking_findings"] = len(
            [f for f in findings
             if isinstance(f, dict) and f.get("severity") == "blocking"])
    return out


# --------------------------------------------------------------------------
# The run
# --------------------------------------------------------------------------

def preflight(build, probes, env, timeout=60):
    """Run the free controls once, before a single paid session starts.

    Returns `(ok, checks)`. Only controls whose prompt is an explicit command
    qualify — they are decided at `init`, so they cost nothing — and each is
    judged by the same `summarize` rule the gate applies later, so pre-flight
    and gate cannot disagree about what a control must produce.
    """
    controls = [p for p in probes
                if p.get("kind") == "control" and explicit_skill(p["prompt"])]
    checks = []
    if not controls:
        return True, checks
    with Sandbox(build, profile="bare") as sb:
        for probe in controls:
            routed, detection, seconds = route_once(probe["prompt"], sb.repo,
                                                    timeout, env)
            rec = {"kind": "routing", "skill": probe["skill"],
                   "expect": {"must_route": probe.get("must_route", True),
                              "skill": probe["skill"], "control": True},
                   "runs": [{"ok": True, "routed_to": routed}]}
            passed = summarize(rec)["reliability"]["hits"] == 1
            checks.append({"id": probe["id"], "routed_to": routed,
                           "detection": detection, "seconds": seconds,
                           "passed": passed})
    return all(c["passed"] for c in checks), checks


#: Routing probes run in this sandbox profile unless they name another.
DEFAULT_ROUTING_PROFILE = "ticketed"


def probe_env(probe):
    """The sandbox a routing probe runs in: `(profile, setup)`.

    A prompt presupposes a state of the world — "this existing codebase", "the
    code change is done" — and a probe is a fair test of a description only
    when the sandbox makes that presupposition true. The 1.3.0 splits were the
    model inspecting an empty seeded repo, finding nothing to reverse-engineer
    or sync, and asking a question instead of routing: a dataset defect, not
    a description defect. `profile` names a harness profile (default
    `ticketed`); `setup` is a list of shell commands run once in the sandbox
    before the probe's first session.
    """
    profile = probe.get("profile", DEFAULT_ROUTING_PROFILE)
    if profile not in PROFILES:
        raise ValueError("%s: unknown sandbox profile %r (known: %s)"
                         % (probe.get("id"), profile, ", ".join(PROFILES)))
    setup = probe.get("setup") or []
    if not isinstance(setup, list) or not all(isinstance(x, str) for x in setup):
        raise ValueError("%s: setup must be a list of shell commands"
                         % probe.get("id"))
    return profile, tuple(setup)


def routing_sandboxes(probes):
    """The distinct sandboxes a probe set needs, in first-use order."""
    seen = []
    for probe in probes:
        key = probe_env(probe)
        if key not in seen:
            seen.append(key)
    return seen


def measure_routing(build, scenarios, probes, env, limit=None):
    conf = scenarios["routing"]
    runs_per = limit or conf.get("runs_per_probe", 5)
    timeout = conf.get("timeout_seconds", 120)
    out = []
    # One sandbox per (profile, setup), built lazily, its setup run once
    # before the first session, shared by every probe that asks for the same
    # state. Routing sessions are killed at their first Skill call (or at
    # init), so no session mutates it.
    sandboxes = {}
    try:
        for probe in probes:
            key = probe_env(probe)
            sb = sandboxes.get(key)
            if sb is None:
                sb = sandboxes[key] = Sandbox(build, profile=key[0])
                for step in key[1]:
                    try:
                        sb.shell(step)
                    except subprocess.CalledProcessError as exc:
                        raise RuntimeError("%s: setup step failed (%s): %s"
                                           % (probe["id"], step,
                                              (exc.stderr or "").strip()))
            runs = []
            for _ in range(runs_per):
                routed, detection, seconds = route_once(
                    probe["prompt"], sb.repo, timeout, env)
                runs.append({"ok": True, "routed_to": routed,
                             "detection": detection, "seconds": seconds,
                             "cost_usd": None, "turns": None})
            rec = {"id": probe["id"], "kind": "routing",
                   "skill": probe["skill"],
                   "expect": {"must_route": probe.get("must_route", True),
                              "skill": probe["skill"],
                              "explicit": explicit_skill(probe["prompt"]) is not None,
                              "control": probe.get("kind") == "control"},
                   "profile": key[0],
                   "runs": runs}
            if key[1]:
                rec["setup"] = list(key[1])
            rec["aggregate"] = summarize(rec)
            hits = rec["aggregate"]["reliability"]
            print("  %-32s %d/%d  %.1fs median"
                  % (probe["id"], hits["hits"], hits["total"],
                     rec["aggregate"]["seconds"]["median"]))
            out.append(rec)
    finally:
        for sb in sandboxes.values():
            sb.close()
    return out


def measure_pipeline(build, scenarios, env, limit=None):
    conf = scenarios["pipeline"]
    runs_per = limit or conf.get("runs_per_scenario", 3)
    out = []
    for scenario in conf["scenarios"]:
        runs = []
        for _ in range(runs_per):
            # A fresh sandbox per run: a second run reusing the first's
            # partition would measure resumption, not the skill.
            with Sandbox(build, profile=scenario["profile"]) as sb:
                def fill(text):
                    return text.replace("TKT-1", sb.ticket_id) if sb.ticket_id else text
                # Setup prompts bring the sandbox to the state the measured
                # skill needs (docs-sync after a real /acs:code run, say).
                # Their cost and time are recorded separately, never folded
                # into the measured run.
                setup = []
                for text in scenario.get("setup_prompts", []):
                    s_run = session_once(fill(text), sb.repo,
                                         scenario.get("timeout_seconds", 1800), env)
                    setup.append(s_run)
                    if not s_run["ok"]:
                        break
                if setup and not setup[-1]["ok"]:
                    run = {"ok": False, "seconds": 0.0, "cost_usd": None,
                           "turns": None, "error": "setup prompt failed: %s"
                           % (setup[-1].get("error") or "session not ok")}
                else:
                    run = session_once(fill(scenario["prompt"]), sb.repo,
                                       scenario.get("timeout_seconds", 1800), env)
                if setup:
                    run["setup"] = setup
                ledger = read_ledger(sb, scenario["skill"])
            run["status"] = ledger["status"]
            run["stop_reason"] = ledger["stop_reason"]
            run["role_usage"] = ledger["role_usage"]
            run["quality"] = ledger["quality"]
            # The ledger is authoritative on cost when it has an opinion: it
            # is what /acs:usage bills the consumer from.
            if ledger["ledger_cost_usd"] is not None:
                run["cost_usd"] = ledger["ledger_cost_usd"]
            runs.append(run)
        rec = {"id": scenario["id"], "kind": "pipeline",
               "skill": scenario["skill"], "runs": runs}
        rec["aggregate"] = summarize(rec)
        agg = rec["aggregate"]
        print("  %-32s %d/%d completed  %s median"
              % (scenario["id"], agg["reliability"]["hits"],
                 agg["reliability"]["total"],
                 ("$%.2f" % agg["cost_usd"]["median"])
                 if agg["cost_usd"] else "cost n/a"))
        out.append(rec)
    return out


def claude_version():
    if not shutil.which("claude"):
        return None
    try:
        proc = subprocess.run(["claude", "--version"], capture_output=True,
                              text=True, timeout=30)
        return proc.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def plan(scenarios, probes, routing_only, pipeline_only, limit):
    """What a run would cost, in sessions. Printed before anything is spent."""
    lines, sessions = [], 0
    free = [p for p in probes
            if p.get("kind") == "control" and explicit_skill(p["prompt"])]
    lines.append("  preflight %d free control probes before any paid session"
                 % len(free))
    if not pipeline_only:
        n = limit or scenarios["routing"].get("runs_per_probe", 5)
        lines.append("  routing   %d probes x %d runs = %d sessions "
                     "(killed at first Skill call, or at init for explicit "
                     "probes)" % (len(probes), n, len(probes) * n))
        sessions += len(probes) * n
        envs = routing_sandboxes(probes)
        lines.append("  sandboxes %d for routing: %s"
                     % (len(envs), ", ".join(
                         "%s%s" % (profile, " (+%d setup steps)" % len(setup) if setup else "")
                         for profile, setup in envs)))
    if not routing_only:
        n = limit or scenarios["pipeline"].get("runs_per_scenario", 3)
        for s in scenarios["pipeline"]["scenarios"]:
            lines.append("  pipeline  %-22s x %d runs, up to %ds each"
                         % (s["id"], n, s.get("timeout_seconds", 1800)))
            sessions += n
    lines.append("  TOTAL     %d claude sessions" % sessions)
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(
        description="tier 3 — measure skill quality, reliability, cost, time")
    ap.add_argument("--out", default="results/measurements.json")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the plan and spend nothing")
    ap.add_argument("--routing-only", action="store_true")
    ap.add_argument("--pipeline-only", action="store_true")
    ap.add_argument("--runs", type=int, default=None,
                    help="override runs per probe (1 is cheap and NOISY — a "
                         "single run cannot satisfy the routing decision rule)")
    ap.add_argument("--probe", default=None, help="glob-filter routing probes")
    ap.add_argument("--skip-preflight", action="store_true",
                    help="spend without first proving the sandbox can see the "
                         "plugin (only for debugging the pre-flight itself)")
    args = ap.parse_args()

    with open(SCENARIOS) as fh:
        scenarios = json.load(fh)
    with open(ROUTING) as fh:
        all_probes = json.load(fh)["probes"]
    probes = all_probes
    if args.probe:
        import fnmatch
        probes = [p for p in probes if fnmatch.fnmatch(p["id"], args.probe)]

    print(plan(scenarios, probes, args.routing_only, args.pipeline_only,
               args.runs))
    if args.dry_run:
        print("\ndry run — nothing executed, nothing spent.")
        return 0

    if not shutil.which("claude"):
        sys.stderr.write(
            "\nerror: `claude` is not on PATH. Tier 3 measures real sessions; "
            "there is no offline mode.\n"
            "Use --dry-run to check the plan, or runner/perf_gate.py to "
            "re-judge a measurement you already have.\n")
        return 2

    try:
        build = resolve_build()
    except BuildError as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 2

    env = dict(os.environ)
    print("\nbuild under test: acs %s\n" % build.version)
    started = time.time()

    # The instrument is checked before the plugin is: a sandbox that cannot
    # see the plugin would otherwise report every probe as a miss and charge
    # for it. Free (decided at init), and it refuses to write a measurement.
    preflight_doc = {"ok": True, "checks": [], "skipped": bool(args.skip_preflight)}
    if not args.skip_preflight:
        ok, checks = preflight(build, all_probes, env)
        preflight_doc = {"ok": ok, "checks": checks, "skipped": False}
        for c in checks:
            print("  preflight %-32s %s  (%s, %.1fs)"
                  % (c["id"], "ok" if c["passed"] else "FAILED",
                     c["detection"], c["seconds"]))
        if not ok:
            sys.stderr.write(
                "\nerror: pre-flight failed — the sandbox cannot see the "
                "plugin the way a consumer's claude would (see the checks "
                "above). Nothing was spent and no measurement was written; a "
                "measurement taken now would record 30 misses that are not "
                "routing results.\n")
            return 3
        print()
    records = []
    if not args.pipeline_only:
        records += measure_routing(build, scenarios, probes, env, args.runs)
    if not args.routing_only:
        records += measure_pipeline(build, scenarios, env, args.runs)

    # A run declares its scope up front — full, routing, or pipeline — and is
    # marked incomplete only when it did not finish what it set out to do (a
    # probe filter, or a probe that produced no runs). A routing-scoped run is
    # a whole measurement of the cheap half, not half a measurement: it may be
    # promoted as a routing-scoped baseline, which the gate then compares
    # routing probes against and nothing else.
    scope = ("routing" if args.routing_only
             else "pipeline" if args.pipeline_only else "full")
    expected_routing = 0 if args.pipeline_only else len(probes)
    expected_pipeline = (0 if args.routing_only
                         else len(scenarios["pipeline"]["scenarios"]))
    incomplete = (len(records) != expected_routing + expected_pipeline
                  or any(r["aggregate"]["runs"] == 0 for r in records)
                  or bool(args.probe))

    doc = {
        "schema": "acs-evals/measurement/1",
        "generated_at": datetime.datetime.now(datetime.timezone.utc)
                                .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "build": {"version": build.version, "root": build.root},
        "scenario_set_version": scenarios["scenario_set_version"],
        "set_hashes": set_hashes(scenarios, all_probes),
        "scope": scope,
        "environment": {"claude_cli_version": claude_version(),
                        "host": sys.platform,
                        "preflight": preflight_doc},
        "incomplete": incomplete,
        "probes": records,
    }
    directory = os.path.dirname(os.path.abspath(args.out))
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")

    print("\nmeasurement written to %s  (%.1fs)"
          % (args.out, time.time() - started))
    if incomplete:
        print("marked INCOMPLETE — a partial measurement may not be promoted "
              "to a baseline.")
    elif scope != "full":
        print("scope: %s — promotable as a %s-scoped baseline "
              "(dataset/baselines/acs-<version>-%s.json); a full baseline "
              "supersedes it." % (scope, scope, scope))
    print("judge it with: python3 runner/perf_gate.py --measurement %s"
          % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
