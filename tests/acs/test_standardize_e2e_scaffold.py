"""MAR-126 (E2E-2) — brownfield e2e scaffold via `/acs:standardize-project`.

Prose-contract tests pinning the three-way e2e scaffold logic (unset / set-and-
missing / set-and-present) across the skill + planner + executor, the never-
wire-branch-protection rule (D1), and a direct regression over the pre-existing
`classify_additive_diff` helper with the two e2e scaffold paths. Mirrors the
bounded-window `section()` technique from
tests/acs/test_standardize_project_skill.py and
tests/acs/test_init_e2e_gate.py — never a bare file-wide `assertIn`.

Run:  python3 -m unittest tests.acs.test_mar126_standardize_e2e_scaffold -v
"""

import os
import re
import subprocess
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SKILLS = os.path.join(PLUGIN, "skills")
AGENTS = os.path.join(PLUGIN, "agents")

SKILL_PATH = os.path.join(SKILLS, "standardize-project", "SKILL.md")
PLANNER_PATH = os.path.join(AGENTS, "standardize-project-planner.md")
EXECUTOR_PATH = os.path.join(AGENTS, "standardize-project-executor.md")
VERIFIER_PATH = os.path.join(AGENTS, "standardize-project-verifier.md")
SCHEMA_PATH = os.path.join(PLUGIN, "schemas", "settings.schema.json")

HOOKS_DIR = os.path.join(PLUGIN, "hooks", "scripts")
sys.path.insert(0, HOOKS_DIR)

import acs_lib  # noqa: E402


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def section(body, heading):
    """Bounded-window helper: from `heading` (line-start) to the next
    same-or-higher-level heading, or EOF. Mirrors
    test_standardize_project_skill.py:41-52."""
    m = re.search(r"(?m)^" + re.escape(heading) + r".*$", body)
    if m is None:
        raise AssertionError("heading %r not found" % heading)
    start = m.start()
    level = len(heading) - len(heading.lstrip("#"))
    nxt = re.search(r"(?m)^#{1,%d} \S" % level, body[m.end():])
    end = m.end() + nxt.start() if nxt else len(body)
    return body[start:end]


def skill_e2e_window(body):
    """The SKILL.md 'Inputs & mode' e2e sub-bullet, bounded to just before the
    next top-level paragraph ('**No bootstrap/re-run mode split.**')."""
    inputs = section(body, "## Inputs & mode")
    m = re.search(r"(?m)^  - e2e harness/config presence.*$", inputs)
    if m is None:
        raise AssertionError("SKILL.md e2e readiness-tooling bullet not found")
    start = m.start()
    nxt = re.search(r"(?m)^\*\*No bootstrap/re-run mode split", inputs[m.end():])
    end = m.end() + nxt.start() if nxt else len(inputs)
    return inputs[start:end]


def planner_item4_window(body):
    """The planner's analysis item 4 (acs-readiness tooling), bounded to the
    next top-level `## ` heading."""
    m = re.search(r"(?m)^4\. \*\*acs-readiness tooling\*\*.*$", body)
    if m is None:
        raise AssertionError("planner item 4 heading not found")
    start = m.start()
    nxt = re.search(r"(?m)^## ", body[m.end():])
    end = m.end() + nxt.start() if nxt else len(body)
    return body[start:end]


