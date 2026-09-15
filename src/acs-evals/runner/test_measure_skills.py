#!/usr/bin/env python3
"""Self-test for the routing collector's decision rule (`classify`).

Pure: feeds synthetic stream-json lines, no `claude`, no network, no cost.
The rule under test is the one `docs/PERFORMANCE.md` states — a description
prompt is decided by the first `Skill` tool_use; an explicit `/acs:<skill>`
prompt is decided by the `init` event's `slash_commands`; an explicit probe
whose stream never reports a registration list is `unmeasured`, never a pass.
"""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import measure_skills  # noqa: E402
from measure_skills import (DEFAULT_ROUTING_PROFILE, classify,  # noqa: E402
                            route_cmd, session_cmd,
                            explicit_skill, measure_routing, plan,
                            probe_env, routing_sandboxes)
from gen_plugin_eval import renderable  # noqa: E402
from perf_gate import summarize  # noqa: E402


def _init(commands=("acs:install-hooks", "acs:update", "acs:code"),
          with_list=True):
    event = {"type": "system", "subtype": "init", "session_id": "s"}
    if with_list:
        event["slash_commands"] = list(commands)
    return json.dumps(event)


def _assistant(*blocks):
    return json.dumps({"type": "assistant",
                       "message": {"content": list(blocks)}})


def _skill(name, call_id="t1"):
    return {"type": "tool_use", "id": call_id, "name": "Skill",
            "input": {"skill": name}}


def _result(call_id="t1", content="ok", is_error=False):
    """The tool_result the CLI returns for a Skill call.

    The decision needs this, not just the request: a `disable-model-invocation`
    skill is offered to the model, and asking for it is refused here.
    """
    return json.dumps({"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": call_id,
         "is_error": is_error, "content": content}]}})


REFUSAL = ("<tool_use_error>Skill acs:create-standards cannot be used with "
           "Skill tool due to disable-model-invocation. Ask the user to run "
           "/acs:create-standards themselves</tool_use_error>")


def _text(text):
    return {"type": "text", "text": text}


class ExplicitSkillTest(unittest.TestCase):
    def test_description_prompt_is_not_explicit(self):
        self.assertIsNone(explicit_skill("Set up the git hooks for this repo."))

    def test_slash_command_names_its_skill(self):
        self.assertEqual(explicit_skill("/acs:install-hooks"), "acs:install-hooks")
        self.assertEqual(explicit_skill("  /acs:update  "), "acs:update")

    def test_arguments_are_dropped(self):
        self.assertEqual(explicit_skill("/acs:code MAR-1"), "acs:code")

    def test_bare_slash_is_nothing(self):
        self.assertIsNone(explicit_skill("/"))
        self.assertIsNone(explicit_skill(""))
        self.assertIsNone(explicit_skill(None))


class DescriptionProbeTest(unittest.TestCase):
    PROMPT = "Implement ticket TKT-1 using the TDD cycle."

    def test_first_skill_tool_use_decides(self):
        lines = [_init(), _assistant(_text("Thinking."), _skill("acs:code")),
                 _result(), _assistant(_skill("acs:create-pr", "t2"))]
        self.assertEqual(classify(lines, self.PROMPT),
                         ("acs:code", "skill_tool_use", None))

    def test_stops_reading_at_the_decision(self):
        # The decision is the RESULT of the first Skill call, not the request:
        # a refused call did not route. So it reads one event further than it
        # used to, and not one more than that.
        seen = []

        def lines():
            for line in [_init(), _assistant(_skill("acs:code")), _result(),
                         _assistant(_skill("acs:create-pr", "t2"))]:
                seen.append(line)
                yield line

        classify(lines(), self.PROMPT)
        self.assertEqual(len(seen), 3)

    def test_no_skill_call_is_a_none_result(self):
        lines = [_init(), _assistant(_text("I cannot help with that."))]
        self.assertEqual(classify(lines, self.PROMPT), (None, "skill_tool_use", None))

    def test_a_refused_user_only_skill_did_not_route(self):
        # 2026-09-13: the negative probes reported two CRITICAL findings on a
        # guarantee that held on every run, because they scored the request.
        lines = [_init(), _assistant(_skill("acs:create-standards")),
                 _result(content=REFUSAL, is_error=True)]
        self.assertEqual(classify(lines, self.PROMPT),
                         (None, "refused_user_only", "acs:create-standards"))

    def test_the_attempt_is_kept_even_though_it_did_not_route(self):
        lines = [_init(), _assistant(_skill("acs:create-standards")),
                 _result(content=REFUSAL, is_error=True)]
        self.assertEqual(classify(lines, self.PROMPT)[2], "acs:create-standards")

    def test_a_gate_rejection_is_still_a_correct_route(self):
        # The commonest result on a positive probe, and the one that nearly
        # inverted the suite: the model picks exactly the right skill, the
        # skill IS invoked, and its own pre-hook refuses to proceed in a
        # sandbox that cannot satisfy it. Routing is what this measures.
        hook = ("PreToolUse:Skill hook error: acs pre-code: blocked — no "
                "plan.md found for TKT-1 — run /acs:create-impl-plan first.")
        lines = [_init(), _assistant(_skill("acs:code")),
                 _result(content=hook, is_error=True)]
        self.assertEqual(classify(lines, self.PROMPT),
                         ("acs:code", "skill_tool_use", None))

    def test_only_the_user_only_refusal_undoes_a_route(self):
        for text, expected in (
                ("no such skill", ("acs:code", "skill_tool_use", None)),
                ("rate limited, try again", ("acs:code", "skill_tool_use", None))):
            lines = [_init(), _assistant(_skill("acs:code")),
                     _result(content=text, is_error=True)]
            self.assertEqual(classify(lines, self.PROMPT), expected, text)

    def test_a_result_for_some_other_call_does_not_decide(self):
        lines = [_init(), _assistant(_skill("acs:code")),
                 _result("other", content=REFUSAL, is_error=True), _result()]
        self.assertEqual(classify(lines, self.PROMPT),
                         ("acs:code", "skill_tool_use", None))

    def test_a_request_whose_result_never_comes_reports_the_request(self):
        # An unanswered call is not evidence of a refusal. Say so in the
        # detection rather than quietly scoring it either way.
        lines = [_init(), _assistant(_skill("acs:code"))]
        routed, detection, attempted = classify(lines, self.PROMPT)
        self.assertEqual((routed, detection), ("acs:code",
                                               "skill_tool_use_unresolved"))
        self.assertEqual(attempted, "acs:code")

    def test_the_lookahead_for_a_result_is_bounded(self):
        lines = ([_init(), _assistant(_skill("acs:code"))]
                 + [_assistant(_text("still going"))
                    for _ in range(measure_skills.RESULT_LOOKAHEAD + 5)])
        self.assertEqual(classify(lines, self.PROMPT)[1],
                         "skill_tool_use_unresolved")

    def test_events_whose_message_is_not_an_object_are_survived(self):
        # A live stream carries events whose `message` is a bare string (the
        # final `result` event among them), and since the decision now reads
        # every event rather than only assistant ones, reading `.content` off
        # one raised — mid-measurement, after the money was spent.
        odd = [json.dumps({"type": "result", "message": "all done"}),
               json.dumps({"type": "user", "message": {"content": "plain text"}}),
               json.dumps({"type": "assistant", "message": {"content": ["x", 7]}})]
        lines = [_init()] + odd + [_assistant(_skill("acs:code"))] + odd + [_result()]
        self.assertEqual(classify(lines, self.PROMPT),
                         ("acs:code", "skill_tool_use", None))

    def test_init_registration_never_decides_a_description_probe(self):
        # The model must choose; the CLI knowing the command is not routing.
        lines = [_init(), _assistant(_text("Done."))]
        self.assertEqual(classify(lines, self.PROMPT), (None, "skill_tool_use", None))

    def test_garbage_lines_are_skipped(self):
        lines = ["not json", "[1,2]", "null", _assistant(_skill("acs:setup")),
                 "garbage too", _result()]
        self.assertEqual(classify(lines, self.PROMPT),
                         ("acs:setup", "skill_tool_use", None))


