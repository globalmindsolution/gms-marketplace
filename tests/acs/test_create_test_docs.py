"""Prose contracts for /acs:create-test-docs — the Build step that writes the
ticket's test cases.

The registration wiring (HOOKED_SKILLS, GATES, the hook wrappers, the pipeline
enum) is tests/acs/test_build_test_skill_registry.py's; the gate bodies are
tests/acs/test_acs_lib_gates.py's. THIS module pins the part that lives in
markdown and would otherwise drift away from the deterministic layer:

  * test-cases.md's front matter — three keys, checked with the SAME checker
    and the SAME `--require` spec the SKILL.md tells the coordinator to run;
  * the four required sections, declared byte-identically in the skill and in
    the verifier's re-run, linted here against a doc built from the skill's own
    skeleton;
  * the CASES TABLE's machine-read contract: the documented example is counted
    by `acs_lib.e2e_case_count` — the very function /acs:create-e2e-tests' gate
    calls — and the backticked `e2e` cell the prose forbids really does count
    as zero, which is why the rule is stated at all;
  * the `states` keys the result document records, cross-checked against
    post-create-test-docs.py's docstring;
  * independence: order lives in workflows/ship.yaml and the gate requires no
    predecessor run;
  * the triad's shape (one planner, execute -> verify, artifacts, grounding).

Run:  python3 -m unittest tests.acs.test_create_test_docs -v
"""

import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
HOOKS = os.path.join(PLUGIN, "hooks", "scripts")
SKILL_PATH = os.path.join(PLUGIN, "skills", "create-test-docs", "SKILL.md")
AGENTS = os.path.join(PLUGIN, "agents")

sys.path.insert(0, HOOKS)

import front_matter_check as fmc  # noqa: E402
import structure_lint  # noqa: E402
import acs_lib as lib  # noqa: E402
import validate_xml  # noqa: E402

ROLES = ("planner", "executor", "verifier")

#: The result-document keys the post-hook documents and the next steps read.
STATES_KEYS = ("cases", "e2e_cases", "untraced_acs")

#: The four headings, in order.
SECTIONS = ["Scope", "Cases", "Traceability", "Gaps and assumptions"]

#: The three front-matter keys test-cases.md publishes.
FRONT_MATTER_KEYS = ["ticket", "cases", "e2e_cases"]

#: The columns of the cases table, in order.
COLUMNS = ["ID", "AC", "Type", "Preconditions", "Steps", "Expected", "Suite"]


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def frontmatter(text, path):
    parts = text.split("---\n", 2)
    assert len(parts) >= 3 and parts[0] == "", "%s: missing frontmatter" % path
    return parts[1], parts[2]


def agent(role):
    return read(os.path.join(AGENTS, "create-test-docs-%s.md" % role))


def flag_values(body, flag):
    """Every double-quoted value a CLI flag is given in the prose."""
    return re.findall(r'%s "([^"]+)"' % re.escape(flag), body)


def doc_skeleton(body):
    """The fenced markdown example that carries the doc's headings."""
    match = re.search(r"(?ms)^```markdown\n(---\nticket:.*?)```", body)
    assert match, "no fenced doc skeleton found"
    return match.group(1)


def doc_front_matter_example(body):
    match = re.search(r"(?ms)^```markdown\n(---\nticket:.*?\n---\n)", body)
    assert match, "no fenced front-matter example found"
    return match.group(1)


def xml_examples(body):
    return re.findall(r"(?ms)^```xml\n(.*?)^```", body)


def cases_table(body):
    """The documented cases table, dedented: header, separator and rows."""
    lines = [line.strip() for line in body.splitlines() if line.strip().startswith("|")]
    start = next(i for i, line in enumerate(lines) if line.startswith("| ID | AC |"))
    rows = [lines[start]]
    for line in lines[start + 1:]:
        if not line.startswith("|"):
            break
        if line.startswith("| ID |") or line.startswith("| AC |"):
            break
        rows.append(line)
    return rows


def columns_of(row):
    return [cell.strip() for cell in row.strip().strip("|").split("|")]


