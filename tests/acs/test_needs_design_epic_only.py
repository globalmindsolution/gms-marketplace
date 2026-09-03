"""Behavior tests for the needs_design epic-only narrowing (design.md slice 6).

Originating ticket: MAR-76. Covers derive_lane's Rule 4 removal (the
needs_design floor), create-ticket/SKILL.md no longer prompting for
needs_design on story/task, the new-ticket.py --needs-design CLI flag
staying unchanged, design_requirement's parent-epic resolution path, and
the CHANGELOG.md release note documenting the derive_lane behavior change.
"""

import inspect
import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
sys.path.insert(0, SCRIPTS)

import acs_lib as lib  # noqa: E402

sys.path.insert(0, os.path.join(REPO_ROOT, "tests", "acs"))
from acs_case import AcsWorkspaceCase  # noqa: E402

SKILL_MD = os.path.join(REPO_ROOT, "plugins", "acs", "skills", "create-ticket", "SKILL.md")
CHANGELOG_MD = os.path.join(REPO_ROOT, "plugins", "acs", "CHANGELOG.md")


def _normalize(text):
    return re.sub(r"\s+", " ", text).strip()


class TestDeriveLaneNeedsDesignRuleRemoved(unittest.TestCase):
    """AC-1/AC-2: Rule 4 (the needs_design floor) is removed by source text,
    the docstring truth table drops its row, and the adjacent Rule 3 stakes
    floor plus every other rule survive untouched.
    """

    def test_needs_design_true_no_longer_floors_trivial(self):
        self.assertEqual(
            lib.derive_lane("trivial", "low", True, "story"), "TRIVIAL"
        )

    def test_needs_design_true_no_longer_floors_small(self):
        self.assertEqual(
            lib.derive_lane("small", "normal", True, "story"), "SMALL"
        )

    def test_needs_design_true_task_uses_size_dispatch(self):
        self.assertEqual(
            lib.derive_lane("trivial", "low", True, "task"), "TRIVIAL"
        )

    def test_derive_lane_source_has_no_needs_design_branch(self):
        source = inspect.getsource(lib.derive_lane)
        self.assertNotIn("if needs_design:", source)

    def test_docstring_truth_table_has_no_rule_4_needs_design_row(self):
        doc = inspect.getdoc(lib.derive_lane)
        self.assertNotRegex(doc, r"Rule 4 \(needs_design\)")
        for line in doc.splitlines():
            self.assertNotIn("needs_design", line)

    def test_stakes_high_floor_survives_rule_removal(self):
        self.assertEqual(
            lib.derive_lane("trivial", "high", False, "task"), "STANDARD"
        )

    def test_stakes_high_floor_source_text_survives(self):
        source = inspect.getsource(lib.derive_lane)
        self.assertIn('if stakes == "high":', source)

    def test_stakes_high_floor_survives_for_small_and_standard(self):
        self.assertEqual(lib.derive_lane("small", "high", False, "task"), "STANDARD")
        self.assertEqual(lib.derive_lane("standard", "high", False, "story"), "STANDARD")

    def test_epic_override_still_wins_over_everything(self):
        self.assertEqual(
            lib.derive_lane("trivial", "low", True, "epic"), "COMPLEX"
        )

    def test_signature_unchanged(self):
        params = tuple(inspect.signature(lib.derive_lane).parameters)
        self.assertEqual(params, ("size", "stakes", "needs_design", "ticket_type"))


class TestCreateTicketSkillNeedsDesignEpicOnly(unittest.TestCase):
    """AC-3: /acs:create-ticket no longer offers or confirms needs_design for
    story/task; the epic carve-out and the separate docs_only confirmation
    gate both survive unchanged.
    """

    @classmethod
    def setUpClass(cls):
        with open(SKILL_MD, "r", encoding="utf-8") as fh:
            cls.text = fh.read()
        cls.normalized = _normalize(cls.text)

    def test_step_2_4_needs_design_confirmation_sentence_removed(self):
        removed = _normalize(
            "For story/task, present the recommendation and obtain USER CONFIRMATION"
        )
        self.assertNotIn(removed, self.normalized)

    def test_step_1_needs_design_recommendation_bullet_removed(self):
        removed = _normalize(
            "`needs_design` recommendation + one-line rationale"
        )
        self.assertNotIn(removed, self.normalized)

    def test_epic_state_it_do_not_ask_language_survives(self):
        expected = _normalize(
            "epics are always `needs_design: true` (state it, do not ask)"
        )
        self.assertIn(expected, self.normalized)

    def test_docs_only_confirmation_gate_survives(self):
        gate = _normalize(
            "it relaxes /acs:code's TDD/coverage gates — never set it without "
            "explicit user confirmation; when `false`, don't ask"
        )
        self.assertIn(gate, self.normalized)
        # Co-located with USER CONFIRMATION within the same Step-2.4 item.
        step_match = re.search(
            r"4\. \*\*Type and needs_design\*\*.*?(?=\n5\. )", self.text, re.DOTALL
        )
        self.assertIsNotNone(step_match)
        item_text = _normalize(step_match.group(0))
        self.assertIn("docs_only", item_text)
        self.assertIn("USER CONFIRMATION", item_text)


