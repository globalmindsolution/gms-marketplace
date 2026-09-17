"""/acs:create-impl-plan — the plan phase carved out of /acs:code.

The skills-independence refactor made the plan a skill of its own: it owns the
planner charter, the spec-authoring fold, plan approval, plan revocation and
the `acs.py filemap set` declaration, and it publishes the ticket's `plan.md`,
which `/acs:code`'s gate now REQUIRES. This module carries the plan-phase
prose contracts that used to be asserted against `skills/code/SKILL.md` and
`agents/code-planner.md` (test_lane_conditional_planning, test_code_loop_topology,
test_plan_artifact_naming, test_plan_approval, test_oversize_split_signal,
test_code_plan_doc_graph_gap), retargeted at their new home, plus the new
result-document `states` and the matching /acs:code carve-out.

Every assertion is by file plus whitespace-normalized substring/regex, never by
line number (line numbers drift as prose is revised) — the house style of
tests/acs/test_code_loop_topology.py. Stdlib only (os, re, unittest). Run:
  python3 -m unittest tests.acs.test_create_impl_plan -v
"""

import io
import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "src", "acs")
SKILLS_DIR = os.path.join(PLUGIN, "skills")
AGENTS_DIR = os.path.join(PLUGIN, "agents")
HOOKS_DIR = os.path.join(PLUGIN, "hooks", "scripts")

IMPL_PLAN_SKILL = os.path.join(SKILLS_DIR, "create-impl-plan", "SKILL.md")
#: `## Resume & reconcile` and `### Plan revocation` moved here under
#: progressive disclosure: both answer what a run does when the ticket already
#: carries a prior run or a superseded plan, and a first run reads neither.
IMPL_PLAN_RERUN_REF = os.path.join(
    SKILLS_DIR, "create-impl-plan", "references", "not-a-first-run.md")
IMPL_PLAN_PLANNER = os.path.join(AGENTS_DIR, "create-impl-plan-executor.md")  # the plan charter lives in the executor's survey since ADR-0092
IMPL_PLAN_EXECUTOR = os.path.join(AGENTS_DIR, "create-impl-plan-executor.md")
IMPL_PLAN_VERIFIER = os.path.join(AGENTS_DIR, "create-impl-plan-verifier.md")
IMPL_PLAN_AGENTS = [IMPL_PLAN_EXECUTOR, IMPL_PLAN_VERIFIER]

CODE_SKILL = os.path.join(SKILLS_DIR, "code", "SKILL.md")
CODE_PLANNER = os.path.join(AGENTS_DIR, "code-planner.md")
CODE_EXECUTOR = os.path.join(AGENTS_DIR, "code-executor.md")
CODE_VERIFIER = os.path.join(AGENTS_DIR, "code-verifier.md")

GATE_INPUTS = os.path.join(HOOKS_DIR, "acs_lib", "gate_inputs.py")
POST_HOOK = os.path.join(HOOKS_DIR, "post-create-impl-plan.py")

# The five fold sections, in the order structure_lint.py --ordered checks.
FOLD_SECTIONS = ("Scope", "Approach", "API/data changes", "Test plan",
                 "Out of scope")
# The six required plan headings, unchanged by the move.
PLAN_HEADINGS = ("## Spec analysis", "## Executor tasks & file map",
                 "## Test strategy", "## Documentation map", "## Risks",
                 "## Verifier checklist")
C9_STOP_REASON = "user chose to split; restructure required before implementation"

# .md-anchored only — iter-<n>-plan.xml (the message snapshot) must NOT match.
LEGACY_PLAN_LITERAL = re.compile(r"iter-(?:<n>|\{n\}|\*|\d+)-plan\.md")


