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
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
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


class QuotaExhausted(RuntimeError):
    """The CLI refused a session because the account's usage allowance is spent.

    Not a routing result and not a pipeline failure: nothing about the plugin
    was exercised. The measurement stops at the first one rather than paying
    for a sandbox per run to record the same refusal N more times as
    `unmeasured` -- which is what happened on 2026-09-14, when two PIPE-code
    runs were "measured" in 12 seconds against a limit that had already reset
    by the time anyone read the output.
    """


QUOTA_RE = re.compile(r"session limit|usage limit", re.IGNORECASE)


def quota_message(envelope):
    """The CLI's limit message when `envelope` (a result event or a tool
    result block) is one, else None."""
    if not isinstance(envelope, dict) or not envelope.get("is_error"):
        return None
    text = envelope.get("result", envelope.get("content"))
    if not isinstance(text, str):
        text = json.dumps(text) if text is not None else ""
    return text.strip() if QUOTA_RE.search(text) else None


def _skill_refusal(block):
    """Did the CLI refuse to DISPATCH this Skill call?

    Returns a detection label when it did, None otherwise — and the test is
    deliberately narrow: only `disable-model-invocation` counts.

    Any other error on a Skill call happened AFTER dispatch. The commonest by
    far is the skill's own pre-hook declining to proceed in the probe's
    sandbox, e.g.

        PreToolUse:Skill hook error: acs pre-code: blocked — no plan.md found
        for TKT-1 ... run /acs:create-impl-plan TKT-1 first

    That is a correctly routed probe: the model picked exactly the right
    skill, the skill was invoked, and its gate refused the work. Routing is
    what this measures, so it is a HIT. Treating every `is_error` as "did not
    route" inverts the positive half of the suite — most probes run in a
    sandbox that cannot satisfy the skill they are meant to reach, which is
    fine, because the probe is killed at the routing decision and never wanted
    the skill to run.
    """
    if not block.get("is_error"):
        return None
    content = block.get("content")
    text = content if isinstance(content, str) else json.dumps(content)
    if "disable-model-invocation" in text:
        return "refused_user_only"
    return None


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
    model_turns = 0
    for line in lines:
        try:
            event = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(event, dict):
            continue
        kind = event.get("type")
        # The CLI declining the whole session for a spent usage allowance
        # arrives as the final `result` event. Not a route and not a miss:
        # the caller stops the measurement on it (QuotaExhausted).
        if kind == "result" and quota_message(event):
            return None, "quota_exhausted", None
        if (want is not None and kind == "system"
                and event.get("subtype") == "init"):
            if "slash_commands" not in event:
                return None, "unmeasured", None
            registered = event.get("slash_commands") or []
            return (want if want in registered else None), "registered", None
        # `message` is a dict on assistant/user events and a bare string on
        # others (the final `result` event, notably). Reading `.content` off
        # the string form raises, and this runs on EVERY event now, not just
        # assistant ones.
        message = event.get("message")
        blocks = message.get("content") or [] if isinstance(message, dict) else []
        if isinstance(blocks, str):
            blocks = []
        if pending is not None:
            for block in blocks:
                if not isinstance(block, dict):
                    continue
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
            model_turns += 1
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use" and block.get("name") == "Skill":
                    pending = (block.get("id"),
                               (block.get("input") or {}).get("skill"))
                    break
    if pending is not None:
        # The stream ended before the result did.
        return pending[1], "skill_tool_use_unresolved", pending[1]
    if want is None and model_turns == 0:
        # The session ended before the model ever spoke -- an API that gave
        # no response (the stream then carries an `api_retry` with
        # `no_response` and nothing after it), not a model that chose not
        # to route. On 2026-09-15 ROUTE-create-docs was scored 4/5 on exactly
        # this: the kept stream was six lines long and none of them was a
        # model turn. The caller retries it as the instrument failing.
        return None, "no_model_turn", None
    return None, ("unmeasured" if want is not None else "skill_tool_use"), None


