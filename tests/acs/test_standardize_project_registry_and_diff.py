"""MAR-121 spec 01 — standardize-project registry, gate, and the pure
additive-only diff-status classification helper.

Pure unit tests (no git/subprocess), mirroring
tests/acs/test_setup_standards_path.py's `sys.path.insert(0, HOOKS_DIR);
import acs_lib` fixture shape.

Run:  python3 -m unittest tests.acs.test_mar121_registry_and_diff_helper -v
"""

import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
HOOKS_DIR = os.path.join(PLUGIN, "hooks", "scripts")
sys.path.insert(0, HOOKS_DIR)

import acs_lib  # noqa: E402


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
        # v0.5.0: one gate for every step (`gate_outcome`), with the
        # architecture precondition declared as membership rather than as a
        # per-skill function. The registry row IS the registration now.
        self.assertIn("standardize-project", acs_lib.ARCHITECTURE_GATED)


class Mar121GateStandardizeProjectCase(unittest.TestCase):
    """AC-3 boundary + R1 non-reproduction, direct function-level.

    The per-skill `gate_standardize_project` is gone: `gate_outcome` runs the
    shared `_require_architecture_doc_set` for every member of
    ARCHITECTURE_GATED. The PRECONDITION is unchanged, so it is still
    asserted here -- against the function that now owns it."""

    def _ctx(self, root, settings=None):
        return {"checkout_root": root, "settings": settings or {}}

    def _gate(self, ctx):
        return acs_lib.gates._require_architecture_doc_set(ctx)

    def test_blocks_without_architecture_tech_stack(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(acs_lib.GateError):
                self._gate(self._ctx(tmp))

    def test_an_empty_architecture_directory_is_not_a_doc_set(self):
        """What a half-finished /acs:create-architecture leaves behind: the
        directory without the file it exists to hold."""
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "docs", "architecture", "hld"))
            with self.assertRaises(acs_lib.GateError):
                self._gate(self._ctx(tmp))

    def test_passes_with_tech_stack_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            hld = os.path.join(tmp, "docs", "architecture", "hld")
            os.makedirs(hld)
            with open(os.path.join(hld, "tech-stack.md"), "w") as fh:
                fh.write("# tech stack")
            self.assertIsNone(self._gate(self._ctx(tmp)))

    def test_passes_with_principles_and_standards_path_unset_or_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            hld = os.path.join(tmp, "docs", "architecture", "hld")
            os.makedirs(hld)
            with open(os.path.join(hld, "tech-stack.md"), "w") as fh:
                fh.write("# tech stack")
            null_settings = {"principles_path": None, "standards_path": None}
            self.assertIsNone(self._gate(self._ctx(tmp, null_settings)))
            self.assertIsNone(self._gate(self._ctx(tmp, {})))

    def test_does_not_hard_require_project_structure_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            hld = os.path.join(tmp, "docs", "architecture", "hld")
            os.makedirs(hld)
            with open(os.path.join(hld, "tech-stack.md"), "w") as fh:
                fh.write("# tech stack")
            # hld/project-structure.md deliberately absent.
            self.assertIsNone(self._gate(self._ctx(tmp)))


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
