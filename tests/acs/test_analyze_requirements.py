"""Prose contracts for /acs:analyze-requirements — the first Build step.

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
    post-analyze-requirements.py's docstring;
  * independence: the skill points at workflows/ship.yaml for order and claims
    no predecessor-completed check, because there no longer is one;
  * the one recommendation (refined ACs / needs_design) going through its CLI
    — `acs.py ticket save` — and never through a hand-written ticket field;
  * that the skill classifies NOTHING: ADR-0095 retired the `stakes` axis, and
    the delivery path is judged once from the plan by /acs:ship. What this step
    owes that judgement is evidence — load-bearing surfaces named in `## Risks`
    — not a rigor setting written ahead of it;
  * the pair's shape (execute -> verify, no planner, artifacts, grounding).

Run:  python3 -m unittest tests.acs.test_analyze_requirements -v
"""

import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "src", "acs")
HOOKS = os.path.join(PLUGIN, "hooks", "scripts")
SKILL_PATH = os.path.join(PLUGIN, "skills", "analyze-requirements", "SKILL.md")
SKILL_REFERENCES = os.path.join(PLUGIN, "skills", "analyze-requirements", "references")


def skill_contract():
    """SKILL.md plus the references it points at.

    The reconcile procedure and the `ready_for_planning: false` arm moved into
    `references/` under progressive disclosure -- a fresh run that finds the
    ticket plannable reads neither. The rule for deciding whether a question
    blocks stayed inline, because it fires on every run. These pins say what
    the skill SAYS, never which of its files says it.
    """
    import glob as _glob
    parts = [read(SKILL_PATH)]
    parts += [read(q) for q in
              sorted(_glob.glob(os.path.join(SKILL_REFERENCES, "*.md")))]
    return "\n".join(parts)
AGENTS = os.path.join(PLUGIN, "agents")

sys.path.insert(0, HOOKS)

import front_matter_check as fmc  # noqa: E402
import structure_lint  # noqa: E402
import acs_lib as lib  # noqa: E402

ROLES = ("executor", "verifier")

#: The result-document keys the post-hook documents and the next steps read.
STATES_KEYS = ("ready_for_planning", "api_surface", "questions_open")

#: The seven headings, in order. Declared here so a reordering in the prose is
#: a failure rather than a silent contract change.
SECTIONS = ["Problem restated", "Impact map", "Questions", "Assumptions",
            "Risks", "Refined acceptance criteria", "Verdict"]

#: The four front-matter keys the analysis publishes. `stakes_recommendation`
#: left with the axis it set (ADR-0095).
FRONT_MATTER_KEYS = ["ticket", "ready_for_planning", "api_surface",
                     "needs_design_recommendation"]


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def frontmatter(text, path):
    parts = text.split("---\n", 2)
    assert len(parts) >= 3 and parts[0] == "", "%s: missing frontmatter" % path
    return parts[1], parts[2]


def agent(role):
    return read(os.path.join(AGENTS, "analyze-requirements-%s.md" % role))


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
        self.assertRegex(self.fm, r"(?m)^name: analyze-requirements$")

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
        self.assertIn('acs.py" step start', self.body)
        self.assertRegex(self.body, r"--step analyze-requirements\b")
        self.assertIn("MANDATORY first action", self.body)

    def test_the_finish_verb_closes_the_step_from_its_result_document(self):
        """The POST-HOOK closes the step, and it reads the status and
        outcome from the result document it is handed -- a step's transition
        is read from its result, never asserted on the command line.

        `acs step finish` closes only the RUN's view of the step; the
        post-hook does that AND derives the states, writes the index and the
        metrics, and releases the lock."""
        self.assertIn('post-analyze-requirements.py" --result-file', self.body)
        self.assertIn("result.json", self.body)

    def test_every_message_is_validated_in_the_hook(self):
        """The XSD and its second validator are gone (§6): what a subagent
        returns is checked by the SubagentStop hook, in one language."""
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
                self.assertIn("acs:analyze-requirements-%s" % role, self.body)
                self.assertTrue(os.path.isfile(
                    os.path.join(AGENTS, "analyze-requirements-%s.md" % role)))


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
        """One gate for every step now (`gate_outcome`), and what it checks is
        the skill's OWN declaration: `reads` in skills/<name>/acs.yaml drives
        both the runtime input check and `acs workflow validate`'s order
        check, so the two cannot disagree."""
        self.assertTrue(lib.is_step_candidate("analyze-requirements"))
        required, optional = lib.reads_of("analyze-requirements")
        self.assertEqual(required, ["subject"],
                         "the first implementation step reads the run's SUBJECT "
                         "and nothing another step wrote")
        self.assertEqual(optional, [])

    def test_the_epic_refusal_points_at_design_then_fan_out_then_a_child(self):
        self.assertIn("/acs:create-design <id>", self.body)
        self.assertIn("/acs:create-ticket <id>", self.body)
        self.assertRegex(self.body, r"/acs:analyze-requirements` on a child")


