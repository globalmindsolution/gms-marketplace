"""MAR-575 -- how the eval harness decides where a routing probe went.

A user-typed `/acs:<skill>` is expanded into the prompt by the CLI and never
dispatched through the `Skill` tool, so a detector that only watches for a
`Skill` tool_use can never see an explicit probe: the two
`disable-model-invocation` skills scored as misses on every paid run. The rule
pinned here is the one `evals/behavioural/acs/harness.py` implements -- a description
prompt is decided by the first `Skill` tool_use, an explicit prompt by the
`init` event's `slash_commands` registration list, and an explicit prompt whose
stream never reports that list is `unmeasured`, never a pass.

Also pins the PROBE SET, which now lives in `evals/dataset/routing.json` and is
rendered into `claude plugin eval` cases: every shipped skill carries a probe,
no description prompt names a skill, and only the skills a user types directly
are probed explicitly. The sets are derived from the registry and the dataset
rather than written down here, so a new skill or a new leg moves them by itself.

This guard found two defects the moment it was pointed at the dataset:
`acs:test` was probed after skills/test was deleted, and `review-code` had no
probe at all.

Pure: synthetic stream-json lines and fake sandboxes -- no `claude`, no
network, no cost.

Run:  python3 -m unittest tests.acs.test_eval_trigger_detection -v
"""

import json
import os
import re
import sys
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SKILLS_DIR = os.path.join(REPO_ROOT, "plugins", "acs", "skills")
ROUTING = os.path.join(REPO_ROOT, "evals", "dataset", "routing.json")

sys.path.insert(0, os.path.join(REPO_ROOT, "evals", "behavioural", "acs"))
sys.path.insert(0, os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts"))
import acs_lib as lib  # noqa: E402  (the registry is the single source for legs)
import harness  # noqa: E402  (path-inserted, same resolution run_evals.py uses)


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


def internal_legs():
    """The legs of an entry-point fold — the set probed by explicit command
    plus a negative saying a description of the leg's subject must reach the
    ENTRY POINT rather than the leg. Read from the registry (phases.yaml's
    `internal` map), which is the single source and is itself pinned by
    test_phases_registry.py, so a new leg cannot drift out of this guard.

    This used to read `disable-model-invocation: true` off each SKILL.md. No
    skill sets that flag: the CLI enforces it by refusing the Skill call, and
    every one of these legs is dispatched by its entry point with a real
    `Skill(acs:<leg>)` call, so the flag broke both folds. Steering a
    description away from a leg is the description's job, which is what
    NEGATIVE measures."""
    return set(lib.skill_legs())


class ProbeSetTest(unittest.TestCase):
    """Every shipped skill is probed, and the probes stay honest.

    The probe set used to live in a behavioural scenario's hard-coded lists.
    It is now `evals/dataset/routing.json`, the curated data the
    `claude plugin eval` cases are rendered from, so this reads the dataset."""

    #: Skills whose probes were added by the docs-set fold and must expect
    #: themselves rather than the entry point that used to answer for them.
    NEW_CASES = {"create-docs", "create-requirements", "docs-sync"}

    #: Shipped skill directories with no probe, each for a stated reason.
    #: Empty, and it should stay empty: every shipped skill has a probe, so a
    #: missing one is a defect this test catches with no exclusions at all.
    UNPROBED = set()

    @staticmethod
    def _probes():
        with open(ROUTING, encoding="utf-8") as fh:
            doc = json.load(fh)
        return [p for p in doc["probes"] if p.get("kind") != "control"]

    @classmethod
    def _skill(cls, probe):
        return probe["skill"].split(":", 1)[1]

    def test_every_shipped_skill_has_a_probe_or_a_recorded_reason(self):
        probed = {self._skill(p) for p in self._probes()}
        shipped = set(shipped_skills())
        self.assertEqual(
            probed, shipped - self.UNPROBED,
            "every shipped skill needs a probe unless it is listed in UNPROBED "
            "with its reason")
        self.assertEqual(
            self.UNPROBED & shipped, self.UNPROBED,
            "UNPROBED names a skill that no longer ships — drop it from the set")

    def test_no_probe_names_a_skill_that_is_not_shipped(self):
        """The failure mode this caught: a renamed skill leaves its old name
        asserted, and the probe reads as a routing failure forever."""
        missing = sorted({self._skill(p) for p in self._probes()}
                         - set(shipped_skills()))
        self.assertEqual(missing, [], "probed skills with no directory on disk")

    def test_every_skill_carries_a_positive_probe(self):
        """Derived, not pinned: a negative alone proves nothing routes there."""
        positive = {self._skill(p) for p in self._probes() if p["must_route"]}
        self.assertEqual(positive, set(shipped_skills()) - self.UNPROBED)

    def test_only_the_internal_legs_are_probed_negatively(self):
        negative = {self._skill(p) for p in self._probes() if not p["must_route"]}
        self.assertEqual(negative, internal_legs())

    def test_the_three_new_cases_expect_their_own_skill(self):
        positive = {self._skill(p) for p in self._probes() if p["must_route"]}
        for name in sorted(self.NEW_CASES):
            self.assertIn(name, positive)

    def test_new_prompts_do_not_name_their_own_skill(self):
        """A description probe must describe the intent, never name the skill
        it should reach -- otherwise it grades the prompt, not the description.

        Scoped to the probe's OWN skill, deliberately. Testing every prompt
        against every skill name fails on ordinary English: the docs-sync probe
        opens "The code change is done", which names no skill but contains the
        word `code`. The hyphen-spaced form is checked too, so "create ticket"
        is caught as readily as "create-ticket"."""
        for probe in self._probes():
            name = self._skill(probe)
            if name not in self.NEW_CASES or not probe["must_route"]:
                continue
            text = probe["prompt"].lower()
            for form in (name, name.replace("-", " ")):
                self.assertIsNone(
                    re.search(r"\b%s\b" % re.escape(form), text),
                    "%s prompt names its own skill as %r" % (name, form))

    def test_only_directly_typed_skills_are_probed_explicitly(self):
        """An explicit probe sends `/acs:<skill>`. Two kinds earn one: the
        internal legs, which a user types to resume a run already judged onto
        that path, and the two user actions (`install-hooks`, `update`) that
        are commands rather than pipeline steps."""
        explicit = {self._skill(p) for p in self._probes()
                    if p["prompt"].strip().startswith("/")}
        self.assertEqual(explicit, internal_legs() | {"install-hooks", "update"})


# `_FakeSandbox` and `S04DetectionIsReportedTest` stood here. They drove
# s04_skill_triggers' own run() against a scripted sandbox and pinned how it
# REPORTED a routing decision -- that an unmeasured explicit probe is never
# scored a pass, and that every assertion label names the rule that decided it.
#
# That scenario is gone: routing is measured once, by the `claude plugin eval`
# tree rendered from evals/dataset/routing.json. Its reporting is the CLI's,
# not ours, so there is nothing here left to pin. The property those tests
# protected -- an explicit probe that could not be measured must not read as a
# pass -- has no enforcement in the new format, because a grader cannot observe
# an explicit invocation at all. That limit is recorded in CLAUDE.md and
# plugins/acs/evals/README.md rather than silently dropped here.

if __name__ == "__main__":
    unittest.main()