def identity_of(build):
    """`<version>[<digest>]` -- what makes two builds the same build.

    The version string alone is not enough: source and the release it
    supersedes share one. Nor is `harness.fingerprint`: it hashes the skill
    surface -- which skills exist, which a model may route to -- and so reads
    a rewritten SKILL.md, a deleted agent or a changed hook as the same build,
    when every one of those is exactly what a measurement is taken to judge.
    The content digest of the plugin tree (`harness.build_digest`) is the
    identity; the version rides along because it is what a human recognises.
    Returns None when there is no build, which leaves every identity check
    inert rather than guessing.
    """
    if build is None:
        return None
    return "%s[%s]" % (getattr(build, "version", "?"),
                       getattr(build, "digest", None) or "?")


def build_record(build):
    """The `build` block of a measurement: what it exercised, by content."""
    return {"version": build.version, "root": build.root,
            "fingerprint": getattr(build, "fingerprint", None),
            "digest": getattr(build, "digest", None)}


def already_measured(doc, build, hashes, scope):
    """Why `doc` already answers what this run would spend to ask, or None.

    A complete measurement of the identical build, against the identical
    experiment, covering the requested scope, IS the answer: running it again
    buys noise, and a release gate that re-spent four hours on every re-run
    would be skipped. Anything less -- another build, a changed scenario set,
    an incomplete run, a narrower scope, a document too old to name its
    build -- is not, and the run spends.
    """
    if not isinstance(doc, dict) or doc.get("incomplete"):
        return None
    recorded = doc.get("build") or {}
    digest = recorded.get("digest")
    if not digest or digest != getattr(build, "digest", None):
        return None
    if doc.get("set_hashes") != hashes:
        return None
    have = doc.get("scope", "full")
    if have != "full" and have != scope:
        return None
    return ("a complete %s-scoped measurement of this exact build (acs %s, "
            "content %s) already exists, taken %s"
            % (have, recorded.get("version", "?"), digest,
               doc.get("generated_at", "?")))


def select_scenarios(scenarios, pattern):
    """A copy of `scenarios` keeping only the pipeline scenarios whose id
    matches `pattern` (a glob). The original is untouched, because the
    experiment's hashes are taken from the full set: a diagnostic run of one
    scenario is a subset of the experiment, not a different one."""
    import fnmatch
    conf = dict(scenarios["pipeline"])
    conf["scenarios"] = [s for s in conf["scenarios"]
                         if fnmatch.fnmatch(s["id"], pattern)]
    out = dict(scenarios)
    out["pipeline"] = conf
    return out


def read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


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

    def __init__(self, path, build=None):
        self.path = path
        self.done = {}
        self.identity = identity_of(build)
        self.dropped = None
        if not path:
            return
        found = {}
        stamp = None
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
                    if rec.get("__build__"):
                        stamp = rec["__build__"]
                    elif rec.get("id"):
                        found[rec["id"]] = rec
        except OSError:
            return
        # Reuse costs nothing and saves real money -- but only for the SAME
        # build. A checkpoint carried no build identity until 2026-09-13, so a
        # run interrupted against one build and resumed against another
        # silently reported the first build's probes as the second's. That is
        # exactly what would have happened here: four probes measured with
        # disable-model-invocation still set, reused by the run that removed
        # it. An unstamped or mismatched checkpoint is dropped, loudly.
        if self.identity and stamp != self.identity:
            self.dropped = (stamp or "unstamped", len(found))
            self.discard()
            return
        self.done = found

    def get(self, rec_id):
        return self.done.get(rec_id)

    def _stamp(self):
        """Write the build identity as the file's first line, once."""
        if not self.identity or os.path.exists(self.path):
            return
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"__build__": self.identity}) + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def add(self, rec):
        self.done[rec.get("id")] = rec
        if not self.path:
            return
        try:
            self._stamp()
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


#: Inherited variables that would make a measured session behave like THIS
#: session instead of a consumer's. The runner is often launched from inside
#: a Claude Code session (the release gate is), and `claude -p` reads these
#: from the environment: CLAUDE_AUTO_BACKGROUND_TASKS moved every subagent
#: spawn into the background on the 2026-09-15 gate, and the coordinators
#: then waited on ten-minute sleep loops (17 in 6 of 56 transcripts) until a
#: 1800s setup ran out; CLAUDE_EFFORT=xhigh made every session reason at the
#: launcher's effort rather than the model's default, which is what a
#: consumer pays for; the session-binding ones tie the child to the parent's
#: transcript, messaging socket and compaction state. ACS_PLUGIN_ROOT would
#: still name the source checkout the build was staged away from.
CHILD_ENV_SCRUB = (
    "ACS_PLUGIN_ROOT",
    "CLAUDE_AUTO_BACKGROUND_TASKS",
    "CLAUDE_CODE_BG_TASKS_REPORT_RUNNING",
    "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE",
    "CLAUDE_AFTER_LAST_COMPACT",
    "CLAUDE_EFFORT",
    "CLAUDE_CODE_SESSION_ID",
    "CLAUDE_CODE_CHILD_SESSION",
    "CLAUDE_PID",
    "CLAUDE_CODE_MESSAGING_SOCKET",
    "CLAUDE_CODE_MESSAGING_TOKEN",
    "CLAUDE_CODE_DIAGNOSTICS_FILE",
)


