"""Prose contracts for /acs:create-api-contract — the conditional Build step.

Registration wiring is tests/acs/test_build_test_skill_registry.py's and the
gate body is tests/acs/test_acs_lib_gates.py's. THIS module pins the markdown
layer and, where the markdown makes a claim about the deterministic layer,
checks the claim against that layer:

  * independence: the Start section promises no input gate — a missing plan or
    analysis is a fallback to the subject, never a refusal — and a plan that
    owes no surface is settled by the pre-hook as `no_surface_owed`;
  * the contract's front matter (ticket / items / contract_files), checked with
    the same checker and the same `--require` spec the skill runs, and the
    seven required sections, linted from the skill's own skeleton;
  * traceability: every item to an acceptance criterion AND a plan item, which
    is what `states.traced_acs` records and what /acs:create-test-docs reads;
  * `contracts_mode` — contract files are found where the repo keeps them,
    else `docs/api/` (ADR-0102 removed the `contracts_path` setting and its
    `null` opt-out) — including the refusal to invent a contract format a
    repo does not already keep;
  * the pair's shape (contract-author -> contract-reviewer, artifacts,
    grounding).

Run:  python3 -m unittest tests.acs.test_create_api_contract -v
"""

import json
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

ROLES = ("contract-author", "contract-reviewer")

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
        self.assertIn('acs.py" step start', self.body)
        self.assertRegex(self.body, r"--step create-api-contract\b")
        self.assertIn("MANDATORY first action", self.body)

    def test_post_hook_closes_the_run_with_the_result_document(self):
        self.assertIn('post-create-api-contract.py" --result-file', self.body)
        self.assertIn("result.json", self.body)

    def test_every_message_is_schema_validated(self):
        self.assertNotIn("validate_xml.py", self.body)
        self.assertNotIn("acs-messages.xsd", self.body)
        self.assertIn("the SubagentStop hook's message check", self.body)

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
    """The Start section is a map of what the kernel checks; it must be accurate.

    Each skill is independent: the pre-hook never refuses because an upstream
    artifact is missing, so the prose must not promise an input gate either.
    """

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)

    def test_a_missing_plan_is_a_fallback_not_a_refusal(self):
        """The generic input gate (`reads_of`, the per-skill manifest) is gone:
        with no plan the skill works from the subject, and the pointer to
        /acs:create-impl-plan is advice in the report, not a refusal."""
        self.assertFalse(hasattr(lib, "reads_of"))
        self.assertRegex(self.body, r"never refuses because an upstream artifact is missing")
        self.assertRegex(self.body, r"`plan.md` absent — work from the subject")
        self.assertIn("run /acs:create-impl-plan <id> first", self.body)
        self.assertNotIn("acs.yaml", self.body)
        self.assertNotRegex(self.body, r"Missing → \"run")

    def test_nothing_owed_completes_the_step_without_spawning_it(self):
        """`api_surface_changed` was a workflow PREDICATE; the workflow has
        none (§2.1). The step reads the plan's Contract block itself and
        records `no_surface_owed` when nothing is owed -- zero tokens, and an
        answer on the ledger rather than a step that silently did not run."""
        self.assertIn("no_surface_owed", lib.outcome_vocabulary("create-api-contract"))
        self.assertIn("no_surface_owed", self.body)
        self.assertIn("api_surface", self.body)

    def test_the_prose_forbids_working_around_the_flag(self):
        self.assertRegex(self.body, r"Do not work around it by editing")




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

    def test_the_author_emits_the_same_keys(self):
        example = doc_front_matter_example(agent("contract-author"))
        self.assertEqual(
            fmc.check_front_matter(example, fmc.parse_spec(self.specs[0]),
                                   ticket="SHOP-123"), [])

    def test_the_reviewer_re_runs_the_same_spec(self):
        self.assertIn(self.specs[0], agent("contract-reviewer"))

    def test_a_string_item_count_is_caught_by_that_spec(self):
        broken = re.sub(r"(?m)^items: 3$", 'items: "three"', self.example)
        self.assertEqual(
            [f.rule for f in fmc.check_front_matter(broken, fmc.parse_spec(self.specs[0]))],
            ["wrong-type"])

    def test_items_is_defined_as_the_count_of_surface_subsections(self):
        self.assertRegex(self.body, r"(?s)`items`.*?`### ` subsections")
        self.assertRegex(agent("contract-author"), r"(?s)`items` is the number of `### `")


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

    def test_the_author_skeleton_matches_the_skill_skeleton(self):
        found = re.findall(r"(?m)^## (.+)$", doc_skeleton(agent("contract-author")))
        self.assertEqual(found, SECTIONS)

    def test_the_reviewer_re_runs_the_same_section_list(self):
        self.assertIn(self.sections[0], agent("contract-reviewer"))

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

    def test_the_author_survey_reports_gaps_in_both_directions(self):
        author = agent("contract-author")
        self.assertRegex(author, r"traces to no acceptance criterion")
        self.assertRegex(author, r"no item covers is a gap in the plan")

    def test_the_reviewer_checks_the_table_against_the_author_report(self):
        reviewer = agent("contract-reviewer")
        self.assertIn("traceability", reviewer)
        self.assertRegex(reviewer, r"`traced_acs` in the contract-author report matches")

    def test_create_test_docs_is_named_as_the_consumer_of_the_table(self):
        self.assertIn("/acs:create-test-docs", self.body)
        self.assertRegex(agent("contract-author"),
                         r"/acs:create-test-docs` derives its\s+contract cases")


