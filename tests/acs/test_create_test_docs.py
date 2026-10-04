"""Prose contracts for /acs:create-test-docs — the Build step that writes the
ticket's test cases.

The registration wiring (HOOKED_SKILLS, GATES, the hook wrappers, the pipeline
enum) is tests/acs/test_build_test_skill_registry.py's; the gate bodies are
tests/acs/test_acs_lib_gates.py's. THIS module pins the part that lives in
markdown and would otherwise drift away from the deterministic layer:

  * test-cases.md's front matter — three keys, checked with the SAME checker
    and the SAME `--require` spec the SKILL.md tells the coordinator to run;
  * the four required sections, declared byte-identically in the skill and in
    the trace-reviewer's re-run, linted here against a doc built from the skill's own
    skeleton;
  * the CASES TABLE's machine-read contract: the documented example is counted
    by `acs_lib.e2e_case_count` — the very function /acs:create-e2e-tests' gate
    calls — and the backticked `e2e` cell the prose forbids really does count
    as zero, which is why the rule is stated at all;
  * the `states` keys the result document records, cross-checked against
    post-create-test-docs.py's docstring;
  * independence: order lives in workflows/ship.yaml, the gate requires no
    predecessor run and no upstream artifact;
  * the pair's shape (test-designer -> trace-reviewer, artifacts, grounding).

Run:  python3 -m unittest tests.acs.test_create_test_docs -v
"""

import json
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

ROLES = ("test-designer", "trace-reviewer")

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
        self.assertIn('acs.py" step start', self.body)
        self.assertRegex(self.body, r"--step create-test-docs\b")
        self.assertIn("MANDATORY first action", self.body)

    def test_post_hook_closes_the_run_with_the_result_document(self):
        self.assertIn('post-create-test-docs.py" --result-file', self.body)
        self.assertIn("result.json", self.body)

    def test_every_message_is_schema_validated(self):
        self.assertNotIn("validate_xml.py", self.body)
        self.assertNotIn("acs-messages.xsd", self.body)
        self.assertIn("the SubagentStop hook's message check", self.body)

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
        """The skill ships and is a step a workflow may name (not a leg); the
        per-skill manifest and its reads/writes declaration are gone, so
        nothing about an upstream artifact can gate it."""
        self.assertIn("create-test-docs", lib.registered_skills())
        self.assertNotIn("create-test-docs", lib.SKILL_LEGS)
        self.assertFalse(os.path.exists(
            os.path.join(PLUGIN, "skills", "create-test-docs", "acs.yaml")))
        self.assertNotIn("acs.yaml", self.body)

    def test_a_missing_plan_or_contract_is_a_fallback_not_a_refusal(self):
        """Each skill is independent: with no plan or contract the cases are
        derived from the criteria alone, and the gate says nothing about it."""
        self.assertFalse(hasattr(lib, "reads_of"))
        self.assertRegex(self.body,
                         r"It never refuses because an upstream artifact\s+is missing")
        self.assertRegex(self.body, r"cases derived from criteria alone are a legitimate")


