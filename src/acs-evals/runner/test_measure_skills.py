#!/usr/bin/env python3
"""Self-test for the routing collector's decision rule (`classify`).

Pure: feeds synthetic stream-json lines, no `claude`, no network, no cost.
The rule under test is the one `docs/PERFORMANCE.md` states — a description
prompt is decided by the first `Skill` tool_use; an explicit `/acs:<skill>`
prompt is decided by the `init` event's `slash_commands`; an explicit probe
whose stream never reports a registration list is `unmeasured`, never a pass.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

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


def _skill(name):
    return {"type": "tool_use", "name": "Skill", "input": {"skill": name}}


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
                 _assistant(_skill("acs:create-pr"))]
        self.assertEqual(classify(lines, self.PROMPT),
                         ("acs:code", "skill_tool_use"))

    def test_stops_reading_at_the_decision(self):
        seen = []

        def lines():
            for line in [_init(), _assistant(_skill("acs:code")),
                         _assistant(_skill("acs:create-pr"))]:
                seen.append(line)
                yield line

        classify(lines(), self.PROMPT)
        self.assertEqual(len(seen), 2)

    def test_no_skill_call_is_a_none_result(self):
        lines = [_init(), _assistant(_text("I cannot help with that."))]
        self.assertEqual(classify(lines, self.PROMPT), (None, "skill_tool_use"))

    def test_init_registration_never_decides_a_description_probe(self):
        # The model must choose; the CLI knowing the command is not routing.
        lines = [_init(), _assistant(_text("Done."))]
        self.assertEqual(classify(lines, self.PROMPT), (None, "skill_tool_use"))

    def test_garbage_lines_are_skipped(self):
        lines = ["not json", "[1,2]", "null", _assistant(_skill("acs:setup"))]
        self.assertEqual(classify(lines, self.PROMPT),
                         ("acs:setup", "skill_tool_use"))


class ExplicitProbeTest(unittest.TestCase):
    def test_registered_command_routes_at_init(self):
        lines = [_init(), _assistant(_text("Resolving repo roots."))]
        self.assertEqual(classify(lines, "/acs:install-hooks"),
                         ("acs:install-hooks", "registered"))

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
                         (None, "registered"))

    def test_init_without_a_registration_list_is_unmeasured(self):
        lines = [_init(with_list=False), _assistant(_text("?"))]
        self.assertEqual(classify(lines, "/acs:install-hooks"),
                         (None, "unmeasured"))

    def test_no_init_at_all_is_unmeasured(self):
        lines = [_assistant(_text("?"))]
        self.assertEqual(classify(lines, "/acs:update"), (None, "unmeasured"))

    def test_exact_command_match_only(self):
        # A same-named command from another namespace is not this skill.
        lines = [_init(commands=("other:install-hooks", "install-hooks"))]
        self.assertEqual(classify(lines, "/acs:install-hooks"),
                         (None, "registered"))


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
        for pid in ("ROUTE-create-requirements", "ROUTE-docs-sync"):
            prompt = self._probe(pid)["prompt"].lower()
            self.assertNotIn("acs:", prompt)
            self.assertNotIn(pid[len("ROUTE-"):], prompt)

    def test_every_other_probe_keeps_the_default_sandbox(self):
        others = [p for p in self.probes
                  if p["id"] not in ("ROUTE-create-requirements", "ROUTE-docs-sync")]
        self.assertEqual({probe_env(p) for p in others}, {("ticketed", ())})

    def test_the_plan_counts_the_sandboxes(self):
        text = plan({"routing": {"runs_per_probe": 5},
                     "pipeline": {"runs_per_scenario": 3, "scenarios": []}},
                    self.probes, True, False, None)
        self.assertIn("sandboxes 3 for routing: ticketed, app, "
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
    def _fake_route(prompt, cwd, timeout, env, build=None):
        # `build` is recorded, not just accepted: measure_routing must hand the
        # resolved build to every probe, or the session loads whatever is
        # installed and the measurement describes the wrong plugin.
        _FakeSandbox.events.append(("route", cwd, prompt, build))
        if prompt == "boom":
            raise RuntimeError("session failed")
        return "acs:code", "skill_tool_use", 1.0

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
        root = "/somewhere/plugins/acs"
        version = "0.4.10-rc1"

    def test_a_routing_probe_loads_the_resolved_build(self):
        cmd = route_cmd("do the thing", self._Build())
        self.assertIn("--plugin-dir", cmd)
        self.assertEqual(cmd[cmd.index("--plugin-dir") + 1], self._Build.root)

    def test_a_pipeline_session_loads_the_resolved_build(self):
        cmd = session_cmd("do the thing", self._Build())
        self.assertIn("--plugin-dir", cmd)
        self.assertEqual(cmd[cmd.index("--plugin-dir") + 1], self._Build.root)

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

if __name__ == "__main__":
    unittest.main()