class ExplicitProbeTest(unittest.TestCase):
    def test_registered_command_routes_at_init(self):
        lines = [_init(), _assistant(_text("Resolving repo roots."))]
        self.assertEqual(classify(lines, "/acs:install-hooks"),
                         ("acs:install-hooks", "registered", None))

    def test_decided_before_any_model_turn(self):
        seen = []

        def lines():
            for line in [_init(), _assistant(_text("first turn"))]:
                seen.append(line)
                yield line

        classify(lines(), "/acs:update")
        self.assertEqual(len(seen), 1)

    def test_unregistered_command_is_a_miss(self):
        lines = [_init(commands=("acs:code",)), _assistant(_text("?"))]
        self.assertEqual(classify(lines, "/acs:install-hooks"),
                         (None, "registered", None))

    def test_init_without_a_registration_list_is_unmeasured(self):
        lines = [_init(with_list=False), _assistant(_text("?"))]
        self.assertEqual(classify(lines, "/acs:install-hooks"),
                         (None, "unmeasured", None))

    def test_no_init_at_all_is_unmeasured(self):
        lines = [_assistant(_text("?"))]
        self.assertEqual(classify(lines, "/acs:update"), (None, "unmeasured", None))

    def test_exact_command_match_only(self):
        # A same-named command from another namespace is not this skill.
        lines = [_init(commands=("other:install-hooks", "install-hooks"))]
        self.assertEqual(classify(lines, "/acs:install-hooks"),
                         (None, "registered", None))


class ControlProbeTest(unittest.TestCase):
    """The three controls have known answers; the dataset must carry them."""

    def setUp(self):
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(os.path.dirname(here), "dataset", "routing.json")
        self.probes = json.load(open(path))["probes"]
        self.controls = [p for p in self.probes if p.get("kind") == "control"]

    def test_the_dataset_ships_all_three_controls(self):
        ids = sorted(p["id"] for p in self.controls)
        self.assertEqual(ids, ["CONTROL-off-domain",
                               "CONTROL-registration-canary",
                               "CONTROL-unregistered-command"])

    def test_the_two_explicit_controls_are_free(self):
        free = [p["id"] for p in self.controls if explicit_skill(p["prompt"])]
        self.assertEqual(sorted(free), ["CONTROL-registration-canary",
                                        "CONTROL-unregistered-command"])

    def test_controls_are_never_rendered_as_plugin_eval_cases(self):
        self.assertTrue(all(not renderable(p) for p in self.controls))
        self.assertTrue(all(renderable(p) for p in self.probes
                            if p.get("kind") != "control"))

    def test_the_off_domain_control_routes_nowhere_by_definition(self):
        off = [p for p in self.controls if p["id"] == "CONTROL-off-domain"][0]
        self.assertIsNone(off["skill"])
        self.assertFalse(off["must_route"])
        self.assertIsNone(explicit_skill(off["prompt"]))

    def test_the_plan_names_the_preflight_before_any_session(self):
        runs = 5
        text = plan({"routing": {"runs_per_probe": runs},
                     "pipeline": {"runs_per_scenario": 3, "scenarios": []}},
                    self.probes, True, False, None)
        free = len([p for p in self.probes
                    if p.get("kind") == "control"
                    and measure_skills.explicit_skill(p["prompt"])])
        self.assertIn("build-identity check", text,
                      "the plan must name the check that proves the session "
                      "loaded the build the run claims to describe")
        self.assertIn("%d free control probe(s)" % free, text)
        # Derived from the shipped probe set, not pinned: widening routing.json
        # is exactly the change this line should keep describing, and a literal
        # here went stale the moment the probe set grew from 30 to 43.
        #
        # `plan` counts EVERY probe, controls included, even though the two
        # lines above it declare two of those controls free. So the estimate is
        # the honest upper bound on sessions, not a cost estimate net of the
        # free preflight. Asserted as observed rather than corrected here --
        # changing what the estimator counts is a decision about the estimator.
        total = len(self.probes)
        self.assertIn("%d probes x %d runs = %d sessions"
                      % (total, runs, total * runs), text)
        self.assertIn("TOTAL     %d claude sessions" % (total * runs), text)


class GateReadsDetectionHonestlyTest(unittest.TestCase):
    """`summarize` scores `routed_to` only; `detection` explains, never scores."""

    def _probe(self, runs):
        return {"id": "ROUTE-install-hooks-explicit", "kind": "routing",
                "skill": "acs:install-hooks",
                "expect": {"must_route": True, "skill": "acs:install-hooks",
                           "explicit": True},
                "runs": runs}

    def test_registered_runs_are_hits(self):
        runs = [{"ok": True, "routed_to": "acs:install-hooks",
                 "detection": "registered", "seconds": 4.0, "cost_usd": None,
                 "turns": None}] * 3
        self.assertEqual(summarize(self._probe(runs))["reliability"]["hits"], 3)

    def test_unmeasured_runs_are_misses(self):
        runs = [{"ok": True, "routed_to": None, "detection": "unmeasured",
                 "seconds": 4.0, "cost_usd": None, "turns": None}] * 3
        rel = summarize(self._probe(runs))["reliability"]
        self.assertEqual((rel["hits"], rel["total"]), (0, 3))


class ProbeEnvTest(unittest.TestCase):
    """A probe names the sandbox that makes its prompt's presupposition true."""

    def test_default_is_the_ticketed_profile_with_no_setup(self):
        self.assertEqual(DEFAULT_ROUTING_PROFILE, "ticketed")
        self.assertEqual(probe_env({"id": "X", "prompt": "p"}), ("ticketed", ()))

    def test_profile_and_setup_are_read(self):
        probe = {"id": "X", "profile": "app-ticketed",
                 "setup": ["git checkout -qb t", "git commit -qam m"]}
        self.assertEqual(probe_env(probe),
                         ("app-ticketed", ("git checkout -qb t", "git commit -qam m")))

    def test_unknown_profile_is_refused_before_any_session(self):
        with self.assertRaises(ValueError) as ctx:
            probe_env({"id": "ROUTE-x", "profile": "mansion"})
        self.assertIn("ROUTE-x", str(ctx.exception))
        self.assertIn("mansion", str(ctx.exception))

    def test_setup_must_be_a_list_of_shell_strings(self):
        with self.assertRaises(ValueError):
            probe_env({"id": "X", "setup": "git checkout -qb t"})
        with self.assertRaises(ValueError):
            probe_env({"id": "X", "setup": [1]})

    def test_identical_environments_share_one_sandbox(self):
        probes = [{"id": "a"}, {"id": "b", "profile": "app"}, {"id": "c"},
                  {"id": "d", "profile": "app", "setup": ["x"]},
                  {"id": "e", "profile": "app", "setup": ["x"]}]
        self.assertEqual(routing_sandboxes(probes),
                         [("ticketed", ()), ("app", ()), ("app", ("x",))])