class TestGateAgreement(unittest.TestCase):
    """What the prose promises about the pre-hook is what gates.py does."""

    @classmethod
    def setUpClass(cls):
        # The brakes moved out of gates.py into acs_lib.brakes when gates
        # crossed the line budget: a brake reads the run and the repo and
        # resolves nothing, which is a layer of its own.
        cls.brakes_source = read(os.path.join(HOOKS, "acs_lib", "brakes.py"))

    def test_the_gate_refuses_epics_for_this_skill(self):
        """The epic brake runs for every implementation step, from a table
        naming what each one refuses an epic FOR -- rather than a per-skill
        gate function that could be added for one step and forgotten for the
        next."""
        self.assertIn("analyze-requirements", lib.gates._EPIC_VERBS)
        self.assertIn("_refuse_epic(ticket_id, step,", self.brakes_source)

    def test_the_gate_requires_no_artifact_of_its_own(self):
        """analyze-requirements is the first implementation step: its only
        input is the run's subject, so its `reads` list is empty and the input
        gate asks for nothing."""
        required, optional = lib.reads_of("analyze-requirements")
        self.assertEqual((required, optional), (["subject"], []))


class TestAnalysisFrontMatterContract(unittest.TestCase):
    """The machine-read half: four keys, and the documented example passes the
    checker the skill tells the coordinator (and the verifier) to run."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.specs = flag_values(cls.body, "--require")
        cls.example = doc_front_matter_example(cls.body)

    def test_the_skill_declares_exactly_one_require_spec(self):
        self.assertEqual(len(self.specs), 1, self.specs)

    def test_the_spec_declares_the_four_keys_with_their_types(self):
        spec = fmc.parse_spec(self.specs[0])
        self.assertEqual([key for key, _ in spec], FRONT_MATTER_KEYS)
        self.assertEqual(dict(spec)["api_surface"], "bool")
        self.assertEqual(dict(spec)["ready_for_planning"], "bool")
        self.assertEqual(dict(spec)["needs_design_recommendation"], "bool")

    def test_the_documented_example_satisfies_the_documented_spec(self):
        findings = fmc.check_front_matter(self.example, fmc.parse_spec(self.specs[0]),
                                          ticket="SHOP-123")
        self.assertEqual(findings, [])

    def test_the_executor_emits_the_same_four_keys(self):
        example = doc_front_matter_example(agent("executor"))
        self.assertEqual(findings_of(example, self.specs[0]), [])

    def test_the_verifier_re_runs_the_same_spec(self):
        self.assertIn(self.specs[0], agent("verifier"))

    def test_a_missing_api_surface_key_is_caught_by_that_spec(self):
        broken = re.sub(r"(?m)^api_surface: .*\n", "", self.example)
        self.assertEqual([f.rule for f in findings_of(broken, self.specs[0])],
                         ["missing-key"])

    def test_api_surface_is_read_by_the_step_that_acts_on_it(self):
        """The front-matter key is not a local convention. `ship.yaml` has no
        predicates any more -- every step decides for itself and records why
        (§2.1) -- so what reads this is `/acs:create-api-contract`, which
        completes with `no_surface_owed` when nothing is owed."""
        self.assertIn("api_surface", self.body)
        self.assertIn("no_surface_owed", lib.outcome_vocabulary("create-api-contract"))


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
        cls.post_hook = read(os.path.join(HOOKS, "post-analyze-requirements.py"))

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
        """needs_design is applied through its own CLI, so a `states` key for it
        would be a second, divergent source of truth — and `stakes` is not a
        field anywhere any more."""
        block = re.search(r'(?s)"states": \{(.*?)\}', self.body).group(1)
        self.assertNotIn("stakes", block)
        self.assertNotIn("needs_design", block)


class TestItClassifiesNothingTest(unittest.TestCase):
    """ADR-0095: this step sets no rigor. It records the evidence the delivery
    judgement will read, and leaves the judgement to /acs:ship.

    The stakes recommendation used to live here — `acs.py stakes recommend`
    over the impact map, applied through `acs.py lane apply --proposed-stakes
    high`. Both commands are gone with the axis. What survives is the reason
    the recommendation existed: the impact map is the first place anyone can
    see which load-bearing surfaces a ticket touches, so the analysis must say
    so where the plan (and then the judge) will read it."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)

    def test_no_retired_axis_command_survives(self):
        for dead in ("stakes recommend", "lane apply", "--proposed-stakes",
                     "--proposed-size", "derive_lane", "verify_depth"):
            with self.subTest(command=dead):
                self.assertNotIn(dead, self.body)

    def test_it_says_outright_that_it_does_not_classify(self):
        self.assertRegex(
            self.body,
            r"(?s)no `stakes` axis any more, and this skill does not classify")

    def test_load_bearing_surfaces_are_named_in_risks(self):
        self.assertRegex(self.body,
                         r"(?s)load-bearing.{0,400}`## Risks`, naming the paths")

    def test_the_evidence_is_addressed_to_the_delivery_judgement(self):
        self.assertRegex(self.body, r"(?s)delivery-path judgement.{0,200}ADR-0095")


