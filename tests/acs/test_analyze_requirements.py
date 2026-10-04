"""Prose contracts for /acs:analyze-requirements — the first Build step.

The registration wiring (HOOKED_SKILLS, GATES, the hook wrappers, the pipeline
enum) is tests/acs/test_build_test_skill_registry.py's; the gate bodies are
tests/acs/test_acs_lib_gates.py's. THIS module pins the part that lives in
markdown and would otherwise drift away from the deterministic layer:

  * the analysis's front matter — the four keys, checked here with the SAME
    checker and the SAME `--require` spec the SKILL.md tells the coordinator to
    run, so the documented example actually passes it;
  * the seven required sections, declared byte-identically in the skill and in
    the impact reviewer's re-run, and linted here against a doc built from the skill's
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
  * the pair's shape (analyst -> impact review, artifacts, grounding);
  * the three stages, in order -- Impact (the survey lanes -- the analyst's
    requirements lane and the impact analysts' code lanes -- separate from
    the draft pass, starting from the previously published analysis),
    Clarify (one grouped ask, defaults asked as confirmations when the user
    is reachable, confirmed criteria written into the ticket, one follow-up
    round), Store (draft, review, publish the reusable record).

Run:  python3 -m unittest tests.acs.test_analyze_requirements -v
"""

import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
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

ROLES = ("analyst", "impact-analyst", "impact-reviewer")

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
    ticket — the shape the analyst is told to emit."""
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

    def test_it_names_its_own_subagents(self):
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
        """The skill is independent: it ships as a skill a workflow may name
        (not a leg), no manifest declares what it reads, and the gate has no
        input check left to refuse it on -- it works from the ticket alone."""
        self.assertTrue(lib.is_skill("analyze-requirements"))
        self.assertIsNone(lib.entry_point_of("analyze-requirements"))
        self.assertFalse(os.path.exists(
            os.path.join(PLUGIN, "skills", "analyze-requirements", "acs.yaml")))
        self.assertFalse(hasattr(lib.stepgate, "check_inputs"))
        self.assertIn("Nothing\nupstream is required", self.body)

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
        input is the run's subject. No gate asks for an upstream artifact --
        the generic input check is gone, and no brake names this skill for
        anything but the epic refusal."""
        self.assertFalse(hasattr(lib.stepgate, "check_inputs"))
        self.assertNotIn("missing_reads", self.brakes_source)


class TestAnalysisFrontMatterContract(unittest.TestCase):
    """The machine-read half: four keys, and the documented example passes the
    checker the skill tells the coordinator (and the impact reviewer) to run."""

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

    def test_the_analyst_emits_the_same_four_keys(self):
        example = doc_front_matter_example(agent("analyst"))
        self.assertEqual(findings_of(example, self.specs[0]), [])

    def test_the_impact_reviewer_re_runs_the_same_spec(self):
        self.assertIn(self.specs[0], agent("impact-reviewer"))

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

    def test_the_analyst_skeleton_matches_the_skill_skeleton(self):
        found = re.findall(r"(?m)^## (.+)$", doc_skeleton(agent("analyst")))
        self.assertEqual(found, SECTIONS)

    def test_the_impact_reviewer_re_runs_the_same_section_list(self):
        self.assertIn(self.sections[0], agent("impact-reviewer"))

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
        # `needs_input` is a stop reason, not a status: the post-hook admits
        # only completed | failed | interrupted (acs_lib.run.STEP_STATUSES).
        self.assertIn('"status": "interrupted"', self.body)
        self.assertIn('"stop_reason": "needs_input"', self.body)
        self.assertNotIn('"status": "needs_input"', self.body)
        self.assertIn("`clarify.py add` without\n   `--answer`", self.body)

    def test_the_handoff_carries_the_questions(self):
        self.assertIn("<handoff status=\"needs_input\">", self.body)

    def test_a_conventional_default_is_an_assumption_not_a_blocker(self):
        # 2026-09-15 gate: a two-line login ticket came back
        # `ready_for_planning: false` on stdout-vs-stderr, case sensitivity
        # and unmentioned argument counts -- three questions a competent
        # implementer settles by convention, asked of a run with nobody to
        # answer. The rule lives in the skill AND in the analyst's verdict
        # contract, so neither can reintroduce the blocker alone. Since the
        # 2026-09-27 three-stage split it is the rule for an UNREACHABLE user
        # only: a reachable one is asked the same defaults as confirmations.
        skill = " ".join(self.body.split())
        self.assertIn(
            "and no answers were relayed in a `/acs:ship` brief. Then, and only "
            "then: **A question with a conventional default is an assumption, "
            "not a blocker.**", skill)
        self.assertIn("keep `ready_for_planning: true`", skill)
        self.assertIn("where every default could build the wrong thing", skill)
        analyst = " ".join(
            read(os.path.join(AGENTS, "analyze-requirements-analyst.md")).split())
        self.assertIn("A detail with a conventional default", analyst)
        self.assertIn("never a reason for `false`", analyst)
        self.assertIn("every default could build the wrong thing", analyst)


