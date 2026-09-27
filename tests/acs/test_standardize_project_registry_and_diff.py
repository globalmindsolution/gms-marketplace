"""MAR-121 spec 01 — standardize-project registry, its architecture
precondition, and the pure additive-only diff-status classification helper.

The precondition was a pre-hook gate until ADR-0102 moved it into the skill's
Start (decision 3); the gate tests are inverted into guards that the hook half
stays gone, and the precondition is asserted against the Start prose.

Pure unit tests (no git/subprocess), mirroring
tests/acs/test_setup_standards_path.py's `sys.path.insert(0, HOOKS_DIR);
import acs_lib` fixture shape.

Run:  python3 -m unittest tests.acs.test_mar121_registry_and_diff_helper -v
"""

import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
HOOKS_DIR = os.path.join(PLUGIN, "hooks", "scripts")
SKILL_PATH = os.path.join(PLUGIN, "skills", "standardize-project", "SKILL.md")
sys.path.insert(0, HOOKS_DIR)

import acs_lib  # noqa: E402

#: The refusal Start used to carry. Skills independence removed it: a missing
#: architecture set narrows the audit, it never stops the run.
ARCHITECTURE_REFUSAL = ("no architecture doc set found (expected hld/tech-stack.md) "
                        "— run /acs:create-architecture first.")
ARCHITECTURE_FALLBACK_NOTE = "no architecture set: project-structure checks skipped"


def _section(body, heading):
    """A `## ` section of `body`, from `heading` up to the next `## `
    heading."""
    start = body.index(heading)
    nxt = re.search(r"(?m)^## ", body[start + len(heading):])
    end = start + len(heading) + nxt.start() if nxt else len(body)
    return body[start:end]


def _norm(text):
    return " ".join(text.split())


class Mar121RegistryCase(unittest.TestCase):
    """AC-1, AC-2 negative space: standardize-project joins HOOKED_SKILLS via
    WORKFLOW_SKILLS, never via PRODUCT_SKILLS."""

    def test_standardize_project_in_workflow_skills(self):
        self.assertIn("standardize-project", acs_lib.WORKFLOW_SKILLS)

    def test_standardize_project_in_hooked_skills(self):
        self.assertIn("standardize-project", acs_lib.HOOKED_SKILLS)

    def test_standardize_project_not_in_product_skills(self):
        self.assertNotIn("standardize-project", acs_lib.PRODUCT_SKILLS)

    def test_standardize_project_not_in_product_ticket_titles(self):
        self.assertNotIn("standardize-project", acs_lib.PRODUCT_TICKET_TITLES)

    def test_standardize_project_in_delivery_ticket_skills(self):
        self.assertIn("standardize-project", acs_lib.DELIVERY_TICKET_SKILLS)
        for skill in acs_lib.PRODUCT_SKILLS:
            self.assertIn(skill, acs_lib.DELIVERY_TICKET_SKILLS)

    def test_delivery_ticket_titles_has_standardize_project_entry(self):
        self.assertEqual(
            acs_lib.DELIVERY_TICKET_TITLES["standardize-project"],
            "Brownfield project standardization",
        )
        for key, value in acs_lib.PRODUCT_TICKET_TITLES.items():
            self.assertEqual(acs_lib.DELIVERY_TICKET_TITLES.get(key), value)

    def test_gate_registered_for_standardize_project(self):
        self.assertIn("standardize-project", acs_lib.HOOKED_SKILLS)
        # v0.5.0 declared the architecture precondition as ARCHITECTURE_GATED
        # membership; ADR-0102 deleted that table and moved the check into
        # the skill's Start. The pre-hook still runs for the skill (the
        # HOOKED_SKILLS row); the document table stays gone.
        self.assertFalse(hasattr(acs_lib, "ARCHITECTURE_GATED"))
        self.assertFalse(hasattr(acs_lib.gates, "ARCHITECTURE_GATED"))


