"""Prose contracts for /acs:create-api-contract — the conditional Build step.

Registration wiring is tests/acs/test_build_test_skill_registry.py's and the
gate body is tests/acs/test_acs_lib_gates.py's. THIS module pins the markdown
layer and, where the markdown makes a claim about the deterministic layer,
checks the claim against that layer:

  * the gate the Start section describes — plan.md, analysis.md, and
    `api_surface: true` — is the gate `acs_lib.gates` actually registers, with
    the refusal pointers the prose quotes;
  * the contract's front matter (ticket / items / contract_files), checked with
    the same checker and the same `--require` spec the skill runs, and the
    seven required sections, linted from the skill's own skeleton;
  * traceability: every item to an acceptance criterion AND a plan item, which
    is what `states.traced_acs` records and what /acs:create-test-docs reads;
  * `contracts_path` modes — including the refusal to invent a contract format
    a repo does not already keep;
  * the triad's shape (one planner, execute -> verify, artifacts, grounding).

Run:  python3 -m unittest tests.acs.test_create_api_contract -v
"""

import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
HOOKS = os.path.join(PLUGIN, "hooks", "scripts")
SKILL_PATH = os.path.join(PLUGIN, "skills", "create-api-contract", "SKILL.md")
AGENTS = os.path.join(PLUGIN, "agents")

sys.path.insert(0, HOOKS)

import front_matter_check as fmc  # noqa: E402
import structure_lint  # noqa: E402
import acs_lib as lib  # noqa: E402

ROLES = ("planner", "executor", "verifier")

STATES_KEYS = ("contract_path", "items", "traced_acs")

SECTIONS = ["Scope & sources", "Surface", "Error model",
            "Compatibility & versioning", "Examples", "Traceability",
            "Contract files"]

FRONT_MATTER_KEYS = ["ticket", "items", "contract_files"]


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def frontmatter(text, path):
    parts = text.split("---\n", 2)
    assert len(parts) >= 3 and parts[0] == "", "%s: missing frontmatter" % path
    return parts[1], parts[2]


def agent(role):
    return read(os.path.join(AGENTS, "create-api-contract-%s.md" % role))


def flag_values(body, flag):
    return re.findall(r'%s "([^"]+)"' % re.escape(flag), body)


def doc_skeleton(body):
    match = re.search(r"(?ms)^```markdown\n(---\nticket:.*?)```", body)
    assert match, "no fenced doc skeleton found"
    return match.group(1)


def doc_front_matter_example(body):
    match = re.search(r"(?ms)^```markdown\n(---\nticket:.*?\n---\n)", body)
    assert match, "no fenced front-matter example found"
    return match.group(1)


def synthesized_contract(sections):
    lines = ["# API contract — SHOP-123: Accept large imports", ""]
    for name in sections:
        lines += ["## %s" % name, "content for %s" % name, ""]
    return "\n".join(lines)


