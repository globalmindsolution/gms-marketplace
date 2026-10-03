"""Prose contracts for /acs:create-e2e-tests — the Test step that writes a
ticket's end-to-end suites.

The registration wiring (HOOKED_SKILLS, GATES, the hook wrappers, the pipeline
enum) is tests/acs/test_build_test_skill_registry.py's; the gate bodies are
tests/acs/test_acs_lib_gates.py's. THIS module pins the part that lives in
markdown:

  * the skill is independent: nothing gates it on an upstream artifact, so it
    checks for itself that an e2e suite is configured, falls back to the
    ticket's acceptance criteria when there is no test-cases.md, and records
    `no_e2e_owed` when the case document types no case e2e;
  * the two rules that make this skill safe to run inside a pipeline: it never
    writes product code (a declared file map under the e2e location is the
    mechanism), and it never weakens a test to turn a red suite green — a
    product failure belongs to /acs:run-e2e-tests and ship.yaml's relay;
  * the `states` keys the result document records, cross-checked against
    post-create-e2e-tests.py's docstring;
  * the e2e location is DERIVED from the repo, never invented, because the
    settings carry a command and no directory;
  * the pair's shape -- a test-writer (write) and a suite-runner (judge) --
    including the suite-runner's single suite run and its
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

#: The two subagents this skill owns: the one that writes the suites and the
#: one that judges and runs them.
WRITER, RUNNER = "test-writer", "suite-runner"
ROLES = (WRITER, RUNNER)

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
        self.assertIn('acs.py" step start', self.body)
        self.assertRegex(self.body, r"--step create-e2e-tests\b")
        self.assertIn("MANDATORY first action", self.body)

    def test_post_hook_closes_the_run_with_the_result_document(self):
        self.assertIn('post-create-e2e-tests.py" --result-file', self.body)
        self.assertIn("result.json", self.body)

    def test_every_message_is_schema_validated(self):
        self.assertNotIn("validate_xml.py", self.body)
        self.assertNotIn("acs-messages.xsd", self.body)
        self.assertIn("the SubagentStop hook's message check", self.body)

    def test_clarification_ledger_rule_and_completion_report(self):
        self.assertIn("Clarification ledger first.", self.body)
        self.assertIn("clarify.py", self.body)
        self.assertIn("## Completion report (normative)", self.body)

    def test_it_names_its_own_subagents(self):
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
    """What the Start section promises is what the kernel checks.

    There is no `gate_create_e2e_tests` and no per-skill manifest any more: the
    pre-hook refuses only what would do damage, never a missing upstream
    artifact. So the skill must SAY what it does without one, and the pins are
    on that fallback and on the outcome vocabulary, which is what makes them
    impossible to satisfy with prose alone.
    """

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)

    def test_the_gate_never_refuses_for_a_missing_upstream_artifact(self):
        self.assertFalse(hasattr(lib, "reads_of"),
                         "the per-skill reads declaration is gone")
        self.assertRegex(self.body, r"never refuses because an upstream artifact is\s+missing")

    def test_without_test_cases_it_falls_back_to_the_acceptance_criteria(self):
        self.assertIn("test-cases.md", self.body)
        self.assertRegex(self.body, r"(?s)When there is none.*?acceptance\s+criteria are the specification")
        self.assertRegex(agent(WRITER), r"(?s)no `test-cases.md`.*?acceptance\s+criteria")
        self.assertRegex(agent(RUNNER), r"acceptance-criteria fallback")

    def test_zero_e2e_cases_is_recorded_not_refused(self):
        self.assertRegex(self.body, r'outcome: "no_e2e_owed"')

    def test_the_skill_still_describes_the_e2e_configuration_it_needs(self):
        self.assertIn("settings.e2e", self.body)
        self.assertIn("/acs:setup", self.body)

    def test_nothing_owed_completes_the_step_without_spawning_it(self):
        """`when: e2e_configured` is gone -- the workflow has no predicates
        (§2.1). The step decides for itself and RECORDS why: a run with no
        e2e case owed is completed by the pre-hook from the plan's Contract
        block, for zero tokens, and says `no_e2e_owed`."""
        self.assertIn("no_e2e_owed", lib.outcome_vocabulary("create-e2e-tests"))
        self.assertIn("no_e2e_owed", self.body)

    def test_the_skill_forbids_editing_the_case_document_to_get_past_the_gate(self):
        self.assertRegex(self.body, r"Do NOT work around this by editing `test-cases.md`")


class TestNeverWritesProductCode(unittest.TestCase):
    """The mechanical half of 'tests only': a file map under the e2e location."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)

    def test_the_coordinator_declares_the_file_map_before_the_test_writer(self):
        self.assertIn("acs.py\" filemap set", self.body)
        self.assertRegex(self.body, r"--iteration <n> --task 1 --file")
        self.assertRegex(self.body, r"(?i)declare the file map before you spawn")

    def test_the_map_is_declared_for_this_skill_not_code(self):
        """The guard checks a writer against the map of ITS OWN skill, and
        `filemap set` defaults to `code`: without `--skill` the map lands
        where the test-writer is never checked against it."""
        self.assertRegex(self.body, r"filemap set \\\n\s+--skill create-e2e-tests ")

    def test_the_map_holds_no_source_path(self):
        self.assertRegex(self.body, r"NOTHING under the product's source tree")

    def test_an_executor_needing_a_source_change_returns_needs_input(self):
        self.assertRegex(self.body, r"returns `needs_input` naming the\s+file")
        self.assertRegex(agent(WRITER),
                         r"(?s)status=\"needs_input\".*?product change")

    def test_the_commit_is_limited_to_the_declared_paths(self):
        self.assertRegex(self.body, r"Commit ONLY the paths in the file map")
        self.assertRegex(self.body, r"Do NOT\s+push")

    def test_every_role_carries_the_rule(self):
        for role in ROLES:
            with self.subTest(role=role):
                self.assertRegex(agent(role), r"(?i)never (write |plan a )?product[- ]code")

    def test_the_suite_runner_checks_the_changeset_for_source_edits(self):
        self.assertIn("git status --porcelain", agent(RUNNER))


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

    def test_the_test_writer_is_forbidden_the_shortcuts_by_name(self):
        body = agent(WRITER)
        for shortcut in ("xfail", ".only", "retry"):
            with self.subTest(shortcut=shortcut):
                self.assertIn(shortcut, body)
        self.assertRegex(body, r"Nothing is weakened to go green")

    def test_the_suite_runner_separates_wiring_from_product_failures(self):
        body = agent(RUNNER)
        self.assertRegex(body, r"wiring failure is a blocking finding")
        self.assertRegex(body, r"product failure is NOT a finding")
        self.assertRegex(body, r'NEVER report "make the\s+test pass" as the fix')

    def test_the_suite_runner_severities_are_the_schema_s_severities(self):
        severities = set(re.findall(r'severity="(\w+)"', agent(RUNNER)))
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


