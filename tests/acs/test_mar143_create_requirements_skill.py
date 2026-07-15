"""MAR-143 spec 01 — /acs:create-requirements skill scaffold, triad, hooks,
registration (AC-1, AC-6, AC-7 partial).

Registers the new producer skill in `acs_lib.py` (`PRODUCT_SKILLS`,
`PRODUCT_TICKET_TITLES`, a standalone `gate_create_requirements`, `GATES`),
proves the coordinator + triad + hooks exist on disk, and pins the
count-bump doc-set (`c4-container.md`/`c4-component.md`) to the post-registration
totals (15th HOOKED skill: 24 skills / 45 agent files (39 reachable) / 15 pre
+ 15 post hooks / twelve triad-keeping skills / 12 active triads (36 agents
in triads)). Mirrors `test_mar117_principles_path_init.py`'s
`Mar117PrinciplesRegistryCase` registry-case pattern.

Stdlib-only (os, re, sys, unittest). Run:
  python3 -m unittest tests.acs.test_mar143_create_requirements_skill -v
"""

import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
HOOKS_DIR = os.path.join(PLUGIN, "hooks", "scripts")
SKILL_PATH = os.path.join(PLUGIN, "skills", "create-requirements", "SKILL.md")
sys.path.insert(0, HOOKS_DIR)

import acs_lib  # noqa: E402


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class Mar143RegistryCase(unittest.TestCase):
    """AC-1: create-requirements is registered in PRODUCT_SKILLS and
    PRODUCT_TICKET_TITLES, and consequently joins the derived HOOKED_SKILLS."""

    def test_create_requirements_in_product_skills(self):
        self.assertIn(
            "create-requirements", acs_lib.PRODUCT_SKILLS,
            msg="'create-requirements' must be registered in PRODUCT_SKILLS (AC-1)",
        )

    def test_create_requirements_in_product_ticket_titles(self):
        self.assertEqual(
            acs_lib.PRODUCT_TICKET_TITLES.get("create-requirements"),
            "Product requirements doc set",
            msg="PRODUCT_TICKET_TITLES['create-requirements'] must equal "
                "'Product requirements doc set' (AC-1)",
        )

    def test_create_requirements_in_hooked_skills(self):
        self.assertIn(
            "create-requirements", acs_lib.HOOKED_SKILLS,
            msg="'create-requirements' must join HOOKED_SKILLS via the derived "
                "PRODUCT_SKILLS + WORKFLOW_SKILLS expression (AC-1)",
        )


class Mar143GateCase(unittest.TestCase):
    """AC-6: the gate is standalone (`return None`), NOT
    `_require_architecture_doc_set` — architecture-awareness is a planner
    BEHAVIOR, not a hard gate (design.md 521-525)."""

    def test_gate_registered(self):
        self.assertIn("create-requirements", acs_lib.GATES)

    def test_gate_resolves_and_returns_none(self):
        gate = acs_lib.GATES["create-requirements"]
        ctx = {"checkout_root": "/nonexistent/does-not-matter", "settings": {}}
        self.assertIsNone(
            gate(ctx, {}),
            msg="gate_create_requirements must be standalone: return None "
                "unconditionally, like gate_create_prd (AC-6)",
        )

    def test_gate_is_not_require_architecture_doc_set(self):
        self.assertIsNot(
            acs_lib.GATES["create-requirements"],
            acs_lib._require_architecture_doc_set,
            msg="gate_create_requirements must NOT be "
                "_require_architecture_doc_set — that hard-gate is reserved "
                "for create-quality/-operations/-principles/-standards (AC-6)",
        )

    def test_gate_function_exists_and_named_conventionally(self):
        self.assertTrue(hasattr(acs_lib, "gate_create_requirements"))
        self.assertIs(
            acs_lib.GATES["create-requirements"], acs_lib.gate_create_requirements)


class Mar143FilesExistCase(unittest.TestCase):
    """AC-1: the coordinator, triad agents, and hooks exist on disk at the
    expected paths."""

    def test_skill_md_exists(self):
        self.assertTrue(os.path.isfile(SKILL_PATH), SKILL_PATH)

    def test_triad_agents_exist(self):
        for role in ("planner", "executor", "verifier"):
            path = os.path.join(PLUGIN, "agents", "create-requirements-%s.md" % role)
            self.assertTrue(os.path.isfile(path), path)

    def test_hooks_exist(self):
        for name in ("pre-create-requirements.py", "post-create-requirements.py"):
            path = os.path.join(HOOKS_DIR, name)
            self.assertTrue(os.path.isfile(path), path)

    def test_hooks_delegate_to_acs_lib_run_pre_post(self):
        pre = read(os.path.join(HOOKS_DIR, "pre-create-requirements.py"))
        post = read(os.path.join(HOOKS_DIR, "post-create-requirements.py"))
        self.assertIn("run_pre", pre)
        self.assertIn('"create-requirements"', pre)
        self.assertIn("run_post", post)
        self.assertIn('"create-requirements"', post)