def child_env(base):
    """The environment a measured session runs in: the launcher's, minus
    what would make it behave like the launcher's own session."""
    env = dict(base)
    for name in CHILD_ENV_SCRUB:
        env.pop(name, None)
    return env


def stage_build(build):
    """A copy of the build under test in a directory that is not a checkout.

    The build is resolved from wherever it lives -- for this marketplace,
    `plugins/acs` inside the very checkout that runs the measurement. Every
    command a skill's prose embeds then names that path, and on 2026-09-14
    two of three PIPE-create-ticket sessions read it as the project: they
    ran `cd /home/user/gms-marketplace` before `skill-start.py --allocate`,
    the hooks resolved THAT checkout's `.acs/settings.json`, and MAR-580 and
    MAR-581 were minted -- locked, in progress -- in the marketplace's own
    workspace, from inside a sandbox. Staged under a temp directory the
    build has no checkout above it: the same stray `cd` finds no settings
    and `skill-start.py` refuses, visibly, instead of writing elsewhere. The
    content digest is unchanged by the copy, so the build's identity is too.
    """
    from harness import SKIP_DIRS, Build  # runner/ is on sys.path
    base = tempfile.mkdtemp(prefix="acs-build-")
    root = os.path.join(base, "acs")
    # Leave out exactly what the digest leaves out, so the copy is the same
    # tree by the one definition of "same" the repo has.
    shutil.copytree(build.root, root,
                    ignore=shutil.ignore_patterns("*.pyc", *sorted(SKIP_DIRS)))
    staged = Build(root)
    if staged.digest != build.digest:
        shutil.rmtree(base, ignore_errors=True)
        raise BuildError("staging %s changed its content digest (%s -> %s)"
                         % (build.root, build.digest, staged.digest))
    staged.source_root = build.root
    staged.stage_base = base
    return staged


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
    """The argv for a routing probe. Pure, so the plugin wiring is testable.

    `--tools Skill` is load-bearing, and `--allowedTools Skill` is NOT a
    substitute for it. `--allowedTools` is a PERMISSION allowlist — what may
    run without prompting — so the session still advertised all 38 built-in
    tools, Bash, Read, Edit and Write among them. With `--permission-mode
    acceptEdits` the model could therefore just do the work, and on the
    2026-09-13 measurement it sometimes did: every "routed nowhere" miss on
    create-design, docs-sync and create-test-docs was the model reading the
    repo and either answering from it or starting the job by hand, never a
    wrong skill. That measures whether a task is doable, not whether a
    description attracts it, and it costs a working session per probe instead
    of the few seconds the design assumes. `--tools` is the tool-set selector:
    it leaves exactly one tool, so the only move available is to route.
    """
    cmd = ["claude", "-p", prompt, "--output-format", "stream-json",
           "--verbose", "--permission-mode", "acceptEdits",
           "--tools", "Skill", "--allowedTools", "Skill"]
    return cmd + plugin_args(build) if build is not None else cmd