class TestTicketAmendments(unittest.TestCase):
    """Refined ACs and needs_design are proposals; the ticket changes only on a
    user answer, and only through the CLI that re-indexes it."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)

    def test_amendments_go_through_the_ticket_save_cli(self):
        self.assertIn("acs.py\" ticket save --ticket <id> --from -", self.body)

    def test_they_are_recorded_in_the_ledger_before_acting(self):
        self.assertIn("clarify.py add --skill analyze-requirements", self.body)
        self.assertRegex(self.body, r"ONLY on an explicit user answer")

    def test_without_an_answer_the_ticket_is_left_alone(self):
        self.assertRegex(self.body, r"leave the ticket untouched")


class TestNotReadyArm(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.body = skill_contract()

    def test_not_ready_finishes_as_needs_input_with_open_questions(self):
        self.assertIn("ready_for_planning: false", self.body)
        self.assertIn('"status": "needs_input"', self.body)
        self.assertIn("`clarify.py add` without\n   `--answer`", self.body)

    def test_the_handoff_carries_the_questions(self):
        self.assertIn("<handoff status=\"needs_input\">", self.body)

    def test_a_conventional_default_is_an_assumption_not_a_blocker(self):
        # 2026-09-15 gate: a two-line login ticket came back
        # `ready_for_planning: false` on stdout-vs-stderr, case sensitivity
        # and unmentioned argument counts -- three questions a competent
        # implementer settles by convention, asked of a run with nobody to
        # answer. The rule lives in the skill AND in the executor's verdict
        # contract, so neither role can reintroduce the blocker alone.
        skill = " ".join(self.body.split())
        self.assertIn(
            "**A question with a conventional default is an assumption, not a "
            "blocker.**", skill)
        self.assertIn("keep `ready_for_planning: true`", skill)
        self.assertIn("where every default could build the wrong thing", skill)
        executor = " ".join(
            read(os.path.join(AGENTS, "analyze-requirements-executor.md")).split())
        self.assertIn("A detail with a conventional default", executor)
        self.assertIn("never a reason for `false`", executor)
        self.assertIn("every default could build the wrong thing", executor)


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
        self.assertRegex(self.body, r"cp \"<partition>/steps/analyze-requirements/analysis.md\"")
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
        fm, _ = frontmatter(agent("verifier"), "verifier")
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
        self.assertIn("steps/analyze-requirements/iter-<n>/authoring.md", agent("executor"))
        self.assertIn("steps/analyze-requirements/iter-<n>/execute.json", agent("executor"))
        self.assertIn("steps/analyze-requirements/iter-<n>/verify.md", agent("verifier"))

    def test_each_role_returns_only_a_result_element(self):
        for role in ROLES:
            with self.subTest(role=role):
                body = agent(role)
                self.assertIn('<result skill="analyze-requirements"', body)
                self.assertIn("FINAL message", body)
                self.assertIn("Nothing follows the closing `</result>` tag.", body)

    def test_grounding_everywhere_and_policing_in_the_verifier(self):
        for role in ROLES:
            with self.subTest(role=role):
                self.assertIn("## Grounding (anti-hallucination)", agent(role))
        self.assertIn("police grounding", agent("verifier"))

    def test_no_planner_and_a_capped_loop(self):
        """ADR-0092 class D: the deliverable is the analysis, so a plan for it
        would be a second copy of the work — execute -> verify only."""
        body = read(SKILL_PATH)
        self.assertRegex(body, r"execute → verify, no planner")
        self.assertNotIn("acs:analyze-requirements-planner", body)
        self.assertNotIn("iter-1-plan.md", body)
        self.assertFalse(os.path.exists(os.path.join(AGENTS, "analyze-requirements-planner.md")))
        self.assertRegex(body, r"fixed \*\*3\*\*\s+on every run")
        self.assertRegex(body, r"no path-driven verify depth")
        self.assertIn("never spawn subagents", body.lower())

    def test_the_executor_surveys_first_and_does_not_plan_the_implementation(self):
        """The survey the planner used to do is the executor's first job, and
        the boundary with /acs:create-impl-plan is stated where it is enforced."""
        body = agent("executor")
        self.assertIn("## Survey — what you establish before you write (iteration 1)", body)
        self.assertIn("## The authoring notes (mandatory, every iteration)", body)
        self.assertRegex(body, r"NEVER plan the implementation")
        self.assertRegex(agent("verifier"), r"(?m)^7\. `authoring-conformance`")

    def test_the_verifier_re_derives_rather_than_trusting_the_draft(self):
        body = agent("verifier")
        self.assertIn("NEVER rubber-stamp", body)
        self.assertRegex(body, r"re-derive[sd]? the impact (map|surface)")


if __name__ == "__main__":
    unittest.main()