class Mar143CountBumpCase(unittest.TestCase):
    """AC-1, AC-7(partial): registering the 15th HOOKED skill flips the
    architecture doc-set counts in lockstep across c4-container.md and
    c4-component.md; both must be internally consistent with the new
    HOOKED_SKILLS length (15)."""

    def _c4_container(self):
        return read(os.path.join(REPO_ROOT, "docs", "architecture", "hld", "c4-container.md"))

    def _c4_component(self):
        return read(os.path.join(REPO_ROOT, "docs", "architecture", "hld", "c4-component.md"))

    def test_hooked_skills_count_is_fifteen(self):
        self.assertEqual(len(acs_lib.HOOKED_SKILLS), 15)

    def test_c4_container_bumped_counts_present(self):
        body = self._c4_container()
        self.assertIn("24 x SKILL.md", body)
        self.assertIn("45 x agent .md (39 reachable)", body)
        self.assertIn("twelve triad-keeping skills", body)
        self.assertIn("create-requirements", body)
        self.assertIn("dispatch + 15 pre + 15 post hooks", body)

    def test_c4_container_stale_counts_absent(self):
        body = self._c4_container()
        for stale in (
            "23 x SKILL.md", "42 x agent .md (36 reachable)",
            "eleven triad-keeping skills", "dispatch + 14 pre + 14 post hooks",
        ):
            self.assertNotIn(stale, body, "stale form %r still in c4-container.md" % stale)

    def test_c4_component_bumped_counts_present(self):
        body = self._c4_component()
        self.assertIn("twelve triad-keeping skills", body)
        self.assertIn("12 active triads (36 agents in triads)", body)
        self.assertIn("39 reachable agents", body)
        self.assertIn("create-requirements", body)

    def test_c4_component_stale_counts_absent(self):
        body = self._c4_component()
        for stale in (
            "eleven triad-keeping skills",
            "11 active triads (33 agents in triads)",
            "36 reachable agents",
        ):
            self.assertNotIn(stale, body, "stale form %r still in c4-component.md" % stale)


class Mar143CoordinatorContractCase(unittest.TestCase):
    """AC-1, AC-6: the coordinator recognizes all three modes, elicits
    greenfield interactively (updated for the landed greenfield mode), and
    threads the settings-driven write target (never a hardcoded marketplace
    literal)."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)

    def test_declares_all_three_modes(self):
        for mode in ("brownfield", "greenfield", "amend"):
            self.assertIn(mode, self.body, "SKILL.md must name mode %r" % mode)

    def test_greenfield_elicits_not_deferred(self):
        # Greenfield is now a real elicitation mode, not a deferral.
        self.assertRegex(
            self.body, r"(?is)greenfield.{0,600}elicit",
            msg="the coordinator must state greenfield ELICITS requirements "
                "from the user (a real mode), not silently fall through to "
                "brownfield",
        )
        self.assertNotRegex(
            self.body, r"(?i)greenfield[\s\S]{0,600}MAR-144",
            msg="the old greenfield-deferred-to-MAR-144 language must be gone",
        )

    def test_g36_required_sections_constraint_declared(self):
        self.assertIn("required_sections", self.body)

    def test_g36_audience_style_profile_declared(self):
        self.assertIn("engineers (behavioral-contract prose)", self.body)

    def test_threads_requirements_settings(self):
        self.assertIn("requirements_path", self.body)
        self.assertIn("requirements_layout", self.body)

    def test_ships_own_docs_only_pr(self):
        self.assertIn("gh pr create", self.body)
        self.assertIn("pr-conventions.py", self.body)

    def test_allocate_default_title(self):
        self.assertIn("Product requirements doc set", self.body)

    def test_result_document_states_keys(self):
        self.assertIn('"requirements"', self.body)
        self.assertIn('"pr"', self.body)


if __name__ == "__main__":
    unittest.main()
