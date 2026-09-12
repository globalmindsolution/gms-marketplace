"""MAR-575 -- how the eval harness decides where a routing probe went.

A user-typed `/acs:<skill>` is expanded into the prompt by the CLI and never
dispatched through the `Skill` tool, so a detector that only watches for a
`Skill` tool_use can never see an explicit probe: the two
`disable-model-invocation` skills scored as misses on every paid run. The rule
pinned here is the one `evals/acs/harness.py` implements -- a description
prompt is decided by the first `Skill` tool_use, an explicit prompt by the
`init` event's `slash_commands` registration list, and an explicit prompt whose
stream never reports that list is `unmeasured`, never a pass.

Also pins s04's probe set: 27 cases covering all 25 shipped skills, with no new
description prompt naming a skill, and every assertion label stating which rule
decided it.

Pure: synthetic stream-json lines and fake sandboxes -- no `claude`, no
network, no cost.

Run:  python3 -m unittest tests.acs.test_eval_trigger_detection -v
"""

import json
import os
import sys
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SKILLS_DIR = os.path.join(REPO_ROOT, "plugins", "acs", "skills")

sys.path.insert(0, os.path.join(REPO_ROOT, "evals", "acs"))
import harness  # noqa: E402  (path-inserted, same resolution run_evals.py uses)
from scenarios import s04_skill_triggers as s04  # noqa: E402


def _init(commands=("acs:install-hooks", "acs:update", "acs:code"),
          with_list=True):
    event = {"type": "system", "subtype": "init", "session_id": "s"}
    if with_list:
        event["slash_commands"] = list(commands)
    return json.dumps(event)


def _assistant(*blocks):
    return json.dumps({"type": "assistant", "message": {"content": list(blocks)}})


def _skill(name):
    return {"type": "tool_use", "name": "Skill", "input": {"skill": name}}


def _text(text):
    return {"type": "text", "text": text}


def shipped_skills():
    """Every skill name the plugin ships (a dir with a SKILL.md)."""
    return sorted(
        name for name in os.listdir(SKILLS_DIR)
        if os.path.isfile(os.path.join(SKILLS_DIR, name, "SKILL.md"))
    )


class ExplicitSkillTest(unittest.TestCase):
    def test_description_prompt_is_not_explicit(self):
        self.assertIsNone(harness.explicit_skill("Set up the git hooks for this repo."))

    def test_slash_command_names_its_skill(self):
        self.assertEqual(harness.explicit_skill("/acs:install-hooks"), "acs:install-hooks")
        self.assertEqual(harness.explicit_skill("  /acs:update  "), "acs:update")

    def test_arguments_are_dropped(self):
        self.assertEqual(harness.explicit_skill("/acs:code EVAL-1"), "acs:code")

    def test_bare_slash_is_nothing(self):
        self.assertIsNone(harness.explicit_skill("/"))
        self.assertIsNone(harness.explicit_skill(""))
        self.assertIsNone(harness.explicit_skill(None))


class DescriptionProbeTest(unittest.TestCase):
    PROMPT = "Implement ticket EVAL-1 using the TDD cycle."

    def test_first_skill_tool_use_decides(self):
        lines = [_init(), _assistant(_text("Thinking."), _skill("acs:code")),
                 _assistant(_skill("acs:create-pr"))]
        self.assertEqual(harness.classify(lines, self.PROMPT),
                         ("acs:code", "skill_tool_use"))

    def test_stops_reading_at_the_decision(self):
        seen = []

        def lines():
            for line in [_init(), _assistant(_skill("acs:code")),
                         _assistant(_skill("acs:create-pr"))]:
                seen.append(line)
                yield line

        harness.classify(lines(), self.PROMPT)
        self.assertEqual(len(seen), 2)

    def test_no_skill_call_is_a_none_result(self):
        lines = [_init(), _assistant(_text("I cannot help with that."))]
        self.assertEqual(harness.classify(lines, self.PROMPT), (None, "skill_tool_use"))

    def test_init_registration_never_decides_a_description_probe(self):
        # The model must choose; the CLI knowing the command is not routing.
        lines = [_init(commands=("acs:code",)), _assistant(_text("Done."))]
        self.assertEqual(harness.classify(lines, self.PROMPT), (None, "skill_tool_use"))

    def test_garbage_lines_are_skipped(self):
        lines = ["not json", "[1,2]", "null", _assistant(_skill("acs:setup"))]
        self.assertEqual(harness.classify(lines, self.PROMPT),
                         ("acs:setup", "skill_tool_use"))