def _code_contract():
    """/acs:code's contract: the dispatcher, the four delivery-path legs, and
    the references they share.

    ADR-0095 split one 750-line body this way. These assertions pin what the
    SKILL SAYS, never which of its files says it, so reading the concatenation
    keeps the pin honest while the layout stays free to change -- and a rule
    that genuinely vanishes still fails.
    """
    import glob as _glob
    base = os.path.join(PLUGIN, "skills")
    parts = []
    for name in ("code", "code-trivial", "code-small", "code-standard", "code-complex"):
        path = os.path.join(base, name, "SKILL.md")
        if os.path.isfile(path):
            with io.open(path, encoding="utf-8") as fh:
                parts.append(fh.read())
    for path in sorted(_glob.glob(os.path.join(base, "code", "references", "*.md"))):
        with io.open(path, encoding="utf-8") as fh:
            parts.append(fh.read())
    return "\n".join(parts)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def norm(body):
    """Collapse whitespace runs so markdown line-wrap can never break a
    phrase-spanning match."""
    return re.sub(r"\s+", " ", body)


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if m is None:
        raise AssertionError("file must open with a YAML frontmatter block")
    return m.group(1)


def slice_between(body, start_literal, end_literal):
    start = body.index(start_literal)
    end = body.index(end_literal, start)
    return body[start:end]


class SkillSurfaceTest(unittest.TestCase):
    """The skill and its triad exist in the house shape, and the plan phase's
    old home is gone."""

    def test_skill_frontmatter(self):
        fm = frontmatter(read(IMPL_PLAN_SKILL))
        self.assertRegex(fm, r"(?m)^name: create-impl-plan$")
        self.assertRegex(fm, r"(?m)^argument-hint: \"\[ticket-id\]\"$")
        self.assertRegex(fm, r"(?m)^disallowed-tools: Edit, NotebookEdit$")
        self.assertRegex(fm, r"(?m)^description: .+")

    def test_each_agent_exists_with_matching_name(self):
        for path in IMPL_PLAN_AGENTS:
            with self.subTest(agent=os.path.basename(path)):
                fm = frontmatter(read(path))
                expected = os.path.basename(path)[:-len(".md")]
                self.assertRegex(fm, r"(?m)^name: %s$" % re.escape(expected))
                self.assertIn("not for direct invocation", fm)

    def test_code_planner_is_retired(self):
        self.assertFalse(
            os.path.exists(CODE_PLANNER),
            "agents/code-planner.md moved to create-impl-plan-planner.md and "
            "must not survive alongside it")

    def test_skill_body_is_written(self):
        body = read(IMPL_PLAN_SKILL)
        self.assertNotIn("written in the next phase of the skills-independence "
                         "refactor", body,
                         "the placeholder body must be replaced by the real skill")

    def test_skill_starts_and_finishes_through_its_own_hooks(self):
        body = read(IMPL_PLAN_SKILL)
        self.assertIn("skill-start.py\" --skill create-impl-plan", body)
        self.assertIn("post-create-impl-plan.py", body)