class TestSubagentShape(unittest.TestCase):

    def test_role_tool_restrictions(self):
        fm, _ = frontmatter(agent(RUNNER), RUNNER)
        self.assertRegex(fm, r"(?m)^tools: Read, Glob, Grep, Bash, Write$")
        fm, _ = frontmatter(agent(WRITER), WRITER)
        self.assertRegex(fm, r"(?m)^disallowedTools: Agent, Skill$")
        self.assertNotRegex(fm, r"(?m)^tools:")

    def test_no_model_or_effort_pinned_in_an_agent(self):
        for role in ROLES:
            fm, _ = frontmatter(agent(role), role)
            self.assertNotRegex(fm, r"(?m)^model:")
            self.assertNotRegex(fm, r"(?m)^effort:")
            self.assertIn("not for direct invocation", fm)

    def test_each_role_writes_its_phase_artifact(self):
        self.assertIn("steps/create-e2e-tests/iter-<n>/authoring.md", agent(WRITER))
        self.assertIn("steps/create-e2e-tests/iter-<n>/test-writer.json", agent(WRITER))
        self.assertIn("steps/create-e2e-tests/iter-<n>/suite-runner.md", agent(RUNNER))

    def test_the_phase_each_role_echoes_is_its_role(self):
        for role in ROLES:
            with self.subTest(role=role):
                self.assertIn('<result skill="create-e2e-tests" phase="%s"' % role,
                              agent(role))
                self.assertIn('phase="test-writer|suite-runner"', read(SKILL_PATH))

    def test_no_role_names_a_model_tier(self):
        """Model and effort come from settings.models.create-e2e-tests.<role>
        through the agent the coordinator spawns, not from the agent's text."""
        for role in (WRITER, RUNNER):
            with self.subTest(role=role):
                body = agent(role)
                self.assertNotIn("model tier", body)
                self.assertNotRegex(body, r"`(planner|executor|verifier)` model")

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
                    self.assertEqual(lib.validate_message(example), [])

    def test_grounding_everywhere_and_policing_in_the_suite_runner(self):
        for role in ROLES:
            with self.subTest(role=role):
                self.assertIn("## Grounding (anti-hallucination)", agent(role))
        self.assertIn("police grounding", agent(RUNNER))

    def test_no_planner_and_a_capped_loop(self):
        """ADR-0092 class D: the deliverable is the suite, so a plan for it
        would be a second copy of the work — test-writer -> suite-runner only."""
        body = read(SKILL_PATH)
        self.assertRegex(body, r"test-writer → suite-runner, no planner")
        for stale in ("acs:create-e2e-tests-planner", "acs:create-e2e-tests-executor",
                      "acs:create-e2e-tests-verifier", "iter-1-plan.md"):
            with self.subTest(stale=stale):
                self.assertNotIn(stale, body)
        for stale in ("planner", "executor", "verifier"):
            self.assertFalse(os.path.exists(
                os.path.join(AGENTS, "create-e2e-tests-%s.md" % stale)), stale)
        writer = agent(WRITER)
        self.assertIn("## Survey — what you establish before you write (iteration 1)", writer)
        self.assertIn("## The authoring notes (mandatory, every iteration)", writer)
        self.assertRegex(agent(RUNNER), r"(?m)^7\. `authoring-conformance`")
        # The pin is that the cap is unconditional, not that it is phrased in
        # lane vocabulary: ADR-0095 retired lanes, so the same claim now reads
        # "on every run" and disclaims a path-driven depth.
        self.assertRegex(body, r"fixed \*\*3\*\* on every run")
        self.assertRegex(body, r"no path-driven verify depth")
        self.assertIn("never spawn subagents", body.lower())

    def test_only_the_suite_runner_runs_the_suite_and_only_once(self):
        self.assertRegex(agent(WRITER), r"NEVER run the e2e suite")
        runner = agent(RUNNER)
        self.assertRegex(runner, r"Run the command ONCE")
        self.assertRegex(runner, r"teardown ALWAYS")

    def test_the_suite_runner_takes_the_commands_verbatim(self):
        """The R1 no-interpolation posture the suite runner already carries."""
        self.assertRegex(agent(RUNNER),
                         r"never rewrite, wrap, or interpolate captured output")