class TestSkillFrontmatter(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.fm, cls.body = frontmatter(read(SKILL_PATH), SKILL_PATH)

    def test_name_matches_the_directory(self):
        self.assertRegex(self.fm, r"(?m)^name: create-api-contract$")

    def test_it_is_a_ticket_scoped_coordinator(self):
        self.assertRegex(self.fm, r'(?m)^argument-hint: "\[ticket-id\]"$')
        self.assertRegex(self.fm, r"(?m)^disallowed-tools: Edit, NotebookEdit$")

    def test_description_says_when_it_runs(self):
        self.assertIn("api-contract.md", self.fm)
        self.assertIn("/acs:create-impl-plan", self.fm)


class TestLifecycleWiring(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)

    def test_start_hook_is_the_mandatory_first_action(self):
        self.assertIn("skill-start.py", self.body)
        self.assertRegex(self.body, r"--skill create-api-contract\b")
        self.assertIn("MANDATORY first action", self.body)

    def test_post_hook_closes_the_run_with_the_result_document(self):
        self.assertIn("post-create-api-contract.py", self.body)
        self.assertIn("--result-file", self.body)

    def test_every_message_is_schema_validated(self):
        self.assertIn("validate_xml.py", self.body)
        self.assertIn("schemas/acs-messages.xsd", self.body)

    def test_clarification_ledger_rule_and_completion_report(self):
        self.assertIn("Clarification ledger first.", self.body)
        self.assertIn("clarify.py add --skill create-api-contract", self.body)
        self.assertIn("## Completion report (normative)", self.body)

    def test_it_names_its_own_triad(self):
        for role in ROLES:
            with self.subTest(role=role):
                self.assertIn("acs:create-api-contract-%s" % role, self.body)
                self.assertTrue(os.path.isfile(
                    os.path.join(AGENTS, "create-api-contract-%s.md" % role)))


class TestGateAgreement(unittest.TestCase):
    """The Start section is a map of the gate's refusals; it must be accurate."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.gates_source = read(os.path.join(HOOKS, "acs_lib", "gates.py"))
        cls.gate_body = re.search(r"(?s)def gate_create_api_contract\(.*?\n\n\ndef ",
                                  cls.gates_source).group(0)

    def test_the_registered_gate_is_the_ticket_scoped_one(self):
        self.assertIs(lib.GATES["create-api-contract"], lib.gate_create_api_contract)
        self.assertIn("create-api-contract", lib.GATE_INPUTS["ticket"])

    def test_the_gate_requires_both_documents_the_prose_names(self):
        self.assertIn('"plan.md", "create-impl-plan"', self.gate_body)
        self.assertIn('"analysis.md", "analyze-ticket"', self.gate_body)
        self.assertIn("run /acs:create-impl-plan <id> first", self.body)
        self.assertIn("run /acs:analyze-ticket <id> first", self.body)

    def test_the_gate_reads_the_api_surface_predicate(self):
        self.assertIn("api_surface_changed", self.gate_body)
        self.assertIn("api_surface_changed", lib.PREDICATES)
        self.assertIn("api_surface: true", self.body)

    def test_the_prose_forbids_working_around_the_flag(self):
        self.assertRegex(self.body, r"Do not work around it by editing `analysis.md`")
        self.assertRegex(self.body, r"re-run `/acs:analyze-ticket <id>`")

    def test_order_is_declared_in_the_workflow_not_the_gate(self):
        self.assertIn("workflows/ship.yaml", self.body)
        self.assertRegex(self.body, r"no predecessor-completed check")
        for dead in ("_require_completed", "has not run for"):
            self.assertNotIn(dead, self.body)

    def test_the_step_is_conditional_in_the_shipped_workflow(self):
        """`when: api_surface_changed` is why the skill can say ship.yaml skips
        it for a ticket whose analysis found no surface."""
        workflow = read(os.path.join(PLUGIN, "workflows", "ship.yaml"))
        self.assertRegex(workflow, r"(?s)skill: create-api-contract.*?when: api_surface_changed")


class TestContractFrontMatterContract(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.specs = flag_values(cls.body, "--require")
        cls.example = doc_front_matter_example(cls.body)

    def test_the_skill_declares_exactly_one_require_spec(self):
        self.assertEqual(len(self.specs), 1, self.specs)

    def test_the_spec_declares_the_three_keys_with_their_types(self):
        spec = fmc.parse_spec(self.specs[0])
        self.assertEqual([key for key, _ in spec], FRONT_MATTER_KEYS)
        self.assertEqual(dict(spec)["items"], "int")
        self.assertEqual(dict(spec)["contract_files"], "list")

    def test_the_documented_example_satisfies_the_documented_spec(self):
        self.assertEqual(
            fmc.check_front_matter(self.example, fmc.parse_spec(self.specs[0]),
                                   ticket="SHOP-123"), [])

    def test_the_executor_emits_the_same_keys(self):
        example = doc_front_matter_example(agent("executor"))
        self.assertEqual(
            fmc.check_front_matter(example, fmc.parse_spec(self.specs[0]),
                                   ticket="SHOP-123"), [])

    def test_the_verifier_re_runs_the_same_spec(self):
        self.assertIn(self.specs[0], agent("verifier"))

    def test_a_string_item_count_is_caught_by_that_spec(self):
        broken = re.sub(r"(?m)^items: 3$", 'items: "three"', self.example)
        self.assertEqual(
            [f.rule for f in fmc.check_front_matter(broken, fmc.parse_spec(self.specs[0]))],
            ["wrong-type"])

    def test_items_is_defined_as_the_count_of_surface_subsections(self):
        self.assertRegex(self.body, r"(?s)`items`.*?`### ` subsections")
        self.assertRegex(agent("executor"), r"(?s)`items` is the number of `### `")


class TestContractSectionContract(unittest.TestCase):

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
        doc = synthesized_contract(SECTIONS)
        self.assertEqual(structure_lint.lint_structure(doc, SECTIONS, ordered=True), [])

    def test_an_out_of_order_doc_is_caught_by_that_declaration(self):
        swapped = list(SECTIONS)
        swapped[1], swapped[2] = swapped[2], swapped[1]
        rules = [f.rule for f in structure_lint.lint_structure(
            synthesized_contract(swapped), SECTIONS, ordered=True)]
        self.assertIn("section-order", rules)

    def test_the_error_model_and_examples_are_required_not_optional(self):
        """Errors and examples are the halves implementers most often omit."""
        for name in ("Error model", "Examples"):
            self.assertIn(name, self.sections[0])


class TestTraceability(unittest.TestCase):
    """Every item traces to an acceptance criterion AND a plan item — that pair
    is what makes the contract checkable rather than decorative."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)

    def test_the_skill_states_the_two_way_trace(self):
        self.assertRegex(self.body, r"traces back to an\s+acceptance criterion AND to the plan item")

    def test_the_planner_reports_gaps_in_both_directions(self):
        planner = agent("planner")
        self.assertRegex(planner, r"traces to no acceptance criterion")
        self.assertRegex(planner, r"no item covers is a gap in the plan")

    def test_the_verifier_checks_the_table_against_the_execute_report(self):
        verifier = agent("verifier")
        self.assertIn("traceability", verifier)
        self.assertRegex(verifier, r"`traced_acs` in the execute report matches")

    def test_create_test_docs_is_named_as_the_consumer_of_the_table(self):
        self.assertIn("/acs:create-test-docs", self.body)
        self.assertRegex(agent("executor"),
                         r"/acs:create-test-docs` derives its\s+contract cases")


class TestContractsPathModes(unittest.TestCase):
    """settings.contracts_path decides whether repo-level contract files move."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)

    def test_the_default_and_the_null_opt_out_are_both_described(self):
        self.assertIn("settings.contracts_path", self.body)
        self.assertIn("`docs/api`", self.body)
        self.assertRegex(self.body, r"`null` = the\s+ticket folder only")

    def test_the_settings_default_is_what_the_prose_claims(self):
        self.assertEqual(lib.DEFAULT_SETTINGS["contracts_path"], "docs/api")

    def test_it_refuses_to_invent_a_contract_format(self):
        self.assertRegex(self.body, r"Do NOT invent the convention")
        self.assertRegex(agent("planner"),
                         r"never propose introducing a contract format")

    def test_the_mode_is_declared_to_every_subagent(self):
        self.assertIn("contracts_mode", self.body)
        for role in ROLES:
            with self.subTest(role=role):
                self.assertIn("contracts_mode", agent(role))

    def test_contract_files_are_committed_on_the_ticket_branch_never_pushed(self):
        self.assertRegex(self.body, r"Do NOT push")
        self.assertRegex(self.body, r"never recreate or reset\s+it")
        self.assertRegex(agent("executor"), r"NEVER push, NEVER create a branch")


class TestResultDocument(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.post_hook = read(os.path.join(HOOKS, "post-create-api-contract.py"))

    def test_the_skill_records_exactly_the_documented_states(self):
        block = re.search(r'(?s)"states": \{(.*?)\}', self.body).group(1)
        self.assertEqual(re.findall(r'"(\w+)":', block), list(STATES_KEYS))

    def test_the_post_hook_documents_the_same_keys(self):
        for key in STATES_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, self.post_hook)

    def test_items_in_the_result_is_the_front_matter_count(self):
        self.assertRegex(self.body, r"(?s)`items` \(int\).*?same number as the front matter")

    def test_the_machine_readable_files_are_reported_not_stated(self):
        self.assertRegex(self.body, r"not\s+recorded in `states`")

    def test_a_failed_run_leaves_code_without_a_contract_and_says_so(self):
        self.assertRegex(self.body, r"(?s)no published\s+contract.*?stop_reason")


class TestUserDecisions(unittest.TestCase):
    """Compatibility is a decision, not a derivation."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)

    def test_breaking_changes_are_asked_before_they_are_specified(self):
        self.assertRegex(self.body, r"compatibility questions")
        self.assertRegex(self.body, r"Ask\s+before specifying")

    def test_an_unanswered_breaking_change_is_needs_input_not_a_guess(self):
        self.assertIn('"needs_input"', self.body)
        self.assertRegex(agent("executor"),
                         r"undecided breaking change is a\s+`needs_input`")

    def test_every_breaking_decision_cites_its_ledger_entry(self):
        self.assertRegex(agent("executor"), r"cites the\s+`C-n` ledger entry")
        self.assertRegex(agent("verifier"),
                         r"breaking decision cites the `C-n` ledger entry")


class TestPublishing(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)

    def test_the_artifact_path_is_resolved_by_the_cli_not_guessed(self):
        self.assertIn("artifacts show --ticket <id>", self.body)
        self.assertRegex(self.body, r'artifacts\["api-contract.md"\]')

    def test_the_gate_resolved_inputs_are_reused_not_re_derived(self):
        self.assertRegex(self.body, r'artifacts\["plan.md"\]')
        self.assertRegex(self.body, r"do not\nre-derive them")

    def test_publishing_copies_the_verified_bytes(self):
        self.assertRegex(self.body,
                         r"cp \"<partition>/phases/create-api-contract/api-contract.md\"")
        self.assertIn("Copy, never re-author", self.body)

    def test_the_coordinator_publishes_and_the_guard_is_named(self):
        self.assertIn("never a subagent", self.body)
        self.assertIn("acs_lib/filemap.py", self.body)

    def test_the_executor_is_barred_from_the_published_file(self):
        self.assertRegex(agent("executor"), r"NEVER the published\n  `api-contract.md`")


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
        self.assertIn("phases/create-api-contract/iter-<n>-plan.md", agent("planner"))
        self.assertIn("phases/create-api-contract/iter-<n>-execute.json", agent("executor"))
        self.assertIn("phases/create-api-contract/iter-<n>-verify.md", agent("verifier"))

    def test_each_role_returns_only_a_result_element(self):
        for role in ROLES:
            with self.subTest(role=role):
                body = agent(role)
                self.assertIn('<result skill="create-api-contract"', body)
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

    def test_the_executor_specifies_and_never_implements(self):
        self.assertRegex(agent("executor"), r"NEVER implement the contract")

    def test_the_verifier_re_derives_the_surface_itself(self):
        body = agent("verifier")
        self.assertIn("NEVER rubber-stamp", body)
        self.assertRegex(body, r"re-derive the surface")


if __name__ == "__main__":
    unittest.main()
