"""Prose contracts for /acs:analyze-ticket — the first Build step.

The registration wiring (HOOKED_SKILLS, GATES, the hook wrappers, the pipeline
enum) is tests/acs/test_build_test_skill_registry.py's; the gate bodies are
tests/acs/test_acs_lib_gates.py's. THIS module pins the part that lives in
markdown and would otherwise drift away from the deterministic layer:

  * the analysis's front matter — the five keys, checked here with the SAME
    checker and the SAME `--require` spec the SKILL.md tells the coordinator to
    run, so the documented example actually passes it;
  * the seven required sections, declared byte-identically in the skill and in
    the verifier's re-run, and linted here against a doc built from the skill's
    own skeleton;
  * the `states` keys the result document records, cross-checked against
    post-analyze-ticket.py's docstring;
  * independence: the skill points at workflows/ship.yaml for order and claims
    no predecessor-completed check, because there no longer is one;
  * the two recommendations (stakes, refined ACs / needs_design) going through
    their CLIs — `acs.py lane apply`, `acs.py ticket save` — and never through
    a hand-written ticket field;
  * the triad's shape (one planner, execute -> verify, artifacts, grounding).

Run:  python3 -m unittest tests.acs.test_analyze_ticket -v
"""

import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
HOOKS = os.path.join(PLUGIN, "hooks", "scripts")
SKILL_PATH = os.path.join(PLUGIN, "skills", "analyze-ticket", "SKILL.md")
AGENTS = os.path.join(PLUGIN, "agents")

sys.path.insert(0, HOOKS)

import front_matter_check as fmc  # noqa: E402
import structure_lint  # noqa: E402
import acs_lib as lib  # noqa: E402

ROLES = ("planner", "executor", "verifier")

#: The result-document keys the post-hook documents and the next steps read.
STATES_KEYS = ("ready_for_planning", "api_surface", "questions_open")

#: The seven headings, in order. Declared here so a reordering in the prose is
#: a failure rather than a silent contract change.
SECTIONS = ["Problem restated", "Impact map", "Questions", "Assumptions",
            "Risks", "Refined acceptance criteria", "Verdict"]

#: The five front-matter keys the analysis publishes.
FRONT_MATTER_KEYS = ["ticket", "ready_for_planning", "api_surface",
                     "stakes_recommendation", "needs_design_recommendation"]


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def frontmatter(text, path):
    parts = text.split("---\n", 2)
    assert len(parts) >= 3 and parts[0] == "", "%s: missing frontmatter" % path
    return parts[1], parts[2]


def agent(role):
    return read(os.path.join(AGENTS, "analyze-ticket-%s.md" % role))


def flag_values(body, flag):
    """Every double-quoted value a CLI flag is given in the prose."""
    return re.findall(r'%s "([^"]+)"' % re.escape(flag), body)


def doc_front_matter_example(body):
    """The `---` block of the first fenced example whose front matter names a
    ticket — the shape the executor is told to emit."""
    match = re.search(r"(?ms)^```markdown\n(---\nticket:.*?\n---\n)", body)
    assert match, "no fenced front-matter example found"
    return match.group(1)


