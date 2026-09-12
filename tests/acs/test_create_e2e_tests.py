"""Prose contracts for /acs:create-e2e-tests — the Test step that writes a
ticket's end-to-end suites.

The registration wiring (HOOKED_SKILLS, GATES, the hook wrappers, the pipeline
enum) is tests/acs/test_build_test_skill_registry.py's; the gate bodies are
tests/acs/test_acs_lib_gates.py's. THIS module pins the part that lives in
markdown:

  * the three refusals the skill tells the user the pre-hook already made are
    the three the gate actually makes (e2e configured, test-cases.md present,
    at least one e2e case);
  * the two rules that make this skill safe to run inside a pipeline: it never
    writes product code (a declared file map under the e2e location is the
    mechanism), and it never weakens a test to turn a red suite green — a
    product failure belongs to /acs:run-e2e-tests and ship.yaml's relay;
  * the `states` keys the result document records, cross-checked against
    post-create-e2e-tests.py's docstring;
  * the e2e location is DERIVED from the repo, never invented, because the
    settings carry a command and no directory;
  * the triad's shape, including the verifier's single suite run and its
    wiring-versus-product classification.

Run:  python3 -m unittest tests.acs.test_create_e2e_tests -v
"""

import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
HOOKS = os.path.join(PLUGIN, "hooks", "scripts")
SKILL_PATH = os.path.join(PLUGIN, "skills", "create-e2e-tests", "SKILL.md")
AGENTS = os.path.join(PLUGIN, "agents")

sys.path.insert(0, HOOKS)

import acs_lib as lib  # noqa: E402
import validate_xml  # noqa: E402

ROLES = ("planner", "executor", "verifier")

#: The result-document keys the post-hook documents and the next step reads.
STATES_KEYS = ("suites_written", "cases_covered")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def frontmatter(text, path):
    parts = text.split("---\n", 2)
    assert len(parts) >= 3 and parts[0] == "", "%s: missing frontmatter" % path
    return parts[1], parts[2]


def agent(role):
    return read(os.path.join(AGENTS, "create-e2e-tests-%s.md" % role))


def xml_examples(body):
    return re.findall(r"(?ms)^```xml\n(.*?)^```", body)


