"""What replaced /acs:ship's full-verify handoff boundary.

Successor to test_ship_full_verify_handoff (MAR-179). That module pinned a
stop keyed on `ship.yaml`'s `boundary: full_verify_stop` field, carried on
`code` and resolved per delivery path: on `standard` and `complex` the step's
whole reflection cycle ran inside /acs:ship's own context, so the workflow
declared a designed stop after it rather than letting the run trail off.

v0.5.0 removed the field with every other per-step key -- `boundary:` is one
the schema REJECTS -- and removed most of what made the stop necessary: the
review left /acs:code for /acs:review-code, so no step runs four merged lens
passes in the coordinator's context any more.

The underlying hazard did not go away, though: a long step still spends
context, and a run that trails off silently reads as a failure. What replaced
a workflow-declared stop is a GENERAL protocol that applies at any step
boundary -- ship's own "Context pressure" section -- resting on the property
that makes it safe: ship's per-step state is recoverable from `run.json`, so
compaction or a fresh session at a step boundary loses nothing.

So what is pinned here is that protocol, and the absence of the field.

Stdlib-only (glob, json, os, re, sys, unittest). Run:
  python3 -m unittest tests.acs.test_ship_context_pressure -v
"""

import glob
import json
import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "src", "acs")
SHIP_SKILL = os.path.join(PLUGIN, "skills", "ship", "SKILL.md")
WORKFLOW_SCHEMA = os.path.join(PLUGIN, "schemas", "workflow.schema.json")

sys.path.insert(0, os.path.join(PLUGIN, "hooks", "scripts"))
from acs_lib import workflow  # noqa: E402
from acs_lib._common import WorkflowError  # noqa: E402

BOUNDARY_MARKER_RE = re.compile(r"(?i)(context|full-verify pipeline) boundary")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def normalize(text):
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


class BoundaryFieldIsGoneTest(unittest.TestCase):
    """Asserted at the schema and the validator, not just by absence from the
    shipped file: a key a workflow could still SET and the engine ignore is
    worse than one it rejects."""

    def test_the_schema_has_no_boundary_key(self):
        schema = json.loads(read(WORKFLOW_SCHEMA))
        self.assertIs(schema.get("additionalProperties"), False)
        self.assertNotIn("boundary", schema.get("properties", {}))
        self.assertNotIn("boundary", json.dumps(schema.get("$defs", {})))

    def test_a_workflow_that_sets_boundary_is_refused(self):
        doc = {"version": 3, "steps": ["code", "review-code"], "loops": [],
               "boundary": "full_verify_stop"}
        with self.assertRaises(WorkflowError) as caught:
            workflow.validate_workflow(doc)
        self.assertIn("boundary", str(caught.exception))

    def test_no_skill_still_describes_a_boundary_stop(self):
        """The section belonged to exactly one file; now it belongs to none."""
        skill_files = sorted(glob.glob(os.path.join(PLUGIN, "skills", "*", "SKILL.md")))
        matches = [os.path.relpath(p, REPO_ROOT) for p in skill_files
                   if BOUNDARY_MARKER_RE.search(read(p))]
        self.assertEqual(matches, [])

    def test_no_full_verify_stop_vocabulary_survives_in_the_plugin(self):
        hits = []
        for root, dirs, names in os.walk(PLUGIN):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in names:
                if not name.endswith((".py", ".json", ".yaml", ".md")):
                    continue
                # CHANGELOG and the redesign doc are the historical record.
                if name in ("CHANGELOG.md", "REDESIGN-IMPLEMENTATION-PIPELINE.md"):
                    continue
                body = read(os.path.join(root, name))
                if "full_verify_stop" in body and "reject" not in body:
                    hits.append(os.path.relpath(os.path.join(root, name), REPO_ROOT))
        self.assertEqual(hits, [])


class ContextPressureProtocolTest(unittest.TestCase):
    """The general protocol that replaced the declared stop."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SHIP_SKILL)
        cls.section = normalize(section(cls.body, "## Context pressure"))

    def test_the_section_exists(self):
        self.assertTrue(self.section.strip())

    def test_it_names_what_ship_actually_holds_between_steps(self):
        """The whole reason a fresh session is safe: nothing ship holds is
        unique to its window."""
        for item in ("run id", "subject", "status"):
            with self.subTest(item=item):
                self.assertIn(item, self.section)
        self.assertIn("run.json", self.section)
        self.assertIsNotNone(
            re.search(r"(?i)compaction at a\s+step boundary loses nothing",
                      self.section))

    def test_it_finishes_the_handoff_before_stopping(self):
        self.assertIsNotNone(
            re.search(r"(?i)never abandon an in-flight handoff", self.section))

    def test_it_prints_the_resume_command(self):
        self.assertIn("/acs:ship <ticket-id>", self.section)
        self.assertIsNotNone(re.search(r"(?i)fresh session", self.section))

    def test_ship_runs_no_handoff_py_for_itself(self):
        """/acs:ship is not hooked and owns no invocation, so there is nothing
        for handoff.py to finalize; a step that was mid-flight flushes through
        its own protocol."""
        self.assertIsNotNone(
            re.search(r"(?i)do not run\s+`?handoff\.py`?", self.section))

    def test_the_context_tiny_rule_no_longer_carves_out_a_boundary_step(self):
        """The ground rule used to end with an exception for the boundary
        step, which is what the two rules needed to coexist. With no boundary
        there is no exception, and the rule stands unqualified."""
        ground_rules = self.body[:self.body.index("## Start")]
        m = re.search(r"(?m)^- Keep your own context tiny\..*$", ground_rules)
        self.assertIsNotNone(m, "the context-tiny ground rule must exist")
        rest = ground_rules[m.start():]
        nxt = re.search(r"\n- ", rest[1:])
        bullet = rest[:1 + nxt.start()] if nxt else rest
        self.assertIsNone(BOUNDARY_MARKER_RE.search(bullet))
        self.assertIsNotNone(
            re.search(r"(?i)safe to compact", normalize(bullet)),
            "the rule must state why compaction between steps is safe")

    def test_no_subagent_architecture_change(self):
        self.assertNotIn('subagent_type: "general-purpose"', self.body)
        self.assertNotIn("one subagent per step", self.body)
        self.assertIsNone(re.search(r"spawn a fresh subagent", self.body, re.IGNORECASE))


if __name__ == "__main__":
    unittest.main()
