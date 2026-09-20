"""The ONE loop /acs:ship drives, and the absence of the machinery it replaced.

Successor to test_ship_fix_retest_loop, whose whole subject v0.5.0 retired.
That module pinned a fix-and-re-test loop keyed on `ship.yaml`'s `on_fail:
{relay_to}` field, a per-step `fix_loops` counter on the ledger, and a
`post_code_test` settings block whose `enabled: null` auto-resolved from
whether e2e was configured. All three were ways of making the WORKFLOW decide
something about the change:

  * `on_fail: relay_to` was a second, conditional loop;
  * `fix_loops` was its counter, independent of the review's own;
  * `post_code_test.enabled` was a `when:` predicate wearing a settings key.

`workflows/ship.yaml` version 3 carries a version, a list of skill names and
`loops:`, and the schema REJECTS every one of those keys. So what is pinned
here is the replacement and its negative space: exactly one loop, its cap, its
`on_exhausted: fail`, and the fact that no relay/counter/gate mechanism
survives anywhere in the plugin.

Stdlib-only (json, os, re, sys, unittest). Run:
  python3 -m unittest tests.acs.test_ship_single_loop -v
"""

import json
import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "src", "acs")
SHIP_SKILL = os.path.join(PLUGIN, "skills", "ship", "SKILL.md")
SETTINGS_SCHEMA_PATH = os.path.join(PLUGIN, "schemas", "settings.schema.json")
WORKFLOW_SCHEMA_PATH = os.path.join(PLUGIN, "schemas", "workflow.schema.json")

sys.path.insert(0, os.path.join(PLUGIN, "hooks", "scripts"))
from acs_lib import workflow  # noqa: E402
from acs_lib._common import WorkflowError  # noqa: E402


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def norm(text):
    return re.sub(r"\s+", " ", text)


def section(body, heading):
    m = re.search(r"(?m)^" + re.escape(heading) + r".*$", body)
    if m is None:
        raise AssertionError("heading %r not found" % heading)
    start = m.start()
    level = len(heading) - len(heading.lstrip("#"))
    nxt = re.search(r"(?m)^#{1,%d} \S" % level, body[m.end():])
    end = m.end() + nxt.start() if nxt else len(body)
    return body[start:end]


class TheOneLoopTest(unittest.TestCase):
    """The workflow declares exactly one loop, and it is the review's."""

    @classmethod
    def setUpClass(cls):
        cls.wf = workflow.validate_workflow_file(workflow.default_workflow_path())

    def test_exactly_one_loop(self):
        self.assertEqual(len(workflow.loops_of(self.wf)), 1,
                         workflow.loops_of(self.wf))

    def test_it_is_the_review_loop(self):
        loop = workflow.loops_of(self.wf)[0]
        self.assertEqual(loop["from"], "review-code")
        self.assertEqual(loop["back_to"], "code")

    def test_it_carries_a_cap_and_fails_when_exhausted(self):
        """`on_exhausted: fail` is the whole point: a run that cannot clear
        its findings never "passes with findings"."""
        loop = workflow.loops_of(self.wf)[0]
        self.assertIsInstance(loop["max_iterations"], int)
        self.assertGreaterEqual(loop["max_iterations"], 1)
        self.assertEqual(loop["on_exhausted"], "fail")

    def test_back_to_precedes_from(self):
        steps = workflow.steps_of(self.wf)
        loop = workflow.loops_of(self.wf)[0]
        self.assertLess(steps.index(loop["back_to"]), steps.index(loop["from"]))


class RetiredMachineryTest(unittest.TestCase):
    """Asserted ABSENT, at the schema and in the plugin's own files: a key
    the schema merely ignored would be a workflow silently doing nothing."""

    def test_the_workflow_schema_rejects_the_retired_keys(self):
        schema = json.loads(read(WORKFLOW_SCHEMA_PATH))
        self.assertIs(schema.get("additionalProperties"), False)
        for key in ("when", "paths", "requires", "needs", "max_parallel",
                    "exclusive", "on_fail", "boundary", "delivery", "id",
                    "name", "stop_after"):
            with self.subTest(key=key):
                self.assertNotIn(key, schema.get("properties", {}))

    def test_a_workflow_carrying_a_retired_key_does_not_validate(self):
        doc = {"version": 3, "steps": ["code", "review-code"],
               "loops": [], "on_fail": {"relay_to": "code"}}
        with self.assertRaises(WorkflowError) as caught:
            workflow.validate_workflow(doc)
        self.assertIn("on_fail", str(caught.exception))

    def test_settings_carry_no_post_code_test_block(self):
        schema = json.loads(read(SETTINGS_SCHEMA_PATH))
        self.assertNotIn("post_code_test", schema["properties"])

    def test_no_fix_loop_counter_survives_in_the_plugin(self):
        hits = []
        for root, dirs, names in os.walk(PLUGIN):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in names:
                if not name.endswith((".py", ".json", ".yaml", ".md")):
                    continue
                path = os.path.join(root, name)
                # CHANGELOG and the redesign doc are the historical record:
                # they must name what was removed, which is not a survival.
                if os.path.basename(path) in ("CHANGELOG.md",
                                              "REDESIGN-IMPLEMENTATION-PIPELINE.md"):
                    continue
                body = read(path)
                for token in ("fix_loops", "post_code_test", "relay_to"):
                    if token in body and "rejected" not in body and "retired" not in body:
                        hits.append((os.path.relpath(path, REPO_ROOT), token))
        self.assertEqual(hits, [], "retired fix-loop machinery still referenced")


class ShipDrivesTheCursorTest(unittest.TestCase):
    """/acs:ship reads the cursor and runs one step; it owns no second loop."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SHIP_SKILL)
        cls.norm = norm(cls.body)

    def test_the_loop_calls_run_next(self):
        loop = section(self.body, "## The loop")
        self.assertIsNotNone(
            re.search(r"acs\.py\"? run next", loop),
            "the loop must call `acs.py run next`")
        self.assertIn("CLAUDE_PLUGIN_ROOT", loop,
                      "hooks/scripts is not on PATH: the fenced call must "
                      "resolve through CLAUDE_PLUGIN_ROOT")

    def test_the_skill_states_there_is_one_step_at_a_time(self):
        self.assertIsNotNone(
            re.search(r"(?i)there is one step at a time", self.norm),
            "ship must say the cursor offers one step, not a ready-set")

    def test_the_skill_names_the_workflows_cap_as_the_one_it_enforces(self):
        self.assertIsNotNone(
            re.search(r"(?i)loops\[\]\.max_iterations", self.norm),
            "ship must name ship.yaml's loop cap")
        self.assertIsNotNone(
            re.search(r"(?i)the one cap you enforce", self.norm),
            "ship must say which cap is its own to enforce")

    def test_no_second_relay_mechanism_is_described(self):
        for token in ("on_fail", "relay_to", "fix_loops", "on_replan",
                      "## Fix loop", "## Replan", "## Parallel mode"):
            with self.subTest(token=token):
                self.assertNotIn(token, self.body)

    def test_exactly_one_relay_or_handoff_heading(self):
        headings = re.findall(r"(?m)^## .*(?:[Rr]elay|[Hh]andoff).*$", self.body)
        self.assertEqual(headings, ["## Handling the handoff"], headings)


if __name__ == "__main__":
    unittest.main()