class DatasetProfilesTest(unittest.TestCase):
    """The shipped probes: every environment resolves, and the two probes whose
    prompts presuppose a codebase / a finished change run where that holds."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), "dataset", "routing.json")) as fh:
            cls.probes = json.load(fh)["probes"]

    def _probe(self, pid):
        return [p for p in self.probes if p["id"] == pid][0]

    def test_every_probe_resolves_to_a_known_sandbox(self):
        for probe in self.probes:
            probe_env(probe)  # raises on an unknown profile or bad setup

    def test_create_requirements_runs_on_a_real_codebase(self):
        self.assertEqual(probe_env(self._probe("ROUTE-create-requirements")),
                         ("app", ()))

    def test_docs_sync_runs_after_a_committed_change_on_a_ticket_branch(self):
        profile, setup = probe_env(self._probe("ROUTE-docs-sync"))
        self.assertEqual(profile, "app-ticketed")
        self.assertTrue(setup[0].startswith("git checkout -qb task/TKT-1-"))
        self.assertTrue(any(step.startswith("git commit") for step in setup))
        self.assertTrue(any("orders/api.py" in step for step in setup))

    def test_the_prompts_themselves_are_unchanged_by_the_environment(self):
        # The environment carries the presupposition; the prompt still never
        # names the skill (the description-discrimination test is intact).
        for pid in ("ROUTE-create-requirements", "ROUTE-docs-sync",
                    "ROUTE-create-design"):
            prompt = self._probe(pid)["prompt"].lower()
            self.assertNotIn("acs:", prompt)
            self.assertNotIn(pid[len("ROUTE-"):], prompt)

    def test_a_prompt_about_an_epic_runs_where_an_epic_exists(self):
        # `ticketed` mints a small, low-stakes TASK; "this epic is
        # design-significant" is simply false there. `epic` mints a large,
        # high-stakes epic — the thing the prompt describes.
        self.assertEqual(probe_env(self._probe("ROUTE-create-design")),
                         ("epic", ()))

    def test_every_other_probe_keeps_the_default_sandbox(self):
        placed = ("ROUTE-create-requirements", "ROUTE-docs-sync",
                  "ROUTE-create-design")
        others = [p for p in self.probes if p["id"] not in placed]
        self.assertEqual({probe_env(p) for p in others}, {("ticketed", ())})

    def test_the_plan_counts_the_sandboxes(self):
        text = plan({"routing": {"runs_per_probe": 5},
                     "pipeline": {"runs_per_scenario": 3, "scenarios": []}},
                    self.probes, True, False, None)
        self.assertIn("sandboxes 4 for routing: ticketed, epic, app, "
                      "app-ticketed (+3 setup steps)", text)


class _FakeSandbox:
    events = []
    live = []

    def __init__(self, build, profile="bare", keep=False):
        self.profile = profile
        self.repo = "/repo/" + profile
        self.closed = False
        _FakeSandbox.live.append(self)
        _FakeSandbox.events.append(("build", profile))

    def shell(self, command):
        _FakeSandbox.events.append(("setup", self.profile, command))

    def close(self):
        self.closed = True
        _FakeSandbox.events.append(("close", self.profile))


class MeasureRoutingSandboxesTest(unittest.TestCase):
    """measure_routing builds one sandbox per environment, runs its setup once
    before the first session, and closes every sandbox — also on failure."""

    def setUp(self):
        _FakeSandbox.events, _FakeSandbox.live = [], []
        self._sandbox, self._route = measure_skills.Sandbox, measure_skills.route_once
        measure_skills.Sandbox = _FakeSandbox
        measure_skills.route_once = self._fake_route

    def tearDown(self):
        measure_skills.Sandbox, measure_skills.route_once = self._sandbox, self._route

    @staticmethod
    def _fake_route(prompt, cwd, timeout, env, build=None, keep_path=None):
        # `build` is recorded, not just accepted: measure_routing must hand the
        # resolved build to every probe, or the session loads whatever is
        # installed and the measurement describes the wrong plugin.
        _FakeSandbox.events.append(("route", cwd, prompt, build))
        if prompt == "boom":
            raise RuntimeError("session failed")
        return "acs:code", "skill_tool_use", None, 1.0

    _scenarios = {"routing": {"runs_per_probe": 2, "timeout_seconds": 1}}

    def test_one_sandbox_per_environment_with_setup_before_the_first_session(self):
        probes = [{"id": "a", "skill": "acs:code", "prompt": "pa"},
                  {"id": "b", "skill": "acs:code", "prompt": "pb",
                   "profile": "app-ticketed", "setup": ["git checkout -qb t", "git commit"]},
                  {"id": "c", "skill": "acs:code", "prompt": "pc"},
                  {"id": "d", "skill": "acs:code", "prompt": "pd",
                   "profile": "app-ticketed", "setup": ["git checkout -qb t", "git commit"]}]
        build = object()   # a sentinel: only threading can put it there
        out = measure_routing(build, self._scenarios, probes, {})
        builds = [e for e in _FakeSandbox.events if e[0] == "build"]
        self.assertEqual(builds, [("build", "ticketed"), ("build", "app-ticketed")])
        setups = [e for e in _FakeSandbox.events if e[0] == "setup"]
        self.assertEqual(setups, [("setup", "app-ticketed", "git checkout -qb t"),
                                  ("setup", "app-ticketed", "git commit")])
        # setup precedes the first session in that sandbox, and never re-runs
        first_route = next(i for i, e in enumerate(_FakeSandbox.events)
                           if e[0] == "route" and e[1:3] == ("/repo/app-ticketed", "pb"))
        self.assertTrue(all(_FakeSandbox.events.index(s) < first_route for s in setups))
        self.assertEqual([e[1] for e in _FakeSandbox.events if e[0] == "route"],
                         ["/repo/ticketed"] * 2 + ["/repo/app-ticketed"] * 2
                         + ["/repo/ticketed"] * 2 + ["/repo/app-ticketed"] * 2)
        self.assertTrue(all(sb.closed for sb in _FakeSandbox.live))
        self.assertEqual([r["profile"] for r in out],
                         ["ticketed", "app-ticketed", "ticketed", "app-ticketed"])
        # Every probe was handed the RESOLVED build. Asserted with a sentinel
        # rather than None, so the check cannot pass on the parameter default.
        self.assertEqual({e[3] for e in _FakeSandbox.events if e[0] == "route"},
                         {build},
                         "measure_routing must pass its build to every probe, "
                         "or the session loads whatever is installed")
        self.assertNotIn("setup", out[0])
        self.assertEqual(out[1]["setup"], ["git checkout -qb t", "git commit"])

    def test_every_sandbox_is_closed_when_a_session_raises(self):
        probes = [{"id": "a", "skill": "acs:code", "prompt": "pa", "profile": "app"},
                  {"id": "b", "skill": "acs:code", "prompt": "boom"}]
        with self.assertRaises(RuntimeError):
            measure_routing(None, self._scenarios, probes, {})
        self.assertEqual(len(_FakeSandbox.live), 2)
        self.assertTrue(all(sb.closed for sb in _FakeSandbox.live))

    def test_a_failing_setup_step_names_the_probe_and_the_step(self):
        import subprocess

        def bad_shell(self, command):
            raise subprocess.CalledProcessError(1, command, stderr="fatal: nope")
        original = _FakeSandbox.shell
        _FakeSandbox.shell = bad_shell
        try:
            with self.assertRaises(RuntimeError) as ctx:
                measure_routing(None, self._scenarios,
                                [{"id": "ROUTE-x", "skill": "acs:code", "prompt": "p",
                                  "setup": ["git checkout -qb t"]}], {})
        finally:
            _FakeSandbox.shell = original
        self.assertIn("ROUTE-x", str(ctx.exception))
        self.assertIn("git checkout -qb t", str(ctx.exception))
        self.assertIn("fatal: nope", str(ctx.exception))
        self.assertTrue(all(sb.closed for sb in _FakeSandbox.live))



class BuildUnderTestIsActuallyLoadedTest(unittest.TestCase):
    """`build under test: acs X` must name the build the session RAN.

    It did not. `measure_skills` resolved a build, printed that line, and then
    spawned `claude` with no plugin selector, so every session loaded whatever
    was installed. On a checkout ahead of the last release that silently
    invalidates a third of routing.json: skills the probes name do not exist in
    the installed build, and negative probes assert a no-auto-invoke guarantee
    its skills do not carry.
    """

    class _Build:
        root = "/somewhere/src/acs"
        version = "0.4.10-rc1"

    def test_a_routing_probe_loads_the_resolved_build(self):
        cmd = route_cmd("do the thing", self._Build())
        self.assertIn("--plugin-dir", cmd)
        self.assertEqual(cmd[cmd.index("--plugin-dir") + 1], self._Build.root)

    def test_a_pipeline_session_loads_the_resolved_build(self):
        cmd = session_cmd("do the thing", self._Build())
        self.assertIn("--plugin-dir", cmd)
        self.assertEqual(cmd[cmd.index("--plugin-dir") + 1], self._Build.root)

    def test_a_routing_probe_has_exactly_one_tool_to_reach_for(self):
        # --allowedTools is a PERMISSION allowlist: with it alone the session
        # still advertised all 38 built-in tools, so the model could read the
        # repo and do the job by hand instead of routing -- which is what
        # every "routed nowhere" miss on the 2026-09-13 measurement turned out
        # to be. --tools is the tool-SET selector.
        cmd = route_cmd("do the thing")
        self.assertIn("--tools", cmd)
        self.assertEqual(cmd[cmd.index("--tools") + 1], "Skill")

    def test_a_pipeline_session_keeps_its_full_tool_set(self):
        # The opposite requirement: a pipeline scenario must actually do the
        # work, so it is never narrowed to one tool.
        self.assertNotIn("--tools", session_cmd("do the thing"))

    def test_without_a_build_no_plugin_is_forced(self):
        """The parameter is optional so a caller can still measure whatever is
        installed -- deliberately, but only by asking for it."""
        for cmd in (route_cmd("x"), session_cmd("x")):
            self.assertNotIn("--plugin-dir", cmd)


class BuildIdentityCheckTest(unittest.TestCase):
    """Passing --plugin-dir fixes the cause; this check keeps it honest."""

    def _build(self, skills):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        for name in skills:
            os.makedirs(os.path.join(tmp, "skills", name))
        return type("B", (), {"root": tmp, "version": "test"})()

    def _check(self, shipped, registered):
        build = self._build(shipped)
        original = measure_skills.registered_skills
        measure_skills.registered_skills = lambda *a, **k: registered
        self.addCleanup(setattr, measure_skills, "registered_skills", original)
        return measure_skills.build_identity_check(build, "/tmp", {})

    def test_matching_sets_pass(self):
        got = self._check(["code", "ship"], {"acs:code", "acs:ship"})
        self.assertTrue(got["passed"], got)

    def test_a_shipped_skill_the_session_never_registered_fails(self):
        got = self._check(["code", "ship"], {"acs:code"})
        self.assertFalse(got["passed"])
        self.assertIn("acs:ship", got["reason"])

    def test_a_registered_skill_the_build_does_not_ship_fails(self):
        """The installed-build case: the session carries skills from somewhere
        other than the build the measurement claims to describe."""
        got = self._check(["code"], {"acs:code", "acs:create-quality"})
        self.assertFalse(got["passed"])
        self.assertIn("acs:create-quality", got["reason"])

    def test_no_registration_list_is_a_failure_not_a_pass(self):
        got = self._check(["code"], None)
        self.assertFalse(got["passed"])
        self.assertEqual(got["detection"], "unmeasured")

    def test_an_unreadable_build_is_a_failure(self):
        build = type("B", (), {"root": "/no/such/build", "version": "x"})()
        got = measure_skills.build_identity_check(build, "/tmp", {})
        self.assertFalse(got["passed"])
        self.assertEqual(got["detection"], "unreadable")


class CheckpointTest(unittest.TestCase):
    """Paid work must survive the process that bought it.

    A tier-3 run spends hundreds of real sessions and used to write once, at
    the very end. The run that proved this necessary was killed at 29 of 43
    probes: roughly 145 paid sessions, and not one byte on disk to show for
    them, because every record was still in memory.
    """

    def _path(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        return os.path.join(tmp, "m.json.partial")

    def test_a_record_is_on_disk_the_moment_it_exists(self):
        path = self._path()
        measure_skills.Checkpoint(path).add({"id": "ROUTE-code", "kind": "routing"})
        self.assertTrue(os.path.exists(path))
        self.assertEqual(measure_skills.Checkpoint(path).get("ROUTE-code")["kind"],
                         "routing")

    def test_a_later_run_reads_back_everything_already_bought(self):
        path = self._path()
        first = measure_skills.Checkpoint(path)
        for i in range(3):
            first.add({"id": "ROUTE-%d" % i, "kind": "routing"})
        self.assertEqual(len(measure_skills.Checkpoint(path).done), 3)

    def test_a_torn_final_line_costs_one_record_not_all_of_them(self):
        """A kill mid-write leaves half a line. JSONL is used precisely so the
        records before it still count -- half a JSON object would lose every
        session in the file."""
        path = self._path()
        cp = measure_skills.Checkpoint(path)
        cp.add({"id": "ROUTE-a", "kind": "routing"})
        cp.add({"id": "ROUTE-b", "kind": "routing"})
        with open(path, "a", encoding="utf-8") as fh:
            fh.write('{"id": "ROUTE-c", "kind": "rout')     # killed mid-write
        reread = measure_skills.Checkpoint(path)
        self.assertEqual(sorted(reread.done), ["ROUTE-a", "ROUTE-b"])

    def test_discard_removes_it_only_when_asked(self):
        path = self._path()
        cp = measure_skills.Checkpoint(path)
        cp.add({"id": "ROUTE-a"})
        self.assertTrue(os.path.exists(path))
        cp.discard()
        self.assertFalse(os.path.exists(path))

    def test_no_path_keeps_working_in_memory(self):
        cp = measure_skills.Checkpoint(None)
        cp.add({"id": "ROUTE-a"})
        self.assertIsNotNone(cp.get("ROUTE-a"))
        cp.discard()   # must not raise


class RoutingResumesInsteadOfRespendingTest(unittest.TestCase):
    """The point of the checkpoint: a resumed run buys nothing twice."""

    def setUp(self):
        _FakeSandbox.events, _FakeSandbox.live = [], []
        self._sandbox = measure_skills.Sandbox
        self._route = measure_skills.route_once
        measure_skills.Sandbox = _FakeSandbox
        self.spent = []

        def fake_route(prompt, cwd, timeout, env, build=None, keep_path=None):
            self.spent.append(prompt)
            return "acs:code", "skill_tool_use", None, 1.0

        measure_skills.route_once = fake_route

    def tearDown(self):
        measure_skills.Sandbox = self._sandbox
        measure_skills.route_once = self._route

    def test_a_probe_already_in_the_checkpoint_spends_nothing(self):
        probes = [{"id": "a", "skill": "acs:code", "prompt": "pa"},
                  {"id": "b", "skill": "acs:code", "prompt": "pb"}]
        cp = measure_skills.Checkpoint(None)
        cp.add({"id": "a", "kind": "routing", "skill": "acs:code",
                "runs": [], "aggregate": {"reliability": {"hits": 5, "total": 5}}})
        out = measure_routing(None, {"routing": {"runs_per_probe": 2}},
                              probes, {}, checkpoint=cp)
        self.assertEqual(self.spent, ["pb", "pb"],
                         "only the unmeasured probe may spend")
        self.assertEqual([r["id"] for r in out], ["a", "b"],
                         "the reused record must still reach the measurement")

    def test_every_fresh_record_is_checkpointed_as_it_completes(self):
        probes = [{"id": "a", "skill": "acs:code", "prompt": "pa"}]
        cp = measure_skills.Checkpoint(None)
        measure_routing(None, {"routing": {"runs_per_probe": 1}}, probes, {},
                        checkpoint=cp)
        self.assertIn("a", cp.done)

class SkillTrailTest(unittest.TestCase):
    """What a pipeline run actually invoked, from its stream-json transcript.

    PIPE-code fell from 3/3 to 1/3 on 2026-09-13 with two runs hitting the
    1800s wall, and the measurement could not say what either was doing: the
    old `--output-format json` emits one envelope at the end, and a killed run
    never gets there.
    """

    def _transcript(self, events):
        path = tempfile.mktemp(suffix=".jsonl")
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        with open(path, "w", encoding="utf-8") as fh:
            for e in events:
                fh.write(json.dumps(e) + "\n")
        return path

    @staticmethod
    def _use(skill, call_id):
        return {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": call_id, "name": "Skill",
             "input": {"skill": skill}}]}}

    @staticmethod
    def _res(call_id, is_error=False):
        return {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": call_id,
             "is_error": is_error, "content": "ok"}]}}

    def test_the_sequence_is_recorded_in_order(self):
        path = self._transcript([
            self._use("acs:create-impl-plan", "t1"), self._res("t1"),
            self._use("acs:code", "t2"), self._res("t2"),
            {"type": "result", "total_cost_usd": 1.5, "num_turns": 9}])
        envelope, skills, truncated = measure_skills.read_stream(path)
        self.assertEqual([s["skill"] for s in skills],
                         ["acs:create-impl-plan", "acs:code"])
        self.assertEqual(envelope["num_turns"], 9)
        self.assertFalse(truncated)

    def test_a_transcript_with_no_result_event_still_yields_its_trail(self):
        # The timeout case, and the reason this exists at all.
        path = self._transcript([self._use("acs:code", "t1"), self._res("t1"),
                                 self._use("acs:create-standards", "t2")])
        envelope, skills, _ = measure_skills.read_stream(path)
        self.assertIsNone(envelope)
        self.assertEqual([s["skill"] for s in skills],
                         ["acs:code", "acs:create-standards"])

    def test_a_refused_call_is_marked_not_dropped(self):
        path = self._transcript([self._use("acs:update", "t1"),
                                 self._res("t1", is_error=True)])
        _, skills, _ = measure_skills.read_stream(path)
        self.assertEqual(skills, [{"skill": "acs:update", "ok": False}])

    def test_the_trail_is_bounded(self):
        events = []
        for i in range(measure_skills.MAX_SKILL_TRAIL + 20):
            events.append(self._use("acs:code", "t%d" % i))
        path = self._transcript(events)
        _, skills, truncated = measure_skills.read_stream(path)
        self.assertEqual(len(skills), measure_skills.MAX_SKILL_TRAIL)
        self.assertTrue(truncated)

    def test_garbage_and_odd_shapes_are_survived(self):
        path = self._transcript([])
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("not json\n[1,2]\nnull\n")
            fh.write(json.dumps({"type": "result", "message": "a string",
                                 "total_cost_usd": 2.0}) + "\n")
        envelope, skills, _ = measure_skills.read_stream(path)
        self.assertEqual(envelope["total_cost_usd"], 2.0)
        self.assertEqual(skills, [])

    def test_a_missing_transcript_is_empty_not_an_error(self):
        self.assertEqual(measure_skills.read_stream("/no/such/file"),
                         (None, [], False))

    def test_the_pipeline_session_asks_for_the_stream(self):
        cmd = measure_skills.session_cmd("do the thing")
        self.assertEqual(cmd[cmd.index("--output-format") + 1], "stream-json")
        self.assertIn("--verbose", cmd)

    def test_runs_of_one_skill_collapse_in_the_summary(self):
        trail = [{"skill": "acs:code", "ok": True}] * 3 + [
            {"skill": "acs:create-pr", "ok": True}]
        self.assertEqual(measure_skills.summarize_trail(trail),
                         "acs:code x3 -> acs:create-pr")

    def test_the_summary_names_a_refusal(self):
        self.assertEqual(
            measure_skills.summarize_trail([{"skill": "acs:update", "ok": False}]),
            "acs:update(refused)")


class AlreadyMeasuredTest(unittest.TestCase):
    """`make measure` is a no-op for a build already measured -- and only then.

    The release gate runs `make measure` before every cut. Re-spending four
    hours on a build whose complete measurement is already on disk would get
    the gate skipped; spending nothing on a build that merely LOOKS measured
    would get a release quoting another build's numbers. The reuse rule has
    to be exact.
    """

    class _Build:
        version = "0.5.0"
        digest = "c0ffeec0ffeec0ff"

    HASHES = {"routing": "r1", "pipeline": "p1"}

    def _doc(self, **over):
        doc = {"build": {"version": "0.5.0", "digest": "c0ffeec0ffeec0ff"},
               "set_hashes": dict(self.HASHES), "scope": "full",
               "incomplete": False, "generated_at": "2026-09-14T00:00:00Z"}
        doc.update(over)
        return doc

    def _reuse(self, doc, scope="full"):
        return measure_skills.already_measured(doc, self._Build(),
                                               dict(self.HASHES), scope)

    def test_the_identical_build_and_experiment_are_reused(self):
        reason = self._reuse(self._doc())
        self.assertIn("2026-09-14", reason, "say when it was taken")
        self.assertIn("c0ffeec0ffeec0ff", reason)

    def test_other_content_spends(self):
        self.assertIsNone(self._reuse(self._doc(
            build={"version": "0.5.0", "digest": "d15ea5ed15ea5ed1"})))

    def test_a_document_that_cannot_name_its_build_spends(self):
        self.assertIsNone(self._reuse(self._doc(build={"version": "0.5.0"})))

    def test_a_changed_experiment_spends(self):
        self.assertIsNone(self._reuse(self._doc(
            set_hashes={"routing": "r1", "pipeline": "p2"})))

    def test_an_incomplete_measurement_spends(self):
        self.assertIsNone(self._reuse(self._doc(incomplete=True)))

    def test_a_full_measurement_covers_a_half_request(self):
        self.assertIsNotNone(self._reuse(self._doc(), scope="routing"))

    def test_a_half_measurement_does_not_cover_the_full_request(self):
        self.assertIsNone(self._reuse(self._doc(scope="routing"), scope="full"))

    def test_a_half_measurement_covers_its_own_half_only(self):
        self.assertIsNotNone(self._reuse(self._doc(scope="routing"),
                                         scope="routing"))
        self.assertIsNone(self._reuse(self._doc(scope="routing"),
                                      scope="pipeline"))

    def test_no_document_spends(self):
        self.assertIsNone(self._reuse(None))


class SelectScenariosTest(unittest.TestCase):

    SET = {"scenario_set_version": "1.6.0",
           "pipeline": {"runs_per_scenario": 3,
                        "scenarios": [{"id": "PIPE-code"},
                                      {"id": "PIPE-code-app"},
                                      {"id": "PIPE-docs-sync"}]}}

    def test_a_glob_selects_and_the_original_is_untouched(self):
        got = measure_skills.select_scenarios(self.SET, "PIPE-code*")
        self.assertEqual([s["id"] for s in got["pipeline"]["scenarios"]],
                         ["PIPE-code", "PIPE-code-app"])
        self.assertEqual(got["pipeline"]["runs_per_scenario"], 3)
        self.assertEqual(len(self.SET["pipeline"]["scenarios"]), 3,
                         "the hashes come from the full set, which must "
                         "survive the selection")

    def test_an_exact_id_selects_one(self):
        got = measure_skills.select_scenarios(self.SET, "PIPE-code")
        self.assertEqual([s["id"] for s in got["pipeline"]["scenarios"]],
                         ["PIPE-code"])


class BuildRecordTest(unittest.TestCase):

    def test_a_measurement_names_its_build_by_content(self):
        class B:
            version, root = "0.5.0", "/src/acs"
            fingerprint, digest = "fac10cbbcd9f7fb5", "c077424d2d52ac47"
        rec = measure_skills.build_record(B())
        self.assertEqual(rec, {"version": "0.5.0", "root": "/src/acs",
                               "fingerprint": "fac10cbbcd9f7fb5",
                               "digest": "c077424d2d52ac47"})

    def test_identity_is_version_and_content(self):
        class B:
            version, digest = "0.5.0", "c077424d2d52ac47"
        self.assertEqual(measure_skills.identity_of(B()),
                         "0.5.0[c077424d2d52ac47]")
        self.assertIsNone(measure_skills.identity_of(None))


class CheckpointBuildIdentityTest(unittest.TestCase):
    """A checkpoint is reusable only for the build that bought it.

    On 2026-09-13 a run was stopped after 4 probes so the plugin could be
    changed; its checkpoint carried no build identity at all, so the next run
    would have reported those four probes -- measured with
    disable-model-invocation still set -- as the fixed build's.
    """

    class _Build:
        version = "0.4.9"
        digest = "aaaaaaaaaaaaaaaa"

    class _Other:
        version = "0.4.9"          # same version string, different content
        digest = "bbbbbbbbbbbbbbbb"

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="acs-cp-")
        self.path = os.path.join(self.dir, "m.json.partial")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _write(self, build):
        cp = measure_skills.Checkpoint(self.path, build)
        cp.add({"id": "ROUTE-code", "kind": "routing"})
        return cp

    def test_the_same_build_reuses_what_it_already_bought(self):
        self._write(self._Build())
        cp = measure_skills.Checkpoint(self.path, self._Build())
        self.assertIn("ROUTE-code", cp.done)
        self.assertIsNone(cp.dropped)

    def test_different_content_on_the_same_version_is_dropped(self):
        self._write(self._Build())
        cp = measure_skills.Checkpoint(self.path, self._Other())
        self.assertEqual(cp.done, {})
        self.assertEqual(cp.dropped[1], 1)
        self.assertFalse(os.path.exists(self.path),
                         "a checkpoint from another build must not survive to "
                         "be half-reused by the run after this one")

    def test_an_unstamped_checkpoint_is_dropped(self):
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"id": "ROUTE-code", "kind": "routing"}) + "\n")
        cp = measure_skills.Checkpoint(self.path, self._Build())
        self.assertEqual(cp.done, {})
        self.assertEqual(cp.dropped[0], "unstamped")

    def test_without_a_build_the_check_is_inert_not_guessed(self):
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"id": "ROUTE-code"}) + "\n")
        cp = measure_skills.Checkpoint(self.path, None)
        self.assertIn("ROUTE-code", cp.done)
        self.assertIsNone(cp.dropped)

    def test_the_stamp_is_written_once_and_is_not_a_record(self):
        cp = self._write(self._Build())
        cp.add({"id": "ROUTE-setup", "kind": "routing"})
        with open(self.path, encoding="utf-8") as fh:
            lines = [json.loads(l) for l in fh if l.strip()]
        self.assertEqual(sum(1 for l in lines if l.get("__build__")), 1)
        self.assertEqual(lines[0]["__build__"], "0.4.9[aaaaaaaaaaaaaaaa]")
        again = measure_skills.Checkpoint(self.path, self._Build())
        self.assertEqual(sorted(again.done), ["ROUTE-code", "ROUTE-setup"])


class SetupPreconditionTest(unittest.TestCase):
    """`setup_assert`: did the setup leave the sandbox where the scenario needs it?

    A setup prompt is a model session, so "it exited 0" is not the same claim
    as "the precondition holds". On 2026-09-13 a PIPE-docs-sync setup finished
    clean having asked five clarifying questions and written no code; docs-sync
    then correctly refused, and the refusal was scored against docs-sync.
    """

    class FakeSandbox:
        def __init__(self, repo, partition, ticket_id="TKT-1"):
            self.repo, self._partition = repo, partition
            self.ticket_id = ticket_id

        def ticket_dir(self):
            return self._partition

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="acs-setup-assert-")
        self.repo = os.path.join(self.base, "repo")
        self.partition = os.path.join(self.base, "part")
        os.makedirs(self.repo)
        os.makedirs(self.partition)
        self.sb = self.FakeSandbox(self.repo, self.partition)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def ledger(self, doc):
        with open(os.path.join(self.partition, "pipeline-state.json"), "w") as fh:
            json.dump(doc, fh)

    def test_no_assert_is_nothing_to_check_not_a_failure(self):
        self.assertTrue(measure_skills.setup_holds({}, self.sb, {}))

    def test_the_assert_reads_the_partition_the_sandbox_names(self):
        self.ledger({"steps": {"code": {"status": "completed"}}})
        scenario = {"setup_assert":
                    "test -f \"$ACS_PARTITION/pipeline-state.json\""}
        self.assertTrue(measure_skills.setup_holds(scenario, self.sb, {}))

    def test_the_ticket_id_is_bound_too(self):
        scenario = {"setup_assert": "test \"$ACS_TICKET_ID\" = TKT-1"}
        self.assertTrue(measure_skills.setup_holds(scenario, self.sb, {}))

    def test_a_failing_assert_marks_the_run_unmeasured(self):
        scenario = {"setup_assert": "false"}
        self.assertFalse(measure_skills.setup_holds(scenario, self.sb, {}))

    def test_an_assert_that_cannot_run_fails_closed(self):
        # An unmeasurable precondition is not a held precondition.
        scenario = {"setup_assert": "exec 2>/dev/null; sleep 5"}
        self.assertFalse(measure_skills.setup_holds(
            dict(scenario, setup_assert="no-such-command-anywhere"),
            self.sb, {}))

    def test_the_shipped_docs_sync_assert_reads_the_code_step(self):
        # The dataset's own command, run against real and degenerate ledgers.
        with open(os.path.join(
                os.path.dirname(os.path.abspath(__file__)), os.pardir,
                "dataset", "scenarios.json")) as fh:
            scenarios = json.load(fh)
        cmd = [s for s in scenarios["pipeline"]["scenarios"]
               if s["id"] == "PIPE-docs-sync"][0]["setup_assert"]
        scenario = {"setup_assert": cmd}
        self.ledger({"steps": {"code": {"status": "completed"}}})
        self.assertTrue(measure_skills.setup_holds(scenario, self.sb, {}))
        for short in ({"steps": {"code": {"status": "in_progress"}}},
                      {"steps": {"code": {"status": "failed"}}},
                      {"steps": {}}, {}):
            self.ledger(short)
            self.assertFalse(measure_skills.setup_holds(scenario, self.sb, {}),
                             "%r must not read as a completed code step" % short)
        os.remove(os.path.join(self.partition, "pipeline-state.json"))
        self.assertFalse(measure_skills.setup_holds(scenario, self.sb, {}),
                         "no ledger at all must fail closed")


class SetupBudgetTest(unittest.TestCase):
    """A setup prompt is another scenario's whole body, not a preamble.

    PIPE-docs-sync's setup is PIPE-code's prompt verbatim. Sized by docs-sync's
    900s it timed out; PIPE-code itself is given 1800s and took up to 1204s.
    """

    def budgets(self, scenario):
        return (scenario.get("setup_timeout_seconds",
                             scenario.get("timeout_seconds", 1800)),
                scenario.get("timeout_seconds", 1800))

    def test_a_scenario_without_setup_prompts_is_unchanged(self):
        self.assertEqual(self.budgets({"timeout_seconds": 600}), (600, 600))

    def test_setup_may_outrun_the_measured_budget(self):
        self.assertEqual(
            self.budgets({"timeout_seconds": 900,
                          "setup_timeout_seconds": 1800}), (1800, 900))

    def test_every_shipped_setup_gets_at_least_its_own_scenario_s_budget(self):
        with open(os.path.join(
                os.path.dirname(os.path.abspath(__file__)), os.pardir,
                "dataset", "scenarios.json")) as fh:
            scenarios = json.load(fh)["pipeline"]["scenarios"]
        # Keyed on (prompt, profile): PIPE-code and PIPE-code-app run the
        # same prompt on different sandboxes and cost differently.
        by_prompt = {(s["prompt"], s["profile"]): s for s in scenarios}
        for s in scenarios:
            for prompt in s.get("setup_prompts", []):
                twin = by_prompt.get((prompt, s["profile"]))
                if twin is None or twin["id"] == s["id"]:
                    continue
                setup_budget = self.budgets(s)[0]
                self.assertGreaterEqual(
                    setup_budget, twin["timeout_seconds"],
                    "%s's setup runs %s's body and must carry at least its "
                    "budget" % (s["id"], twin["id"]))



class QuotaExhaustedTest(unittest.TestCase):
    """The CLI refusing a session for a spent usage allowance is the
    instrument giving out, not a result: it is recognised, and the caller
    stops rather than paying a sandbox per run to record it N more times."""

    LIMIT = "You've hit your session limit \u00b7 resets 10:30am (UTC)"

    def test_a_limit_envelope_is_recognised(self):
        self.assertEqual(measure_skills.quota_message(
            {"is_error": True, "result": self.LIMIT}), self.LIMIT)
        self.assertEqual(measure_skills.quota_message(
            {"is_error": True, "result": "Usage limit reached for this week"}),
            "Usage limit reached for this week")

    def test_other_errors_and_clean_results_are_not(self):
        for envelope in ({"is_error": False, "result": self.LIMIT},
                         {"is_error": True, "result": "no such skill"},
                         {"is_error": True, "result": "rate limited, try again"},
                         {"is_error": True}, None, "text"):
            self.assertIsNone(measure_skills.quota_message(envelope), envelope)

    def test_a_routing_session_refused_for_quota_is_neither_route_nor_miss(self):
        result_event = json.dumps({"type": "result", "subtype": "success",
                                   "is_error": True, "result": self.LIMIT,
                                   "num_turns": 1, "total_cost_usd": 0})
        lines = [_init(), _assistant(_text(self.LIMIT)), result_event]
        self.assertEqual(classify(lines, "Implement the login feature"),
                         (None, "quota_exhausted", None))

    def test_a_tool_result_mentioning_a_rate_limit_still_routes(self):
        # A tool-level throttle is a routed probe whose call got a transient
        # error; only the session-level allowance message stops the run.
        lines = [_init(), _assistant(_skill("acs:code")),
                 _result(content="rate limited, try again", is_error=True)]
        self.assertEqual(classify(lines, "Implement the login feature"),
                         ("acs:code", "skill_tool_use", None))


class PromptIsTheWholePromptTest(unittest.TestCase):
    """`claude -p` appends a non-tty stdin to the prompt, and a child inherits
    its parent's stdin. The 2026-09-14 gate ran `make measure` from a shell
    loop reading its command list from a file: 25 of 27 pipeline sessions were
    prompted with the scenario text plus the three gate commands, and spent
    their first turns hunting for a `src/acs-evals` the sandbox does not have.
    Every spawn therefore closes stdin, whatever the caller's is."""

    class _Done:
        returncode = 0
        stdout = ""

    def _capture_run(self, calls):
        def fake_run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return self._Done()
        return fake_run

    def test_a_pipeline_session_never_reads_the_caller_s_stdin(self):
        calls = []
        with mock.patch.object(measure_skills.subprocess, "run",
                               self._capture_run(calls)):
            measure_skills.session_once("do the thing", os.getcwd(), 5, {})
        self.assertEqual(len(calls), 1)
        self.assertIs(calls[0][1].get("stdin"), subprocess.DEVNULL)

    def test_a_routing_probe_never_reads_the_caller_s_stdin(self):
        calls = []

        class _Proc:
            def __init__(self):
                self.stdout = io.StringIO("")

            def kill(self):
                pass

            def wait(self, timeout=None):
                return 0

            def poll(self):
                return 0

        def fake_popen(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return _Proc()

        with mock.patch.object(measure_skills.subprocess, "Popen", fake_popen):
            measure_skills.route_once("Implement the login feature",
                                      os.getcwd(), 5, {})
            measure_skills.registered_skills(None, os.getcwd(), {}, timeout=5)
        self.assertEqual(len(calls), 2)
        for _cmd, kwargs in calls:
            self.assertIs(kwargs.get("stdin"), subprocess.DEVNULL)


class WorkspaceIsEditableTest(unittest.TestCase):
    """Under `acceptEdits` a headless session may edit only its working
    directory and the directories it was given; the acs workspace sits beside
    the sandbox repo. A PIPE-docs-sync run on 2026-09-14 was interrupted
    exactly there: the coordinator's task XML failed validation, its Edit of
    the file in its own partition was refused, and it gave up on the loop."""

    def test_the_session_argv_adds_the_directories_it_is_given(self):
        cmd = session_cmd("do the thing", add_dirs=("/tmp/x/ws",))
        self.assertEqual(cmd[cmd.index("--add-dir") + 1], "/tmp/x/ws")

    def test_by_default_nothing_is_added(self):
        self.assertNotIn("--add-dir", session_cmd("do the thing"))
        self.assertNotIn("--add-dir", route_cmd("do the thing"))

    def test_the_pipeline_passes_the_sandbox_workspace(self):
        seen = []

        class FakeSandbox:
            ticket_id = "TKT-1"

            def __init__(self, build, profile="bare", keep=False):
                self.repo, self.ws = "/sb/repo", "/sb/ws"

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def fake_session(prompt, cwd, timeout, env, build=None, keep_dir=None,
                         add_dirs=()):
            seen.append(add_dirs)
            return {"ok": True, "seconds": 1.0, "cost_usd": 0.1, "turns": 1,
                    "error": None}

        ledger = {"status": "completed", "stop_reason": "", "role_usage": [],
                  "quality": {}, "ledger_cost_usd": None}
        scenarios = {"pipeline": {"runs_per_scenario": 1, "scenarios": [
            {"id": "PIPE-x", "skill": "acs:x", "profile": "seeded",
             "prompt": "do it", "setup_prompts": ["prepare"],
             "timeout_seconds": 5}]}}
        with mock.patch.object(measure_skills, "Sandbox", FakeSandbox), \
                mock.patch.object(measure_skills, "session_once", fake_session), \
                mock.patch.object(measure_skills, "read_ledger",
                                  lambda sb, skill: ledger), \
                mock.patch.object(measure_skills, "apply_ticket_patch",
                                  lambda scenario, sb: True), \
                mock.patch.object(measure_skills, "setup_holds",
                                  lambda scenario, sb, env: True), \
                mock.patch("sys.stdout", new=io.StringIO()):
            measure_skills.measure_pipeline(None, scenarios, {})
        self.assertEqual(seen, [("/sb/ws",), ("/sb/ws",)],
                         "setup and measured sessions alike may edit the workspace")


class MintedTicketLedgerTest(unittest.TestCase):
    """PIPE-create-ticket's skill mints the ticket, so the sandbox starts with
    no ticket id and the ledger lives under a directory only the run knows.
    Reading `<partition>/create-ticket-state.json` found nothing on every run
    of the 2026-09-14 gate, scoring transcripts that end in the post-hook's
    `completed` as "never ran"."""

    class FakeSandbox:
        def __init__(self, partition, ticket_id=None):
            self.partition, self.ticket_id = partition, ticket_id

        def ticket_dir(self, ticket_id=None):
            return os.path.join(self.partition, ticket_id or self.ticket_id or "")

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="acs-ledger-")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def ledger(self, ticket, skill, doc):
        d = os.path.join(self.base, ticket)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "%s-state.json" % skill), "w") as fh:
            json.dump(doc, fh)

    def test_a_minted_ticket_s_ledger_is_found_without_a_ticket_id(self):
        self.ledger("TKT-1", "create-ticket",
                    {"runs": [{"status": "completed", "stop_reason": "done"}]})
        out = measure_skills.read_ledger(self.FakeSandbox(self.base),
                                         "acs:create-ticket")
        self.assertEqual(out["status"], "completed")

    def test_no_ticket_at_all_is_still_never_ran(self):
        out = measure_skills.read_ledger(self.FakeSandbox(self.base),
                                         "acs:create-ticket")
        self.assertIsNone(out["status"])

    def test_a_known_ticket_id_is_read_directly(self):
        self.ledger("TKT-1", "code", {"runs": [{"status": "failed"}]})
        self.ledger("TKT-2", "code", {"runs": [{"status": "completed"}]})
        out = measure_skills.read_ledger(self.FakeSandbox(self.base, "TKT-1"),
                                         "acs:code")
        self.assertEqual(out["status"], "failed")


