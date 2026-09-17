"""Contract tests for /acs:ship's full-verify handoff boundary.

MAR-179: pins the explicit, contractual stop after the boundary step on
full-verify lanes in src/acs/skills/ship/SKILL.md, replacing the previous
implicit silent stop.

Since the skills-independence refactor the boundary is keyed on the ready
step's own `boundary: full_verify_stop` field (workflows/ship.yaml carries it
on `code`), and the walk that follows it is `acs.py workflow next`, not a
hard-coded order — so the assertions below pin the boundary mechanism and the
delegation, never a step sequence. Run:
  python3 -m unittest tests.acs.test_ship_full_verify_handoff -v
"""

import ast
import builtins
import glob
import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "src", "acs")
SHIP_SKILL = os.path.join(PLUGIN, "skills", "ship", "SKILL.md")

BOUNDARY_HEADING = "## The context boundary"
BOUNDARY_HEADING_RE = re.compile(
    r"(?m)^## .*(context|full-verify).*(boundary|handoff|stop).*$", re.IGNORECASE)
BOUNDARY_MARKER_RE = re.compile(r"(?i)(context|full-verify pipeline) boundary")


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

    def test_boundary_is_resolved_by_the_walk_not_recomputed(self):
        """ADR-0095: the ready entry arrives with `boundary` already resolved
        for the ticket's recorded delivery path. /acs:ship recomputes nothing —
        the mapping lives in ship.yaml, where a reviewer can see which paths
        are expensive."""
        sect = section(self.body, BOUNDARY_HEADING)
        self.assertIn("standard", sect)
        self.assertIn("complex", sect)
        self.assertIn("trivial", sect)
        self.assertIn("small", sect)
        self.assertNotIn("verify_depth", sect,
                         "the depth computation was retired; the walk resolves "
                         "the boundary from the recorded path")
        self.assertRegex(normalize(sect), r"(?i)nothing to recompute")

    def test_a_deep_path_stops_with_a_resume_command(self):
        sect = normalize(section(self.body, BOUNDARY_HEADING))
        self.assertIsNotNone(
            re.search(r"(?i)full_verify_stop.{0,200}STOP", sect),
            "the section must state that a boundary step STOPs")
        self.assertIn("/acs:ship <ticket-id>", sect)
        self.assertIn("pipeline-state.json", sect)

    def test_stop_is_a_designed_boundary_not_a_failure(self):
        sect = normalize(section(self.body, BOUNDARY_HEADING))
        self.assertIsNotNone(re.search(r"(?i)designed boundary", sect))
        self.assertIsNotNone(re.search(r"(?i)not a failure", sect))

    def test_the_cheap_paths_are_explicitly_unaffected(self):
        sect = normalize(section(self.body, BOUNDARY_HEADING))
        self.assertIsNotNone(
            re.search(r"(?i)null.{0,200}(continue|no stop)", sect),
            "the section must state that a null boundary continues unaffected")
        self.assertIsNotNone(re.search(r"(?i)docs-sync", sect))
        self.assertIsNotNone(re.search(r"(?i)create-pr", sect))

    def test_boundary_is_keyed_on_the_step_field_not_a_step_name(self):
        """The stop belongs to whichever step ship.yaml marks, so the section
        must key on `boundary: full_verify_stop` rather than hard-coding the
        skill the default workflow happens to put it on."""
        sect = normalize(section(self.body, BOUNDARY_HEADING))
        self.assertIn("boundary: full_verify_stop", sect)

    def test_the_walk_is_delegated_not_restated(self):
        """`acs.py workflow next` decides what runs after the boundary; the
        lane-uniform walk is no longer spelled out in the prose at all."""
        walk_section = section(self.body, "## The loop")
        self.assertIn("workflow next", walk_section)
        self.assertNotIn("TRIVIAL", walk_section)
        self.assertNotIn("SMALL", walk_section)
        self.assertNotIn("→ create-pr", normalize(walk_section),
                         "the loop must not restate a hard-coded step order")

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

    def test_stop_precedes_the_next_walk(self):
        sect = normalize(section(self.body, BOUNDARY_HEADING))
        self.assertIsNotNone(
            re.search(r"(?i)before the next\s+`?workflow next`?", sect),
            "the section must state the stop happens before the next "
            "`workflow next` — i.e. before any further step is picked")
        self.assertIsNotNone(
            re.search(r"(?i)fresh session", sect),
            "the section must state the remaining steps run in a fresh "
            "session")

    def test_no_subagent_architecture_change(self):
        self.assertNotIn('subagent_type: "general-purpose"', self.body)
        self.assertNotIn("one subagent per step", self.body)
        self.assertIsNone(re.search(r"spawn a fresh subagent", self.body, re.IGNORECASE))

    def test_boundary_vocabulary_confined_to_ship_skill(self):
        """Only /acs:ship acts on the boundary. A leg may NAME
        `full_verify_stop` to say the boundary applies to it -- the two deep
        ones do -- but the stop itself is the coordinator's, so the section
        heading belongs to exactly one file."""
        skill_files = sorted(glob.glob(os.path.join(PLUGIN, "skills", "*", "SKILL.md")))
        matches = [p for p in skill_files if BOUNDARY_MARKER_RE.search(read(p))]
        self.assertEqual(matches, [SHIP_SKILL])

    def test_the_boundary_needs_no_snippet_at_all(self):
        """This used to pin that the section's inline-Python heredoc had no
        free names, because /acs:ship recomputed the depth itself by calling
        verify_depth over the ticket.

        ADR-0095 removed the computation: `workflow next` resolves `boundary`
        against the ticket's recorded delivery path and hands it back on the
        ready entry. So the strongest form of "the snippet is correct" is that
        there is no snippet -- no re-read of the ticket, nothing to get wrong.
        """
        sect = section(self.body, BOUNDARY_HEADING)
        self.assertNotIn("```bash", sect,
                         "the boundary is resolved by the walk; a code fence "
                         "here means /acs:ship is recomputing it again")
        self.assertNotIn("verify_depth", sect)
        self.assertRegex(normalize(sect), r"(?i)the walk already did")


if __name__ == "__main__":
    unittest.main()
