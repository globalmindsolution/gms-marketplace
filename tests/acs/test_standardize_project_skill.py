"""MAR-121 spec 02 — /acs:standardize-project skill, triad, and prose-contract tests.

Focused prose-contract tests pinning what the shared tests/acs/test_skill_contracts.py
suite does not already cover: brownfield non-refusal framing (AC-2), no <set>_path
producer semantics (AC-2), planner audit-inputs + graceful degradation (AC-3),
executor tool restriction + never-touch-existing-source + never-write-under-doc-set-
paths (AC-4), narrowed allowlist + recommended_follow_ups shape (AC-4/AC-6), verifier
re-run-every-iteration diff-status gate (AC-5), recommended-only / one-PR (AC-6),
completion-report + recommended_follow_ups on the result document (AC-6/AC-7), and the
delivery-title string verbatim (cross-spec identity with spec 01's
DELIVERY_TICKET_TITLES).

Stdlib-only (os, re, unittest), mirroring the bounded-window `section()` technique from
test_create_standards_skill.py and test_create_architecture_project_structure.py.

Run:  python3 -m unittest tests.acs.test_mar121_standardize_project_skill -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SKILLS = os.path.join(PLUGIN, "skills")
AGENTS = os.path.join(PLUGIN, "agents")

SKILL_PATH = os.path.join(SKILLS, "standardize-project", "SKILL.md")
PLANNER_PATH = os.path.join(AGENTS, "standardize-project-planner.md")
EXECUTOR_PATH = os.path.join(AGENTS, "standardize-project-executor.md")
VERIFIER_PATH = os.path.join(AGENTS, "standardize-project-verifier.md")

DELIVERY_TITLE = "Brownfield project standardization"


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def section(body, heading):
    """Return the text of a markdown section: from the line whose start is
    `heading` (matched at line-start) up to the next same-or-higher-level
    heading (or end of file)."""
    m = re.search(r"(?m)^" + re.escape(heading) + r".*$", body)
    if m is None:
        raise AssertionError("heading %r not found" % heading)
    start = m.start()
    level = len(heading) - len(heading.lstrip("#"))
    nxt = re.search(r"(?m)^#{1,%d} \S" % level, body[m.end():])
    end = m.end() + nxt.start() if nxt else len(body)
    return body[start:end]


class Mar121BrownfieldNonRefusalCase(unittest.TestCase):
    """AC-2: the Brownfield orientation section exists, names create-project by
    file reference, and does NOT contain create-project's refusal/exit pattern."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.orientation = section(cls.body, "## Brownfield orientation")

    def test_section_present(self):
        self.assertIn("## Brownfield orientation", self.body)

    def test_names_create_project_by_file_reference(self):
        self.assertIn("create-project/SKILL.md", self.orientation)

    def test_no_refusal_exit_pattern(self):
        self.assertNotIn('dimension: "greenfield"', self.orientation)
        self.assertNotIn("REFUSE", self.orientation)


class Mar121NoSetPathProducerCase(unittest.TestCase):
    """AC-2: SKILL.md is not a <set>_path doc-set producer — no new settings key
    in frontmatter, and no Start-time refusal guard keyed to principles_path or
    standards_path being null (unlike create-standards' own-set-only guard)."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.fm = cls.body.split("---\n", 2)[1]
        cls.start = section(cls.body, "## Start")

    def test_no_new_settings_key_in_frontmatter(self):
        self.assertNotIn("_path:", self.fm)

    def test_no_refusal_guard_on_principles_path(self):
        self.assertIsNone(
            re.search(r"STOP.{0,120}principles_path.{0,40}null", self.start, re.DOTALL))
        self.assertIsNone(
            re.search(r"principles_path.{0,40}null.{0,120}STOP", self.start, re.DOTALL))

    def test_no_refusal_guard_on_standards_path(self):
        self.assertIsNone(
            re.search(r"STOP.{0,120}standards_path.{0,40}null", self.start, re.DOTALL))
        self.assertIsNone(
            re.search(r"standards_path.{0,40}null.{0,120}STOP", self.start, re.DOTALL))


class Mar121PlannerAuditInputsCase(unittest.TestCase):
    """AC-3: the planner's analysis language names all four Inputs & mode
    categories, and graceful-degradation language co-occurs with an
    unset/absent doc-set condition (mirrors Mar118GracefulDegradationCase)."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(PLANNER_PATH)

    def test_names_principles_path(self):
        self.assertIn("principles_path", self.body)

    def test_names_standards_path(self):
        self.assertIn("standards_path", self.body)

    def test_names_project_structure_target(self):
        self.assertIn("hld/project-structure.md", self.body)

    def test_names_readiness_tooling_terms(self):
        for term in ("CI", "pre-commit", "coverage", "e2e"):
            self.assertIn(term, self.body)

    def test_graceful_degradation_language_present(self):
        self.assertIsNotNone(
            re.search(
                r"(?s)(principles_path|standards_path).{0,600}"
                r"(N/A|proceed|never a.{0,20}block)"
                r"|(N/A|proceed|never a.{0,20}block).{0,600}"
                r"(principles_path|standards_path)",
                self.body,
            ),
            "planner must co-locate a principles_path/standards_path null/absent "
            "condition with N/A / proceed / never-a-block language",
        )


