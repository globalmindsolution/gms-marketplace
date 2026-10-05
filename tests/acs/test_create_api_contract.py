"""Prose contracts for /acs:create-api-contract — a Design skill, documents only (ADR-0134).

The deterministic half of the move (registry, gate, outcomes, commit layer)
is tests/acs/test_create_api_contract_design.py's. THIS module pins the
markdown layer and, where the markdown makes a claim about the deterministic
layer, checks the claim against that layer:

  * Design, not Development: no plan is needed or read as a boundary, items
    trace to acceptance criteria only, an epic is a valid subject, and the
    `api-contract` LLD type decides whether anything is written
    (`type_disabled` otherwise);
  * documents only: one living, versioned document per interface under
    `lld/<feature>/api/`, plus the per-run record `api-contract.md` -- never a
    machine-readable contract file (`contracts_mode` and its detection are
    gone; /acs:create-impl-plan plans those files and /acs:code writes them);
  * the record's front matter (ticket / items / interfaces) and the two
    section lists, checked with the same checkers and specs the skill runs;
  * the triad (contract-author -> contract-reviewer, plus the gap-analyst in
    the survey's message), the writer slices per interface with an
    integration pass on the seams, and the three reviewer slices.

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
SKILL_DIR = os.path.join(PLUGIN, "skills", "create-api-contract")
SKILL_PATH = os.path.join(SKILL_DIR, "SKILL.md")
AGENTS = os.path.join(PLUGIN, "agents")
sys.path.insert(0, HOOKS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import front_matter_check as fmc  # noqa: E402
import structure_lint  # noqa: E402
import acs_lib as lib  # noqa: E402
from skill_text import skill_contract  # noqa: E402

ROLES = ("contract-author", "contract-reviewer", "gap-analyst")

STATES_KEYS = ("contract_path", "feature", "files", "types", "interfaces", "items",
               "traced_acs", "gaps")

INTERFACE_SECTIONS = ["Scope", "Surface", "Error model", "Compatibility & versioning",
                      "Examples", "Traceability"]
RECORD_SECTIONS = ["Scope & sources", "Interfaces", "Compatibility & versioning",
                   "Traceability", "Gaps"]
RECORD_KEYS = ["ticket", "items", "interfaces"]


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def flat(text):
    return " ".join(text.split())


def frontmatter(text, path):
    parts = text.split("---\n", 2)
    assert len(parts) >= 3 and parts[0] == "", "%s: missing frontmatter" % path
    return parts[1], parts[2]


def contract():
    """What the skill SAYS: SKILL.md with the `references/` it points at read
    in place. Pins on the SKILL.md file itself -- its front matter -- still
    read SKILL_PATH."""
    return skill_contract("create-api-contract")


def agent(role):
    return read(os.path.join(AGENTS, "create-api-contract-%s.md" % role))


def flag_values(body, flag):
    return re.findall(r'%s "([^"]+)"' % re.escape(flag), body)


def record_skeleton(body):
    match = re.search(r"(?ms)^```markdown\n(---\nticket:.*?)```", body)
    assert match, "no fenced run-record skeleton found"
    return match.group(1)


def interface_skeleton(body):
    match = re.search(r"(?ms)^```markdown\n((?:---\n[^`]*?---\n\n)?# [^\n]+\n\n## Scope\n## Surface\n.*?)```",
                      body)
    assert match, "no fenced interface-document skeleton found"
    return match.group(1)


def synthesized(title, sections):
    lines = [title, ""]
    for name in sections:
        lines += ["## %s" % name, "content for %s" % name, ""]
    return "\n".join(lines)


class TestSkillFrontmatter(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.fm, cls.body = frontmatter(read(SKILL_PATH), SKILL_PATH)

    def test_name_matches_the_directory(self):
        self.assertRegex(self.fm, r"(?m)^name: create-api-contract$")

    def test_it_takes_any_subject_like_the_other_design_skills(self):
        self.assertRegex(self.fm, r'(?m)^argument-hint: "\[ticket-id\] \[feature-slug\] '
                                  r'\[documents…\] \[prompt\]"$')
        self.assertRegex(self.fm, r"(?m)^disallowed-tools: Edit, NotebookEdit$")

    def test_description_places_it_in_design_before_or_without_a_plan(self):
        desc = flat(self.fm)
        for phrase in ("Design phase", "before or without an implementation plan",
                       "lld/<feature>/api/", "api-contract.md", "documents only",
                       "never OpenAPI, JSON Schema, proto"):
            self.assertIn(phrase, desc)
        self.assertNotIn("Use after /acs:create-impl-plan", desc)
        self.assertNotIn("approved plan", desc)


class TestDesignNotDevelopment(unittest.TestCase):
    """ADR-0134: the step left the ship pipeline for Design."""

    @classmethod
    def setUpClass(cls):
        cls.body = contract()
        cls.flat = flat(cls.body)

    def test_start_hook_is_the_mandatory_first_action(self):
        self.assertIn('step start --step create-api-contract --args "$ARGUMENTS"', self.body)
        self.assertIn("MANDATORY first action", self.body)
        self.assertIn('post-create-api-contract.py" --result-file', self.body)

    def test_no_plan_is_needed_and_none_bounds_the_contract(self):
        self.assertIn("no plan is needed and none is read as a boundary", self.flat)
        self.assertIn("No plan is needed, and none is read as a boundary.", self.flat)
        self.assertIn("no item traces to a plan item", self.flat)
        self.assertNotRegex(self.body, r"plan\.md` present — \*\*the primary input")
        self.assertNotIn("run /acs:create-impl-plan <id> first", self.body)

    def test_it_never_refuses_for_a_missing_upstream_artifact(self):
        self.assertFalse(hasattr(lib, "reads_of"))
        self.assertIn("never refuses because an upstream artifact is missing", self.flat)
        self.assertIn("The analysis absent", self.body)

    def test_epics_and_ticketless_runs_are_valid_subjects(self):
        self.assertIn("an epic too: Design runs on epics", self.flat)
        self.assertIn("No ticket is required", self.body)
        self.assertNotIn("an epic is designed and fanned out, never given one contract", self.flat)
        for phrase in ("**the argument**", "`requirements.feature`, else `requirements.features`",
                       "`context.ticket.features`", "requirements refine --from -",
                       "never call `ticket save` on a run with no ticket"):
            self.assertIn(phrase, self.flat)

    def test_the_ship_no_op_and_the_api_surface_flag_are_gone(self):
        for gone in ("no_surface_owed", "owes.api_contract", "When nothing is owed",
                     "workflows/ship.yaml"):
            self.assertNotIn(gone, self.body)
        self.assertNotIn("no_surface_owed", lib.outcome_vocabulary("create-api-contract"))
        # An older analysis may still carry the key; the prose says it is ignored.
        self.assertIn("`api_surface:` front-matter key; it is ignored (ADR-0134)", self.flat)
        self.assertRegex(self.body, r"Do not work around a stale analysis by\s+editing it")

    def test_it_owns_the_api_contract_type_and_a_disabled_type_is_a_recorded_no_op(self):
        self.assertIn("api-contract", lib.design_types.LLD_TYPES)
        for phrase in ("This skill owns one LLD type, `api-contract`",
                       "a disabled type is never written", "`outcome: type_disabled`",
                       "the api-contract type is not enabled in design.lld_types"):
            self.assertIn(phrase, self.flat)
        self.assertEqual(sorted(lib.outcome_vocabulary("create-api-contract")),
                         ["contract_written", "type_disabled"])

    def test_the_inputs_are_the_design_inputs(self):
        for phrase in ("hld/integration-map.md", "hld/cross-cutting.md",
                       "`lld/<feature>/api/*.md`", "`lld/<feature>/data/*.md`",
                       "`feature_analysis`", "The interfaces in code"):
            self.assertIn(phrase, self.body)


class TestDocumentsOnly(unittest.TestCase):
    """Machine-readable contract files are /acs:code's, from the plan."""

    @classmethod
    def setUpClass(cls):
        cls.body = contract()
        cls.flat = flat(cls.body)

    def test_contracts_mode_and_its_detection_are_gone(self):
        for gone in ("contracts_mode", "<contracts_dir>", "no-machine-readable-contracts",
                     "contract-file group", "contract_files"):
            self.assertNotIn(gone, self.body)
        self.assertFalse(os.path.exists(os.path.join(SKILL_DIR, "references",
                                                     "contract-files.md")))
        for role in ROLES:
            with self.subTest(role=role):
                self.assertNotIn("contracts_mode", agent(role))
                self.assertNotIn("contract_files", agent(role))

    def test_the_skill_names_who_writes_the_machine_readable_files(self):
        self.assertIn("**Documents only**", self.body)
        self.assertIn("`/acs:create-impl-plan` plans their update from the approved contract "
                      "and `/acs:code` writes them", self.flat)
        self.assertIn("never a machine-readable contract file", self.flat)

    def test_the_author_and_reviewer_hold_the_line(self):
        self.assertIn("You write **documents only**", agent("contract-author"))
        self.assertIn("NEVER implement the contract", agent("contract-author"))
        self.assertIn("read, never edited", flat(agent("contract-author")))
        self.assertIn("7. `documents-only`", agent("contract-reviewer"))
        self.assertIn("never edited", flat(agent("gap-analyst")))

    def test_nothing_is_branched_or_committed(self):
        """ADR-0127: only /acs:create-pr branches and commits; it commits the
        recorded paths in its `design` layer."""
        self.assertRegex(self.body, r"never stages,\s+commits or pushes \(ADR-0127\)")
        self.assertIn("`states.files`", self.body)
        self.assertIn("as the change's `design` layer", self.flat)
        self.assertEqual(lib.commit_plan.SKILL_LAYER["create-api-contract"], "design")
        self.assertNotIn("git checkout -b", self.body)
        self.assertRegex(agent("contract-author"),
                         r"NEVER stage, commit or push, NEVER create or switch a branch")