class Mar121GateStandardizeProjectCase(unittest.TestCase):
    """AC-3 boundary + R1 non-reproduction.

    Until ADR-0102, `gate_outcome` ran the shared
    `_require_architecture_doc_set` for every member of ARCHITECTURE_GATED.
    ADR-0102 moved the check into the skill's Start; the skills-independence
    rule then removed the refusal itself -- no skill refuses because an
    upstream skill has not run. Start still LOOKS for the architecture set;
    without one the audit proceeds against what exists and records that the
    project-structure checks were skipped. The hook half stays guarded as
    gone."""

    @classmethod
    def setUpClass(cls):
        with open(SKILL_PATH, encoding="utf-8") as fh:
            cls.body = fh.read()
        cls.start = _norm(_section(cls.body, "## Start"))
        arch = [b for b in re.split(r"(?m)^- ", _section(cls.body, "## Start"))
                if "**The architecture set**" in b]
        if len(arch) != 1:
            raise AssertionError("Start must carry exactly one architecture-set bullet, "
                                 "found %d" % len(arch))
        cls.arch = _norm(arch[0])

    def test_the_hook_no_longer_gates_on_the_architecture_set(self):
        """Inverted: the pre-hook's document gate is deleted, and no subject
        gate took its place for this skill."""
        self.assertFalse(hasattr(acs_lib.gates, "_require_architecture_doc_set"))
        self.assertNotIn("standardize-project", acs_lib.SUBJECT_GATES)

    def test_start_never_stops_on_a_missing_architecture_set(self):
        self.assertNotIn("STOP", self.start)
        self.assertNotIn(ARCHITECTURE_REFUSAL, self.start)
        self.assertIn("never a stop", self.arch)

    def test_a_missing_architecture_set_falls_back_to_what_exists(self):
        self.assertIn(ARCHITECTURE_FALLBACK_NOTE, self.arch)
        self.assertIn("audits against what exists", self.arch)
        self.assertIn("pass `architecture_dir` as `none` to the auditor", self.arch)
        self.assertIn("only as a recommendation", self.arch)
        with open(os.path.join(PLUGIN, "agents", "standardize-project-auditor.md"),
                  encoding="utf-8") as fh:
            auditor = _norm(fh.read())
        self.assertIn(ARCHITECTURE_FALLBACK_NOTE, auditor)

    def test_the_completion_report_recommends_create_architecture(self):
        # The report's own template holds `## ` lines, so read to the end.
        report = self.body[self.body.index("## Completion report"):]
        self.assertIn("/acs:create-architecture", report)

    def test_an_empty_architecture_directory_is_not_a_doc_set(self):
        """What a half-finished /acs:create-architecture leaves behind: the
        directory without the file it exists to hold."""
        self.assertIn("a directory without `hld/tech-stack.md` does not count", self.arch)

    def test_passes_with_tech_stack_present(self):
        self.assertIn("the directory holding `hld/tech-stack.md` is `<architecture_dir>`",
                      self.arch)

    def test_passes_with_principles_and_standards_sets_absent(self):
        self.assertIn("Not finding either is never a stop", self.start)

    def test_does_not_hard_require_project_structure_md(self):
        self.assertNotIn("project-structure.md", self.arch)
        inputs = _norm(_section(self.body, "## Inputs & mode"))
        self.assertIsNotNone(
            re.search(r"hld/project-structure\.md`.{0,200}\*\*May not exist\*\*"
                      r".{0,600}never a block", inputs))


class Mar121AdditiveDiffHelperCase(unittest.TestCase):
    """AC-5, AC-7, AC-10 — line-covers every row of the classification table."""

    def test_empty_diff_passes(self):
        self.assertEqual(acs_lib.classify_additive_diff("", ["docs/principles/**"]), [])
        self.assertEqual(acs_lib.classify_additive_diff("   \n", ["docs/principles/**"]), [])

    def test_added_status_always_passes(self):
        self.assertEqual(acs_lib.classify_additive_diff("A\tdocs/anything.md", []), [])

    def test_modify_inside_allowlist_passes(self):
        self.assertEqual(
            acs_lib.classify_additive_diff(
                "M\tdocs/principles/new.md", ["docs/principles/**"]
            ),
            [],
        )

    def test_modify_outside_allowlist_blocks(self):
        result = acs_lib.classify_additive_diff("M\tsrc/app.py", ["docs/principles/**"])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["reason"], "modify-outside-allowlist")
        self.assertEqual(result[0]["path"], "src/app.py")

    def test_rename_blocks_regardless_of_destination(self):
        result = acs_lib.classify_additive_diff(
            "R100\told/path.py\tdocs/principles/new.py", ["docs/principles/**"]
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["reason"], "rename")

    def test_delete_blocks(self):
        result = acs_lib.classify_additive_diff("D\tsrc/legacy.py", [])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["reason"], "delete")
        self.assertEqual(result[0]["path"], "src/legacy.py")

    def test_unrecognized_status_blocks(self):
        result = acs_lib.classify_additive_diff("C100\told.py\tnew.py", [])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["reason"], "unrecognized-status")

    def test_mixed_diff_reports_only_the_violations(self):
        diff = "\n".join([
            "A\tdocs/new.md",
            "M\tdocs/principles/edited.md",
            "D\tsrc/legacy.py",
        ])
        result = acs_lib.classify_additive_diff(diff, ["docs/principles/**"])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["reason"], "delete")


if __name__ == "__main__":
    unittest.main()