class TestNewTicketNeedsDesignFlagUnchanged(AcsWorkspaceCase):
    """AC-4: new-ticket.py's --needs-design flag keeps working unchanged for
    scripted/internal callers.
    """

    def test_needs_design_true_flag_still_sets_flag_on_task(self):
        ticket_id = self.new_ticket("Task", "task", "--needs-design", "true")
        ticket = lib.load_ticket(self.tdir(ticket_id))
        self.assertIs(ticket["needs_design"], True)

    def test_needs_design_false_flag_still_overrides_epic_default(self):
        ticket_id = self.new_ticket("Epic", "epic", "--needs-design", "false")
        ticket = lib.load_ticket(self.tdir(ticket_id))
        self.assertIs(ticket["needs_design"], False)

    def test_needs_design_rejects_values_outside_true_false(self):
        out = self.run_script(
            "new-ticket.py", "--title", "Task", "--type", "task",
            "--needs-design", "maybe",
        )
        self.assertEqual(out.returncode, 2)


class TestDesignRequirementParentPath(AcsWorkspaceCase):
    """AC-5: design_requirement's source == 'parent' path is the only route a
    child ever sees a design through, now that needs_design narrows to
    epic-only.
    """

    def _ctx(self):
        return lib.build_context(self.repo)

    def test_task_child_of_needs_design_epic_resolves_via_parent(self):
        epic_id = self.new_ticket("Design epic", "epic", "--needs-design", "true")
        child_id = self.new_ticket(
            "Child task", "task", "--parent", epic_id, "--needs-design", "false",
        )
        ctx = self._ctx()
        child_dir = self.tdir(child_id)
        child_ticket = lib.load_ticket(child_dir)
        result = lib.design_requirement(ctx, child_dir, child_ticket)
        self.assertEqual(result, (True, self.tdir(epic_id), "parent"))

    def test_child_of_non_design_epic_returns_false_none_none(self):
        epic_id = self.new_ticket("Plain epic", "epic", "--needs-design", "false")
        child_id = self.new_ticket(
            "Child task", "task", "--parent", epic_id, "--needs-design", "false",
        )
        ctx = self._ctx()
        child_dir = self.tdir(child_id)
        child_ticket = lib.load_ticket(child_dir)
        result = lib.design_requirement(ctx, child_dir, child_ticket)
        self.assertEqual(result, (False, None, None))

    def test_own_needs_design_still_returns_own(self):
        ticket_id = self.new_ticket("Standalone", "story", "--needs-design", "true")
        ctx = self._ctx()
        tdir = self.tdir(ticket_id)
        ticket = lib.load_ticket(tdir)
        result = lib.design_requirement(ctx, tdir, ticket)
        self.assertEqual(result, (True, tdir, "own"))


class TestReleaseNoteDocumentsDeriveLaneChange(unittest.TestCase):
    """AC-6: the CHANGELOG documents the derive_lane behavior change for
    consumer repos with legacy non-epic needs_design:true tickets. The note
    lives under [Unreleased] until a release cut dates that section and
    moves it into a `## [<version>] - <date>` section instead (release_notes.py
    `bump`) -- either location satisfies AC-6's "the CHANGELOG documents this"
    requirement, so this test searches the whole file rather than pinning to
    [Unreleased] specifically.
    """

    def test_unreleased_section_documents_derive_lane_needs_design_change(self):
        with open(CHANGELOG_MD, "r", encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("derive_lane", text)
        self.assertIn("needs_design", text)
        recompute_cue = any(
            cue in text for cue in ("recompute", "recomputes", "recomputed")
        )
        self.assertTrue(
            recompute_cue,
            "expected a recompute/migration cue for legacy non-epic needs_design:true tickets",
        )


if __name__ == "__main__":
    unittest.main()