class TestContractsPathModes(unittest.TestCase):
    """Where repo-level contract files live decides whether they move. Until
    ADR-0102 that was `settings.contracts_path` (default `docs/api`, `null` =
    the ticket folder only); now they are found where the repo keeps them,
    else `docs/api/`, and no setting or opt-out exists."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)

    def test_the_found_location_and_the_default_are_both_described(self):
        norm = " ".join(self.body.split())
        self.assertIn("live where the repo keeps them, else at `docs/api/`, "
                      "the conventional default", norm)
        self.assertIn("mode is the repo-relative directory that holds them "
                      "(`<contracts_dir>`)", norm)
        # Inverted: the setting and its `null` ticket-folder-only opt-out are gone.
        self.assertNotIn("contracts_path", self.body)
        self.assertNotRegex(self.body, r"`null` = the\s+ticket folder only")
        self.assertNotIn("ticket-folder-only", self.body)

    def test_no_setting_seeds_or_validates_a_contracts_location(self):
        """Inverted from "the settings default is what the prose claims":
        DEFAULT_SETTINGS no longer seeds `contracts_path`, and the schema no
        longer declares it (ADR-0102)."""
        self.assertNotIn("contracts_path", lib.DEFAULT_SETTINGS)
        with open(os.path.join(PLUGIN, "schemas", "settings.schema.json"),
                  encoding="utf-8") as fh:
            schema = json.load(fh)
        self.assertNotIn("contracts_path", schema.get("properties", {}))

    def test_it_refuses_to_invent_a_contract_format(self):
        self.assertRegex(self.body, r"Do NOT invent the\s+convention")
        self.assertRegex(agent("contract-author"),
                         r"never propose introducing a contract format")

    def test_the_mode_is_declared_to_every_subagent(self):
        self.assertIn("contracts_mode", self.body)
        for role in ROLES:
            with self.subTest(role=role):
                self.assertIn("contracts_mode", agent(role))

    def test_contract_files_are_committed_on_the_ticket_branch_never_pushed(self):
        self.assertRegex(self.body, r"Do NOT push")
        self.assertRegex(self.body, r"never recreate or reset\s+it")
        self.assertRegex(agent("contract-author"), r"NEVER push, NEVER create a branch")


class TestResultDocument(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.post_hook = read(os.path.join(HOOKS, "post-create-api-contract.py"))

    def test_the_skill_records_exactly_the_documented_states(self):
        block = re.search(r'(?s)"states": \{(.*?)\}', self.body).group(1)
        self.assertEqual(re.findall(r'"(\w+)":', block), list(STATES_KEYS))

    def test_the_documented_result_is_admissible(self):
        """The step completes in two ways, so the post-hook refuses a result
        document that does not say which; the documented example must pass
        the kernel's own validator."""
        block = re.search(r"(?ms)^   ```json\n(.*?)^   ```", self.body).group(1)
        doc = json.loads(block)
        self.assertEqual(doc["outcome"], "contract_written")
        self.assertEqual(lib.validate_result(doc, "create-api-contract"), [])

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
        self.assertRegex(agent("contract-author"),
                         r"undecided breaking change is a\s+`needs_input`")

    def test_every_breaking_decision_cites_its_ledger_entry(self):
        self.assertRegex(agent("contract-author"), r"cites the\s+`C-n` ledger entry")
        self.assertRegex(agent("contract-reviewer"),
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
                         r"cp \"<partition>/steps/create-api-contract/api-contract.md\"")
        self.assertIn("Copy, never re-author", self.body)

    def test_the_coordinator_publishes_and_the_guard_is_named(self):
        self.assertIn("never a subagent", self.body)
        self.assertIn("acs_lib/filemap.py", self.body)

    def test_the_author_is_barred_from_the_published_file(self):
        self.assertRegex(agent("contract-author"), r"NEVER the published\n  `api-contract.md`")


