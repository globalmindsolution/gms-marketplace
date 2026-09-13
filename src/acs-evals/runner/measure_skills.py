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


#: How many further events to read looking for a Skill call's result. The
#: refusal below is a CLI check, not a model turn, so it lands within a couple
#: of events; the bound only stops a hung stream from being read forever.
RESULT_LOOKAHEAD = 40


def _skill_refusal(block):
    """Did this tool_result say the Skill call was refused, and why?

    Returns None when the call was honoured. The `disable-model-invocation`
    case has its own detection label because it is the whole subject of the
    negative probes.
    """
    if not block.get("is_error"):
        return None
    content = block.get("content")
    text = content if isinstance(content, str) else json.dumps(content)
    if "disable-model-invocation" in text:
        return "refused_user_only"
    return "refused"


def classify(lines, prompt):
    """Decide where a stream-json session routed, from its raw event lines.

    Returns `(routed_to, detection, attempted)`. Pure: `lines` is any iterable
    of stream-json lines, so the decision rule is testable without a `claude`,
    and the caller may stop reading the moment a value comes back.

    * A description prompt is routed by the model: `routed_to` is the `skill`
      of the first `Skill` tool_use — PROVIDED the call was honoured.
    * An explicit `/acs:<skill>` prompt is routed by the CLI: the `init` event
      lists every registered command in `slash_commands`, so `routed_to` is the
      named command when it is registered and `detection` is `registered`.
      The probe is decided at `init`, before any model turn.
    * An explicit probe whose stream never reports a registration list — an
      `init` without `slash_commands`, or no `init` at all — is `unmeasured`:
      `routed_to` is None, which the gate counts as a miss, never as a pass.

    **A request is not an invocation.** Until 2026-09-13 this stopped at the
    tool_use and reported the skill the model ASKED for. A skill carrying
    `disable-model-invocation: true` is offered in the session's `skills` list
    and the model does sometimes reach for it, but the CLI refuses the call
    outright — "cannot be used with Skill tool due to disable-model-invocation"
    — and the skill body never loads. Scoring the request as an invocation
    turned a guarantee that held on every run into two CRITICAL findings
    against it. So the decision now reads one step further, to the matching
    tool_result: a refused call did not route. `attempted` keeps the skill the
    model reached for, because "the model tried and was stopped" is real signal
    about the descriptions — just not a broken guarantee.
    """
    want = explicit_skill(prompt)
    pending = None          # (tool_use_id, skill) awaiting its result
    since = 0
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
                return None, "unmeasured", None
            registered = event.get("slash_commands") or []
            return (want if want in registered else None), "registered", None
        blocks = (event.get("message") or {}).get("content") or []
        if pending is not None:
            for block in blocks:
                if (block.get("type") == "tool_result"
                        and block.get("tool_use_id") == pending[0]):
                    refusal = _skill_refusal(block)
                    if refusal:
                        return None, refusal, pending[1]
                    return pending[1], "skill_tool_use", None
            since += 1
            if since > RESULT_LOOKAHEAD:
                # No result in sight. Report what was asked for rather than
                # claim nothing happened: an unanswered call is not evidence
                # of a refusal.
                return pending[1], "skill_tool_use_unresolved", pending[1]
            continue
        if kind == "assistant":
            for block in blocks:
                if block.get("type") == "tool_use" and block.get("name") == "Skill":
                    pending = (block.get("id"),
                               (block.get("input") or {}).get("skill"))
                    break
    if pending is not None:
        # The stream ended before the result did.
        return pending[1], "skill_tool_use_unresolved", pending[1]
    return None, ("unmeasured" if want is not None else "skill_tool_use"), None