def synthesized_cases_doc(table_rows, front=("ticket: SHOP-123", "cases: 3"),
                          sections=None):
    """A whole test-cases.md built from the documented table and headings."""
    sections = SECTIONS if sections is None else sections
    out = ["---"] + list(front) + ["---", "",
                                   "# Test cases — SHOP-123: Accept large imports", ""]
    for name in sections:
        out += ["## %s" % name]
        out += table_rows if name == "Cases" else ["content for %s" % name]
        out += [""]
    return "\n".join(out)


class TestSkillFrontmatter(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.fm, cls.body = frontmatter(read(SKILL_PATH), SKILL_PATH)

    def test_name_matches_the_directory(self):
        self.assertRegex(self.fm, r"(?m)^name: create-test-docs$")

    def test_it_is_a_ticket_scoped_coordinator(self):
        self.assertRegex(self.fm, r'(?m)^argument-hint: "\[ticket-id\]"$')
        self.assertRegex(self.fm, r"(?m)^disallowed-tools: Edit, NotebookEdit$")

    def test_description_routes_on_what_it_produces(self):
        self.assertRegex(self.fm, r"(?m)^description: \S")
        self.assertIn("test-cases.md", self.fm)


class TestLifecycleWiring(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)

    def test_start_hook_is_the_mandatory_first_action(self):
        self.assertIn("skill-start.py", self.body)
        self.assertRegex(self.body, r"--skill create-test-docs\b")
        self.assertIn("MANDATORY first action", self.body)

    def test_post_hook_closes_the_run_with_the_result_document(self):
        self.assertIn("post-create-test-docs.py", self.body)
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
                self.assertIn("acs:create-test-docs-%s" % role, self.body)
                self.assertTrue(os.path.isfile(
                    os.path.join(AGENTS, "create-test-docs-%s.md" % role)))


class TestIndependence(unittest.TestCase):
    """Order lives in ship.yaml; the gate checks this skill's one input."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)

    def test_order_is_declared_in_the_workflow_not_the_gate(self):
        self.assertIn("workflows/ship.yaml", self.body)
        self.assertRegex(self.body, r"no\s+predecessor-completed check")

    def test_it_never_claims_a_predecessor_run_gate(self):
        for dead in ("_require_completed", "has not run for",
                     "last ended with status"):
            with self.subTest(dead=dead):
                self.assertNotIn(dead, self.body)

    def test_the_plan_and_the_contract_are_optional_inputs(self):
        """create-test-docs runs on criteria alone: the gate requires neither."""
        self.assertRegex(self.body, r"read WHEN PRESENT — neither is required")

    def test_the_gate_it_describes_is_the_gate_that_exists(self):
        self.assertIs(lib.GATES["create-test-docs"], lib.gate_create_test_docs)
        self.assertIn("create-test-docs", lib.GATE_INPUTS["ticket"])

    def test_the_gate_requires_no_artifact_of_its_own(self):
        source = read(os.path.join(HOOKS, "acs_lib", "gates.py"))
        body = re.search(r"(?s)def gate_create_test_docs\(.*?\n\n\ndef ", source).group(0)
        self.assertNotIn("_require_artifact", body)
        self.assertNotIn("skill_completed", body)


class TestFrontMatterContract(unittest.TestCase):
    """The machine-read half: three keys, and the documented example passes the
    checker the skill tells the coordinator (and the verifier) to run."""

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
        self.assertEqual(dict(spec)["cases"], "int")
        self.assertEqual(dict(spec)["e2e_cases"], "int")

    def test_the_documented_example_satisfies_the_documented_spec(self):
        self.assertEqual(findings_of(self.example, self.specs[0]), [])

    def test_the_executor_emits_the_same_three_keys(self):
        example = doc_front_matter_example(agent("executor"))
        self.assertEqual(findings_of(example, self.specs[0]), [])

    def test_the_verifier_re_runs_the_same_spec(self):
        self.assertIn(self.specs[0], agent("verifier"))

    def test_a_missing_e2e_cases_key_is_caught_by_that_spec(self):
        broken = re.sub(r"(?m)^e2e_cases: .*\n", "", self.example)
        self.assertEqual([f.rule for f in findings_of(broken, self.specs[0])],
                         ["missing-key"])

    def test_a_boolean_is_not_an_integer_count(self):
        broken = re.sub(r"(?m)^cases: .*$", "cases: true", self.example)
        self.assertEqual([f.rule for f in findings_of(broken, self.specs[0])],
                         ["wrong-type"])


def findings_of(front_matter_text, spec):
    return fmc.check_front_matter(front_matter_text, fmc.parse_spec(spec),
                                  ticket="SHOP-123")


class TestSectionContract(unittest.TestCase):
    """The human-read half: four sections, one declaration, linted for real."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.sections = flag_values(cls.body, "--sections")

    def test_the_skill_declares_the_four_sections_in_order(self):
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
        doc = synthesized_cases_doc(cases_table(agent("executor")))
        self.assertEqual(structure_lint.lint_structure(doc, SECTIONS, ordered=True), [])

    def test_dropping_a_section_is_caught_by_that_declaration(self):
        doc = synthesized_cases_doc(cases_table(agent("executor")),
                                    sections=[s for s in SECTIONS
                                              if s != "Traceability"])
        rules = [f.rule for f in structure_lint.lint_structure(doc, SECTIONS,
                                                               ordered=True)]
        self.assertEqual(rules, ["missing-section"])


class TestCasesTableContract(unittest.TestCase):
    """The table is machine-read: this is the contract /acs:create-e2e-tests'
    gate counts, so the documented example must count."""

    @classmethod
    def setUpClass(cls):
        cls.skill = read(SKILL_PATH)
        cls.rows = cases_table(agent("executor"))
        cls.doc = synthesized_cases_doc(cls.rows)

    def test_the_executor_declares_the_seven_columns_in_order(self):
        self.assertEqual(columns_of(self.rows[0]), COLUMNS)

    def test_the_skill_shows_the_same_columns(self):
        self.assertEqual(columns_of(cases_table(self.skill)[0]), COLUMNS)

    def test_every_example_row_is_a_tc_id_traced_to_a_criterion(self):
        for row in self.rows[2:]:
            cells = columns_of(row)
            with self.subTest(row=cells[0]):
                self.assertRegex(cells[0], r"^TC-\d+$")
                self.assertRegex(cells[1], r"^AC-\d+")
                self.assertIn(cells[2], ("unit", "integration", "e2e"))

    def test_the_documented_example_is_counted_by_the_gates_own_counter(self):
        """acs_lib.e2e_case_count is what pre-create-e2e-tests.py calls."""
        expected = sum(1 for row in self.rows[2:] if columns_of(row)[2] == "e2e")
        self.assertGreaterEqual(expected, 1, "the example must show an e2e row")
        self.assertEqual(count_e2e(self.doc), expected)

    def test_a_backticked_type_cell_counts_as_zero(self):
        """Why the prose forbids backticks: the gate compares the cell exactly,
        so `e2e` silently skips the step that would write the suites."""
        broken = self.doc.replace("| e2e |", "| `e2e` |")
        self.assertNotEqual(broken, self.doc)
        self.assertEqual(count_e2e(broken), 0)

    def test_front_matter_overrides_the_table(self):
        """The counter trusts an integer e2e_cases over the rows — which is why
        the skill calls a wrong value there the one defect nothing downstream
        can catch."""
        doc = synthesized_cases_doc(
            self.rows, front=("ticket: SHOP-123", "cases: 3", "e2e_cases: 9"))
        self.assertEqual(count_e2e(doc), 9)
        self.assertRegex(self.skill, r"trusts\s+`e2e_cases` OVER the table")

    def test_the_bare_word_rule_is_stated_where_it_is_written(self):
        for body in (self.skill, agent("executor")):
            with self.subTest():
                self.assertRegex(body, r"(?i)\bbare word\b")
                self.assertRegex(body, r"no\s+backticks")

    def test_the_coordinator_and_the_verifier_run_the_real_counter(self):
        for body in (self.skill, agent("verifier")):
            with self.subTest():
                self.assertIn("acs_lib.e2e_case_count(sys.argv[2])", body)


def count_e2e(doc):
    """Run the gate's counter over an in-memory document."""
    import tempfile
    handle, path = tempfile.mkstemp(suffix=".md")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as fh:
            fh.write(doc)
        return lib.e2e_case_count(path)
    finally:
        os.unlink(path)


class TestResultDocument(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.post_hook = read(os.path.join(HOOKS, "post-create-test-docs.py"))

    def test_the_skill_records_exactly_the_documented_states(self):
        block = re.search(r'(?s)"states": \{(.*?)\}', self.body).group(1)
        self.assertEqual(re.findall(r'"(\w+)":', block), list(STATES_KEYS))

    def test_the_post_hook_documents_the_same_keys(self):
        for key in STATES_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, self.post_hook)

    def test_the_counts_must_equal_the_published_front_matter(self):
        self.assertEqual(
            len(re.findall(r"MUST equal the\s+published front", self.body)), 2,
            "both counts must be pinned to the published front matter")

    def test_untraced_acs_is_empty_on_a_completed_run(self):
        self.assertRegex(self.body, r"Empty on a\s+completed run")
        self.assertRegex(self.body, r"`untraced_acs` must be `\[\]`")

    def test_zero_e2e_cases_is_a_legitimate_value(self):
        """A ticket with no e2e case is not a failure — the next step simply
        refuses and ship.yaml has nothing to hand it."""
        self.assertRegex(self.body, r"Zero is a legitimate value")


class TestUntracedArm(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)

    def test_an_uncoverable_criterion_becomes_a_question_not_a_dropped_row(self):
        self.assertRegex(self.body, r"do NOT\s*\ndrop it and do NOT invent a case")
        self.assertIn('"status": "needs_input"', self.body)
        self.assertIn('<handoff status="needs_input">', self.body)

    def test_a_ticket_with_no_criteria_is_called_vacuous_not_covered(self):
        self.assertRegex(self.body, r"vacuous case")


class TestPublishing(unittest.TestCase):
    """Only the coordinator writes the published document — the write guard
    denies an executor any write under the ticket docs tree."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)

    def test_the_artifact_path_is_resolved_by_the_cli_not_guessed(self):
        self.assertIn("artifacts show --ticket <id>", self.body)
        self.assertIn("acs_lib.artifacts.artifact_path", self.body)

    def test_publishing_copies_the_verified_bytes(self):
        self.assertRegex(self.body,
                         r'cp "<partition>/phases/create-test-docs/test-cases.md"')
        self.assertRegex(self.body, r"Copy, never re-author")

    def test_the_coordinator_publishes_and_the_guard_is_named(self):
        self.assertIn("never a subagent", self.body)
        self.assertIn("acs_lib/filemap.py", self.body)

    def test_the_executor_is_barred_from_the_published_file(self):
        self.assertRegex(agent("executor"),
                         r"NEVER the published `test-cases.md`")


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
        self.assertIn("phases/create-test-docs/iter-<n>-plan.md", agent("planner"))
        self.assertIn("phases/create-test-docs/iter-<n>-execute.json", agent("executor"))
        self.assertIn("phases/create-test-docs/iter-<n>-verify.md", agent("verifier"))

    def test_each_role_returns_only_a_result_element(self):
        for role in ROLES:
            with self.subTest(role=role):
                body = agent(role)
                self.assertIn('<result skill="create-test-docs"', body)
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

    def test_nobody_in_the_triad_writes_or_runs_tests(self):
        """This skill specifies cases; /acs:code and /acs:create-e2e-tests
        write them, and neither is run here."""
        self.assertRegex(agent("planner"), r"NEVER write test CODE")
        self.assertRegex(agent("executor"), r"NEVER write test code")
        for role in ROLES:
            with self.subTest(role=role):
                self.assertRegex(
                    agent(role),
                    r"(?i)never run the repo's test suites|never write or run tests")

    def test_the_verifier_re_derives_the_traceability(self):
        body = agent("verifier")
        self.assertIn("NEVER rubber-stamp", body)
        self.assertRegex(body, r"re-derive the\s+traceability yourself")


if __name__ == "__main__":
    unittest.main()