class TestTriadShape(unittest.TestCase):

    def test_role_tool_restrictions(self):
        fm, _ = frontmatter(agent("contract-reviewer"), "contract-reviewer")
        self.assertRegex(fm, r"(?m)^tools: Read, Glob, Grep, Bash, Write$")
        fm, _ = frontmatter(agent("contract-author"), "contract-author")
        self.assertRegex(fm, r"(?m)^disallowedTools: Agent, Skill$")
        self.assertNotRegex(fm, r"(?m)^tools:")

    def test_no_model_or_effort_pinned_in_an_agent(self):
        for role in ROLES:
            fm, _ = frontmatter(agent(role), role)
            self.assertNotRegex(fm, r"(?m)^model:")
            self.assertNotRegex(fm, r"(?m)^effort:")
            self.assertIn("not for direct invocation", fm)

    def test_each_role_writes_its_phase_artifact(self):
        self.assertIn("steps/create-api-contract/iter-<n>/authoring.md", agent("contract-author"))
        self.assertIn("steps/create-api-contract/iter-<n>/contract-author.json",
                      agent("contract-author"))
        self.assertIn("steps/create-api-contract/iter-<n>/contract-reviewer.md",
                      agent("contract-reviewer"))

    def test_each_role_returns_only_a_result_element(self):
        for role in ROLES:
            with self.subTest(role=role):
                body = agent(role)
                self.assertIn('<result skill="create-api-contract"', body)
                self.assertIn("FINAL message", body)
                self.assertIn("Nothing follows the closing `</result>` tag.", body)

    def test_grounding_everywhere_and_policing_in_the_reviewer(self):
        for role in ROLES:
            with self.subTest(role=role):
                self.assertIn("## Grounding (anti-hallucination)", agent(role))
        self.assertIn("police grounding", agent("contract-reviewer"))

    def test_each_role_echoes_its_role_as_the_phase(self):
        for role in ROLES:
            with self.subTest(role=role):
                self.assertIn('<result skill="create-api-contract" phase="%s"' % role,
                              agent(role))
                self.assertIn("acs:create-api-contract-%s" % role, read(SKILL_PATH))

    def test_no_planner_and_a_capped_loop(self):
        """ADR-0092 class D: the deliverable is the document, so a plan for it
        would be a second copy of the work — the contract-author surveys and
        writes, the contract-reviewer judges, and nothing plans in between."""
        body = read(SKILL_PATH)
        self.assertRegex(body, r"contract-author → contract-reviewer")
        self.assertNotIn("acs:create-api-contract-planner", body)
        self.assertNotIn("iter-1-plan.md", body)
        self.assertFalse(os.path.exists(os.path.join(AGENTS, "create-api-contract-planner.md")))
        author = agent("contract-author")
        self.assertIn("## Survey — what you establish before you write (iteration 1)", author)
        self.assertIn("## The authoring notes (mandatory, every iteration)", author)
        self.assertRegex(agent("contract-reviewer"), r"(?m)^8\. `authoring-conformance`")
        # The pin is that the cap is unconditional, not that it is phrased in
        # lane vocabulary: ADR-0095 retired lanes, so the same claim now reads
        # "on every run" and disclaims a path-driven depth.
        self.assertRegex(body, r"fixed \*\*3\*\* on every run")
        self.assertRegex(body, r"no path-driven verify depth")
        self.assertIn("never spawn subagents", body.lower())

    def test_the_author_specifies_and_never_implements(self):
        self.assertRegex(agent("contract-author"), r"NEVER implement the contract")

    def test_the_reviewer_re_derives_the_surface_itself(self):
        body = agent("contract-reviewer")
        self.assertIn("NEVER rubber-stamp", body)
        self.assertRegex(body, r"re-derive the surface")



