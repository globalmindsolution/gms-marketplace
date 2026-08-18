"""Contract tests for /acs:ship's full-verify handoff boundary.

MAR-179: pins the explicit, contractual stop between the `code` step and
docs-sync on full-verify lanes in plugins/acs/skills/ship/SKILL.md, replacing
the previous implicit silent stop. Run:
  python3 -m unittest tests.acs.test_ship_full_verify_handoff -v
"""

import glob
import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SHIP_SKILL = os.path.join(PLUGIN, "skills", "ship", "SKILL.md")

BOUNDARY_HEADING = "## Full-verify pipeline boundary"
BOUNDARY_HEADING_RE = re.compile(
    r"(?m)^## .*full-verify.*(boundary|handoff|stop).*$", re.IGNORECASE)
BOUNDARY_MARKER_RE = re.compile(r"(?i)full-verify pipeline boundary")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def section(body, heading):
    """Return the text of a markdown section: from the line whose start is
    `heading` up to the next same-or-higher-level heading (or end of file)."""
    m = re.search(r"(?m)^" + re.escape(heading) + r".*$", body)
    if m is None:
        raise AssertionError("heading %r not found" % heading)
    start = m.start()
    level = len(heading) - len(heading.lstrip("#"))
    nxt = re.search(r"(?m)^#{1,%d} \S" % level, body[m.end():])
    end = m.end() + nxt.start() if nxt else len(body)
    return body[start:end]


def normalize(text):
    return re.sub(r"\s+", " ", text)


class FullVerifyHandoffBoundaryTest(unittest.TestCase):
    def setUp(self):
        self.body = read(SHIP_SKILL)

    def test_boundary_section_exists(self):
        self.assertIsNotNone(
            BOUNDARY_HEADING_RE.search(self.body),
            "an H2 heading naming the full-verify boundary/handoff/stop "
            "must exist in ship/SKILL.md")

    def test_boundary_keyed_to_verify_depth(self):
        sect = section(self.body, BOUNDARY_HEADING)
        self.assertIn("verify_depth", sect)
        self.assertIn('"full"', sect)
        self.assertIn('"light"', sect)

    def test_full_verify_lane_stops_with_resume_command(self):
        sect = normalize(section(self.body, BOUNDARY_HEADING))
        self.assertIsNotNone(
            re.search(r'(?i)"full".{0,200}STOP', sect),
            "the section must state that a full-verify lane STOPs")
        self.assertIn("/acs:ship <ticket-id>", sect)
        self.assertIn("pipeline-state.json", sect)

    def test_stop_is_a_designed_boundary_not_a_failure(self):
        sect = normalize(section(self.body, BOUNDARY_HEADING))
        self.assertIsNotNone(re.search(r"(?i)designed boundary", sect))
        self.assertIsNotNone(re.search(r"(?i)not a failure", sect))

    def test_light_verify_lanes_explicitly_unaffected(self):
        sect = normalize(section(self.body, BOUNDARY_HEADING))
        self.assertIsNotNone(
            re.search(r'(?i)"light".{0,200}(continue|unaffected)', sect),
            "the section must state that a light-verify lane continues "
            "unaffected")
        self.assertIsNotNone(re.search(r"(?i)docs-sync", sect))
        self.assertIsNotNone(re.search(r"(?i)create-pr", sect))

    def test_picking_next_step_walk_unchanged(self):
        section_start = self.body.index("## Picking the next step")
        next_heading = re.search(r"\n## ", self.body[section_start + 1:])
        walk = self.body[section_start:section_start + 1 + next_heading.start()] \
            if next_heading else self.body[section_start:]
        self.assertNotIn("TRIVIAL", walk)
        self.assertNotIn("SMALL", walk)
        normalized = normalize(walk)
        self.assertIn(
            "create-ticket → create-design (when required per the rules "
            "above) → code → test (when the gate is active, per "
            "\"Post-code test gate\" above) → docs-sync → create-pr",
            normalized,
            "ship/SKILL.md must keep the single lane-uniform walk order "
            "byte-identical")

    def test_boundary_reachable_from_completed_handoff_branch(self):
        sect = section(self.body, "## Handling the handoff")
        completed_m = re.search(r"(?m)^- \*\*completed\*\*.*$", sect)
        self.assertIsNotNone(completed_m, "the completed bullet must exist")
        rest = sect[completed_m.start():]
        next_bullet = re.search(r"\n- \*\*", rest[1:])
        bullet_text = rest[:1 + next_bullet.start()] if next_bullet else rest
        self.assertIsNotNone(
            BOUNDARY_MARKER_RE.search(bullet_text),
            "the 'completed' bullet must cross-reference the full-verify "
            "handoff boundary section")

    def test_context_tiny_rule_reconciled(self):
        ground_rules_end = self.body.index("## Start")
        ground_rules = self.body[:ground_rules_end]
        m = re.search(r"(?m)^- Keep your own context tiny\..*$", ground_rules)
        self.assertIsNotNone(
            m, "the 'Keep your own context tiny' ground rule must exist")
        rest = ground_rules[m.start():]
        next_bullet = re.search(r"\n- ", rest[1:])
        bullet_text = rest[:1 + next_bullet.start()] if next_bullet else rest
        self.assertIsNotNone(
            BOUNDARY_MARKER_RE.search(bullet_text),
            "the context-tiny ground rule must reconcile with the "
            "full-verify handoff boundary section")

    def test_stop_precedes_post_code_test_gate(self):
        sect = normalize(section(self.body, BOUNDARY_HEADING))
        self.assertIsNotNone(
            re.search(r"(?i)before.{0,120}post-code test gate", sect),
            "the section must state the stop happens before the post-code "
            "test gate")
        self.assertIsNotNone(
            re.search(r"(?i)fresh session", sect),
            "the section must state the remaining steps run in a fresh "
            "session")

    def test_no_subagent_architecture_change(self):
        self.assertNotIn('subagent_type: "general-purpose"', self.body)
        self.assertNotIn("one subagent per step", self.body)
        self.assertIsNone(re.search(r"spawn a fresh subagent", self.body, re.IGNORECASE))

    def test_boundary_vocabulary_confined_to_ship_skill(self):
        skill_files = sorted(glob.glob(os.path.join(PLUGIN, "skills", "*", "SKILL.md")))
        matches = [p for p in skill_files if BOUNDARY_MARKER_RE.search(read(p))]
        self.assertEqual(matches, [SHIP_SKILL])


if __name__ == "__main__":
    unittest.main()