class Mar121ExecutorRestrictionCase(unittest.TestCase):
    """AC-4: executor frontmatter carries disallowedTools: Agent, Skill; its
    Doing-the-work section states never-edit/rename/delete-existing-source AND
    never-write-under-principles_path/standards_path, independent of the
    frontmatter tool check."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(EXECUTOR_PATH)
        cls.fm = cls.body.split("---\n", 2)[1]
        cls.doing = section(cls.body, "## Doing the work")

    def test_frontmatter_disallowed_tools(self):
        self.assertRegex(self.fm, r"(?m)^disallowedTools: Agent, Skill$")

    def test_never_touch_existing_source(self):
        self.assertIsNotNone(
            re.search(r"(?i)never edit, rename, move, or delete", self.doing))

    def test_never_write_under_principles_path(self):
        self.assertIsNotNone(
            re.search(r"NEVER.{0,300}principles_path", self.doing, re.DOTALL)
            or re.search(r"principles_path.{0,300}NEVER", self.doing, re.DOTALL))

    def test_never_write_under_standards_path(self):
        self.assertIsNotNone(
            re.search(r"NEVER.{0,300}standards_path", self.doing, re.DOTALL)
            or re.search(r"standards_path.{0,300}NEVER", self.doing, re.DOTALL))


class Mar121AdditiveSurfaceAllowlistCase(unittest.TestCase):
    """AC-4/AC-6: the Additive-surface contract section names the allowlist
    categories (CI workflow, tooling config) and explicitly states
    principles_path/standards_path are NOT scaffold targets; the
    recommended_follow_ups shape keys are all present."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.contract = section(cls.body, "## Additive-surface contract")

    def test_names_ci_workflow_category(self):
        self.assertIn("CI workflow", self.contract)

    def test_names_tooling_config_category(self):
        self.assertIn("tooling config", self.contract)

    def test_states_principles_path_not_scaffold_target(self):
        self.assertIsNotNone(
            re.search(r"NEVER.{0,300}principles_path", self.contract, re.DOTALL)
            or re.search(r"principles_path.{0,300}NEVER", self.contract, re.DOTALL))

    def test_states_standards_path_not_scaffold_target(self):
        self.assertIsNotNone(
            re.search(r"NEVER.{0,300}standards_path", self.contract, re.DOTALL)
            or re.search(r"standards_path.{0,300}NEVER", self.contract, re.DOTALL))

    def test_recommended_follow_ups_shape_keys(self):
        for key in ("title", "rationale", "target_path"):
            self.assertIn("`%s`" % key, self.contract)


class Mar121VerifierDiffStatusGateCase(unittest.TestCase):
    """AC-5: verifier's check-dimensions carry git diff --name-status, every-
    iteration/re-run/never-cached framing, and explicit block conditions for
    R, D, and out-of-allowlist M, invoking spec 01's classify_additive_diff."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(VERIFIER_PATH)

    def test_names_git_diff_name_status(self):
        self.assertIn("diff --name-status", self.body)

    def test_every_iteration_framing(self):
        self.assertIn("every iteration", self.body)

    def test_re_run_never_trust_framing(self):
        self.assertIsNotNone(re.search(r"(?i)re-run", self.body))
        self.assertIsNotNone(re.search(r"(?i)never trust", self.body))

    def test_block_conditions_named(self):
        self.assertIn("`R`", self.body)
        self.assertIn("`D`", self.body)
        self.assertIn("out-of-allowlist", self.body)

    def test_calls_classify_additive_diff_helper(self):
        self.assertIn("classify_additive_diff", self.body)


class Mar121RecommendedOnlyOnePrCase(unittest.TestCase):
    """AC-6: verifier's dimension list and SKILL.md's Additive-surface contract
    both state structural/doc-set gaps are recommended-only, never auto-minted;
    the Delivery section states exactly ONE PR per run."""

    @classmethod
    def setUpClass(cls):
        cls.skill_body = read(SKILL_PATH)
        cls.verifier_body = read(VERIFIER_PATH)
        cls.delivery = section(cls.skill_body, "## Delivery")

    def test_skill_states_never_auto_minted(self):
        contract = section(self.skill_body, "## Additive-surface contract")
        self.assertIsNotNone(re.search(r"(?i)never auto-minted", contract))

    def test_verifier_states_never_ticket_minting(self):
        self.assertIsNotNone(re.search(r"(?i)ticket-minting", self.verifier_body))

    def test_delivery_states_exactly_one_pr(self):
        self.assertIsNotNone(re.search(r"(?i)ONE.{0,20}PR", self.delivery))


class Mar121CompletionReportShapeCase(unittest.TestCase):
    """AC-6/AC-7: the Finish section's JSON example carries the top-level
    recommended_follow_ups key and states.audit/states.scaffold/states.pr keys."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.finish = section(cls.body, "## Finish")

    def test_recommended_follow_ups_key_present(self):
        self.assertIn('"recommended_follow_ups"', self.finish)

    def test_states_audit_key_present(self):
        self.assertIn('"audit"', self.finish)

    def test_states_scaffold_key_present(self):
        self.assertIn('"scaffold"', self.finish)

    def test_states_pr_key_present(self):
        self.assertIn('"pr"', self.finish)


class Mar121DeliveryTitleConsistencyCase(unittest.TestCase):
    """Cross-spec identity: the Start section's delivery-ticket title string
    matches spec 01's DELIVERY_TICKET_TITLES["standardize-project"] verbatim
    (acs_lib.py:65-66)."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.start = section(cls.body, "## Start")

    def test_title_string_verbatim(self):
        self.assertIn(DELIVERY_TITLE, self.start)


if __name__ == "__main__":
    unittest.main()