def reviewer_slices(body):
    """{slice_id: [dimension numbers]} from the Reviewer slices table."""
    rows = re.findall(r"(?m)^\| `(\w+)` \| ([^|]+) \|", body)
    return {sid: [int(n) for n in re.findall(r"(\d+) `", dims)] for sid, dims in rows}


def agent_dimensions(body):
    return dict((int(n), name) for n, name in
                re.findall(r"(?m)^(\d+)\. `([\w-]+)`", body))


class TestParallelFanOut(unittest.TestCase):
    """PARALLEL writers (one contract-author per contract-file group) and
    PARALLEL judges (the reviewer's eight dimensions in three slices): the
    coordinator spawns each fan-out in one message and joins it with the
    deterministic `acs.py notes merge`, never by prose."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.author = agent("contract-author")
        cls.reviewer = agent("contract-reviewer")
        cls.slices = reviewer_slices(cls.body)

    # -- judges ---------------------------------------------------------
    def test_the_reviewer_runs_as_two_or_three_named_slices(self):
        self.assertIn("#### Reviewer slices", self.body)
        self.assertEqual(list(self.slices), ["surface", "trace", "files"])

    def test_every_dimension_is_owned_by_exactly_one_slice(self):
        owned = sorted(n for dims in self.slices.values() for n in dims)
        self.assertEqual(owned, sorted(agent_dimensions(self.reviewer)))

    def test_the_table_names_match_the_agent_dimensions(self):
        dims = agent_dimensions(self.reviewer)
        for row in re.findall(r"(?m)^\| `\w+` \| ([^|]+) \|", self.body):
            for n, name in re.findall(r"(\d+) `([\w-]+)`", row):
                self.assertEqual(dims[int(n)], name)

    def test_the_deterministic_checks_run_in_the_slice_that_owns_them(self):
        files_row = re.search(r"(?m)^\| `files` \|.*$", self.body).group(0)
        self.assertIn("front_matter_check.py", files_row)
        self.assertIn("structure_lint.py", files_row)
        self.assertIn("clarify.py list", re.search(r"(?m)^\| `trace` \|.*$", self.body).group(0))
        self.assertIn("Run each deterministic check only in the slice that owns", self.reviewer)

    def test_judge_slices_are_joined_by_notes_merge_in_table_order(self):
        block = re.search(
            r"(?s)notes merge \\\n  --out <partition>/steps/create-api-contract/"
            r"iter-<n>/contract-reviewer\.md(.*?)```", self.body)
        self.assertIsNotNone(block)
        self.assertEqual(re.findall(r"contract-reviewer-(\w+)\.md", block.group(1)),
                         list(self.slices))

    def test_the_sliced_pass_rule(self):
        self.assertIn("passes only if EVERY\nslice returned `status=\"completed\"` with zero blocking findings",
                      self.body)
        self.assertIn("never \"pass with a missing slice\"", self.body)
        self.assertRegex(self.body, r"all three slices' findings — de-duplicated,\s+otherwise verbatim —\s+go to the next")

    def test_the_reviewer_agent_knows_how_to_be_one_slice(self):
        self.assertIn("## When you are one slice", self.reviewer)
        self.assertIn('<constraint name="dimensions">', self.reviewer)
        self.assertIn("steps/create-api-contract/iter-<n>/contract-reviewer-<id>.md", self.reviewer)
        self.assertIn('phase="contract-reviewer" slice="<id>"', self.reviewer)
        self.assertRegex(self.reviewer, r"Grounding policing always applies")

    # -- writers --------------------------------------------------------
    def test_the_writer_partition_rule_is_stated(self):
        self.assertIn("#### Writer slices — one contract-author per contract-file group", self.body)
        self.assertIn("**The partition rule.**", self.body)
        self.assertRegex(self.body, r"every item has exactly one owner: that is the guarantee two slices\s+cannot overlap")
        self.assertRegex(self.body, r"ONE contract-author writes the whole draft, un-sliced")
        self.assertIn('<constraint name="slice_scope">', self.body)

    def test_writers_are_spawned_in_one_message_under_the_cap(self):
        self.assertRegex(self.body, r"Spawn every slice of a wave in ONE message")
        self.assertRegex(self.body, r"At most\s+`settings.parallel.max_agents` \(default 4\) slices per message")
        self.assertRegex(self.body, r"run in waves of that size")

    def test_writers_commit_only_their_own_files_and_retry_on_lock(self):
        for text in (self.body, self.author):
            self.assertIn('git commit -m "<msg>" -- <', text)
            self.assertIn("`index.lock` contention", text)
            self.assertRegex(text, r"never force|Nothing is ever forced")

    def test_the_notes_and_the_draft_are_joined_by_notes_merge(self):
        self.assertRegex(self.body, r"--out <partition>/steps/create-api-contract/iter-<n>/authoring\.md")
        self.assertRegex(self.body, r"notes merge --no-markers \\\n\s+"
                                    r"--out <partition>/steps/create-api-contract/api-contract\.md \\\n"
                                    r"\s+<partition>/steps/create-api-contract/api-contract-preamble\.md")
        self.assertIn("every\n     value DERIVED", self.body)
        # Only the published draft drops the markers; the workspace joins keep them.
        self.assertEqual(self.body.count("--no-markers"), 2)  # the command + the prose

    def test_a_derived_preamble_and_fragments_join_into_a_clean_draft(self):
        """The join the prose promises really does yield ONE draft that the
        coordinator's own two checks pass: the derived preamble's front matter
        is kept and every heading appears once, in order."""
        spec = fmc.parse_spec(flag_values(self.body, "--require")[0])
        preamble = ('---\nticket: SHOP-123\nitems: 2\n'
                    'contract_files: ["docs/api/openapi.yaml", "docs/api/events.yaml"]\n---\n\n'
                    "# API contract — SHOP-123: Accept large imports\n")
        frag = "\n".join("## %s\n%s for {k}\n" % (name, name) for name in SECTIONS)
        text, order = lib.merge_texts([("preamble", preamble),
                                       ("openapi", frag.format(k="openapi")),
                                       ("events", frag.format(k="events"))],
                                      markers=False)
        self.assertEqual(order, SECTIONS)
        self.assertNotIn("<!-- slice:", text, "the published draft carries no slice markers")
        self.assertEqual(fmc.check_front_matter(text, spec, ticket="SHOP-123"), [])
        self.assertEqual(structure_lint.lint_structure(text, SECTIONS, ordered=True), [])

    def test_the_author_agent_knows_how_to_be_one_slice(self):
        self.assertIn("## When you are one slice", self.author)
        for path in ("steps/create-api-contract/iter-<n>/authoring-<k>.md",
                     "steps/create-api-contract/iter-<n>/contract-author-<k>.json",
                     "steps/create-api-contract/api-contract-<k>.md"):
            self.assertIn(path, self.author)
        self.assertIn('phase="contract-author" slice="<k>"', self.author)
        self.assertRegex(self.author, r"NO front matter and no title\s+line")

    def test_sliced_questions_are_one_grouped_ask(self):
        self.assertRegex(self.body, r"go to the user in ONE grouped ask")

    def test_resume_re_runs_only_the_missing_slices(self):
        self.assertRegex(self.body, r"re-runs ONLY the\s+slices whose report is missing")
        self.assertIn("never re-run a slice whose report is on disk", self.body)

    def test_the_slice_travels_on_the_wire(self):
        self.assertIn("iter-<n>/<phase>-<slice>-message.xml", self.body)
        self.assertRegex(self.body, r"un-sliced instance omits `slice`")


class TestSynthesisAfterFanOut(unittest.TestCase):
    """A mechanical join is not a synthesis: parallel contract-authors are
    followed by ONE integration contract-author that reconciles the seams
    before the reviewer judges, contradictions between slices' notes are
    resolved under `## Synthesis`, and duplicate findings across reviewer
    slices are dropped by the coordinator."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.author = agent("contract-author")
        cls.reviewer = agent("contract-reviewer")

    def test_the_integration_pass_is_one_more_contract_author(self):
        self.assertIn("spawn ONE more contract-author with `slice=\"integration\"`", self.body)
        self.assertIn("## When you are the integration pass", self.author)
        self.assertIn('phase="contract-author" slice="integration"', self.author)
        self.assertIn("`integration` are reserved", self.body)

    def test_it_runs_after_the_slices_and_before_the_join_and_the_reviewer(self):
        integration = self.body.index("**The integration pass — synthesis")
        self.assertLess(self.body.index("**One message.** Spawn every slice"), integration)
        self.assertLess(integration, self.body.index("**The join — deterministic"))
        self.assertLess(integration, self.body.index("### Phase: contract-reviewer"))
        self.assertIn("Once the integration pass\n  completed", self.body)

    def test_it_is_skipped_for_a_single_writer(self):
        self.assertRegex(self.body, r"skipped when the contract-author ran un-sliced — one writer has no\s+seams")

    def test_iteration_two_skips_it_when_no_seam_moved(self):
        """ADR-0125: on iteration 2+ the integration pass runs only when a seam
        finding is open or a re-run slice reports a seam."""
        self.assertRegex(self.body, r"but only when a\s+seam finding is open or a re-run slice's report lists a `seams` entry")
        self.assertRegex(self.body, r"With neither, nothing at a\s+seam has moved since the last integration pass, so skip it")
        self.assertIn("Your report carries `seams`", self.author)

    def test_the_seams_are_named(self):
        for seam in ("error codes", "shared definitions", "cross-references",
                     "compatibility decisions", "scope and traceability hand-offs",
                     "indexes"):
            with self.subTest(seam=seam):
                self.assertIn("**%s**" % seam, self.body)
                self.assertIn("**%s**" % seam.capitalize(), self.author)

    def test_it_reconciles_seams_and_never_substance(self):
        self.assertIn("It never rewrites a slice's substance and never adds or removes an item", self.body)
        self.assertIn("Never rewrite a slice's substance, and never add or remove an item", self.author)
        self.assertRegex(self.author, r"`status=\"needs_input\"` with the question")

    def test_it_reports_every_seam_it_changed(self):
        self.assertIn("iter-<n>/contract-author-integration.json", self.body)
        self.assertIn("steps/create-api-contract/iter-<n>/contract-author-integration.json", self.author)
        self.assertIn("(file, what, why, which slices)", self.body)

    def test_contradicting_notes_are_resolved_under_synthesis(self):
        for text in (self.body, self.author):
            self.assertIn("`## Synthesis`", text)
            self.assertIn("authoring-integration.md", text)
        self.assertRegex(self.author, r"never\s+silently pick one")
        block = re.search(r"(?s)--out <partition>/steps/create-api-contract/iter-<n>/authoring\.md(.*?)```",
                          self.body).group(1)
        self.assertTrue(block.strip().endswith("iter-<n>/authoring-integration.md"),
                        "the integration notes join last")

    def test_seam_findings_go_to_the_next_integration_pass(self):
        self.assertRegex(self.body, r"(?s)A seam finding\b.*?goes to the next iteration's\s+integration pass")
        self.assertRegex(self.reviewer, r"judge the INTEGRATED draft")
        self.assertRegex(self.reviewer, r"routes it to\s+the next integration pass")

    def test_hyphenated_slice_ids_join_as_the_prose_promises(self):
        self.assertEqual(lib.notes.slice_ids(["api-contract-preamble.md",
                                              "api-contract-billing-api.md",
                                              "api-contract-events.md"]),
                         ["preamble", "billing-api", "events"])

    def test_judge_findings_are_de_duplicated_in_the_joined_report(self):
        self.assertIn("**De-duplication — the join is the synthesis.**", self.body)
        self.assertRegex(self.body, r"same location and the same defect as another slice's finding,\s+"
                                    r"keeping the one with the higher severity")
        self.assertIn("`## De-duplicated findings` section to\n`iter-<n>/contract-reviewer.md`", self.body)


if __name__ == "__main__":
    unittest.main()