class StagedBuildTest(unittest.TestCase):
    """The build under test is measured from a copy outside any checkout.

    Resolved in place, this marketplace's build is `src/acs` inside the
    checkout running the measurement, and every command a skill embeds names
    that path. Two PIPE-create-ticket sessions on 2026-09-14 took it for the
    project, `cd`'d into the checkout before `skill-start.py --allocate`, and
    minted MAR-580 and MAR-581 in the marketplace's own workspace from inside
    a sandbox. Staged under a temp directory there is no checkout above the
    build for a stray `cd` to find."""

    def setUp(self):
        self.src = tempfile.mkdtemp(prefix="acs-src-")
        os.makedirs(os.path.join(self.src, ".claude-plugin"))
        with open(os.path.join(self.src, ".claude-plugin", "plugin.json"), "w") as fh:
            json.dump({"name": "acs", "version": "9.9.9"}, fh)
        os.makedirs(os.path.join(self.src, "hooks", "scripts", "__pycache__"))
        with open(os.path.join(self.src, "hooks", "scripts", "acs.py"), "w") as fh:
            fh.write("print('hi')\n")
        with open(os.path.join(self.src, "hooks", "scripts", "__pycache__", "acs.cpython-311.pyc"), "wb") as fh:
            fh.write(b"\x00")
        os.makedirs(os.path.join(self.src, "skills", "code"))
        with open(os.path.join(self.src, "skills", "code", "SKILL.md"), "w") as fh:
            fh.write("---\nname: code\ndescription: x\n---\n")
        from harness import Build
        self.build = Build(self.src)
        self.staged = None

    def tearDown(self):
        shutil.rmtree(self.src, ignore_errors=True)
        if self.staged is not None:
            shutil.rmtree(self.staged.stage_base, ignore_errors=True)

    def test_the_copy_lives_outside_the_source_tree_and_keeps_its_identity(self):
        self.staged = measure_skills.stage_build(self.build)
        self.assertFalse(self.staged.root.startswith(self.src))
        self.assertEqual(self.staged.digest, self.build.digest)
        self.assertEqual(self.staged.version, self.build.version)
        self.assertEqual(self.staged.source_root, self.src)
        self.assertEqual(measure_skills.plugin_args(self.staged),
                         ["--plugin-dir", self.staged.root])

    def test_bytecode_is_not_copied(self):
        self.staged = measure_skills.stage_build(self.build)
        self.assertFalse(os.path.exists(
            os.path.join(self.staged.root, "hooks", "scripts", "__pycache__")))
        self.assertTrue(os.path.isfile(
            os.path.join(self.staged.root, "skills", "code", "SKILL.md")))

    def test_nothing_above_the_staged_build_is_an_acs_checkout(self):
        self.staged = measure_skills.stage_build(self.build)
        d = os.path.dirname(self.staged.root)
        while True:
            self.assertFalse(os.path.exists(os.path.join(d, ".acs", "settings.json")), d)
            parent = os.path.dirname(d)
            if parent == d:
                break
            d = parent