class PlanPhaseContractTest(unittest.TestCase):
    """The plan artifact contract moved intact: six headings, the fold's five
    sections and lint literal, and the two mandatory verbatim clauses."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(IMPL_PLAN_SKILL)
        cls.norm = norm(cls.body)

    def test_six_plan_headings_named(self):
        for heading in PLAN_HEADINGS:
            self.assertIn(heading, self.body,
                          "create-impl-plan/SKILL.md must name %r" % heading)

    def test_five_fold_headings_and_lint_literal(self):
        for heading in FOLD_SECTIONS:
            self.assertIn(heading, self.body)
        self.assertIn(
            'structure_lint.py --sections "Scope; Approach; API/data '
            'changes; Test plan; Out of scope"', self.body)

    def test_mandatory_verbatim_clauses_survive(self):
        self.assertIn(
            "no separate /acs:create-spec invocation and no separate "
            "create-spec planner subagent", self.norm)
        self.assertIn(
            "every ticket.acceptance_criteria entry maps to at least one "
            "test the folded plan will write", self.norm)

    def test_fold_activating_condition_stays_lane_agnostic(self):
        self.assertIsNotNone(
            re.search(r"specs/.{0,40}(absent or empty|empty or absent)", self.body))
        self.assertNotRegex(
            self.body, r"(?i)TRIVIAL.{0,10}(or|/).{0,10}SMALL lanes? with no specs")

    def test_no_content_stub_rule(self):
        self.assertRegex(
            self.norm, r"(?i)never.{0,60}(empty|placeholder|see ticket)")

    def test_no_plan_section_survives(self):
        self.assertNotIn("### Plan (per iteration)", self.body)
        self.assertNotRegex(self.body, r"(?m)^### Plan \(once[^)]*\)$")
        self.assertRegex(self.body, r"(?m)^### Execute \(per iteration\) — survey, then author the plan draft$")

    def test_the_executor_surveys_on_iteration_one(self):
        self.assertRegex(self.norm, r"(?i)There is no plan phase")
        self.assertRegex(self.norm, r"(?i)iteration 1'?s executor surveys")
class PublishTest(unittest.TestCase):
    """`plan.md` is resolved through the artifacts resolver, written by the
    coordinator (never a guarded executor), and mirrored for plan approval."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(IMPL_PLAN_SKILL)
        cls.norm = norm(cls.body)

    def test_artifact_path_is_resolved_through_the_cli(self):
        self.assertIn("artifacts show --ticket", self.body)
        self.assertRegex(
            self.norm,
            r"(?i)docs_dir.{0,120}plan\.md|plan\.md.{0,120}docs_dir")
        self.assertIn("<partition>/plan.md", self.body,
                      "the opted-out (artifacts.tickets_path null) write "
                      "target must be named")

    def test_coordinator_is_the_only_writer_of_the_published_plan(self):
        section = slice_between(self.body, "### Publish", "### Plan approval")
        section_norm = norm(section)
        self.assertRegex(section_norm, r"(?i)coordinator.{0,80}never a subagent")
        self.assertRegex(section_norm, r"(?i)guard.{0,120}denies.{0,120}executor")
        self.assertRegex(section_norm, r"(?i)cop(y|ies)|\bcp\b")

    def test_approval_mirror_is_named_with_its_reason(self):
        self.assertIn("<partition>/phases/code/plan.md", self.body)
        self.assertRegex(
            self.norm,
            r"(?i)phases/code/plan\.md.{0,200}(mirror|plan-approval\.py)|"
            r"(mirror|plan-approval\.py).{0,200}phases/code/plan\.md")

    def test_published_deliverable_carries_no_legacy_iteration_literal(self):
        section = slice_between(self.body, "### Publish", "### Plan approval")
        self.assertEqual(
            LEGACY_PLAN_LITERAL.findall(section), [],
            "the published plan is plan.md — never an iteration-numbered file")

    def test_executor_writes_a_draft_not_the_docs_tree(self):
        body = read(IMPL_PLAN_EXECUTOR)
        self.assertIn("phases/create-impl-plan/plan.md", body)
        self.assertRegex(
            norm(body), r"(?i)never publish|coordinator alone|never.{0,60}docs tree")