class TestPublishing(unittest.TestCase):
    """Only the coordinator writes the published analysis — the write guard
    denies a `write`-kind agent (the analyst) any write under the ticket docs
    tree."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)

    def test_the_artifact_path_is_resolved_by_the_cli_not_guessed(self):
        self.assertIn("artifacts show --ticket <id>", self.body)
        self.assertIn("acs_lib.artifacts.artifact_path", self.body)

    def test_publishing_is_the_controller_s_script(self):
        """ADR-0114 §5: no prose `cp`/`git add` -- the controller copies the
        reviewed bytes and commits the docs folder (tests/acs/test_analysis_loop.py
        proves the bytes, the pathspec and the absent push)."""
        self.assertIn('acs.py" analysis publish', self.body)
        self.assertIn('acs.py" analysis record-publication', self.body)
        self.assertNotRegex(self.body, r"(?m)^cp ")
        self.assertNotIn('git add "<docs_dir>"', self.body)
        self.assertIn("It never pushes.", self.body)

    def test_the_coordinator_never_publishes_and_the_guard_is_named(self):
        self.assertIn("You never copy or commit the analysis yourself, and no "
                      "subagent does", " ".join(self.body.split()))
        self.assertIn("acs_lib/filemap.py", self.body)

    def test_the_analyst_is_barred_from_the_published_file(self):
        self.assertRegex(agent("analyst"),
                         r"NEVER the published\n  `analysis.md`")


class TestSubagentShape(unittest.TestCase):
    """House shape for the two agents (the shared suite covers every skill;
    these keep this pair honest on its own)."""

    def test_role_tool_restrictions(self):
        fm, _ = frontmatter(agent("impact-reviewer"), "impact-reviewer")
        self.assertRegex(fm, r"(?m)^tools: Read, Glob, Grep, Bash, Write$")
        fm, _ = frontmatter(agent("analyst"), "analyst")
        self.assertRegex(fm, r"(?m)^disallowedTools: Agent, Skill$")
        self.assertNotRegex(fm, r"(?m)^tools:")

    def test_no_model_or_effort_pinned_in_an_agent(self):
        for role in ROLES:
            fm, _ = frontmatter(agent(role), role)
            self.assertNotRegex(fm, r"(?m)^model:")
            self.assertNotRegex(fm, r"(?m)^effort:")
            self.assertIn("not for direct invocation", fm)

    def test_each_role_writes_its_phase_artifact(self):
        self.assertIn("steps/analyze-requirements/iter-<n>/authoring.md", agent("analyst"))
        self.assertIn("steps/analyze-requirements/iter-<n>/analyst.json", agent("analyst"))
        self.assertIn("steps/analyze-requirements/iter-<n>/impact-reviewer.md",
                      agent("impact-reviewer"))

    def test_each_role_returns_only_a_result_element(self):
        for role in ROLES:
            with self.subTest(role=role):
                body = agent(role)
                self.assertIn('<result skill="analyze-requirements"', body)
                self.assertIn("FINAL message", body)
                self.assertIn("Nothing follows the closing `</result>` tag.", body)

    def test_grounding_everywhere_and_policing_in_the_impact_reviewer(self):
        for role in ROLES:
            with self.subTest(role=role):
                self.assertIn("## Grounding (anti-hallucination)", agent(role))
        self.assertIn("police grounding", agent("impact-reviewer"))

    def test_no_planner_and_a_capped_loop(self):
        """ADR-0092 class D: the deliverable is the analysis, so a plan for it
        would be a second copy of the work — analyst -> impact review only."""
        body = read(SKILL_PATH)
        self.assertRegex(body, r"analyst → impact review")
        self.assertRegex(body, r"No third role\s+plans the analysis")
        self.assertNotIn("acs:analyze-requirements-planner", body)
        self.assertNotIn("iter-1-plan.md", body)
        self.assertFalse(os.path.exists(os.path.join(AGENTS, "analyze-requirements-planner.md")))
        self.assertRegex(body, r"fixed \*\*3\*\*\s+on every run")
        self.assertRegex(body, r"no path-driven verify depth")
        self.assertRegex(body, r"the controller counts it")
        self.assertIn("never spawn subagents", body.lower())

    def test_the_analyst_surveys_first_and_does_not_plan_the_implementation(self):
        """The survey the planner used to do is the analyst's first job, and
        the boundary with /acs:create-impl-plan is stated where it is enforced."""
        body = agent("analyst")
        self.assertIn("## Survey — what you establish before you write (iteration 1)", body)
        self.assertIn("## The authoring notes (mandatory, every iteration)", body)
        self.assertRegex(body, r"NEVER plan the implementation")
        self.assertRegex(agent("impact-reviewer"), r"(?m)^7\. `authoring-conformance`")

    def test_the_impact_reviewer_re_derives_rather_than_trusting_the_draft(self):
        body = agent("impact-reviewer")
        self.assertIn("NEVER rubber-stamp", body)
        self.assertRegex(body, r"re-derive[sd]? the impact (map|surface)")


def norm(body):
    """Whitespace-normalized, with shell line continuations folded away."""
    return re.sub(r"\s+", " ", body.replace("\\\n", " "))


#: The judge slices and the dimension numbers each owns (SKILL.md's table).
JUDGE_SLICES = {"surface": (2, 3), "form": (4, 5, 6), "evidence": (1, 7)}


class TestParallelism(unittest.TestCase):
    """The fan-out contract: one writer (a single document), survey slices
    over disjoint top-level areas on iteration 1, and the impact reviewer split
    into three dimension slices — each spawned in one message and joined by
    `acs.py notes merge`, never by prose."""

    @classmethod
    def setUpClass(cls):
        cls.skill = norm(read(SKILL_PATH))
        cls.contract = norm(skill_contract())
        cls.analyst = norm(agent("analyst"))
        cls.reviewer = norm(agent("impact-reviewer"))

    def test_the_writer_stays_single_and_says_why(self):
        self.assertIn("Writer — one analyst, never sliced.", self.skill)
        self.assertIn("`analysis.md` is a single document", self.skill)

    def test_every_fan_out_is_one_message_and_capped(self):
        self.assertIn("in ONE message (all foreground, in the same message)",
                      self.skill)
        self.assertIn("`settings.parallel.max_agents` (default 4)", self.skill)
        self.assertIn("waves of that size", self.skill)

    def test_survey_partition_rule(self):
        self.assertIn("**two or more disjoint top-level areas**", self.skill)
        self.assertIn("no directory belongs to two areas, so no two slices "
                      "survey the same path", self.skill)
        self.assertIn('phase="impact-analyst" slice="<area>"', self.skill)
        self.assertIn('phase="analyst" slice="requirements"', self.skill)
        self.assertIn('<constraint name="survey_area">', self.skill)
        self.assertIn("iter-1/authoring-<area>.md", self.skill)
        self.assertIn("iter-1/impact-analyst-<area>.json", self.skill)
        self.assertIn("ONE grouped clarification-ledger ask", self.skill)
        self.assertIn("acs.py analysis plan --areas", self.skill)

    def test_survey_lanes_are_joined_by_the_controller(self):
        self.assertIn("`record-survey` joins every lane's notes into "
                      "`iter-1/authoring.md`", self.skill)
        self.assertIn("`record-synthesis` joins the synthesis last", self.skill)
        self.assertNotIn("notes merge --out", self.skill)

    def test_judge_slice_table_covers_all_seven_dimensions_once(self):
        owned = []
        for sid, dims in JUDGE_SLICES.items():
            row = re.search(r"\| `%s` \| ([^|]+) \|" % sid, read(SKILL_PATH))
            self.assertIsNotNone(row, sid)
            numbers = tuple(int(n) for n in re.findall(r"\b(\d) `", row.group(1)))
            self.assertEqual(numbers, dims)
            owned += numbers
        self.assertEqual(sorted(owned), list(range(1, 8)))
        self.assertIn('<constraint name="dimensions">', self.skill)

    def test_judge_slices_are_joined_into_the_one_report(self):
        self.assertIn("`record-review` joins them, in the table's order, into "
                      "`iter-<n>/impact-reviewer.md`", self.skill)
        self.assertIn("iter-<n>/impact-reviewer-<slice>.md", self.skill)
        from acs_lib import analysis_loop as L
        self.assertEqual([sid for sid, _d in L.JUDGE_SLICES], list(JUDGE_SLICES))
        for sid, dims in L.JUDGE_SLICES:
            self.assertEqual(tuple(n for n, _name in dims), JUDGE_SLICES[sid])
            self.assertTrue(L.review_report_path("/r", 2, sid).endswith(
                "iter-2/impact-reviewer-%s.md" % sid))

    def test_sliced_pass_rule(self):
        """The rule is stated once, and DERIVED by record-review; the
        coordinator hands it no verdict."""
        self.assertIn("the iteration passes only if EVERY slice returned "
                      '`status="completed"` with zero blocking findings', self.skill)
        self.assertIn("never \"pass with a missing slice\"", self.skill)
        self.assertIn("the previous iteration's blocking findings, verbatim", self.skill)
        self.assertIn("ends the run `stalled`", self.skill)
        self.assertIn("never conclude a pass yourself", self.skill)

    def test_resume_reruns_only_missing_agents(self):
        self.assertIn("Re-run ONLY the agents whose evidence is missing", self.contract)
        self.assertIn("is never re-run", self.contract)

    def test_the_agents_know_how_to_run_as_a_slice(self):
        self.assertIn("## When you are one survey slice", self.analyst)
        self.assertIn("steps/analyze-requirements/iter-1/authoring-<area>.md",
                      self.analyst)
        self.assertIn("steps/analyze-requirements/iter-1/authoring-<area>.md",
                      norm(agent("impact-analyst")))
        self.assertIn('<result skill="analyze-requirements" phase="impact-analyst" slice=',
                      norm(agent("impact-analyst")))
        self.assertIn("Do NOT write the draft.", self.analyst)
        self.assertIn('<result skill="analyze-requirements" phase="analyst" slice=',
                      self.analyst)
        self.assertIn("## When you are one slice", self.reviewer)
        self.assertIn("Grounding policing always applies", self.reviewer)
        self.assertIn(
            "steps/analyze-requirements/iter-<n>/impact-reviewer-<slice>.md",
            self.reviewer)
        self.assertIn('<result skill="analyze-requirements" '
                      'phase="impact-reviewer" slice=', self.reviewer)

    def test_a_synthesis_pass_reconciles_the_survey_slices(self):
        """A join is not a synthesis: contradictions between area slices are
        resolved with evidence under `## Synthesis`, or raised as questions for
        the user -- by a dedicated synthesis pass, not by the draft pass."""
        self.assertIn("is a join, not a synthesis: this run MUST reconcile the "
                      "lanes before anything is asked.", self.skill)
        self.assertIn('the ONE synthesis analyst the action names (`slice="synthesis"`, '
                      '`<constraint name="pass">synthesis</constraint>`)', self.skill)
        self.assertIn("under a `## Synthesis` section of the notes", self.skill)
        self.assertIn("never silently picks one", self.skill)
        self.assertIn("de-duplicates the lanes' `## Questions for the user` into "
                      "ONE list", self.skill)
        self.assertIn("the draft pass consumes these reconciled notes — it does "
                      "not reconcile slices itself", self.skill)
        self.assertIn("## When you run the synthesis pass", self.analyst)
        self.assertIn("Write a `## Synthesis` section to "
                      "`iter-1/authoring-synthesis.md`", self.analyst)
        self.assertIn("Never silently pick one slice's claim", self.analyst)
        self.assertIn("a group-(a) question in your `## Questions for the user` "
                      "when no source does", self.analyst)
        self.assertIn("Never write the merged `iter-1/authoring.md`", self.analyst)

    def test_every_survey_is_reconciled(self):
        """ADR-0114: the requirements lane always runs beside at least one
        impact lane, so the controller always hands out `synthesize`."""
        self.assertIn("A ticket inside one area declares none, and gets one impact "
                      "lane over the whole repository.", self.skill)
        self.assertIn("every survey has at least two lanes and is always reconciled "
                      "by a synthesis pass", self.skill)

    def test_the_impact_reviewer_judges_the_synthesis(self):
        self.assertIn("judge that the notes' `## Synthesis` is honest", self.reviewer)
        self.assertIn("silently follows one slice's claim over another's is a "
                      "blocking finding", self.reviewer)

    def test_judge_slice_findings_are_de_duplicated(self):
        self.assertIn("drops exact duplicates (same dimension, file and text) under "
                      "a `## De-duplicated findings` section", self.skill)

    def test_a_single_writer_has_no_integration_pass(self):
        self.assertIn("with one writer there is no integration pass to run", self.skill)

    def test_each_checker_runs_in_exactly_one_judge_slice(self):
        self.assertIn("`front_matter_check.py` and `structure_lint.py` belong "
                      "to `form`", self.reviewer)


def _pos(body, needle):
    index = body.find(needle)
    assert index >= 0, "not found: %r" % needle
    return index


class TestThreeStages(unittest.TestCase):
    """2026-09-27: the skill checks the codebase for impacts, clarifies with
    the user, and stores the analysis in docs for reuse -- three stages, in
    that order, and the SKILL.md reads that way."""

    STAGES = ("## Stage 1 — Impact: survey the codebase",
              "## Stage 2 — Clarify: make the requirements clear with the user",
              "## Stage 3 — Store: write, review and publish the analysis for reuse")

    @classmethod
    def setUpClass(cls):
        cls.raw = read(SKILL_PATH)
        cls.skill = norm(cls.raw)
        cls.analyst = norm(agent("analyst"))

    def test_an_overview_near_the_top_names_the_three_stages_in_order(self):
        overview = _pos(self.raw, "## Three stages")
        self.assertLess(overview, _pos(self.raw, "## Start"))
        for label in ("**1 — Impact: survey the codebase**",
                      "**2 — Clarify: make the requirements clear with the user**",
                      "**3 — Store: write, review and publish the analysis for reuse**"):
            self.assertGreater(_pos(self.raw, label), overview)
        self.assertIn("in this order — each finishes before the next starts",
                      self.skill)

    def test_the_stage_sections_appear_in_order(self):
        positions = [_pos(self.raw, "\n%s\n" % heading) for heading in self.STAGES]
        self.assertEqual(positions, sorted(positions))
        # Publishing and the draft are Stage 3's; the ask is Stage 2's.
        self.assertGreater(_pos(self.raw, "### Phase: publish — the controller"),
                           positions[2])
        self.assertGreater(_pos(self.raw, "### Phase: analyst draft pass"),
                           positions[2])
        self.assertGreater(_pos(self.raw, "**Clarification ledger first.**"),
                           positions[1])

    def test_the_survey_pass_is_separate_from_the_draft_pass(self):
        self.assertIn('`<constraint name="pass">requirements</constraint>`', self.skill)
        self.assertIn('`<constraint name="pass">draft</constraint>`', self.skill)
        self.assertIn("No lane writes the draft.", self.skill)
        self.assertIn("The survey never writes the draft and the draft pass never "
                      "re-surveys", self.skill)
        self.assertIn("## Which pass you run", self.analyst)
        self.assertIn("Run ONLY the pass your task names: a requirements or "
                      "synthesis pass never writes the draft; a draft pass never "
                      "re-surveys.", self.analyst)
        for row in ("| `requirements` |", "| `synthesis` |", "| `draft` |"):
            self.assertIn(row, agent("analyst"))

    def test_each_pass_has_its_own_report_and_snapshot(self):
        """The requirements lane, the synthesis and the draft all run on
        iteration 1 as `analyst`; with the same slice they would share a
        SubagentStop snapshot. The controller names every file -- through the
        hook's own path function -- so the names cannot collide."""
        from acs_lib import analysis_loop as L
        snaps = {L.snapshot_path("/r", 1, "analyst", "requirements"),
                 L.snapshot_path("/r", 1, "analyst", "synthesis"),
                 L.snapshot_path("/r", 1, "analyst"),
                 L.snapshot_path("/r", 1, "impact-analyst", "repo")}
        self.assertEqual(len(snaps), 4)
        self.assertIn("requirements", L.RESERVED_SLICES)
        self.assertIn("synthesis", L.RESERVED_SLICES)
        for name in ("iter-1/analyst-requirements.json", "iter-1/analyst-synthesis.json",
                     "iter-<n>/analyst.json"):
            self.assertIn(name, self.analyst)
        self.assertIn("Use the paths it prints; never derive them yourself.", self.skill)

    def test_the_survey_starts_from_the_published_analysis(self):
        self.assertIn("Stage 1's survey starts from it (reuse — see Stage 1)",
                      self.skill)
        self.assertIn("7. `<previous_analysis>` when `artifacts[\"analysis.md\"]` "
                      "exists", self.skill)
        for body in (self.skill, self.analyst):
            self.assertIn("## Changes since the last analysis", body)
            self.assertIn("still true / changed / gone", body)
        self.assertIn("carries forward its answered `C-n` entries", self.skill)
        self.assertIn("### Reuse — when a previous analysis exists", self.analyst)
        self.assertIn("re-record it verbatim with `clarify.py add … --answer`",
                      self.skill)

    def test_the_survey_ends_with_four_groups_of_questions(self):
        for body in (self.skill, self.analyst):
            self.assertIn("## Questions for the user", body)
            for group in ("(a) Open questions", "(b) Conventional defaults",
                          "(c) Proposed refined acceptance criteria",
                          "(d) A needs_design recommendation"
                          if body is self.skill else "(d) needs_design recommendation"):
                self.assertIn(group, body)
            self.assertIn("Assumed: <default> — confirm or correct", body)
        self.assertIn("Researchable facts are never questions", self.skill)

    def test_the_synthesis_runs_before_the_ask(self):
        synthesis = _pos(self.raw, 'the ONE synthesis analyst the action names')
        self.assertLess(synthesis, _pos(self.raw, "\n%s\n" % self.STAGES[1]))

    def test_every_remaining_question_goes_in_one_grouped_ask(self):
        self.assertIn("**Otherwise ask EVERY remaining question, from all four "
                      "groups, in ONE grouped interaction** — a single "
                      "AskUserQuestion", self.skill)

    def test_defaults_are_confirmed_when_the_user_is_reachable(self):
        self.assertIn("Conventional defaults (b) are asked as confirmations",
                      self.skill)
        self.assertIn("When the user IS reachable, the same defaults are asked — "
                      "as confirmations, in the one grouped ask — never silently "
                      "assumed", self.skill)
        # The assumption arm is scoped to an unreachable user.
        unreachable = _pos(self.raw, "### When the user is not reachable")
        self.assertGreater(
            _pos(self.raw, "**A question with a conventional default is an "
                           "assumption, not a blocker.**"), unreachable)
        self.assertNotIn("record the default as an assumption (`--source "
                         "assumption --rationale \"...\"`), state it in "
                         "`## Assumptions`, propose the matching criterion rewrite "
                         "in `## Refined acceptance criteria`, and keep "
                         "`ready_for_planning: true`. The 2026-09-15",
                         self.skill[:self.skill.find("### When the user is not reachable")])

    def test_confirmed_requirements_are_written_into_the_ticket(self):
        self.assertIn("### Confirmed requirements go into the ticket", self.raw)
        self.assertIn("so the ticket itself carries the clarified requirements "
                      "every later skill plans from", self.skill)
        self.assertIn("send the WHOLE confirmed criteria list", self.skill)
        self.assertIn("A rejected proposal is recorded (its answer says so) and "
                      "NOT applied.", self.skill)
        section = self.raw[_pos(self.raw, "### Confirmed requirements go into the ticket"):
                           _pos(self.raw, "### When the user is not reachable")]
        self.assertIn('acs.py" ticket save --ticket <id> --from -', section)
        self.assertIn('{"needs_design": true}', section)

    def test_at_most_one_follow_up_round(self):
        self.assertIn("**One follow-up round, at most.**", self.skill)
        self.assertIn("in at most ONE more grouped AskUserQuestion", self.skill)
        self.assertIn("Anything still open after that is a blocker: "
                      "`references/not-ready-for-planning.md`", self.skill)
        not_ready = norm(read(os.path.join(SKILL_REFERENCES,
                                           "not-ready-for-planning.md")))
        self.assertIn("still open after the grouped ask and its ONE follow-up round",
                      not_ready)

    def test_stage_two_is_skipped_when_nothing_is_open(self):
        self.assertIn("Stage 2 is skipped; say so in the report", self.skill)
        self.assertIn("Stage 2 skipped", self.skill)

    def test_the_draft_is_written_from_the_answers(self):
        self.assertIn("`## Questions` lists every `C-n` with its answer or status",
                      self.skill)
        self.assertIn("`## Refined acceptance criteria` states which criteria "
                      "were confirmed into the ticket", self.skill)
        self.assertIn("`## Assumptions` holds only what the user did not answer",
                      self.skill)
        self.assertIn("`confirmed into the ticket (C-n)`", self.analyst)
        self.assertIn("Never present an unconfirmed rewrite as applied.",
                      self.analyst)

    def test_a_reviewer_question_goes_back_through_stage_two(self):
        self.assertIn("A reviewer finding that is really a new question for the "
                      "user — or a draft pass that returns `needs_input` — goes "
                      "through Stage 2 again (ledger first, then one grouped ask)",
                      self.skill)

    def test_the_published_file_is_the_reusable_record(self):
        self.assertIn("**The published file is the reusable record.**", self.skill)
        for reader in ("/acs:create-impl-plan", "/acs:create-api-contract",
                       "/acs:create-test-docs"):
            self.assertIn(reader, self.skill[_pos(self.skill,
                          "**The published file is the reusable record.**"):])
        self.assertIn("what the next run of this skill starts from", self.skill)
        self.assertIn("the partition fallback, for the no-checkout case only",
                      self.skill)

    def test_resume_asks_the_controller_where_it_is(self):
        """ADR-0114: the loop's position is loop.json, written from the
        artifacts -- the resume no longer reconstructs the stage from files."""
        resume = norm(read(os.path.join(SKILL_REFERENCES, "resume.md")))
        self.assertIn('acs.py" analysis next', resume)
        self.assertIn("You do NOT work out which stage the prior run reached", resume)
        for action in ("`plan`", "`clarify`", "`publish`", "`completed` / `failed`"):
            self.assertIn(action, resume)