def session_cmd(prompt, build=None, add_dirs=()):
    """The argv for a full pipeline session. Pure, for the same reason.

    `add_dirs` are passed as `--add-dir`: under `acceptEdits` the session may
    edit files only inside its working directory and the directories added
    this way, and a headless session has nobody to ask for anything else. The
    acs workspace sits BESIDE the sandbox repo (`workspace_path: ../ws`), so
    without it every Edit/Write a coordinator aims at its own partition is
    refused. That is what interrupted a PIPE-docs-sync run on 2026-09-14: the
    coordinator's task XML failed validation, its Edit to fix the file was
    denied, and it abandoned the reflection loop and finished inline.

    `stream-json` rather than `json`, so the run's SKILL SEQUENCE is on the
    record. The 2026-09-13 measurement had PIPE-code fall from 3/3 to 1/3 with
    two runs hitting the wall at 1800s, and nothing in the measurement could
    say what those runs were doing: the final envelope is all `json` emits, and
    a run that times out never emits one at all. The final `result` event
    carries the same `total_cost_usd`, `num_turns` and `is_error`, so nothing
    is lost by asking for the whole stream and reading the end of it.
    """
    cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose",
           "--permission-mode", "acceptEdits",
           "--allowedTools", " ".join(PIPELINE_TOOLS)]
    for directory in add_dirs:
        cmd += ["--add-dir", directory]
    return cmd + plugin_args(build) if build is not None else cmd


#: Keep a run's skill sequence bounded: a loop is visible in the first few
#: dozen entries, and an unbounded list would bloat every measurement file.
MAX_SKILL_TRAIL = 60


def read_stream(path):
    """Pull `(envelope, skills)` out of a stream-json transcript on disk.

    `skills` is every Skill the run invoked, in order, each `{skill, ok}` --
    `ok` false when the call came back an error. Order and repetition are the
    point: a coordinator looping on one skill looks nothing like one that ran
    its steps once. `envelope` is the final `result` event, or None when the
    run was killed before emitting one.

    Reads line by line and keeps only what it extracts, so a 30-minute
    transcript costs a file on disk and not a process's memory.
    """
    envelope, skills, truncated = None, [], False
    pending = {}
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return None, [], False
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(event, dict):
                continue
            if event.get("type") == "result":
                envelope = event
                continue
            message = event.get("message")
            blocks = message.get("content") or [] if isinstance(message, dict) else []
            if isinstance(blocks, str):
                blocks = []
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                if (block.get("type") == "tool_use"
                        and block.get("name") == "Skill"):
                    name = (block.get("input") or {}).get("skill")
                    if len(skills) < MAX_SKILL_TRAIL:
                        skills.append({"skill": name, "ok": True})
                        pending[block.get("id")] = len(skills) - 1
                    else:
                        truncated = True
                elif block.get("type") == "tool_result":
                    idx = pending.pop(block.get("tool_use_id"), None)
                    if idx is not None and block.get("is_error"):
                        skills[idx]["ok"] = False
    return envelope, skills, truncated


def route_once(prompt, cwd, timeout, env, build=None, keep_path=None):
    """Return (routed_to, detection, attempted, seconds). Killed at the decision.

    `routed_to` is None when the model stopped, the timeout elapsed, or the CLI
    refused the call — which for a negative probe is the passing outcome, so
    None is a result here and never an error. `detection` says which rule in
    `classify` decided the run, and `attempted` names the skill the model
    reached for when the call was refused.
    """
    cmd = route_cmd(prompt, build)
    started = time.time()
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True,
                            cwd=cwd, env=env)
    deadline = started + timeout
    # stderr rides along in the same stream: the decision skips any line
    # that is not JSON, and a kept miss then shows the CLI's own words.
    # Every line the decision reads is also written to `keep_path`, so a
    # probe that came back wrong can be read instead of guessed at. Until
    # 2026-09-15 a routing miss left nothing behind: ROUTE-create-prd split
    # 4/5 after 20 straight hits, with `routed_to: null` and no Skill call in
    # the stream, and nothing could say what the model did with its 4 seconds.
    sink = open(keep_path, "w", encoding="utf-8") if keep_path else None

    def until_deadline(stream):
        for line in stream:
            if sink is not None:
                sink.write(line)
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
        if sink is not None:
            sink.close()
    return routed, detection, attempted, round(time.time() - started, 3)