class FileMapTest(unittest.TestCase):
    """The plan declares the executor file map /acs:code's guard enforces."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(IMPL_PLAN_SKILL)
        cls.norm = norm(cls.body)

    def test_skill_declares_the_map_for_code(self):
        self.assertIn("filemap set", self.body)
        self.assertRegex(self.norm, r"filemap set.{0,160}--skill code")
        self.assertRegex(
            self.norm,
            r"(?i)additive|declaring task 2 never erases task 1")

    def test_declaration_names_the_guard_it_arms(self):
        self.assertRegex(
            self.norm,
            r"(?i)an undeclared map means no enforcement at all")

    def test_code_still_redeclares_for_its_own_iterations(self):
        code_norm = norm(_code_contract())
        self.assertIn("filemap set", code_norm)
        self.assertRegex(
            code_norm,
            r"(?i)re-declare for the iteration before dispatching remediation")


class PlanApprovalContractTest(unittest.TestCase):
    """Plan approval moved AGAIN with ADR-0095, and for a structural reason:
    it binds per delivery path, and this skill produces the artifact the path
    is judged from, so no path exists while it runs. The call site is now the
    `code-standard` and `code-complex` legs; what this skill owes is the
    approval mirror and an explanation of where the call went."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(IMPL_PLAN_SKILL)

    def _section(self):
        return slice_between(self.body, "### Plan approval", "### Docs-only tickets")

    def test_subsection_sits_after_execute_and_before_docs_only(self):
        """The pin is where the approval note sits, not which sibling follows
        it: `### Plan revocation` used to, and has since moved into
        `references/not-a-first-run.md`, leaving docs-only as the next
        heading and the slice above as exactly the approval note."""
        plan_idx = self.body.index("### Execute (per iteration) — survey, then author the plan draft")
        approval_idx = self.body.index("### Plan approval")
        docs_only_idx = self.body.index("### Docs-only tickets")
        self.assertGreater(approval_idx, plan_idx)
        self.assertLess(approval_idx, docs_only_idx)
        self.assertNotIn("### Plan revocation", self.body)

    def test_subsection_says_which_paths_bind_and_where_the_call_went(self):
        section_norm = norm(self._section())
        self.assertRegex(section_norm, r"(?i)`standard` and `complex` delivery paths")
        self.assertRegex(section_norm, r"(?i)code-standard.{0,40}code-complex")
        self.assertRegex(section_norm, r"(?i)before any path exists")

    def test_the_subsection_does_not_run_the_command_itself(self):
        """Running it here would produce a verdict for a path that does not
        exist yet, and the review would then activate plan-conformance against
        it."""
        self.assertNotIn("python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/scripts/plan-approval.py",
                         self._section())

    def test_subsection_avoids_forbidden_literals(self):
        section = self._section()
        self.assertNotIn("create-spec", section)
        self.assertNotIn("hld/data-model.md", section)

    def test_script_is_the_sole_writer_of_the_record(self):
        # The prohibition travelled with the call site, to the deep legs.
        section_norm = norm(read(os.path.join(SKILLS_DIR, "code-standard", "SKILL.md")))
        found = False
        for m in re.finditer(re.escape("plan-approval.json"), section_norm):
            window = section_norm[max(0, m.start() - 250):m.end() + 250]
            if "Write" in window and ("never" in window.lower()
                                      or "only" in window.lower()):
                found = True
                break
        self.assertTrue(
            found,
            "no bounded window around plan-approval.json co-locates a "
            "Write-tool prohibition and never/only")

    def test_this_skill_records_plan_approved_false(self):
        """It is the honest value: approval is judged per path, and the path
        does not exist yet when this skill finishes."""
        self.assertRegex(norm(self.body),
                         r"(?i)`plan_approved`:\s*always `false` here")


class PlanRevocationTest(unittest.TestCase):
    """Revocation preserves the superseded plan; existing /acs:code verify
    citations stay resolvable."""

    def _section(self):
        # Revocation is the last section of the re-run reference, so the slice
        # runs to end of file.
        body = read(IMPL_PLAN_RERUN_REF)
        return norm(body[body.index("### Plan revocation"):])

    def test_revocation_copies_never_moves(self):
        section = self._section()
        self.assertRegex(section, r"(?i)byte-identical")
        self.assertRegex(section, r"(?i)\bcopy\b")
        self.assertRegex(section, r"(?i)never.{0,10}(?:a\s+)?(?:rename|move)")

    def test_revocation_preserves_citation_resolvability(self):
        section = self._section()
        self.assertIn("plan.md:", section)
        self.assertRegex(section, r"(?i)resolve[sd]?\s+unchanged")
        self.assertIn("plan-superseded-", section)

    def test_revocation_is_boundary_gated_and_recorded(self):
        section = self._section()
        self.assertIn("clarify.py", section)
        self.assertRegex(section, r"(?i)iteration or run boundary|run boundary")
        self.assertRegex(section, r"(?i)never\s+automatic|not\s+automatic")

    def test_superseded_copy_is_never_a_contract(self):
        self.assertRegex(
            self._section(),
            r"(?i)never.{0,60}(?:an?\s+)?approval input|"
            r"never.{0,60}conformance contract")

    def test_replan_entry_names_the_code_stop_reason(self):
        self.assertIn("plan_superseded", self._section())