class TestFrontMatterContract(unittest.TestCase):
    """The machine-read half: three keys, and the documented example passes the
    checker the skill tells the coordinator (and the trace-reviewer) to run."""

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

    def test_the_designer_emits_the_same_three_keys(self):
        example = doc_front_matter_example(agent("test-designer"))
        self.assertEqual(findings_of(example, self.specs[0]), [])

    def test_the_reviewer_re_runs_the_same_spec(self):
        self.assertIn(self.specs[0], agent("trace-reviewer"))

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

    def test_the_designer_skeleton_matches_the_skill_skeleton(self):
        found = re.findall(r"(?m)^## (.+)$", doc_skeleton(agent("test-designer")))
        self.assertEqual(found, SECTIONS)

    def test_the_reviewer_re_runs_the_same_section_list(self):
        self.assertIn(self.sections[0], agent("trace-reviewer"))

    def test_a_doc_built_from_the_skeleton_lints_clean(self):
        doc = synthesized_cases_doc(cases_table(agent("test-designer")))
        self.assertEqual(structure_lint.lint_structure(doc, SECTIONS, ordered=True), [])

    def test_dropping_a_section_is_caught_by_that_declaration(self):
        doc = synthesized_cases_doc(cases_table(agent("test-designer")),
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
        cls.rows = cases_table(agent("test-designer"))
        cls.doc = synthesized_cases_doc(cls.rows)

    def test_the_designer_declares_the_seven_columns_in_order(self):
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
        for body in (self.skill, agent("test-designer")):
            with self.subTest():
                self.assertRegex(body, r"(?i)\bbare word\b")
                self.assertRegex(body, r"no\s+backticks")

    def test_the_coordinator_and_the_reviewer_run_the_real_counter(self):
        for body in (self.skill, agent("trace-reviewer")):
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

    def test_the_documented_result_is_admissible(self):
        """The step completes in two ways, so the post-hook refuses a result
        document that does not say which; the documented example must pass
        the kernel's own validator."""
        block = re.search(r"(?ms)^   ```json\n(.*?)^   ```", self.body).group(1)
        doc = json.loads(block)
        self.assertEqual(doc["outcome"], "cases_written")
        self.assertEqual(lib.validate_result(doc, "create-test-docs"), [])

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
        # `needs_input` is a stop reason, not a status (acs_lib.run.STEP_STATUSES).
        self.assertIn('"status": "interrupted"', self.body)
        self.assertIn('"stop_reason": "needs_input"', self.body)
        self.assertNotIn('"status": "needs_input"', self.body)
        self.assertIn('<handoff status="needs_input">', self.body)

    def test_a_ticket_with_no_criteria_is_called_vacuous_not_covered(self):
        self.assertRegex(self.body, r"vacuous case")


class TestPublishing(unittest.TestCase):
    """Only the coordinator writes the published document — the write guard
    denies a write-kind agent any write under the ticket docs tree."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)

    def test_the_artifact_path_is_resolved_by_the_cli_not_guessed(self):
        self.assertIn("artifacts show --ticket <id>", self.body)
        self.assertIn("acs_lib.artifacts.artifact_path", self.body)

    def test_publishing_copies_the_verified_bytes(self):
        self.assertRegex(self.body,
                         r'cp "<partition>/steps/create-test-docs/test-cases.md"')
        self.assertRegex(self.body, r"Copy, never re-author")

    def test_the_coordinator_publishes_and_the_guard_is_named(self):
        self.assertIn("never a subagent", self.body)
        self.assertIn("acs_lib/filemap.py", self.body)

    def test_the_designer_is_barred_from_the_published_file(self):
        self.assertRegex(agent("test-designer"),
                         r"NEVER the published `test-cases.md`")


class TestTriadShape(unittest.TestCase):

    def test_role_tool_restrictions(self):
        fm, _ = frontmatter(agent("trace-reviewer"), "trace-reviewer")
        self.assertRegex(fm, r"(?m)^tools: Read, Glob, Grep, Bash, Write$")
        fm, _ = frontmatter(agent("test-designer"), "test-designer")
        self.assertRegex(fm, r"(?m)^disallowedTools: Agent, Skill$")
        self.assertNotRegex(fm, r"(?m)^tools:")

    def test_no_model_or_effort_pinned_in_an_agent(self):
        for role in ROLES:
            fm, _ = frontmatter(agent(role), role)
            self.assertNotRegex(fm, r"(?m)^model:")
            self.assertNotRegex(fm, r"(?m)^effort:")
            self.assertIn("not for direct invocation", fm)

    def test_each_role_writes_its_phase_artifact(self):
        self.assertIn("steps/create-test-docs/iter-<n>/authoring.md", agent("test-designer"))
        self.assertIn("steps/create-test-docs/iter-<n>/test-designer.json",
                      agent("test-designer"))
        self.assertIn("steps/create-test-docs/iter-<n>/trace-reviewer.md",
                      agent("trace-reviewer"))

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
                    self.assertEqual(lib.validate_message(example), [])

    def test_grounding_everywhere_and_policing_in_the_reviewer(self):
        for role in ROLES:
            with self.subTest(role=role):
                self.assertIn("## Grounding (anti-hallucination)", agent(role))
        self.assertIn("police grounding", agent("trace-reviewer"))

    def test_each_role_echoes_its_role_as_the_phase(self):
        for role in ROLES:
            with self.subTest(role=role):
                self.assertIn('<result skill="create-test-docs" phase="%s"' % role,
                              agent(role))
                self.assertIn("acs:create-test-docs-%s" % role, read(SKILL_PATH))

    def test_no_planner_and_a_capped_loop(self):
        """ADR-0092 class D: the deliverable is the document, so a plan for it
        would be a second copy of the work — the test-designer decides and
        writes, the trace-reviewer judges, and nothing plans in between."""
        body = read(SKILL_PATH)
        self.assertRegex(body, r"test-designer → trace-reviewer")
        self.assertNotIn("acs:create-test-docs-planner", body)
        self.assertNotIn("iter-1-plan.md", body)
        self.assertFalse(os.path.exists(os.path.join(AGENTS, "create-test-docs-planner.md")))
        designer = agent("test-designer")
        self.assertIn("## Survey — what you establish before you write (iteration 1)", designer)
        self.assertIn("## The authoring notes (mandatory, every iteration)", designer)
        self.assertRegex(agent("trace-reviewer"), r"(?m)^8\. `authoring-conformance`")
        # The pin is that the cap is unconditional, not that it is phrased in
        # lane vocabulary: ADR-0095 retired lanes, so the same claim now reads
        # "on every run" and disclaims a path-driven depth.
        self.assertRegex(body, r"fixed \*\*3\*\* on every run")
        self.assertRegex(body, r"no path-driven verify depth")
        self.assertIn("never spawn subagents", body.lower())

    def test_nobody_in_the_triad_writes_or_runs_tests(self):
        """This skill specifies cases; /acs:code and /acs:create-e2e-tests
        write them, and neither is run here."""
        self.assertRegex(agent("test-designer"), r"NEVER write test code")
        for role in ROLES:
            with self.subTest(role=role):
                self.assertRegex(
                    agent(role),
                    r"(?i)never run the repo's test suites|never write or run tests")

    def test_the_reviewer_re_derives_the_traceability(self):
        body = agent("trace-reviewer")
        self.assertIn("NEVER rubber-stamp", body)
        self.assertRegex(body, r"re-derive the\s+traceability yourself")



def reviewer_slices(body):
    """{slice_id: [dimension numbers]} from the Reviewer slices table."""
    rows = re.findall(r"(?m)^\| `(\w+)` \| ([^|]+) \|", body)
    return {sid: [int(n) for n in re.findall(r"(\d+) `", dims)] for sid, dims in rows}


def agent_dimensions(body):
    return dict((int(n), name) for n, name in
                re.findall(r"(?m)^(\d+)\. `([\w-]+)`", body))


class TestParallelFanOut(unittest.TestCase):
    """PARALLEL judges: the trace-reviewer's eight dimensions run as three
    slices spawned in one message and joined by `acs.py notes merge`. The
    test-designer is deliberately NOT sliced — one contiguous TC- table."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.reviewer = agent("trace-reviewer")
        cls.slices = reviewer_slices(cls.body)

    def test_the_reviewer_runs_as_three_named_slices(self):
        self.assertIn("#### Reviewer slices", self.body)
        self.assertEqual(list(self.slices), ["trace", "cases", "shape"])

    def test_every_dimension_is_owned_by_exactly_one_slice(self):
        owned = sorted(n for dims in self.slices.values() for n in dims)
        self.assertEqual(owned, sorted(agent_dimensions(self.reviewer)))

    def test_the_table_names_match_the_agent_dimensions(self):
        dims = agent_dimensions(self.reviewer)
        for row in re.findall(r"(?m)^\| `\w+` \| ([^|]+) \|", self.body):
            for n, name in re.findall(r"(\d+) `([\w-]+)`", row):
                self.assertEqual(dims[int(n)], name)

    def test_the_deterministic_checks_run_in_the_slice_that_owns_them(self):
        shape = re.search(r"(?m)^\| `shape` \|.*$", self.body).group(0)
        for check in ("front_matter_check.py", "structure_lint.py", "e2e_case_count"):
            self.assertIn(check, shape)
        self.assertIn("Run each deterministic check only in the slice that owns", self.reviewer)

    def test_judge_slices_are_joined_by_notes_merge_in_table_order(self):
        block = re.search(
            r"(?s)notes merge \\\n  --out <partition>/steps/create-test-docs/"
            r"iter-<n>/trace-reviewer\.md(.*?)```", self.body)
        self.assertIsNotNone(block)
        self.assertEqual(re.findall(r"trace-reviewer-(\w+)\.md", block.group(1)),
                         list(self.slices))

    def test_the_slices_are_spawned_in_one_message_under_the_cap(self):
        self.assertIn("Spawn the three in ONE message", self.body)
        self.assertRegex(self.body, r"three is within the default\s+`settings.parallel.max_agents` of 4")

    def test_the_sliced_pass_rule(self):
        self.assertIn("passes only if EVERY\nslice returned `status=\"completed\"` with zero blocking findings",
                      self.body)
        self.assertIn("never \"pass with a missing slice\"", self.body)
        self.assertRegex(self.body, r"all three slices' findings — de-duplicated,\s+otherwise verbatim —\s+go to the next")

    def test_the_reviewer_agent_knows_how_to_be_one_slice(self):
        self.assertIn("## When you are one slice", self.reviewer)
        self.assertIn('<constraint name="dimensions">', self.reviewer)
        self.assertIn("steps/create-test-docs/iter-<n>/trace-reviewer-<id>.md", self.reviewer)
        self.assertIn('phase="trace-reviewer" slice="<id>"', self.reviewer)
        self.assertRegex(self.reviewer, r"Grounding policing always applies")

    def test_the_test_designer_is_deliberately_one_writer(self):
        self.assertIn("**One test-designer, never sliced.**", self.body)
        self.assertNotIn("slice=", agent("test-designer"))

    def test_resume_re_runs_only_the_missing_slices(self):
        self.assertRegex(self.body, r"re-runs ONLY the\s+reviewer slices whose")
        self.assertIn("never\n   re-run a slice whose report is on disk", self.body)

    def test_the_slice_travels_on_the_wire(self):
        self.assertIn("iter-<n>/<phase>-<slice>-message.xml", self.body)
        self.assertRegex(self.body, r"un-sliced instance omits `slice`")


class TestSynthesisAfterFanOut(unittest.TestCase):
    """The join of the reviewer slices is the synthesis, plus de-duplication;
    with one test-designer there are no seams and no merged survey, so no
    integration pass and no `## Synthesis` section apply."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)

    def test_judge_findings_are_de_duplicated_in_the_joined_report(self):
        self.assertIn("**De-duplication — the join is the synthesis.**", self.body)
        self.assertRegex(self.body, r"same location and the same defect as another slice's finding,\s+"
                                    r"keeping the one with the higher severity")
        self.assertIn("`## De-duplicated findings` section to\n`iter-<n>/trace-reviewer.md`", self.body)
        self.assertRegex(self.body, r"de-duplicated,\s+otherwise verbatim")

    def test_no_integration_pass_for_the_single_writer(self):
        self.assertRegex(self.body, r"no integration pass runs")
        self.assertNotIn('slice="integration"', self.body)
        self.assertNotIn('slice="integration"', agent("test-designer"))


if __name__ == "__main__":
    unittest.main()