class RoutingMissKeepsItsStreamTest(unittest.TestCase):
    """A routing miss used to leave nothing behind: ROUTE-create-prd split
    4/5 on 2026-09-15 after 20 straight hits, with `routed_to: null` and no
    Skill call in the stream, and nothing could say what the model did. The
    stream every probe's decision reads is now teed to a file, and a miss
    keeps it beside the pipeline transcripts."""

    def test_the_hit_rule_matches_the_gate_s(self):
        pos = {"skill": "acs:code", "must_route": True}
        neg = {"skill": "acs:standardize-project", "must_route": False}
        ctl = {"skill": None, "must_route": False}
        self.assertTrue(measure_skills.routing_hit(pos, "acs:code"))
        self.assertFalse(measure_skills.routing_hit(pos, None))
        self.assertFalse(measure_skills.routing_hit(pos, "acs:ship"))
        self.assertTrue(measure_skills.routing_hit(neg, "acs:project"))
        self.assertFalse(measure_skills.routing_hit(neg, "acs:standardize-project"))
        self.assertTrue(measure_skills.routing_hit(ctl, None))
        self.assertFalse(measure_skills.routing_hit(ctl, "acs:code"))

    def test_route_once_tees_the_stream_it_reads(self):
        lines = [_init(), _assistant(_text("Which product do you mean?")),
                 json.dumps({"type": "result", "subtype": "success",
                             "is_error": False, "num_turns": 1})]

        class _Proc:
            def __init__(self):
                self.stdout = io.StringIO("\n".join(lines) + "\n")

            def kill(self):
                pass

            def wait(self, timeout=None):
                return 0

        keep = tempfile.mktemp(prefix="acs-route-test-", suffix=".jsonl")
        try:
            with mock.patch.object(measure_skills.subprocess, "Popen",
                                   lambda cmd, **kw: _Proc()):
                routed, detection, attempted, _s = measure_skills.route_once(
                    "Define this product properly", os.getcwd(), 5, {},
                    keep_path=keep)
            self.assertIsNone(routed)
            self.assertEqual(detection, "skill_tool_use")
            with open(keep) as fh:
                kept = fh.read()
            self.assertIn("Which product do you mean?", kept)
        finally:
            if os.path.exists(keep):
                os.unlink(keep)

    def test_only_a_miss_is_kept(self):
        base = tempfile.mkdtemp(prefix="acs-route-keep-")
        transcripts = os.path.join(base, "transcripts")
        outcomes = iter(["acs:create-prd", None, "acs:create-prd"])

        def fake_route(prompt, cwd, timeout, env, build=None, keep_path=None):
            with open(keep_path, "w") as fh:
                fh.write("{}\n")
            return next(outcomes), "skill_tool_use", None, 1.0

        scenarios = {"routing": {"runs_per_probe": 3, "timeout_seconds": 5}}
        probes = [{"id": "ROUTE-create-prd", "skill": "acs:create-prd",
                   "prompt": "Define this product properly", "must_route": True,
                   "profile": "ticketed"}]
        saved = (measure_skills.Sandbox, measure_skills.route_once)
        measure_skills.Sandbox, measure_skills.route_once = _FakeSandbox, fake_route
        _FakeSandbox.events, _FakeSandbox.live = [], []
        try:
            with mock.patch("sys.stdout", new=io.StringIO()):
                recs = measure_skills.measure_routing(None, scenarios, probes, {},
                                                      transcripts=transcripts)
        finally:
            measure_skills.Sandbox, measure_skills.route_once = saved
            shutil.rmtree(base, ignore_errors=True)
        runs = recs[0]["runs"]
        self.assertEqual([r.get("routed_to") for r in runs],
                         ["acs:create-prd", None, "acs:create-prd"])
        self.assertNotIn("transcript", runs[0])
        self.assertIn("ROUTE-create-prd-run1", runs[1]["transcript"])
        self.assertNotIn("transcript", runs[2])
        self.assertEqual(recs[0]["aggregate"]["reliability"]["hits"], 2)


if __name__ == "__main__":
    unittest.main()