class TestSkillFrontmatter(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.fm, cls.body = frontmatter(read(SKILL_PATH), SKILL_PATH)

    def test_name_matches_the_directory(self):
        self.assertRegex(self.fm, r"(?m)^name: create-e2e-tests$")

    def test_it_is_a_ticket_scoped_coordinator(self):
        self.assertRegex(self.fm, r'(?m)^argument-hint: "\[ticket-id\]"$')
        self.assertRegex(self.fm, r"(?m)^disallowed-tools: Edit, NotebookEdit$")

    def test_description_routes_on_what_it_produces(self):
        self.assertRegex(self.fm, r"(?m)^description: \S")
        self.assertIn("e2e", self.fm)

    def test_the_description_distinguishes_it_from_the_runner(self):
        """Two skills carry 'e2e' in their name: this one WRITES the suites,
        /acs:run-e2e-tests RUNS them."""
        self.assertIn("/acs:run-e2e-tests", self.fm)


class TestLifecycleWiring(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)

    def test_start_hook_is_the_mandatory_first_action(self):
        self.assertIn("skill-start.py", self.body)
        self.assertRegex(self.body, r"--skill create-e2e-tests\b")
        self.assertIn("MANDATORY first action", self.body)

    def test_post_hook_closes_the_run_with_the_result_document(self):
        self.assertIn("post-create-e2e-tests.py", self.body)
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
                self.assertIn("acs:create-e2e-tests-%s" % role, self.body)
                self.assertTrue(os.path.isfile(
                    os.path.join(AGENTS, "create-e2e-tests-%s.md" % role)))


class TestIndependence(unittest.TestCase):

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

    def test_it_says_plainly_what_running_out_of_order_means(self):
        """Independence is not a promise that every order works: run before
        /acs:code and the suites are written against a product that cannot
        pass them yet."""
        self.assertRegex(self.body, r"run out of order")


class TestGateAgreement(unittest.TestCase):
    """The three refusals the skill describes are the three gate_create_e2e_tests
    raises — and they are raised in that order."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        source = read(os.path.join(HOOKS, "acs_lib", "gates.py"))
        cls.gate = re.search(r"(?s)def gate_create_e2e_tests\(.*?\n\n\ndef ", source).group(0)

    def test_the_registered_gate_is_the_ticket_scoped_one(self):
        self.assertIs(lib.GATES["create-e2e-tests"], lib.gate_create_e2e_tests)
        self.assertIn("create-e2e-tests", lib.GATE_INPUTS["ticket"])

    def test_the_gate_checks_e2e_configuration(self):
        self.assertIn("workflow.e2e_configured", self.gate)
        self.assertIn("settings.e2e", self.body)
        self.assertIn("settings.suites.e2e", self.body)
        self.assertIn("/acs:setup", self.body)

    def test_the_gate_requires_the_case_document_and_names_its_producer(self):
        self.assertIn('_require_artifact(ctx, ticket_id, tdir, ticket, "test-cases.md", '
                      '"create-test-docs")', self.gate)
        self.assertIn("test-cases.md", self.body)
        self.assertIn("/acs:create-test-docs\n  <id> first", self.body)

    def test_the_gate_counts_the_e2e_cases(self):
        self.assertIn("e2e_case_count(path) < 1", self.gate)
        self.assertRegex(self.body, r"at least one e2e case")

    def test_the_skill_forbids_editing_the_case_document_to_get_past_the_gate(self):
        self.assertRegex(self.body, r"Do NOT work around this by editing `test-cases.md`")

    def test_the_workflow_skips_the_step_when_e2e_is_not_configured(self):
        """The skill claims ship.yaml skips it; the default workflow must say so."""
        doc, _lines = lib.load_workflow(lib.default_workflow_path())
        step = [s for s in doc["steps"] if s["id"] == "create-e2e-tests"][0]
        self.assertEqual(step["when"], "e2e_configured")
        self.assertIn("e2e_configured", lib.PREDICATES)
        self.assertRegex(self.body, r"ship\.yaml` skips this\s+step")


class TestNeverWritesProductCode(unittest.TestCase):
    """The mechanical half of 'tests only': a file map under the e2e location."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)

    def test_the_coordinator_declares_the_file_map_before_the_executor(self):
        self.assertIn("acs.py\" filemap set", self.body)
        self.assertRegex(self.body, r"--iteration <n> --task 1 --file")
        self.assertRegex(self.body, r"(?i)declare the file map before you spawn")

    def test_the_map_holds_no_source_path(self):
        self.assertRegex(self.body, r"NOTHING under the product's source tree")

    def test_an_executor_needing_a_source_change_returns_needs_input(self):
        self.assertRegex(self.body, r"returns `needs_input` naming the\nfile")
        self.assertRegex(agent("executor"),
                         r"(?s)status=\"needs_input\".*?product change")

    def test_the_commit_is_limited_to_the_declared_paths(self):
        self.assertRegex(self.body, r"Commit ONLY the paths in the file map")
        self.assertRegex(self.body, r"Do NOT\s+push")

    def test_every_role_carries_the_rule(self):
        for role in ROLES:
            with self.subTest(role=role):
                self.assertRegex(agent(role), r"(?i)never (write |plan a )?product[- ]code")

    def test_the_verifier_checks_the_changeset_for_source_edits(self):
        self.assertIn("git status --porcelain", agent("verifier"))


class TestNeverWeakensATest(unittest.TestCase):
    """A red suite that is correct is a correct deliverable; the product verdict
    belongs to /acs:run-e2e-tests and ship.yaml's on_fail relay."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)

    def test_the_skill_states_the_rule_up_front(self):
        self.assertRegex(self.body, r"NEVER weaken, skip, or narrow a case's assertion")
        self.assertRegex(self.body, r"currently red is a\s+correct deliverable")

    def test_the_relay_is_named_as_the_owner_of_a_product_failure(self):
        self.assertIn("/acs:run-e2e-tests", self.body)
        self.assertRegex(self.body, r"relays its\s+failure back to `/acs:code")

    def test_the_executor_is_forbidden_the_shortcuts_by_name(self):
        body = agent("executor")
        for shortcut in ("xfail", ".only", "retry"):
            with self.subTest(shortcut=shortcut):
                self.assertIn(shortcut, body)
        self.assertRegex(body, r"Nothing is weakened to go green")

    def test_the_verifier_separates_wiring_from_product_failures(self):
        body = agent("verifier")
        self.assertRegex(body, r"wiring failure is a blocking finding")
        self.assertRegex(body, r"product failure is NOT a finding")
        self.assertRegex(body, r'NEVER report "make the\s+test pass" as the fix')

    def test_the_verifier_severities_are_the_schema_s_severities(self):
        severities = set(re.findall(r'severity="(\w+)"', agent("verifier")))
        self.assertTrue(severities)
        self.assertTrue(severities <= {"blocking", "info"}, severities)


class TestE2eLocation(unittest.TestCase):
    """settings carry a COMMAND, not a directory — so the location is derived."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)

    def test_the_skill_says_the_settings_carry_no_directory(self):
        self.assertRegex(self.body, r"carries a COMMAND, not a directory")

    def test_it_names_the_three_sources_it_derives_from(self):
        for source in ("existing e2e suites", "runner config", "project-structure.md"):
            with self.subTest(source=source):
                self.assertRegex(self.body, r"(?i)%s" % re.escape(source))

    def test_a_repo_with_no_convention_is_a_question_not_an_invention(self):
        self.assertRegex(self.body, r"do NOT invent a convention")
        self.assertRegex(self.body, r"(?i)ask the user")

    def test_suites_are_named_after_the_ticket_and_carry_their_case_ids(self):
        self.assertRegex(self.body, r"named after the ticket")
        self.assertRegex(self.body, r"carries its `TC-<n>` id")

    def test_the_normalized_suites_entry_is_what_is_read(self):
        """settings.e2e is normalized into suites['e2e'] at load time."""
        self.assertRegex(self.body, r'read `suites\["e2e"\]` and never the raw alias')


class TestResultDocument(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.post_hook = read(os.path.join(HOOKS, "post-create-e2e-tests.py"))

    def test_the_skill_records_exactly_the_documented_states(self):
        block = re.search(r'(?s)"states": \{(.*?)\}', self.body).group(1)
        self.assertEqual(re.findall(r'"(\w+)":', block), list(STATES_KEYS))

    def test_the_post_hook_documents_the_same_keys(self):
        for key in STATES_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, self.post_hook)

    def test_a_product_failure_is_a_finding_not_a_state(self):
        block = re.search(r'(?s)"states": \{(.*?)\}', self.body).group(1)
        self.assertNotIn("passed", block)
        self.assertRegex(self.body, r"goes in `findings`")

    def test_cases_covered_must_equal_the_e2e_cases_for_a_completed_run(self):
        self.assertRegex(self.body,
                         r"must equal the set of\s+e2e-typed cases for a completed run")

    def test_the_coverage_check_is_deterministic_and_two_way(self):
        self.assertIn("grep -o 'TC-[0-9]", self.body)
        self.assertRegex(self.body, r"A missing id is a case with no test")
        self.assertRegex(self.body, r"An extra id .* is a finding too")


class TestTriadShape(unittest.TestCase):

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
        self.assertIn("phases/create-e2e-tests/iter-<n>-plan.md", agent("planner"))
        self.assertIn("phases/create-e2e-tests/iter-<n>-execute.json", agent("executor"))
        self.assertIn("phases/create-e2e-tests/iter-<n>-verify.md", agent("verifier"))

    def test_each_role_returns_only_a_result_element(self):
        for role in ROLES:
            with self.subTest(role=role):
                body = agent(role)
                self.assertIn('<result skill="create-e2e-tests"', body)
                self.assertIn("FINAL message", body)
                self.assertIn("Nothing follows the closing `</result>` tag.", body)

    def test_the_documented_messages_validate_against_the_schema(self):
        for role in ROLES:
            examples = xml_examples(agent(role))
            self.assertTrue(examples, role)
            for example in examples:
                with self.subTest(role=role):
                    self.assertEqual(validate_xml.validate_structurally(example), [])

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

    def test_only_the_verifier_runs_the_suite_and_only_once(self):
        self.assertRegex(agent("planner"), r"NEVER run the e2e suite here")
        self.assertRegex(agent("executor"), r"NEVER run the e2e suite")
        verifier = agent("verifier")
        self.assertRegex(verifier, r"Run the command ONCE")
        self.assertRegex(verifier, r"teardown ALWAYS")

    def test_the_verifier_takes_the_commands_verbatim(self):
        """The R1 no-interpolation posture the suite runner already carries."""
        self.assertRegex(agent("verifier"),
                         r"never rewrite, wrap, or interpolate captured output")


if __name__ == "__main__":
    unittest.main()