def session_once(prompt, cwd, timeout, env, build=None, keep_dir=None,
                 add_dirs=()):
    """One full `claude -p` session. The envelope, the wall clock, and the
    sequence of skills the run invoked.

    Every `claude` this module spawns gets `stdin=DEVNULL` — here, in the
    routing probes, and in the registration read. `claude -p` appends
    whatever it finds on a non-tty stdin to the prompt, and a child inherits
    the parent's stdin unless told otherwise. The 2026-09-14 release gate ran
    `make measure` from a shell loop reading its command list from a file, so
    25 of the 27 pipeline sessions were prompted with the scenario text PLUS
    the three gate commands, and most of them spent their first turns
    investigating a `src/acs-evals` that does not exist in the sandbox. The
    prompt a scenario states is the whole prompt, whatever the caller's stdin.

    With `keep_dir` the transcript is kept there (as
    `<stamp>-<prompt slug>.jsonl`, named in `out["transcript"]`) instead of
    deleted, so a run that came back wrong can be read rather than re-bought.

    The transcript goes to a FILE rather than a pipe, for two reasons. It keeps
    `subprocess.run`'s timeout enforcement, which a read loop over a pipe
    quietly loses the moment a session stops emitting. And it survives the
    timeout: a killed run leaves its partial transcript on disk, so the runs
    that hit the wall -- the ones worth understanding -- still report what they
    were doing when they got there. That is the whole reason this exists: two
    PIPE-code runs died at 1800s on 2026-09-13 and the measurement recorded
    nothing about either.
    """
    cmd = session_cmd(prompt, build, add_dirs)
    started = time.time()
    handle, path = tempfile.mkstemp(prefix="acs-session-", suffix=".jsonl")
    out = {"ok": False, "seconds": None, "cost_usd": None, "turns": None,
           "error": None}
    try:
        with os.fdopen(handle, "w") as sink:
            try:
                proc = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=sink,
                                      stderr=subprocess.DEVNULL, text=True,
                                      cwd=cwd, timeout=timeout, env=env)
                returncode = proc.returncode
            except subprocess.TimeoutExpired:
                returncode, out["error"] = None, "timeout"
        out["seconds"] = round(time.time() - started, 3)
        envelope, skills, truncated = read_stream(path)
        if skills:
            out["skills_invoked"] = skills
            if truncated:
                out["skills_truncated"] = True
        if out["error"] == "timeout":
            return out
        if envelope is None:
            out["error"] = "no result event — the session emitted no envelope"
            return out
        out["cost_usd"] = envelope.get("total_cost_usd")
        out["turns"] = envelope.get("num_turns")
        out["ok"] = returncode == 0 and not envelope.get("is_error")
        if envelope.get("is_error"):
            limit = quota_message(envelope)
            if limit:
                out["error"] = "quota exhausted: %s" % limit
                out["quota_exhausted"] = True
            else:
                out["error"] = "session reported is_error"
        return out
    finally:
        kept = keep_transcript(path, keep_dir, prompt) if keep_dir else None
        if kept:
            out["transcript"] = kept
        else:
            try:
                os.remove(path)
            except OSError:
                pass


def keep_transcript(path, keep_dir, prompt):
    """Move a session transcript into `keep_dir`; the new path, or None."""
    slug = re.sub(r"[^a-z0-9]+", "-", prompt.lower()).strip("-")[:48] or "session"
    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    try:
        os.makedirs(keep_dir, exist_ok=True)
        dest = os.path.join(keep_dir, "%s-%s.jsonl" % (stamp, slug))
        n = 1
        while os.path.exists(dest):
            n += 1
            dest = os.path.join(keep_dir, "%s-%s-%d.jsonl" % (stamp, slug, n))
        shutil.move(path, dest)
        return dest
    except OSError:
        return None


# --------------------------------------------------------------------------
# Reading acs's own ledger
# --------------------------------------------------------------------------

def ledger_path(sandbox, skill):
    """Where `skill` left its `<skill>-state.json`, or None.

    A ticketed sandbox knows its ticket, so the ledger is at
    `<partition>/<ticket>/<skill>-state.json`. A scenario whose skill MINTS
    the ticket (PIPE-create-ticket on the `seeded` profile) starts with none:
    the partition root is not a ticket directory and no ledger is ever there,
    which is why that scenario reported "never ran" for every run, including
    the ones whose transcripts end with the post-hook's `completed`. The
    sandbox is fresh per run, so the ticket the skill minted is the one ticket
    directory under the partition; when a profile ever seeds more, the newest
    ledger is the run's.
    """
    name = "%s-state.json" % skill.split(":")[-1]
    if getattr(sandbox, "ticket_id", None):
        path = os.path.join(sandbox.ticket_dir(), name)
        return path if os.path.exists(path) else None
    partition = getattr(sandbox, "partition", None) or sandbox.ticket_dir()
    found = glob.glob(os.path.join(partition, "*", name))
    if not found:
        return None
    return max(found, key=os.path.getmtime)


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
    path = ledger_path(sandbox, skill)
    if path is None:
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
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
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