class TestInterfaceDocuments(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.body = contract()
        cls.flat = flat(cls.body)
        cls.sections = flag_values(cls.body, "--sections")

    def test_one_living_document_per_interface(self):
        self.assertIn("| `api/<interface>.md` — one per interface | `api-contract` |", self.body)
        self.assertIn("an existing `api/` document keeps its name and is revised in place",
                      self.flat)
        self.assertIn("Nothing else in the repo is written — never `data/` or `flows/`, "
                      "never `hld/`", self.flat)

    def test_every_document_is_versioned_through_acs_design(self):
        self.assertIn("design init --status <proposed|implemented> --ticket <id> --feature <slug>",
                      self.flat)
        self.assertIn("design bump --ticket <id>", self.flat)
        self.assertIn("On a run with no ticket drop `--ticket <id>`", self.flat)
        author = flat(agent("contract-author"))
        self.assertIn("design init --status <proposed|implemented> --ticket <id> --feature "
                      "<feature> <file>", author)
        self.assertIn("Once per run", author)

    def test_the_skill_declares_both_section_lists(self):
        lists = [[s.strip() for s in spec.split(";")] for spec in self.sections]
        self.assertEqual(lists, [INTERFACE_SECTIONS, RECORD_SECTIONS])

    def test_the_interface_skeleton_carries_those_headings(self):
        for body in (self.body, agent("contract-author")):
            found = re.findall(r"(?m)^## (.+)$", interface_skeleton(body))
            self.assertEqual(found, INTERFACE_SECTIONS)

    def test_the_reviewer_re_runs_both_section_lists(self):
        for spec in self.sections:
            self.assertIn(spec, agent("contract-reviewer"))

    def test_a_document_built_from_the_skeleton_lints_clean(self):
        doc = synthesized("# Customers API — REST", INTERFACE_SECTIONS)
        self.assertEqual(structure_lint.lint_structure(doc, INTERFACE_SECTIONS, ordered=True), [])
        swapped = list(INTERFACE_SECTIONS)
        swapped[1], swapped[2] = swapped[2], swapped[1]
        rules = [f.rule for f in structure_lint.lint_structure(
            synthesized("# x", swapped), INTERFACE_SECTIONS, ordered=True)]
        self.assertIn("section-order", rules)

    def test_the_design_check_and_lints_run_beside_the_review(self):
        self.assertIn('acs.py" design check <every written interface document>', self.body)
        self.assertIn('mermaid_lint.py" <every written interface document>', self.body)
        self.assertIn("they need no review result, so they never wait for one", self.flat)


class TestRunRecord(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.body = contract()
        cls.flat = flat(cls.body)
        cls.specs = flag_values(cls.body, "--require")
        cls.skeleton = record_skeleton(cls.body)

    def test_the_skill_declares_exactly_one_require_spec(self):
        self.assertEqual(len(self.specs), 1, self.specs)
        spec = fmc.parse_spec(self.specs[0])
        self.assertEqual([key for key, _ in spec], RECORD_KEYS)
        self.assertEqual(dict(spec)["items"], "int")
        self.assertEqual(dict(spec)["interfaces"], "list")

    def test_the_documented_skeleton_satisfies_that_spec(self):
        front = self.skeleton.split("\n# ")[0]
        self.assertEqual(fmc.check_front_matter(front, fmc.parse_spec(self.specs[0]),
                                                ticket="SHOP-123"), [])
        self.assertEqual(re.findall(r"(?m)^## (.+)$", self.skeleton), RECORD_SECTIONS)

    def test_the_reviewer_re_runs_the_same_spec(self):
        self.assertIn(self.specs[0], agent("contract-reviewer"))

    def test_items_and_interfaces_are_derived(self):
        self.assertRegex(self.flat, r"`items` is the number of `### ` subsections under "
                                    r"`## Surface` across the interface documents")
        self.assertIn("every value DERIVED", self.flat)

    def test_the_record_resolves_through_the_cli_and_its_share_choice(self):
        self.assertIn('acs.py" artifacts show\n', self.body)
        self.assertIn('`paths["api-contract.md"]` non-null → publish there', self.body)
        self.assertIn('acs.py" docs where --doc api-contract.md', self.body)
        self.assertIn("Local-only sharing applies to the run record ONLY", self.flat)
        self.assertIn("living documents and always shared", self.flat)

    def test_the_coordinator_publishes_the_verified_bytes(self):
        self.assertIn('cp "<partition>/steps/create-api-contract/api-contract.md" '
                      '"<contract_path>"', self.body)
        self.assertIn("Copy, never re-author", self.flat)
        self.assertIn("never a subagent", self.body)
        self.assertIn("acs_lib/filemap.py", self.body)
        self.assertIn("NEVER the run record `api-contract.md`", flat(agent("contract-author")))

    def test_a_merged_preamble_and_fragments_pass_the_coordinators_checks(self):
        spec = fmc.parse_spec(self.specs[0])
        preamble = ('---\nticket: SHOP-123\nitems: 2\ninterfaces: '
                    '["docs/architecture/lld/shop/api/customers.md", '
                    '"docs/architecture/lld/shop/api/order-events.md"]\n---\n\n'
                    "# API contract — SHOP-123: Order tracking\n")
        frag = "\n".join("## %s\n%s for {k}\n" % (name, name) for name in RECORD_SECTIONS)
        text, order = lib.merge_texts([("preamble", preamble),
                                       ("customers", frag.format(k="customers")),
                                       ("order-events", frag.format(k="order-events"))],
                                      markers=False)
        self.assertEqual(order, RECORD_SECTIONS)
        self.assertNotIn("<!-- slice:", text)
        self.assertEqual(fmc.check_front_matter(text, spec, ticket="SHOP-123"), [])
        self.assertEqual(structure_lint.lint_structure(text, RECORD_SECTIONS, ordered=True), [])


class TestResultDocument(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.body = contract()
        cls.post_hook = read(os.path.join(HOOKS, "post-create-api-contract.py"))

    def test_the_skill_records_exactly_the_documented_states(self):
        block = re.search(r'(?s)"states": \{(.*?)\n     \}', self.body).group(1)
        self.assertEqual(re.findall(r'^\s*"(\w+)":', block, re.M), list(STATES_KEYS))

    def test_the_documented_result_is_admissible(self):
        block = re.search(r"(?ms)^   ```json\n(.*?)^   ```", self.body).group(1)
        doc = json.loads(block)
        self.assertEqual(doc["outcome"], "contract_written")
        self.assertEqual(lib.validate_result(doc, "create-api-contract"), [])

    def test_the_post_hook_documents_the_same_keys(self):
        for key in STATES_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, self.post_hook)

    def test_each_key_is_defined(self):
        for key in STATES_KEYS:
            with self.subTest(key=key):
                self.assertRegex(self.body, r"(?m)^- `%s`" % key)

    def test_a_failed_run_publishes_no_record_and_says_so(self):
        self.assertRegex(self.body, r"no published run record")
        self.assertIn('"stop_reason": "needs_input"', flat(self.body))


class TestUserDecisions(unittest.TestCase):
    """Compatibility is a decision, not a derivation."""

    @classmethod
    def setUpClass(cls):
        cls.body = contract()

    def test_breaking_changes_are_asked_before_they_are_specified(self):
        self.assertIn("compatibility questions", self.body)
        self.assertRegex(self.body, r"Ask before specifying")
        self.assertIn("clarify.py add --skill create-api-contract", self.body)
        self.assertIn("Clarification ledger first.", self.body)

    def test_an_empty_survey_is_a_question_not_an_empty_contract(self):
        self.assertIn("which interface does this change?", self.body)
        self.assertIn("never pad a contract with internals", agent("contract-author"))

    def test_every_breaking_decision_cites_its_ledger_entry(self):
        self.assertRegex(agent("contract-author"), r"cites the `C-n` ledger entry")
        self.assertRegex(agent("contract-author"), r"undecided breaking change is a `needs_input`")
        self.assertRegex(agent("contract-reviewer"),
                         r"breaking decision cites the `C-n` ledger entry")


class TestTriadShape(unittest.TestCase):

    def test_the_roles_and_their_tools(self):
        fm, _ = frontmatter(agent("contract-author"), "contract-author")
        self.assertRegex(fm, r"(?m)^disallowedTools: Agent, Skill$")
        self.assertNotRegex(fm, r"(?m)^tools:")
        for role in ("contract-reviewer", "gap-analyst"):
            fm, _ = frontmatter(agent(role), role)
            self.assertRegex(fm, r"(?m)^tools: Read, Glob, Grep, Bash, Write$")

    def test_no_model_or_effort_pinned_and_every_role_named(self):
        body = contract()
        for role in ROLES:
            with self.subTest(role=role):
                fm, _ = frontmatter(agent(role), role)
                self.assertNotRegex(fm, r"(?m)^model:")
                self.assertNotRegex(fm, r"(?m)^effort:")
                self.assertIn("not for direct invocation", fm)
                self.assertIn("acs:create-api-contract-%s" % role, body)
                self.assertIn('<result skill="create-api-contract" phase="%s"' % role,
                              agent(role))
                self.assertIn("## Grounding (anti-hallucination)", agent(role))

    def test_the_role_table_gives_each_its_kind(self):
        body = contract()
        for role, kind in (("contract-author", "write"), ("gap-analyst", "survey"),
                           ("contract-reviewer", "judge")):
            self.assertIn("| %s | %s | `acs:create-api-contract-%s` |" % (role, kind, role), body)

    def test_a_capped_loop_with_no_planner(self):
        body = contract()
        self.assertIn("contract-author → contract-reviewer", body)
        self.assertRegex(body, r"fixed \*\*3\*\* on every run")
        self.assertIn("no path-driven verify depth", body)
        self.assertFalse(os.path.exists(os.path.join(AGENTS, "create-api-contract-planner.md")))
        self.assertIn("subagents never spawn subagents", body)

    def test_the_gap_analyst_runs_in_the_survey_message_and_classifies_with_two_citations(self):
        body = flat(contract())
        for phrase in ("In the SAME message as the survey",
                       "one gap analyst per existing interface document", "iter-1/gaps.md",
                       "**undocumented** → documented as built",
                       "**unimplemented** → kept and marked planned",
                       "**drifted** → a question in the grouped ask"):
            self.assertIn(phrase, body)
        analyst = flat(agent("gap-analyst"))
        for phrase in ("A gap is a fact with two citations", "## Unverified",
                       "**unimplemented**", "**undocumented**", "**drifted**",
                       "steps/create-api-contract/iter-<n>/gaps-<interface>.md"):
            self.assertIn(phrase, analyst)

    def test_the_reviewer_re_derives_and_polices_grounding(self):
        reviewer = agent("contract-reviewer")
        self.assertIn("NEVER rubber-stamp", reviewer)
        self.assertIn("re-derive the surface", reviewer)
        self.assertIn("police grounding", reviewer)
        self.assertIn("Precision is not the test; truth is.", reviewer)


def reviewer_slices(body):
    """{slice_id: [dimension numbers]} from the Reviewer slices table."""
    rows = re.findall(r"(?m)^\| `(\w+)` \| ([^|]+) \|", body)
    return {sid: [int(n) for n in re.findall(r"(\d+) `", dims)] for sid, dims in rows}


def agent_dimensions(body):
    return dict((int(n), name) for n, name in re.findall(r"(?m)^(\d+)\. `([\w-]+)`", body))


class TestReviewerSlices(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.body = contract()
        cls.reviewer = agent("contract-reviewer")
        cls.slices = reviewer_slices(cls.body)

    def test_three_named_slices_own_every_dimension_once(self):
        self.assertEqual(list(self.slices), ["surface", "trace", "form"])
        owned = sorted(n for dims in self.slices.values() for n in dims)
        self.assertEqual(owned, sorted(agent_dimensions(self.reviewer)))

    def test_the_table_names_match_the_agent_dimensions(self):
        dims = agent_dimensions(self.reviewer)
        for row in re.findall(r"(?m)^\| `\w+` \| ([^|]+) \|", self.body):
            for n, name in re.findall(r"(\d+) `([\w-]+)`", row):
                self.assertEqual(dims[int(n)], name)

    def test_slices_are_joined_by_notes_merge_in_table_order(self):
        block = re.search(r"(?s)notes merge \\\n  --out <partition>/steps/create-api-contract/"
                          r"iter-<n>/contract-reviewer\.md(.*?)```", self.body)
        self.assertEqual(re.findall(r"contract-reviewer-(\w+)\.md", block.group(1)),
                         list(self.slices))

    def test_the_pass_rule_and_de_duplication(self):
        self.assertIn("never \"pass with a missing slice\"", self.body)
        self.assertIn("**De-duplication — the join is the synthesis.**", self.body)
        self.assertRegex(self.body, r"all three slices' findings — de-duplicated,\s+"
                                    r"otherwise verbatim —\s+go to the next writers")
        self.assertIn("## When you are one slice", self.reviewer)
        self.assertIn("Run each deterministic check only in the slice that owns", self.reviewer)


class TestWriterSlices(unittest.TestCase):
    """PARALLEL writers -- one contract-author per interface -- then ONE
    integration pass on the seams, then a deterministic join."""

    @classmethod
    def setUpClass(cls):
        cls.body = contract()
        cls.flat = flat(cls.body)
        cls.author = agent("contract-author")

    def test_one_writer_per_interface_and_the_partition_rule(self):
        self.assertIn("# Writer slices — one contract-author per interface", self.body)
        self.assertIn("**The partition rule.** One slice owns one interface", self.flat)
        self.assertIn("every item has exactly one owner: that is the guarantee two slices "
                      "cannot overlap", self.flat)
        self.assertIn('ONE contract-author, `slice="write"`', self.flat)
        self.assertIn('<constraint name="slice_scope">', self.body)

    def test_writers_are_spawned_in_one_message_under_the_cap(self):
        self.assertIn("Spawn every slice of a wave in ONE message", self.body)
        self.assertRegex(self.flat, r"At most `settings.parallel.max_agents` \(default 4\) "
                                    r"slices per message")

    def test_no_writer_touches_the_index(self):
        for text in (self.body, self.author):
            self.assertNotIn("git commit -m", text)
            self.assertNotIn("index.lock", text)
        self.assertIn("One working tree, no git writes.", self.body)

    def test_the_integration_pass_reconciles_only_the_seams(self):
        self.assertIn('spawn ONE more contract-author with `slice="integration"`', self.flat)
        self.assertIn("## When you are the integration pass", self.author)
        for seam in ("error codes", "shared definitions", "cross-references",
                     "compatibility decisions", "scope and traceability hand-offs", "indexes"):
            with self.subTest(seam=seam):
                self.assertIn("**%s**" % seam, self.body)
                self.assertIn("**%s**" % seam.capitalize(), self.author)
        self.assertIn("It never rewrites a slice's substance and never adds or removes an item",
                      self.flat)
        self.assertIn("`## Synthesis`", self.author)
        self.assertRegex(self.flat, r"skipped when the writer ran un-sliced — one writer has "
                                    r"no seams")

    def test_iteration_two_reruns_only_the_owning_slices(self):
        self.assertRegex(self.flat, r"A seam finding\b.*?goes to the next iteration's "
                                    r"integration pass")
        self.assertIn("but only when a seam finding is open or a re-run slice's report lists "
                      "a `seams` entry", self.flat)
        self.assertIn("never re-run a slice whose report is on disk", self.flat)

    def test_the_draft_is_a_derived_preamble_plus_fragments(self):
        self.assertRegex(self.body, r"notes merge --no-markers \\\n\s+"
                                    r"--out <partition>/steps/create-api-contract/api-contract\.md"
                                    r" \\\n\s+<partition>/steps/create-api-contract/"
                                    r"api-contract-preamble\.md")
        for path in ("steps/create-api-contract/iter-<n>/authoring-<k>.md",
                     "steps/create-api-contract/iter-<n>/contract-author-<k>.json",
                     "steps/create-api-contract/api-contract-<k>.md"):
            self.assertIn(path, self.author)
        self.assertIn("NO front matter and no title line", flat(self.author))

    def test_hyphenated_slice_ids_join_as_the_prose_promises(self):
        self.assertEqual(lib.notes.slice_ids(["api-contract-preamble.md",
                                              "api-contract-order-events.md",
                                              "api-contract-customers.md"]),
                         ["preamble", "order-events", "customers"])


if __name__ == "__main__":
    unittest.main()