class TestReviewerQuestionCoverage(unittest.TestCase):
    """The impact reviewer's new check: nothing asked of the user is lost
    between the survey and the draft, and what the user confirmed is what the
    ticket now says."""

    @classmethod
    def setUpClass(cls):
        cls.reviewer = norm(agent("impact-reviewer"))
        cls.skill = norm(read(SKILL_PATH))

    def test_every_question_for_the_user_is_accounted_for(self):
        self.assertIn("**Questions and ticket coverage:** every item of the "
                      "notes' `## Questions for the user`", self.reviewer)
        self.assertIn("was either answered in the ledger or is carried in "
                      "`## Questions` as an open or assumed `C-n` entry",
                      self.reviewer)

    def test_confirmed_criteria_match_the_ticket(self):
        self.assertIn("matches the ticket's `acceptance_criteria` as the ticket "
                      "file now reads", self.reviewer)
        self.assertIn("a confirmed criterion the ticket does not carry, or "
                      "carries differently, is a finding", self.reviewer)

    def test_the_check_sits_in_the_completeness_dimension_of_the_surface_slice(self):
        dim2 = agent("impact-reviewer").split("2. `completeness`", 1)[1].split(
            "3. `api-surface`", 1)[0]
        self.assertIn("Questions and ticket coverage", dim2)
        self.assertIn("the questions/ticket coverage check", self.skill)
        self.assertIn("the clarification ledger", self.reviewer)


if __name__ == "__main__":
    unittest.main()