def routing_hit(probe, routed_to):
    """The same rule perf_gate.summarize scores by: a positive probe hits
    when its skill routed, a negative one when it did not, and a probe naming
    no skill (the off-domain control) when nothing routed."""
    want = probe.get("skill")
    fired = (routed_to is not None) if want is None else (routed_to == want)
    return fired == bool(probe.get("must_route", True))


def measure_routing(build, scenarios, probes, env, limit=None, checkpoint=None,
                    transcripts=None):
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
            for index in range(runs_per):
                handle, stream_path = tempfile.mkstemp(prefix="acs-route-",
                                                       suffix=".jsonl")
                os.close(handle)
                routed, detection, attempted, seconds = route_once(
                    probe["prompt"], sb.repo, timeout, env, build,
                    keep_path=stream_path)
                if detection == "no_model_turn":
                    # The instrument, not the model: one retry, then the run
                    # is a hole in the measurement rather than a miss.
                    routed, detection, attempted, seconds = route_once(
                        probe["prompt"], sb.repo, timeout, env, build,
                        keep_path=stream_path)
                if detection == "quota_exhausted":
                    os.unlink(stream_path)
                    raise QuotaExhausted(
                        "%s: the claude CLI refused the session (usage limit)"
                        % probe["id"])
                run = {"ok": True, "routed_to": routed,
                       "detection": detection, "seconds": seconds,
                       "cost_usd": None, "turns": None}
                if detection == "no_model_turn":
                    run["ok"] = False
                    run["unmeasured"] = ("the session ended before any model turn, "
                                         "twice (an API that gave no response)")
                if attempted:
                    # The model reached for a skill the CLI would not let it
                    # run. Not a route, but not nothing either.
                    run["attempted"] = attempted
                # A miss keeps its stream, under the same directory as the
                # pipeline transcripts; a hit is the expected outcome and
                # leaves nothing behind.
                if transcripts and (run.get("unmeasured") or not routing_hit(probe, routed)):
                    os.makedirs(transcripts, exist_ok=True)
                    kept = os.path.join(transcripts, "%s-route-%s-run%d.jsonl" % (
                        datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S"),
                        probe["id"], index))
                    shutil.move(stream_path, kept)
                    run["transcript"] = kept
                else:
                    os.unlink(stream_path)
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


def apply_ticket_patch(scenario, sandbox):
    """Merge `scenario["ticket_patch"]` into the sandbox's ticket, via the
    plugin's own `acs.py ticket save` (a PATCH, index re-synced). True when
    there is nothing to apply or it applied; False when the plugin refused."""
    patch = scenario.get("ticket_patch")
    if not patch:
        return True
    if not sandbox.ticket_id:
        return False
    out = sandbox.run("acs.py", "ticket", "save", "--ticket", sandbox.ticket_id,
                      "--from", "-", stdin=json.dumps(patch))
    return out["exit_code"] == 0