class Mar126SkillE2eBulletCase(unittest.TestCase):
    """AC-1/AC-2/AC-3/AC-4: SKILL.md's Inputs & mode e2e bullet carries the
    three-way scaffold logic."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.window = skill_e2e_window(cls.body)

    # AC-1 — scaffold targets, opt-in gate + absence condition co-occur,
    # allowlist categories + A-status, reuse/verbatim + E2E-1 templates,
    # greenfield mirror reference.
    def test_ac1_names_both_scaffold_targets(self):
        self.assertIn("acs-e2e.yml", self.window)
        self.assertIn("run-e2e.py", self.window)

    def test_ac1_opt_in_gate_and_absence_condition_cooccur(self):
        self.assertTrue(
            re.search(r"(?is)(settings\.e2e|suites\.e2e).{0,300}absent", self.window)
            or re.search(r"(?is)absent.{0,300}(settings\.e2e|suites\.e2e)", self.window),
            "the set-and-missing trigger must co-occur with the e2e opt-in gate",
        )

    def test_ac1_allowlist_categories_and_a_status_cooccur(self):
        self.assertTrue(
            re.search(r"(?is)categories 1.{0,40}\+.{0,40}2.{0,200}`A`-status", self.window)
            or re.search(r"(?is)`A`-status.{0,200}categories 1.{0,40}\+.{0,40}2", self.window),
        )

    def test_ac1_reuse_verbatim_cooccurs_with_e2e1_templates(self):
        self.assertTrue(
            re.search(r"(?is)(reus\w*|verbatim).{0,200}(E2E-1|templates)", self.window)
            or re.search(r"(?is)(E2E-1|templates).{0,200}(reus\w*|verbatim)", self.window),
        )

    def test_ac1_greenfield_mirror_reference(self):
        self.assertIn("create-project/SKILL.md", self.window)

    # AC-2 — unset + N/A + no-scaffold consequence co-occur (pin the
    # consequence, not the bare word).
    def test_ac2_unset_cooccurs_with_na_and_no_scaffold(self):
        self.assertTrue(
            re.search(r"(?is)unset.{0,200}N/A.{0,200}no.{0,10}scaffold", self.window),
            "unset must co-occur with N/A AND a no-scaffold consequence",
        )

    # AC-3 — existing-file case states NOT overwritten + becomes a
    # recommended_follow_ups entry; the trigger (set-and-missing) bullet
    # itself carries no overwrite/replace language.
    def test_ac3_existing_file_not_overwritten_and_follow_up(self):
        self.assertTrue(
            re.search(r"(?is)already present.{0,200}NOT overwrite.{0,300}recommended_follow_ups", self.window)
        )

    def test_ac3_trigger_bullet_has_no_overwrite_language(self):
        trigger = re.search(
            r"(?is)Set AND `\.github/workflows/acs-e2e\.yml` absent.*?(?=\n {4}- \*\*Set AND)",
            self.window,
        )
        self.assertIsNotNone(trigger, "could not isolate the set-and-missing trigger bullet")
        self.assertNotIn("overwrite", trigger.group(0).lower())
        self.assertNotIn("replace the existing file", trigger.group(0).lower())

    # AC-4 — never wires branch protection + recommended_follow_ups -> /acs:init.
    def test_ac4_never_wires_branch_protection(self):
        self.assertIsNotNone(
            re.search(r"(?i)never wires? branch protection", self.window)
        )

    def test_ac4_follow_up_points_at_init(self):
        self.assertTrue(
            re.search(r"(?is)recommended_follow_ups.{0,200}/acs:init", self.window)
            or re.search(r"(?is)/acs:init.{0,200}recommended_follow_ups", self.window)
        )


class Mar126PlannerE2eItem4Case(unittest.TestCase):
    """AC-1/AC-2/AC-3/AC-4 mirrored into the planner's analysis item 4."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(PLANNER_PATH)
        cls.window = planner_item4_window(cls.body)

    def test_names_both_scaffold_targets(self):
        self.assertIn("acs-e2e.yml", self.window)
        self.assertIn("run-e2e.py", self.window)

    def test_unset_cooccurs_with_na_and_no_scaffold(self):
        self.assertTrue(
            re.search(r"(?is)unset.{0,200}N/A.{0,200}no.{0,10}scaffold", self.window)
        )

    def test_set_and_missing_emits_scaffoldable_gap(self):
        self.assertTrue(
            re.search(r"(?is)(settings\.e2e|suites\.e2e).{0,300}absent.{0,300}scaffold", self.window)
            or re.search(r"(?is)absent.{0,300}scaffold", self.window)
        )

    def test_set_and_present_drafts_follow_up_not_gap(self):
        self.assertTrue(
            re.search(r"(?is)already present.{0,300}recommended_follow_ups", self.window)
        )

    def test_never_wires_branch_protection(self):
        self.assertIsNotNone(re.search(r"(?i)never wires? branch protection", self.window))