class ExplicitProbeTest(unittest.TestCase):
    def test_registered_command_routes_at_init(self):
        lines = [_init(), _assistant(_text("Resolving repo roots."))]
        self.assertEqual(harness.classify(lines, "/acs:install-hooks"),
                         ("acs:install-hooks", "registered"))

    def test_decided_before_any_model_turn(self):
        seen = []

        def lines():
            for line in [_init(), _assistant(_text("first turn"))]:
                seen.append(line)
                yield line

        harness.classify(lines(), "/acs:update")
        self.assertEqual(len(seen), 1)

    def test_unregistered_command_is_a_miss(self):
        lines = [_init(commands=("acs:code",)), _assistant(_text("?"))]
        self.assertEqual(harness.classify(lines, "/acs:install-hooks"),
                         (None, "registered"))

    def test_init_without_a_registration_list_is_unmeasured(self):
        lines = [_init(with_list=False), _assistant(_text("?"))]
        self.assertEqual(harness.classify(lines, "/acs:install-hooks"),
                         (None, "unmeasured"))

    def test_no_init_at_all_is_unmeasured(self):
        lines = [_assistant(_text("?"))]
        self.assertEqual(harness.classify(lines, "/acs:update"), (None, "unmeasured"))

    def test_exact_command_match_only(self):
        # A same-named command from another namespace is not this skill.
        lines = [_init(commands=("other:install-hooks", "install-hooks"))]
        self.assertEqual(harness.classify(lines, "/acs:install-hooks"),
                         (None, "registered"))


class _FakeProc:
    """A `claude -p` stand-in whose stdout is a fixed stream-json script."""

    def __init__(self, lines):
        self.stdout = iter(lines)
        self.terminated = False
        self.killed = False
        self.waited = False

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        self.waited = True
        return 0


class TriggerDetailTest(unittest.TestCase):
    """`Sandbox.trigger_detail` drives claude and returns the pair; `trigger`
    keeps its single-value contract."""

    def _sandbox(self):
        sb = harness.Sandbox.__new__(harness.Sandbox)
        sb.repo = REPO_ROOT
        sb.env = {}
        return sb

    def _run(self, lines, request):
        proc = _FakeProc(lines)
        with mock.patch.object(harness.subprocess, "Popen", return_value=proc) as popen:
            got = self._sandbox().trigger_detail(request)
        return got, proc, popen

    def test_description_probe_returns_skill_and_rule(self):
        got, proc, _ = self._run([_init(), _assistant(_skill("acs:create-ticket"))],
                                 "Create a ticket for dark mode.")
        self.assertEqual(got, ("acs:create-ticket", "skill_tool_use"))
        self.assertTrue(proc.terminated or proc.killed)
        self.assertTrue(proc.waited or proc.killed)

    def test_explicit_probe_is_decided_at_init(self):
        got, _, _ = self._run([_init(), _assistant(_skill("acs:code"))],
                              "/acs:install-hooks")
        self.assertEqual(got, ("acs:install-hooks", "registered"))

    def test_unmeasured_when_the_session_reports_no_registration(self):
        got, _, _ = self._run([_init(with_list=False)], "/acs:update")
        self.assertEqual(got, (None, "unmeasured"))

    def test_process_is_stopped_even_when_nothing_routes(self):
        got, proc, _ = self._run([_init()], "Do something unrelated.")
        self.assertEqual(got, (None, "skill_tool_use"))
        self.assertTrue(proc.terminated or proc.killed)

    def test_trigger_returns_only_the_routed_skill(self):
        proc = _FakeProc([_init(), _assistant(_skill("acs:create-ticket"))])
        with mock.patch.object(harness.subprocess, "Popen", return_value=proc):
            self.assertEqual(self._sandbox().trigger("Create a ticket for dark mode."),
                             "acs:create-ticket")

    def test_stream_json_command_line_is_unchanged(self):
        _, _, popen = self._run([_init()], "/acs:update")
        argv = popen.call_args[0][0]
        self.assertEqual(argv[:2], ["claude", "-p"])
        self.assertIn("stream-json", argv)
        self.assertIn("--allowedTools", argv)
        self.assertEqual(argv[argv.index("--allowedTools") + 1], "Skill")