class Checkpoint:
    """Durable, append-only record of paid work already done.

    A tier-3 run spends hundreds of real sessions and used to hold every result
    in memory, writing once at the very end. Anything that ended the process
    early -- a kill, a reaped background job, a container recycle -- threw the
    entire spend away with nothing on disk to show for it. That is not a
    theoretical risk: it happened, at 29 of 43 probes, and roughly 145 paid
    sessions went with it.

    So each record lands on disk the moment it exists, and a later run reuses
    what is already there instead of buying it twice. JSONL because a partial
    line at the tail of a killed write is recoverable by dropping it, where
    half a JSON object is not.
    """

    def __init__(self, path):
        self.path = path
        self.done = {}
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue   # a torn final line: drop it, keep the rest
                    if rec.get("id"):
                        self.done[rec["id"]] = rec
        except OSError:
            pass

    def get(self, rec_id):
        return self.done.get(rec_id)

    def add(self, rec):
        self.done[rec.get("id")] = rec
        if not self.path:
            return
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
        except OSError as exc:
            sys.stderr.write("warning: could not checkpoint %s: %s\n"
                             % (rec.get("id"), exc))

    def discard(self):
        if self.path and os.path.exists(self.path):
            try:
                os.remove(self.path)
            except OSError:
                pass


def plugin_args(build):
    """Make the session load the build under test, rather than hoping it does.

    Until this existed, `measure_skills` resolved a build, printed "build under
    test: acs X", and then spawned `claude` with no plugin selector at all -- so
    the session loaded whatever the operator happened to have INSTALLED, and the
    label described a build the measurement never exercised. On a checkout ahead
    of the last release that is not a small discrepancy: seven skills in
    routing.json did not exist in the installed build, and six negative probes
    asserted a no-auto-invoke guarantee the installed legs did not carry, so a
    third of the routing probes could not return a meaningful answer.

    `--plugin-dir` loads a plugin from a directory for that session only. It
    touches no plugin cache and needs no cleanup, which is the whole point:
    staging a build into the operator's real `~/.claude/plugins` works, but it
    mutates shared state and leaves a restore that someone has to remember.
    """
    return ["--plugin-dir", build.root]


def route_cmd(prompt, build=None):
    """The argv for a routing probe. Pure, so the plugin wiring is testable."""
    cmd = ["claude", "-p", prompt, "--output-format", "stream-json",
           "--verbose", "--permission-mode", "acceptEdits",
           "--allowedTools", "Skill"]
    return cmd + plugin_args(build) if build is not None else cmd


def session_cmd(prompt, build=None):
    """The argv for a full pipeline session. Pure, for the same reason."""
    cmd = ["claude", "-p", prompt, "--output-format", "json",
           "--permission-mode", "acceptEdits",
           "--allowedTools", " ".join(PIPELINE_TOOLS)]
    return cmd + plugin_args(build) if build is not None else cmd


def route_once(prompt, cwd, timeout, env, build=None):
    """Return (routed_to, detection, attempted, seconds). Killed at the decision.

    `routed_to` is None when the model stopped, the timeout elapsed, or the CLI
    refused the call — which for a negative probe is the passing outcome, so
    None is a result here and never an error. `detection` says which rule in
    `classify` decided the run, and `attempted` names the skill the model
    reached for when the call was refused.
    """
    cmd = route_cmd(prompt, build)
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
        routed, detection, attempted = classify(until_deadline(proc.stdout),
                                                prompt)
    finally:
        proc.kill()
        proc.wait()
        if proc.stdout:
            proc.stdout.close()
    return routed, detection, attempted, round(time.time() - started, 3)


def session_once(prompt, cwd, timeout, env, build=None):
    """One full `claude -p` session. Returns the envelope plus wall clock."""
    cmd = session_cmd(prompt, build)
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

def registered_skills(build, cwd, env, timeout=60):
    """The acs commands a real session registers, read from its `init` event.

    Free: the stream is abandoned at `init`, before any model turn, exactly as
    an explicit routing probe is.
    """
    cmd = route_cmd("/acs:usage", build)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True,
                            cwd=cwd, env=env)
    deadline = time.time() + timeout
    try:
        for line in proc.stdout:
            if time.time() > deadline:
                return None
            try:
                event = json.loads(line)
            except (json.JSONDecodeError, TypeError):
                continue
            if (isinstance(event, dict) and event.get("type") == "system"
                    and event.get("subtype") == "init"):
                if "slash_commands" not in event:
                    return None
                return {c for c in (event.get("slash_commands") or [])
                        if c.startswith("acs:")}
    finally:
        proc.kill()
        proc.wait()
        if proc.stdout:
            proc.stdout.close()
    return None