class TestSkillFrontmatter(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.text = read(SKILL_PATH)
        cls.fm, cls.body = frontmatter(cls.text, SKILL_PATH)

    def test_name_matches_the_directory(self):
        self.assertRegex(self.fm, r"(?m)^name: analyze-ticket$")

    def test_it_is_a_ticket_scoped_coordinator(self):
        self.assertRegex(self.fm, r'(?m)^argument-hint: "\[ticket-id\]"$')
        self.assertRegex(self.fm, r"(?m)^disallowed-tools: Edit, NotebookEdit$")

    def test_description_routes_on_what_it_produces(self):
        self.assertRegex(self.fm, r"(?m)^description: \S")
        self.assertIn("analysis.md", self.fm)


class TestLifecycleWiring(unittest.TestCase):
    """The three commands every hooked skill must carry, with this skill's name."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)

    def test_start_hook_is_the_mandatory_first_action(self):
        self.assertIn("skill-start.py", self.body)
        self.assertRegex(self.body, r"--skill analyze-ticket\b")
        self.assertIn("MANDATORY first action", self.body)

    def test_post_hook_closes_the_run_with_the_result_document(self):
        self.assertIn("post-analyze-ticket.py", self.body)
        self.assertIn("--result-file", self.body)

    def test_every_message_is_schema_validated(self):
        self.assertIn("validate_xml.py", self.body)
        self.assertIn("schemas/acs-messages.xsd", self.body)

    def test_clarification_ledger_rule_and_completion_report(self):
        self.assertIn("Clarification ledger first.", self.body)
        self.assertIn("clarify.py", self.body)
        self.assertIn("## Completion report (normative)", self.body)

    def test_it_names_its_own_triad(self):
        for role in ROLES:
            with self.subTest(role=role):
                self.assertIn("acs:analyze-ticket-%s" % role, self.body)
                self.assertTrue(os.path.isfile(
                    os.path.join(AGENTS, "analyze-ticket-%s.md" % role)))


class TestIndependence(unittest.TestCase):
    """The refactor's point: order lives in ship.yaml, the gate checks inputs."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)

    def test_order_is_declared_in_the_workflow_not_the_gate(self):
        self.assertIn("workflows/ship.yaml", self.body)
        self.assertRegex(self.body, r"no predecessor-completed check")

    def test_it_never_claims_a_predecessor_run_gate(self):
        for dead in ("_require_completed", "has not run for",
                     "last ended with status"):
            with self.subTest(dead=dead):
                self.assertNotIn(dead, self.body)

    def test_the_gate_it_describes_is_the_gate_that_exists(self):
        """The skill tells the user the pre-hook checked the ticket resolves —
        so the registered gate must be the ticket-scoped one."""
        self.assertIs(lib.GATES["analyze-ticket"], lib.gate_analyze_ticket)
        self.assertIn("analyze-ticket", lib.GATE_INPUTS["ticket"])

    def test_the_epic_refusal_points_at_design_then_fan_out_then_a_child(self):
        self.assertIn("/acs:create-design <id>", self.body)
        self.assertIn("/acs:create-ticket <id>", self.body)
        self.assertRegex(self.body, r"/acs:analyze-ticket` on a child")


class TestGateAgreement(unittest.TestCase):
    """What the prose promises about the pre-hook is what gates.py does."""

    @classmethod
    def setUpClass(cls):
        cls.gates_source = read(os.path.join(HOOKS, "acs_lib", "gates.py"))

    def test_the_gate_refuses_epics_for_this_skill(self):
        self.assertIn('_refuse_epic(ticket_id, "analyze-ticket"', self.gates_source)

    def test_the_gate_requires_no_artifact_of_its_own(self):
        """analyze-ticket is the first Build step: its only inputs are the
        ticket and the partition, so the gate must not require a document."""
        body = re.search(r"(?s)def gate_analyze_ticket\(.*?\n\n\ndef ",
                         self.gates_source).group(0)
        self.assertNotIn("_require_artifact", body)
        self.assertNotIn("skill_completed", body)


class TestAnalysisFrontMatterContract(unittest.TestCase):
    """The machine-read half: five keys, and the documented example passes the
    checker the skill tells the coordinator (and the verifier) to run."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.specs = flag_values(cls.body, "--require")
        cls.example = doc_front_matter_example(cls.body)

    def test_the_skill_declares_exactly_one_require_spec(self):
        self.assertEqual(len(self.specs), 1, self.specs)

    def test_the_spec_declares_the_five_keys_with_their_types(self):
        spec = fmc.parse_spec(self.specs[0])
        self.assertEqual([key for key, _ in spec], FRONT_MATTER_KEYS)
        self.assertEqual(dict(spec)["api_surface"], "bool")
        self.assertEqual(dict(spec)["ready_for_planning"], "bool")
        self.assertEqual(dict(spec)["stakes_recommendation"], "normal|high")

    def test_the_documented_example_satisfies_the_documented_spec(self):
        findings = fmc.check_front_matter(self.example, fmc.parse_spec(self.specs[0]),
                                          ticket="SHOP-123")
        self.assertEqual(findings, [])

    def test_the_executor_emits_the_same_five_keys(self):
        example = doc_front_matter_example(agent("executor"))
        self.assertEqual(findings_of(example, self.specs[0]), [])

    def test_the_verifier_re_runs_the_same_spec(self):
        self.assertIn(self.specs[0], agent("verifier"))

    def test_a_missing_api_surface_key_is_caught_by_that_spec(self):
        broken = re.sub(r"(?m)^api_surface: .*\n", "", self.example)
        self.assertEqual([f.rule for f in findings_of(broken, self.specs[0])],
                         ["missing-key"])

    def test_api_surface_is_the_predicate_the_workflow_reads(self):
        """The front-matter key is not a local convention: ship.yaml's
        `when: api_surface_changed` and the create-api-contract gate read it."""
        self.assertIn("api_surface_changed", lib.PREDICATES)
        self.assertIn("api_surface_changed", self.body)


def findings_of(front_matter_text, spec):
    return fmc.check_front_matter(front_matter_text, fmc.parse_spec(spec),
                                  ticket="SHOP-123")


class TestAnalysisSectionContract(unittest.TestCase):
    """The human-read half: seven sections, one declaration, linted for real."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.sections = flag_values(cls.body, "--sections")

    def test_the_skill_declares_the_seven_sections_in_order(self):
        self.assertEqual(len(self.sections), 1, self.sections)
        self.assertEqual([s.strip() for s in self.sections[0].split(";")], SECTIONS)

    def test_the_skeleton_in_the_skill_carries_those_headings_in_order(self):
        found = re.findall(r"(?m)^## (.+)$", doc_skeleton(self.body))
        self.assertEqual(found, SECTIONS)

    def test_the_executor_skeleton_matches_the_skill_skeleton(self):
        found = re.findall(r"(?m)^## (.+)$", doc_skeleton(agent("executor")))
        self.assertEqual(found, SECTIONS)

    def test_the_verifier_re_runs_the_same_section_list(self):
        self.assertIn(self.sections[0], agent("verifier"))

    def test_a_doc_built_from_the_skeleton_lints_clean(self):
        doc = synthesized_analysis(SECTIONS)
        self.assertEqual(structure_lint.lint_structure(doc, SECTIONS, ordered=True), [])

    def test_dropping_a_section_is_caught_by_that_declaration(self):
        doc = synthesized_analysis([s for s in SECTIONS if s != "Risks"])
        rules = [f.rule for f in structure_lint.lint_structure(doc, SECTIONS, ordered=True)]
        self.assertEqual(rules, ["missing-section"])


def doc_skeleton(body):
    """The fenced markdown example that carries the doc's headings."""
    match = re.search(r"(?ms)^```markdown\n(---\nticket:.*?)```", body)
    assert match, "no fenced doc skeleton found"
    return match.group(1)


def synthesized_analysis(sections):
    lines = ["# Analysis — SHOP-123: Accept large imports", ""]
    for name in sections:
        lines += ["## %s" % name, "content for %s" % name, ""]
    return "\n".join(lines)


class TestResultDocument(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.post_hook = read(os.path.join(HOOKS, "post-analyze-ticket.py"))

    def test_the_skill_records_exactly_the_documented_states(self):
        block = re.search(r'(?s)"states": \{(.*?)\}', self.body).group(1)
        self.assertEqual(re.findall(r'"(\w+)":', block), list(STATES_KEYS))

    def test_the_post_hook_documents_the_same_keys(self):
        for key in STATES_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, self.post_hook)

    def test_the_result_api_surface_must_equal_the_published_front_matter(self):
        self.assertRegex(self.body, r"MUST equal the published front matter")

    def test_questions_open_is_counted_from_the_ledger(self):
        self.assertIn("clarify.py list --open --ticket <id>", self.body)

    def test_the_recommendations_are_not_states(self):
        """stakes and needs_design are applied through their own CLIs, so a
        `states` key for them would be a second, divergent source of truth."""
        block = re.search(r'(?s)"states": \{(.*?)\}', self.body).group(1)
        self.assertNotIn("stakes", block)
        self.assertNotIn("needs_design", block)


class TestStakesRecommendation(unittest.TestCase):
    """The brief's one deterministic side effect: stakes rise BEFORE code."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)

    def test_it_recommends_over_the_impact_map_paths(self):
        self.assertIn("stakes recommend --paths-from -", self.body)
        self.assertRegex(self.body, r"(?s)impact map.*?first column")

    def test_a_high_recommendation_is_applied_through_lane_apply(self):
        self.assertIn("lane apply", self.body)
        self.assertIn("--proposed-stakes high", self.body)
        self.assertIn("--trigger c", self.body)
        self.assertIn("--skill analyze-ticket", self.body)

    def test_normal_writes_nothing(self):
        self.assertRegex(self.body, r'On `"normal"` do\s+nothing')

    def test_stakes_are_never_hand_set(self):
        self.assertRegex(self.body, r"never hand-set `stakes` or `lane`")


class TestTicketAmendments(unittest.TestCase):
    """Refined ACs and needs_design are proposals; the ticket changes only on a
    user answer, and only through the CLI that re-indexes it."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)

    def test_amendments_go_through_the_ticket_save_cli(self):
        self.assertIn("acs.py\" ticket save --ticket <id> --from -", self.body)

    def test_they_are_recorded_in_the_ledger_before_acting(self):
        self.assertIn("clarify.py add --skill analyze-ticket", self.body)
        self.assertRegex(self.body, r"ONLY on an explicit user answer")

    def test_without_an_answer_the_ticket_is_left_alone(self):
        self.assertRegex(self.body, r"leave the ticket untouched")


class TestNotReadyArm(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)

    def test_not_ready_finishes_as_needs_input_with_open_questions(self):
        self.assertIn("ready_for_planning: false", self.body)
        self.assertIn('"status": "needs_input"', self.body)
        self.assertIn("`clarify.py add` without\n   `--answer`", self.body)

    def test_the_handoff_carries_the_questions(self):
        self.assertIn("<handoff status=\"needs_input\">", self.body)


class TestPublishing(unittest.TestCase):
    """Only the coordinator writes the published analysis — the write guard
    denies an executor any write under the ticket docs tree."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)

    def test_the_artifact_path_is_resolved_by_the_cli_not_guessed(self):
        self.assertIn("artifacts show --ticket <id>", self.body)
        self.assertIn("acs_lib.artifacts.artifact_path", self.body)

    def test_publishing_copies_the_verified_bytes(self):
        self.assertRegex(self.body, r"cp \"<partition>/phases/analyze-ticket/analysis.md\"")
        self.assertRegex(self.body, r"Copy, never re-author")

    def test_the_coordinator_publishes_and_the_guard_is_named(self):
        self.assertIn("never a subagent", self.body)
        self.assertIn("acs_lib/filemap.py", self.body)

    def test_the_executor_is_barred_from_the_published_file(self):
        self.assertRegex(agent("executor"),
                         r"NEVER the published\n  `analysis.md`")


class TestTriadShape(unittest.TestCase):
    """House shape for the three agents (the shared suite covers the hooked set;
    these keep this triad honest on its own)."""

    def test_role_tool_restrictions(self):
        for role in ("planner", "verifier"):
            fm, _ = frontmatter(agent(role), role)
            self.assertRegex(fm, r"(?m)^tools: Read, Glob, Grep, Bash, Write$")
        fm, _ = frontmatter(agent("executor"), "executor")
        self.assertRegex(fm, r"(?m)^disallowedTools: Agent, Skill$")
        self.assertNotRegex(fm, r"(?m)^tools:")

    def test_no_model_or_effort_pinned_in_an_agent(self):
        for role in ROLES:
            fm, _ = frontmatter(agent(role), role)
            self.assertNotRegex(fm, r"(?m)^model:")
            self.assertNotRegex(fm, r"(?m)^effort:")
            self.assertIn("not for direct invocation", fm)

    def test_each_role_writes_its_phase_artifact(self):
        self.assertIn("phases/analyze-ticket/iter-<n>-plan.md", agent("planner"))
        self.assertIn("phases/analyze-ticket/iter-<n>-execute.json", agent("executor"))
        self.assertIn("phases/analyze-ticket/iter-<n>-verify.md", agent("verifier"))

    def test_each_role_returns_only_a_result_element(self):
        for role in ROLES:
            with self.subTest(role=role):
                body = agent(role)
                self.assertIn('<result skill="analyze-ticket"', body)
                self.assertIn("FINAL message", body)
                self.assertIn("Nothing follows the closing `</result>` tag.", body)

    def test_grounding_everywhere_and_policing_in_the_verifier(self):
        for role in ROLES:
            with self.subTest(role=role):
                self.assertIn("## Grounding (anti-hallucination)", agent(role))
        self.assertIn("police grounding", agent("verifier"))

    def test_one_planner_per_run_and_a_capped_loop(self):
        body = read(SKILL_PATH)
        self.assertRegex(body, r"Plan once, before the loop")
        self.assertRegex(body, r"fixed \*\*3\*\*\s+in every lane")
        self.assertIn("never spawn subagents", body.lower())

    def test_the_planner_does_not_plan_the_implementation(self):
        """The boundary with /acs:create-impl-plan, stated where it is enforced."""
        self.assertRegex(agent("planner"), r"NEVER plan the implementation")

    def test_the_verifier_re_derives_rather_than_trusting_the_draft(self):
        body = agent("verifier")
        self.assertIn("NEVER rubber-stamp", body)
        self.assertRegex(body, r"re-derive[sd]? the impact (map|surface)")


if __name__ == "__main__":
    unittest.main()