def measure_pipeline(build, scenarios, env, limit=None, checkpoint=None,
                     transcripts=None):
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
                # A scenario may enrich the profile's ticket before anything
                # runs (a description, acceptance criteria): the profile's
                # title is pinned by tier 1's goldens, so the patch lives in
                # the scenario and goes through the plugin's own PATCH path.
                patch_ok = apply_ticket_patch(scenario, sb)
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
                for text in ([] if not patch_ok else scenario.get("setup_prompts", [])):
                    s_run = session_once(fill(text), sb.repo, setup_timeout,
                                         env, build, keep_dir=transcripts,
                                         add_dirs=(sb.ws,))
                    setup.append(s_run)
                    if s_run.get("quota_exhausted"):
                        raise QuotaExhausted("%s setup: %s" % (scenario["id"], s_run["error"]))
                    if not s_run["ok"]:
                        break
                unmeasured = None
                if not patch_ok:
                    unmeasured = "ticket_patch could not be applied"
                elif setup and not setup[-1]["ok"]:
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
                                       env, build, keep_dir=transcripts,
                                       add_dirs=(sb.ws,))
                    if run.get("quota_exhausted"):
                        raise QuotaExhausted("%s: %s" % (scenario["id"], run["error"]))
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
        # Print the skill trail of any run that did not complete. Written to
        # the measurement either way, but a run that times out is the one
        # someone reads the console for, and "what was it doing" should not
        # need a JSON query to answer. "Complete" is the same rule the gate
        # scores by: the session exited clean AND the measured skill's own
        # ledger says `completed` — a clean exit that routed elsewhere is a
        # non-completion, and the trail is exactly what shows where it went.
        for i, run in enumerate(runs):
            if run.get("unmeasured"):
                continue
            if run.get("ok") and run.get("status") == "completed":
                continue
            trail = run.get("skills_invoked") or []
            if run.get("ok"):
                why = "the session ended but %s's ledger says %s" % (
                    scenario["skill"], run.get("status") or "it never ran")
            else:
                why = run.get("error") or "did not complete"
            print("      run %d %s: %s%s" % (
                i, why,
                summarize_trail(trail) if trail else "invoked no skill",
                ("  [%s]" % run["transcript"]) if run.get("transcript") else ""))
        if checkpoint:
            checkpoint.add(rec)
        out.append(rec)
    return out


def summarize_trail(skills):
    """`a -> b -> b x3 -> c` — a run's skill sequence, runs of one collapsed.

    Collapsed because the shape that matters is repetition: a coordinator
    stuck re-invoking one skill reads completely differently from one walking
    its steps once, and an uncollapsed list of forty buries that.
    """
    out, previous, count = [], None, 0

    def flush():
        if previous is None:
            return
        name = previous["skill"] or "?"
        if not previous["ok"]:
            name += "(refused)"
        out.append(name if count == 1 else "%s x%d" % (name, count))

    for entry in skills:
        key = {"skill": entry.get("skill"), "ok": entry.get("ok", True)}
        if previous is not None and key == previous:
            count += 1
            continue
        flush()
        previous, count = key, 1
    flush()
    return " -> ".join(out)


def claude_version():
    if not shutil.which("claude"):
        return None
    try:
        proc = subprocess.run(["claude", "--version"], stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=30)
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
        worst = 0
        for s in scenarios["pipeline"]["scenarios"]:
            # A setup prompt is a paid session of its own, and on the docs-sync
            # scenarios it is a whole /acs:code cycle -- several times the
            # measured skill's budget. Leaving it out of the plan understated
            # the run by hours and by most of its cost.
            setups = s.get("setup_prompts") or []
            cap = s.get("timeout_seconds", 1800)
            setup_cap = s.get("setup_timeout_seconds", cap)
            lines.append("  pipeline  %-22s x %d runs, up to %ds each%s"
                         % (s["id"], n, cap,
                            " + %d setup prompt(s) at up to %ds each"
                            % (len(setups), setup_cap) if setups else ""))
            sessions += n * (1 + len(setups))
            worst += n * (cap + len(setups) * setup_cap)
        lines.append("  worst case %.1f hours of wall clock if every session "
                     "runs to its timeout" % (worst / 3600.0))
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
    ap.add_argument("--scenario", default=None,
                    help="glob-filter pipeline scenarios (a diagnostic: the "
                         "measurement is marked incomplete)")
    ap.add_argument("--checkpoint", default=None,
                    help="where paid records land as they complete, so an "
                         "interrupted run resumes instead of re-spending "
                         "(default: <--out>.partial; '' disables)")
    ap.add_argument("--skip-preflight", action="store_true",
                    help="spend without first proving the sandbox can see the "
                         "plugin (only for debugging the pre-flight itself)")
    ap.add_argument("--force", action="store_true",
                    help="measure again even when --out already holds a "
                         "complete measurement of this exact build")
    ap.add_argument("--transcripts", default=None,
                    help="keep every pipeline session's stream-json "
                         "transcript in this directory, so a run that came "
                         "back wrong can be read instead of re-bought "
                         "(default: <dir of --out>/transcripts; '' disables)")
    args = ap.parse_args()

    with open(SCENARIOS) as fh:
        scenarios = json.load(fh)
    with open(ROUTING) as fh:
        all_probes = json.load(fh)["probes"]
    # The experiment's identity is the FULL set, whatever subset this run
    # exercises: a filtered run is a diagnostic of the experiment, not a
    # different experiment.
    hashes = set_hashes(scenarios, all_probes)
    probes = all_probes
    if args.probe:
        import fnmatch
        probes = [p for p in probes if fnmatch.fnmatch(p["id"], args.probe)]
    if args.scenario:
        scenarios = select_scenarios(scenarios, args.scenario)

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
        build = stage_build(resolve_build())
    except BuildError as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 2

    env = child_env(os.environ)
    print("\nbuild under test: acs %s\n  from %s, staged at %s\n"
          % (identity_of(build), build.source_root, build.root))
    try:
        return _measure(args, build, env, scenarios, probes, all_probes, hashes)
    finally:
        shutil.rmtree(build.stage_base, ignore_errors=True)