class TestParallelFanOut(unittest.TestCase):
    """Both roles fan out. The test-writers split by suite file from iteration
    1; the suite-runner's seven dimensions split across three slices, and the
    single suite run stays in exactly one of them. Every fan-out is one message
    of N instances of the same agent, joined deterministically by
    `acs.py notes merge` so every reader still reads ONE file."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.norm = re.sub(r"\s+", " ", cls.body)

    def slice_table(self):
        """{slice id: [(number, name), ...]} from the suite-runner slice table."""
        rows = re.findall(r"(?m)^\| `(\w+)` \| ([^|]+) \|", self.body)
        self.assertTrue(rows, "the suite-runner slice table is missing")
        return {sid: re.findall(r"(\d+) `([a-z-]+)`", dims) for sid, dims in rows}

    def test_the_writer_partition_rule_is_one_suite_file_per_slice(self):
        self.assertIn("#### Parallel test-writers — one per suite file", self.body)
        self.assertIn("One slice is one **suite file**", self.norm)
        self.assertIn("one suite file per ticket is the default", self.norm)
        self.assertIn("that check is what guarantees two slices cannot overlap", self.norm)
        self.assertIn("filemap show --skill create-e2e-tests --iteration <n>", self.norm)

    def test_each_writer_slice_declares_its_own_map_for_this_skill(self):
        self.assertRegex(self.body,
                         r"filemap set \\\n\s+--skill create-e2e-tests --iteration <n> --task <k> --file")

    def test_every_fan_out_is_one_message_under_the_cap(self):
        self.assertIn("in ONE message", self.norm)
        self.assertIn("max_parallel = 4", self.norm)
        self.assertRegex(self.norm, r"waves of four, each wave one message")

    def test_the_slice_is_on_the_wire(self):
        self.assertIn('phase="test-writer" slice="2"', self.norm)
        self.assertIn("a single, un-sliced instance omits `slice`", self.norm)
        self.assertIn('slice="<k>" …>', re.sub(r"\s+", " ", agent(WRITER)))
        self.assertIn('phase="suite-runner" slice="<id>"', re.sub(r"\s+", " ", agent(RUNNER)))

    def test_both_joins_are_notes_merge_never_prose(self):
        merges = re.findall(r'acs\.py" notes merge \\\n\s+--out (\S+)', self.body)
        self.assertEqual(sorted(m.rsplit("/", 1)[-1] for m in merges),
                         ["authoring.md", "suite-runner.md"])
        self.assertIn("never by merging prose yourself", self.norm)

    def test_the_slice_table_covers_every_dimension_once(self):
        table = self.slice_table()
        self.assertTrue(2 <= len(table) <= 3, table)
        numbered = [pair for dims in table.values() for pair in dims]
        agent_dims = re.findall(r"(?m)^(\d+)\. `([a-z-]+)`", agent(RUNNER))
        self.assertEqual(sorted(numbered, key=lambda p: int(p[0])), agent_dims)

    def test_the_suite_run_stays_in_exactly_one_slice(self):
        table = self.slice_table()
        owners = [sid for sid, dims in table.items() if ("3", "wiring") in dims]
        self.assertEqual(owners, ["run"])
        self.assertIn("The run stays in exactly one slice", self.norm)
        runner = re.sub(r"\s+", " ", agent(RUNNER))
        self.assertIn("Only the slice holding dimension 3 executes the configured e2e command", runner)
        self.assertIn("NEVER runs the suite", runner)

    def test_an_integration_test_writer_reconciles_the_seams_before_the_judge(self):
        """A join is not a synthesis: after the per-suite writers, ONE more
        test-writer (`slice="integration"`) reconciles shared fixtures and
        helpers, suite registration and shared ids -- before the suite-runner,
        and only when more than one test-writer ran."""
        self.assertIn("**Then the integration test-writer — a join is not a synthesis.**",
                      self.norm)
        self.assertIn('with `slice="integration"`', self.norm)
        self.assertIn("BEFORE the suite-runner", self.norm)
        self.assertIn("It is skipped when only one test-writer ran", self.norm)
        for seam in ("**shared fixtures and helpers**", "**suite registration**",
                     "**shared ids and names**"):
            with self.subTest(seam=seam):
                self.assertIn(seam, self.norm)
        self.assertIn("iter-<n>/test-writer-integration.json", self.norm)
        self.assertIn("never the runner config or the configured command", self.norm)
        # the integration notes join the merge, last
        merge = re.search(r'--out \S+/authoring\.md(.*?)```', self.body, re.S).group(1)
        self.assertTrue(merge.strip().endswith("authoring-integration.md"), merge)

    def test_the_integration_writer_synthesizes_and_never_rewrites(self):
        writer = re.sub(r"\s+", " ", agent(WRITER))
        self.assertIn("### When you are the integration slice", agent(WRITER))
        self.assertIn("`## Synthesis`", writer)
        self.assertIn("never silently pick one", writer)
        self.assertIn("Never rewrite a slice's tests", writer)
        self.assertIn("`seams_changed`", writer)
        self.assertIn("## Synthesis", self.norm)

    def test_a_seam_finding_goes_back_to_the_integration_pass(self):
        self.assertIn("a seam finding goes to the integration pass", self.norm)
        self.assertIn("judge the INTEGRATED result", re.sub(r"\s+", " ", agent(RUNNER)))

    def test_judge_slices_are_de_duplicated_after_the_merge(self):
        self.assertIn("**De-duplicate after the merge.**", self.norm)
        self.assertIn("same location and the same defect", self.norm)
        self.assertIn("keep the higher severity", self.norm)
        self.assertIn("`## De-duplicated findings` section to the joined `suite-runner.md`", self.norm)
        self.assertIn("de-duplicated, never reworded", self.norm)

    def test_the_sliced_pass_rule(self):
        self.assertIn('EVERY slice returned `status="completed"` with zero blocking findings',
                      self.norm)
        self.assertIn('never "pass with a missing slice"', self.norm)
        self.assertIn("all three slices' findings go verbatim", self.norm)

    def test_questions_from_every_writer_slice_are_asked_once(self):
        self.assertIn("in ONE grouped clarification-ledger ask", self.norm)

    def test_a_resumed_phase_re_runs_only_the_missing_slices(self):
        self.assertIn("re-run only the slices whose report is missing", self.norm)
        self.assertIn("has already spent the iteration's one suite run", self.norm)

    def test_each_agent_knows_its_sliced_files(self):
        writer, runner = agent(WRITER), agent(RUNNER)
        for body in (writer, runner):
            self.assertIn("## When you are one slice", body)
        self.assertIn("iter-<n>/authoring-<k>.md", writer)
        self.assertIn("iter-<n>/test-writer-<k>.json", writer)
        self.assertIn("iter-<n>/suite-runner-<id>.md", runner)
        self.assertIn('<constraint name="dimensions">', runner)
        self.assertIn("Grounding policing always applies", runner)


if __name__ == "__main__":
    unittest.main()