class Mar126ExecutorE2eScaffoldCase(unittest.TestCase):
    """AC-1/AC-4: executor pins the copy mechanism as a zero-judgment step and
    states the never-mutate-branch-protection rule; positive absence of any
    protection-mutation API-call shape."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(EXECUTOR_PATH)
        cls.doing = section(cls.body, "## Doing the work")

    def test_copy_block_present(self):
        self.assertIn("mkdir -p .acs/ci .github/workflows", self.doing)
        self.assertIn('cp "${CLAUDE_PLUGIN_ROOT}/templates/ci/acs-e2e.yml" .github/workflows/acs-e2e.yml', self.doing)
        self.assertIn('cp "${CLAUDE_PLUGIN_ROOT}/templates/ci/run-e2e.py" .acs/ci/run-e2e.py', self.doing)
        self.assertIn("chmod +x .acs/ci/run-e2e.py", self.doing)

    def test_cites_init_step7f_precedent(self):
        self.assertIn("init/SKILL.md", self.doing)
        self.assertIn("Step 7f", self.doing)

    def test_never_mutates_branch_protection(self):
        self.assertIsNotNone(
            re.search(r"(?is)never.{0,60}(wire|mutate).{0,60}branch\s+protection", self.doing)
        )

    def test_no_protection_mutation_call_shape(self):
        lowered = self.doing.lower()
        for banned in ("-x put", "/protection", "gh api"):
            self.assertNotIn(banned, lowered)


class Mar126VerifierE2eNoteCase(unittest.TestCase):
    """AC-5(a): a one-line clarifying note only — verifier dimension-1
    language (and the fixed 5-dimension count) is unchanged; NO new check
    dimension is added for e2e."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(VERIFIER_PATH)

    def test_dimension_1_language_still_present(self):
        self.assertIn("diff --name-status", self.body)
        self.assertIn("every iteration", self.body)
        self.assertIsNotNone(re.search(r"(?i)re-run", self.body))
        self.assertIsNotNone(re.search(r"(?i)never.{0,10}trust|never reusing", self.body))
        self.assertIn("`R`", self.body)
        self.assertIn("`D`", self.body)
        self.assertIn("out-of-allowlist", self.body)
        self.assertIn("classify_additive_diff", self.body)

    def test_still_exactly_five_dimensions(self):
        dims = re.findall(r"(?m)^\d+\. \*\*", self.body)
        self.assertEqual(len(dims), 5, "e2e note must not add a 6th check dimension")

    def test_e2e_clarifying_note_present(self):
        self.assertTrue(
            re.search(r"(?is)verbatim.{0,300}(branch.protection).{0,300}invisible", self.body)
            or re.search(r"(?is)invisible.{0,300}branch.protection", self.body)
        )


class Mar126ClassifyAdditiveDiffE2eCase(unittest.TestCase):
    """AC-5(b): direct regression over the pre-existing, unmodified
    `classify_additive_diff` helper with the e2e scaffold's two paths."""

    def test_e2e_pair_a_status_is_compliant(self):
        diff = "A\t.github/workflows/acs-e2e.yml\nA\t.acs/ci/run-e2e.py"
        allowlist = [".github/workflows/*.yml", ".acs/ci/*.py"]
        self.assertEqual(acs_lib.classify_additive_diff(diff, allowlist), [])

    def test_e2e_workflow_modify_outside_allowlist_violates(self):
        diff = "M\t.github/workflows/acs-e2e.yml\nA\t.acs/ci/run-e2e.py"
        allowlist = [".acs/ci/*.py"]  # deliberately excludes the workflow glob
        violations = acs_lib.classify_additive_diff(diff, allowlist)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["status"], "M")
        self.assertEqual(violations[0]["path"], ".github/workflows/acs-e2e.yml")

    def test_e2e_runner_rename_violates(self):
        diff = "R100\t.acs/ci/old-runner.py\t.acs/ci/run-e2e.py"
        violations = acs_lib.classify_additive_diff(diff, [".acs/ci/*.py"])
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["reason"], "rename")

    def test_e2e_workflow_delete_violates(self):
        diff = "D\t.github/workflows/acs-e2e.yml"
        violations = acs_lib.classify_additive_diff(diff, [".github/workflows/*.yml"])
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["reason"], "delete")


class Mar126NoSettingsSchemaChangeCase(unittest.TestCase):
    """AC-6 (schema half) / C-4: no new settings key ships with this spec."""

    def test_schema_diff_is_empty(self):
        out = subprocess.run(
            ["git", "diff", "--", SCHEMA_PATH],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(out.stdout.strip(), "", "settings.schema.json must be unchanged (C-4)")


class Mar126UntouchedSurfacesCase(unittest.TestCase):
    """Risks R3/R4/R6/scope guard: this spec never re-authors E2E-1's
    templates, never edits classify_additive_diff, and never touches
    init/SKILL.md or merge-pr/SKILL.md."""

    def test_untouched_paths_have_empty_diff(self):
        untouched = [
            os.path.join(PLUGIN, "templates", "ci", "acs-e2e.yml"),
            os.path.join(PLUGIN, "templates", "ci", "run-e2e.py"),
            os.path.join(HOOKS_DIR, "acs_lib.py"),
            os.path.join(SKILLS, "init", "SKILL.md"),
            os.path.join(SKILLS, "merge-pr", "SKILL.md"),
        ]
        for path in untouched:
            out = subprocess.run(
                ["git", "diff", "--", path],
                cwd=REPO_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(out.stdout.strip(), "", "%s must be unchanged by this spec" % path)


if __name__ == "__main__":
    unittest.main()