class ResultDocumentStatesTest(unittest.TestCase):
    """The three states the post-hook documents are the three the skill
    writes: plan_path, plan_approved, file_map."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(IMPL_PLAN_SKILL)
        cls.post = read(POST_HOOK)

    def test_finish_example_carries_all_three_states(self):
        start = self.body.index('"states": {')
        example = self.body[start:start + 600]
        for key in ('"plan_path"', '"plan_approved"', '"file_map"'):
            self.assertIn(key, example,
                          "the Finish result.json example must carry %s" % key)

    def test_canonical_states_bullets_describe_each_key(self):
        section = slice_between(self.body, "Canonical `states` keys",
                                "2. Run the post-hook")
        for key in ("plan_path", "plan_approved", "file_map"):
            self.assertIn("`%s`" % key, section)

    def test_states_agree_with_the_post_hook_docstring(self):
        for key in ("plan_path", "plan_approved", "file_map"):
            self.assertIn(key, self.post)

    def test_no_verifier_passed_state(self):
        """/acs:code owns verifier_passed; nothing derives it for this skill."""
        self.assertNotIn('"verifier_passed"', self.body)


class OversizeSplitSignalTest(unittest.TestCase):
    """The plan-time oversize signal and its split-answer termination moved
    with the phase (ADR 0069)."""

    @classmethod
    def setUpClass(cls):
        body = read(IMPL_PLAN_PLANNER)
        cls.planner_body = body
        cls.item2 = slice_between(
            body, "2. **Executor decomposition with a file map.**",
            "3. **Test strategy per spec")
        cls.skill_body = read(IMPL_PLAN_SKILL)

    def test_rubric_numbers_present(self):
        for token in ("~4", "~400", "~7", "create-ticket/SKILL.md"):
            self.assertIn(token, self.item2)

    def test_surface_never_block_contract(self):
        self.assertIsNotNone(
            re.search(r"(?i)surface.{0,60}never block", norm(self.item2)),
            "planner item 2 must state the 'surface ... never block' contract")

    def test_plan_artifact_records_seams(self):
        self.assertIn("split seams", self.item2)
        self.assertIn("plan artifact", self.item2)
        self.assertIn("phases/create-impl-plan/plan.md", self.item2)

    def test_no_stop_or_halt_branch(self):
        self.assertNotRegex(self.item2, r"(?i)\bstop the run\b")
        self.assertNotRegex(self.item2, r"(?i)\bhalts? the run\b")

    def test_exactly_one_create_spec_provenance_line(self):
        lines = [ln for ln in self.planner_body.splitlines() if "create-spec" in ln]
        self.assertEqual(
            len(lines), 1,
            "create-impl-plan-planner.md must carry exactly one create-spec "
            "line (the pre-existing provenance note): %r" % lines)
        self.assertIn("migrated from the deleted create-spec-planner.md", lines[0])

    def _split_section(self):
        return slice_between(self.skill_body, "## User interaction",
                             "## Context pressure")

    def test_split_answer_termination_is_stated_in_full(self):
        section = self._split_section()
        section_norm = norm(section)
        self.assertIn('"failed"', section)
        self.assertIn("/acs:create-ticket split", section)
        self.assertIn("clarify.py add", section)
        self.assertIn(C9_STOP_REASON, section_norm)
        self.assertIsNotNone(
            re.search(r"(?i)accept one large PR.{0,200}continue planning",
                      section_norm))
        self.assertIsNotNone(
            re.search(r"(?i)summary.{0,200}restate", section_norm),
            "the split clause must state that <summary> restates the split "
            "instruction, not only <next-step>")
        self.assertIsNotNone(
            re.search(r"(?i)Finish steps.{0,300}(before|then).{0,120}handoff",
                      section_norm),
            "the mandatory Finish steps run before the handoff is returned")
        self.assertIsNotNone(
            re.search(r"(?i)handoff.{0,40}status.{0,80}attribute", section_norm))
        self.assertIn("No new XML element and no new status value", section_norm)


class DocGraphGapTest(unittest.TestCase):
    """The bounded ADR-0012 doc-graph-gap check (E1-E4) moved with item 4, and
    the skill keeps the mirroring pointer sentence."""

    EDGE_TARGET_DOCS = {
        "E1": ("hld/c4-component.md",),
        "E2": ("hld/data-model.md",),
        "E3": ("lld/flows/",),
        "E4": ("prd.md", "roadmap.md"),
    }

    @classmethod
    def setUpClass(cls):
        body = read(IMPL_PLAN_PLANNER)
        cls.item4 = slice_between(
            body, "4. **Documentation map — docs are part of the change.**",
            "5. **Risks.**")
        cls.item4_norm = norm(cls.item4)
        skill = read(IMPL_PLAN_SKILL)
        cls.bullet = slice_between(
            skill, "- The documentation map: whether any factual",
            "**Spec authoring fold")
        cls.bullet_norm = norm(cls.bullet)

    def test_all_four_edges_named_with_target_docs(self):
        for edge, targets in self.EDGE_TARGET_DOCS.items():
            with self.subTest(edge=edge):
                self.assertIn(edge, self.item4)
                for target in targets:
                    self.assertIn(target, self.item4)

    def test_problems_carrier_and_bound_stated(self):
        self.assertIn("`problems`", self.item4)
        self.assertRegex(self.item4_norm, r"(?i)touched-area only")

    def test_explicit_non_coverage_stated(self):
        self.assertIn("requirements_path", self.item4)
        self.assertIn("adr_path", self.item4)
        self.assertRegex(self.item4_norm, r"(?i)not\b.{0,60}covered")

    def test_silent_degradation_stated(self):
        self.assertRegex(
            self.item4_norm,
            r"(?i)no architecture doc set on disk.{0,200}"
            r"(no finding|never fails|never blocks)")

    def test_skill_pointer_names_the_planner_item_without_restating_it(self):
        self.assertIn("create-impl-plan-executor", self.bullet)
        self.assertRegex(self.bullet_norm, r"(?i)item 4")
        self.assertRegex(self.bullet_norm, r"(?i)bounded")
        self.assertRegex(self.bullet_norm, r"(?i)touched-area")
        self.assertRegex(self.bullet_norm, r"(?i)not the full")
        self.assertNotIn("E2", self.bullet)
        self.assertNotIn("hld/data-model.md", self.bullet)


class CodeStartsFromAnExistingPlanTest(unittest.TestCase):
    """The other half of the carve-out: /acs:code requires the plan, never
    authors it."""

    @classmethod
    def setUpClass(cls):
        cls.body = _code_contract()
        cls.norm = norm(cls.body)

    def test_plan_authoring_sections_are_gone(self):
        """The `code` contract never AUTHORS a plan. It may now RUN approval —
        the deep legs do, because approval binds per delivery path and the path
        does not exist while create-impl-plan runs (ADR-0095) — so what is
        pinned is the authoring, not the word "approval"."""
        for heading in ("### Plan (once", "### Plan revocation",
                        "### Plan artifact resolution"):
            self.assertNotIn(heading, self.body,
                             "%r belongs to create-impl-plan" % heading)
        self.assertNotIn("survey, then author the plan draft", self.body)

    def test_plan_input_resolution_replaces_them(self):
        """It lives in the shared protocol now (ADR-0095) -- every leg reads
        the plan the same way, so one copy is right."""
        self.assertIn("### Plan input resolution", self.body)
        self.assertIn("artifacts show --ticket", self.body)
        self.assertRegex(self.norm, r"(?i)never author or revise")
        self.assertIn("plan_superseded", self.body)

    def test_start_names_the_plan_input_gate_and_its_producer(self):
        self.assertIn("no plan.md found for", self.norm)
        self.assertIn("/acs:create-impl-plan", self.norm)

    def test_the_gate_refusal_wording_matches_the_gate(self):
        gate = read(GATE_INPUTS)
        self.assertIn("no %s found for %s", gate)
        self.assertIn("run /acs:%s %s first.", gate)

    def test_no_planner_subagent_on_any_delivery_path(self):
        self.assertNotIn("acs:code-planner", self.body)
        self.assertRegex(self.norm,
                         r"(?i)no plan\s+phase and no planner subagent")

    def test_plan_superseded_is_the_replan_stop_reason(self):
        self.assertIn("plan_superseded", self.body)
        self.assertRegex(self.norm, r"(?i)on_replan")

    def test_result_states_no_longer_carry_plan_approved(self):
        start = self.body.index('"states": {')
        example = self.body[start:start + 600]
        self.assertNotIn('"plan_approved"', example)

    def test_executor_writes_tests_from_test_cases(self):
        for label, body in (("code contract", self.body),
                            ("code-executor", read(CODE_EXECUTOR))):
            with self.subTest(source=label):
                body_norm = norm(body)
                self.assertIn("test-cases.md", body_norm)
                self.assertRegex(body_norm, r"(?i)TC-n")

    def test_verifier_checks_contract_conformance_and_cites_tc_ids(self):
        verifier_norm = norm(read(CODE_VERIFIER))
        self.assertRegex(
            verifier_norm,
            r"(?i)contract-conformance sub-check.{0,200}api-contract\.md")
        self.assertRegex(
            verifier_norm,
            r"(?i)test-case traceability sub-check.{0,300}TC-n")
        self.assertRegex(
            verifier_norm,
            r"(?i)matrix cites the .?TC-n.? ids")


if __name__ == "__main__":
    unittest.main()
class AnalysisProposalsDoNotBlockTest(unittest.TestCase):
    """analyze-ticket promises that with no user answer create-impl-plan
    plans against the ticket as written; the plan skill has to keep that
    promise rather than re-ask the open proposals (the 2026-09-14 PIPE-code
    diagnostic lost a run to a plan run that asked and had no one to answer)."""

    @classmethod
    def setUpClass(cls):
        cls.norm = norm(read(IMPL_PLAN_SKILL))
        cls.analyze = norm(read(os.path.join(SKILLS_DIR, "analyze-ticket", "SKILL.md")))

    def test_the_plan_skill_carries_open_proposals_instead_of_asking(self):
        self.assertIn("Entries the analysis left open are proposals, not blockers.", self.norm)
        self.assertRegex(self.norm, r"(?i)never re-ask them and never return `needs_input` for them")
        self.assertIn("`C-<n> open — planned as written`", self.norm)

    def test_the_grouped_question_rule_is_scoped_to_the_plans_own_questions(self):
        self.assertIn("When ≥2 of your own clarifications are open", self.norm)

    def test_the_two_skills_state_the_same_contract(self):
        self.assertRegex(self.analyze, r"(?i)`/acs:create-impl-plan` plans against the ticket as written")
        self.assertRegex(self.norm, r"(?i)plans? against the ticket(?:'s acceptance criteria)? as written")