def build_identity_check(build, cwd, env, timeout=60):
    """Assert the session loaded THE RESOLVED BUILD, not merely some acs.

    "build under test: acs X" used to be a line of output with nothing behind
    it -- the resolved build was never passed to `claude`, so the session ran
    whatever was installed. Passing `--plugin-dir` fixes the cause; this check
    is what keeps the claim honest, by comparing the commands the session
    actually registered against the skills the resolved build ships. A
    measurement whose subject cannot be confirmed is worse than none: it is
    wrong under a true-sounding label, and every number in it inherits that.
    """
    skills_dir = os.path.join(build.root, "skills")
    try:
        shipped = {"acs:%s" % d for d in os.listdir(skills_dir)
                   if os.path.isdir(os.path.join(skills_dir, d))}
    except OSError as exc:
        return {"id": "CONTROL-build-identity", "passed": False,
                "detection": "unreadable", "seconds": 0.0,
                "reason": "cannot list %s: %s" % (skills_dir, exc)}
    started = time.time()
    registered = registered_skills(build, cwd, env, timeout)
    seconds = round(time.time() - started, 3)
    if registered is None:
        return {"id": "CONTROL-build-identity", "passed": False,
                "detection": "unmeasured", "seconds": seconds,
                "reason": "the session reported no registration list"}
    missing, extra = sorted(shipped - registered), sorted(registered - shipped)
    passed = not missing and not extra
    reason = "" if passed else (
        "the session did not load the resolved build: %d shipped skill(s) "
        "unregistered (%s), %d registered skill(s) not in the build (%s)"
        % (len(missing), ", ".join(missing[:4]) or "-",
           len(extra), ", ".join(extra[:4]) or "-"))
    return {"id": "CONTROL-build-identity", "passed": passed,
            "detection": "registered", "seconds": seconds,
            "registered": len(registered), "shipped": len(shipped),
            "reason": reason}


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
    # No early return when the dataset ships no explicit control: the identity
    # check is not one of them, and it is the one check that must never be
    # skipped -- everything downstream is a claim ABOUT the resolved build.
    with Sandbox(build, profile="bare") as sb:
        checks.append(build_identity_check(build, sb.repo, env, timeout))
        for probe in controls:
            routed, detection, attempted, seconds = route_once(
                probe["prompt"], sb.repo, timeout, env, build)
            rec = {"kind": "routing", "skill": probe["skill"],
                   "expect": {"must_route": probe.get("must_route", True),
                              "skill": probe["skill"], "control": True},
                   "runs": [{"ok": True, "routed_to": routed}]}
            passed = summarize(rec)["reliability"]["hits"] == 1
            check = {"id": probe["id"], "routed_to": routed,
                     "detection": detection, "seconds": seconds,
                     "passed": passed}
            if attempted:
                check["attempted"] = attempted
            checks.append(check)
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


def measure_routing(build, scenarios, probes, env, limit=None, checkpoint=None):
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
            done = checkpoint.get(probe["id"]) if checkpoint else None
            if done is not None:
                agg = done.get("aggregate", {}).get("reliability", {})
                print("  %-32s %s/%s  (from checkpoint, not re-spent)"
                      % (probe["id"], agg.get("hits", "?"), agg.get("total", "?")))
                out.append(done)
                continue
            runs = []
            for _ in range(runs_per):
                routed, detection, attempted, seconds = route_once(
                    probe["prompt"], sb.repo, timeout, env, build)
                run = {"ok": True, "routed_to": routed,
                       "detection": detection, "seconds": seconds,
                       "cost_usd": None, "turns": None}
                if attempted:
                    # The model reached for a skill the CLI would not let it
                    # run. Not a route, but not nothing either.
                    run["attempted"] = attempted
                runs.append(run)
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
            if checkpoint:
                checkpoint.add(rec)
            out.append(rec)
    finally:
        for sb in sandboxes.values():
            sb.close()
    return out


