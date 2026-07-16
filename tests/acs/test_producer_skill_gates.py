"""MAR-122 — fix R1: the four doc-set producer skills (create-quality,
create-operations, create-principles, create-standards) are registered in
HOOKED_SKILLS but had no GATES entry, so run_pre's bare GATES[skill]
subscript raised KeyError -> fail-closed exit 2. This module pins the four
new gate functions directly (pure unit, no subprocess), mirroring
tests/acs/test_standardize_project_registry_and_diff.py's
`sys.path.insert(HOOKS_DIR); import acs_lib` fixture shape.

Run:  python3 -m unittest tests.acs.test_mar122_producer_gates -v
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

PRODUCERS = ("create-quality", "create-operations", "create-principles", "create-standards")


class Mar122RegistryCase(unittest.TestCase):
    """AC-2: the four gate functions exist and are registered in GATES."""

    def test_producers_registered_in_gates(self):
        for skill in PRODUCERS:
            with self.subTest(skill=skill):
                self.assertIn(skill, acs_lib.GATES)

    def test_gate_functions_wired(self):
        for skill in PRODUCERS:
            func_name = "gate_" + skill.replace("-", "_")
            with self.subTest(skill=skill):
                self.assertTrue(hasattr(acs_lib, func_name))
                self.assertIs(acs_lib.GATES[skill], getattr(acs_lib, func_name))

    def test_all_hooked_skills_have_a_gate(self):
        # T6: durable invariant that would have caught R1 (and catches any
        # future HOOKED_SKILLS addition that forgets to register a gate).
        for skill in acs_lib.HOOKED_SKILLS:
            with self.subTest(skill=skill):
                self.assertIn(skill, acs_lib.GATES)


class Mar122GateProducersCase(unittest.TestCase):
    """AC-1, AC-3: each gate passes when the architecture doc set exists and
    raises GateError (not KeyError) when it is absent."""

    def _ctx(self, root, settings=None):
        return {"checkout_root": root, "settings": settings or {}}

    def _gate(self, skill):
        return getattr(acs_lib, "gate_" + skill.replace("-", "_"))

    def test_blocks_without_tech_stack(self):
        for skill in PRODUCERS:
            with self.subTest(skill=skill):
                with tempfile.TemporaryDirectory() as tmp:
                    with self.assertRaises(acs_lib.GateError):
                        self._gate(skill)(self._ctx(tmp), {})

    def test_passes_with_tech_stack(self):
        for skill in PRODUCERS:
            with self.subTest(skill=skill):
                with tempfile.TemporaryDirectory() as tmp:
                    hld = os.path.join(tmp, "docs", "architecture", "hld")
                    os.makedirs(hld)
                    with open(os.path.join(hld, "tech-stack.md"), "w") as fh:
                        fh.write("# tech stack")
                    self.assertIsNone(self._gate(skill)(self._ctx(tmp), {}))

    def test_respects_custom_architecture_path(self):
        for skill in PRODUCERS:
            with self.subTest(skill=skill):
                with tempfile.TemporaryDirectory() as tmp:
                    hld = os.path.join(tmp, "custom-arch", "hld")
                    os.makedirs(hld)
                    with open(os.path.join(hld, "tech-stack.md"), "w") as fh:
                        fh.write("# tech stack")
                    settings = {"architecture_path": "custom-arch"}
                    self.assertIsNone(self._gate(skill)(self._ctx(tmp, settings), {}))
                    # And the same custom path still blocks when the file is absent.
                    with tempfile.TemporaryDirectory() as tmp2:
                        with self.assertRaises(acs_lib.GateError):
                            self._gate(skill)(self._ctx(tmp2, settings), {})


if __name__ == "__main__":
    unittest.main()