def _measure(args, build, env, scenarios, probes, all_probes, hashes):
    """The measurement proper, once the build is staged; main() cleans up."""
    started = time.time()

    # A run declares its scope up front -- full, routing, or pipeline.
    scope = ("routing" if args.routing_only
             else "pipeline" if args.pipeline_only else "full")

    # The same build, the same experiment, already measured to completion:
    # there is nothing left to learn from spending again, so the run does
    # not. A probe or scenario filter or a runs override is a diagnostic,
    # never a measurement, and always spends; --force re-measures on purpose.
    if (not args.force and not args.probe and not args.scenario
            and args.runs is None):
        reason = already_measured(read_json(args.out), build, hashes, scope)
        if reason:
            print("%s: %s.\nnothing to spend -- judge it with: python3 "
                  "runner/perf_gate.py --measurement %s\n(--force measures "
                  "the same build again)" % (args.out, reason, args.out))
            return 0

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
                            else (args.out + ".partial" if args.out else None),
                            build)
    if checkpoint.dropped:
        stamp, count = checkpoint.dropped
        print("discarded a checkpoint of %d record(s) from a different build "
              "(%s, now %s) — they would have been reported as this build's\n"
              % (count, stamp, checkpoint.identity))
    if checkpoint.done:
        print("resuming: %d record(s) already measured and on disk; they are "
              "reused, not re-spent (%s)\n"
              % (len(checkpoint.done), checkpoint.path))

    records = []
    transcripts = args.transcripts
    if transcripts is None and args.out:
        transcripts = os.path.join(
            os.path.dirname(os.path.abspath(args.out)), "transcripts")
    try:
        if not args.pipeline_only:
            records += measure_routing(build, scenarios, probes, env, args.runs,
                                       checkpoint, transcripts or None)
        if not args.routing_only:
            records += measure_pipeline(build, scenarios, env, args.runs,
                                        checkpoint, transcripts or None)
    except QuotaExhausted as exc:
        # The instrument, not the plugin, gave out. No measurement is written
        # (it would be a document of refusals), the checkpoint is kept so the
        # next run resumes where this one stopped, and the exit code says why.
        sys.stderr.write(
            "\nerror: %s\nThe usage allowance is spent; nothing further was "
            "spent here and no measurement was written. %d record(s) already "
            "measured are checkpointed%s and are reused, not re-spent, when "
            "the run is repeated after the limit resets.\n"
            % (exc, len(checkpoint.done) if checkpoint.path else len(records),
               (" at %s" % checkpoint.path) if checkpoint.path else ""))
        return 4

    # A run is marked incomplete only when it did not finish what its scope
    # set out to do (a probe filter, or a probe that produced no runs). A
    # routing-scoped run is a whole measurement of the cheap half, not half a
    # measurement: it may be promoted as a routing-scoped baseline, which the
    # gate then compares routing probes against and nothing else.
    expected_routing = 0 if args.pipeline_only else len(probes)
    expected_pipeline = (0 if args.routing_only
                         else len(scenarios["pipeline"]["scenarios"]))
    incomplete = (len(records) != expected_routing + expected_pipeline
                  or any(r["aggregate"]["runs"] == 0 for r in records)
                  or bool(args.probe) or bool(args.scenario))

    doc = {
        "schema": "acs-evals/measurement/1",
        "generated_at": datetime.datetime.now(datetime.timezone.utc)
                                .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "build": build_record(build),
        "scenario_set_version": scenarios["scenario_set_version"],
        "set_hashes": hashes,
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