class S04ProbeSetTest(unittest.TestCase):
    """AC-3: every shipped skill has a probe unless UNPROBED records why, and
    no new description prompt names a skill. MAR-575 asserted plain equality
    with the shipped set; the skills-independence refactor added five unprobed
    Build/Test skills and the run-e2e-tests alias, so the guard now carries an
    explicit exclusion list instead of a false completeness claim."""

    NEW_CASES = {"create-docs", "create-requirements", "docs-sync"}

    # Shipped skill directories with no probe, each for a stated reason. The
    # skills-independence refactor added five Build/Test skills and left `test`
    # behind as a deprecated alias of run-e2e-tests; probing the five moves the
    # measured routing-coverage claim the PRD and roadmap carry, so they are
    # added with a fresh paid measurement rather than alongside the refactor,
    # and the alias is deliberately unprobed because its own probe targets the
    # new name. Anything else missing a probe is a defect this test catches.
    # `project` joins them for the same reason: the design-phase entry-point
    # fold mints it as a new user-facing umbrella, and probing it moves the
    # measured routing-coverage claim, so its probe lands with the next paid
    # measurement rather than alongside the fold.
    UNPROBED = {"analyze-ticket", "create-api-contract", "create-impl-plan",
                "create-test-docs", "create-e2e-tests", "test", "project"}

    def test_every_shipped_skill_has_a_probe_or_a_recorded_reason(self):
        probed = {expected for _, _, _, expected in s04.CASES}
        probed |= {forbidden for _, _, _, forbidden in s04.NEGATIVE}
        shipped = set(shipped_skills())
        self.assertEqual(
            probed, shipped - self.UNPROBED,
            "every shipped skill needs a probe unless it is listed in UNPROBED "
            "with its reason")
        self.assertEqual(
            self.UNPROBED & shipped, self.UNPROBED,
            "UNPROBED names a skill that no longer ships — drop it from the set")

    def test_case_counts(self):
        self.assertEqual(len(s04.CASES), 25)
        self.assertEqual(len(s04.NEGATIVE), 2)
        self.assertEqual(len({expected for _, _, _, expected in s04.CASES}), 25)

    def test_the_three_new_cases_expect_their_own_skill(self):
        by_label = {label: expected for label, _, _, expected in s04.CASES}
        for name in sorted(self.NEW_CASES):
            self.assertEqual(by_label.get(name), name)

    def test_new_prompts_name_no_skill(self):
        names = shipped_skills()
        forms = [n for n in names] + [n.replace("-", " ") for n in names]
        for label, _, request, _ in s04.CASES:
            if label not in self.NEW_CASES:
                continue
            text = request.lower()
            for form in forms:
                self.assertNotIn(form, text,
                                 "%s prompt names the skill %r" % (label, form))

    def test_only_the_user_only_skills_are_probed_explicitly(self):
        explicit = {label for label, _, request, _ in s04.CASES
                    if request.startswith("/")}
        self.assertEqual(explicit, {"install-hooks", "update"})


class _FakeSandbox:
    """Scripted stand-in for `harness.Sandbox` in a scenario run."""

    def __init__(self, answers):
        self.answers = answers

    def __call__(self, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def trigger_detail(self, request, **kwargs):
        return self.answers(request)


class S04DetectionIsReportedTest(unittest.TestCase):
    """AC-2: each case's assertion output states which rule decided it."""

    def _run(self, answers):
        with mock.patch.object(s04, "Sandbox", _FakeSandbox(answers)):
            return s04.run()

    def _all_right(self, request):
        """The answer that makes every probe pass: explicit probes registered,
        description probes routed to their skill, negative probes routed
        nowhere."""
        if request.startswith("/"):
            return harness.explicit_skill(request), "registered"
        expected = {req: exp for _, _, req, exp in s04.CASES}.get(request)
        if expected is None:  # a NEGATIVE probe: no auto-route is the pass
            return None, "skill_tool_use"
        return "acs:" + expected, "skill_tool_use"

    def test_every_label_states_the_deciding_rule(self):
        check = self._run(lambda request: (None, "skill_tool_use")
                          if not request.startswith("/")
                          else (harness.explicit_skill(request), "registered"))
        labels = [label for label, _, _ in check.results]
        self.assertEqual(len(labels), 27)
        for label in labels:
            self.assertTrue(label.endswith("[registered]")
                            or label.endswith("[skill_tool_use]")
                            or label.endswith("[unmeasured]"), label)

    def test_explicit_cases_pass_on_a_registration_decision(self):
        check = self._run(self._all_right)
        self.assertTrue(check.passed)
        explicit = [label for label, _, _ in check.results if "[registered]" in label]
        self.assertEqual(len(explicit), 2)

    def test_an_unmeasured_explicit_probe_is_never_a_pass(self):
        def answers(request):
            if request.startswith("/"):
                return None, "unmeasured"
            return self._all_right(request)

        check = self._run(answers)
        self.assertFalse(check.passed)
        failed = [label for label, ok, _ in check.results if not ok]
        self.assertEqual(len(failed), 2)
        for label in failed:
            self.assertIn("[unmeasured]", label)


if __name__ == "__main__":
    unittest.main()