def setup_holds(scenario, sandbox, env):
    """Did the setup actually leave the sandbox in the state the scenario needs?

    A setup prompt is a model session, so it can report success and still stop
    short of the precondition — /acs:code asking five clarifying questions and
    finishing with `ready_for_planning=false` leaves no changeset for
    /acs:docs-sync to re-derive. Measuring the skill against that sandbox does
    not measure the skill; it measures the setup, and scores the skill's
    correct refusal as the skill's failure. `setup_assert` is the scenario's
    own statement of what must hold, run as a shell command in the sandbox
    repo with `ACS_PARTITION` and `ACS_TICKET_ID` bound. No assert means there
    is nothing to check, not that nothing needed checking.
    """
    cmd = scenario.get("setup_assert")
    if not cmd:
        return True
    senv = dict(env, ACS_PARTITION=sandbox.ticket_dir(),
                ACS_TICKET_ID=sandbox.ticket_id or "")
    try:
        proc = subprocess.run(cmd, shell=True, cwd=sandbox.repo, env=senv,
                              capture_output=True, text=True, timeout=120)
    except (subprocess.TimeoutExpired, OSError):
        return False
    return proc.returncode == 0


def measure_pipeline(build, scenarios, env, limit=None, checkpoint=None):
    conf = scenarios["pipeline"]
    runs_per = limit or conf.get("runs_per_scenario", 3)
    out = []
    for scenario in conf["scenarios"]:
        done = checkpoint.get(scenario["id"]) if checkpoint else None
        if done is not None:
            agg = done.get("aggregate", {}).get("reliability", {})
            print("  %-32s %s/%s completed  (from checkpoint, not re-spent)"
                  % (scenario["id"], agg.get("hits", "?"), agg.get("total", "?")))
            out.append(done)
            continue
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
                # into the measured run, and they get their OWN budget: a
                # setup prompt is another scenario's whole body, so sizing it
                # by the cheap skill being measured times it out by
                # construction and spends the run for nothing.
                setup_timeout = scenario.get(
                    "setup_timeout_seconds",
                    scenario.get("timeout_seconds", 1800))
                setup = []
                for text in scenario.get("setup_prompts", []):
                    s_run = session_once(fill(text), sb.repo, setup_timeout,
                                         env, build)
                    setup.append(s_run)
                    if not s_run["ok"]:
                        break
                unmeasured = None
                if setup and not setup[-1]["ok"]:
                    unmeasured = ("setup prompt failed: %s"
                                  % (setup[-1].get("error") or "session not ok"))
                elif setup and not setup_holds(scenario, sb, env):
                    unmeasured = ("setup ran but left the precondition unmet: %s"
                                  % scenario["setup_assert"])
                if unmeasured:
                    run = {"ok": False, "unmeasured": unmeasured,
                           "seconds": 0.0, "cost_usd": None, "turns": None,
                           "error": unmeasured}
                else:
                    run = session_once(fill(scenario["prompt"]), sb.repo,
                                       scenario.get("timeout_seconds", 1800),
                                       env, build)
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
        if checkpoint:
            checkpoint.add(rec)
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
    lines.append("  preflight build-identity check + %d free control probe(s), "
                 "before any paid session" % len(free))
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
    ap.add_argument("--checkpoint", default=None,
                    help="where paid records land as they complete, so an "
                         "interrupted run resumes instead of re-spending "
                         "(default: <--out>.partial; '' disables)")
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
    checkpoint = Checkpoint(args.checkpoint if args.checkpoint is not None
                            else (args.out + ".partial" if args.out else None))
    if checkpoint.done:
        print("resuming: %d record(s) already measured and on disk; they are "
              "reused, not re-spent (%s)\n"
              % (len(checkpoint.done), checkpoint.path))

    records = []
    if not args.pipeline_only:
        records += measure_routing(build, scenarios, probes, env, args.runs,
                                   checkpoint)
    if not args.routing_only:
        records += measure_pipeline(build, scenarios, env, args.runs,
                                    checkpoint)

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

    checkpoint.discard()
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
