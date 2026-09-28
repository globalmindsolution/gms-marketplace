"""MAR-143 spec 01 — /acs:create-requirements skill scaffold, triad, hooks,
registration (AC-1, AC-6, AC-7 partial).

Registers the new producer skill in `acs_lib/_common.py` (`PRODUCT_SKILLS`,
`PRODUCT_TICKET_TITLES`, a standalone `gate_create_requirements`, `GATES`),
proves the coordinator + triad + hooks exist on disk, and pins the
count-bump doc-set (`c4-container.md`/`c4-component.md`) to the post-registration
totals (15th HOOKED skill: 24 skills / 45 agent files (39 reachable) / 15 pre
+ 15 post hooks / twelve triad-keeping skills / 12 active triads (36 agents
in triads)). Mirrors `test_setup_principles_path.py`'s
`Mar117PrinciplesRegistryCase` registry-case pattern.

Stdlib-only (os, re, sys, unittest). Run:
  python3 -m unittest tests.acs.test_mar143_create_requirements_skill -v
"""

import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
HOOKS_DIR = os.path.join(PLUGIN, "hooks", "scripts")
SKILL_PATH = os.path.join(PLUGIN, "skills", "create-requirements", "SKILL.md")
sys.path.insert(0, HOOKS_DIR)

import acs_lib  # noqa: E402


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def flat(text):
    return " ".join(text.split())


class Mar143RegistryCase(unittest.TestCase):
    """AC-1: create-requirements is registered in PRODUCT_SKILLS and
    PRODUCT_TICKET_TITLES, and consequently joins the derived HOOKED_SKILLS."""

    def test_create_requirements_in_product_skills(self):
        self.assertIn(
            "create-requirements", acs_lib.PRODUCT_SKILLS,
            msg="'create-requirements' must be registered in PRODUCT_SKILLS (AC-1)",
        )

    def test_create_requirements_in_product_ticket_titles(self):
        self.assertEqual(
            acs_lib.PRODUCT_TICKET_TITLES.get("create-requirements"),
            "Product requirements doc set",
            msg="PRODUCT_TICKET_TITLES['create-requirements'] must equal "
                "'Product requirements doc set' (AC-1)",
        )

    def test_create_requirements_in_hooked_skills(self):
        self.assertIn(
            "create-requirements", acs_lib.HOOKED_SKILLS,
            msg="'create-requirements' must join HOOKED_SKILLS via the derived "
                "PRODUCT_SKILLS + WORKFLOW_SKILLS expression (AC-1)",
        )


class Mar143GateCase(unittest.TestCase):
    """AC-6: `/acs:create-requirements` is NOT architecture-gated --
    architecture-awareness is an authoring BEHAVIOR, not a hard gate
    (design.md 521-525).

    There is one gate now (`gate_outcome`), so "the gate is standalone" is no
    longer a property of a function: it is the absence of this skill from the
    hook's gate tables, and the absence of a required run artifact from its own
    declaration. Both are data, which is what makes them checkable. ADR-0102
    removed the hook's document gates (`ARCHITECTURE_GATED`, `PRD_GATED`)
    outright; a skill that needs a document now refuses at its own Start, and
    this skill's Start refuses on neither.
    """

    def test_it_is_a_hooked_skill(self):
        self.assertIn("create-requirements", acs_lib.HOOKED_SKILLS)

    def test_it_is_not_architecture_gated(self):
        from acs_lib import gates
        # The hook's document gates stay gone (ADR-0102): SUBJECT_GATES is the
        # one table left, and it gates ticket state, not this skill.
        self.assertFalse(hasattr(gates, "ARCHITECTURE_GATED"))
        self.assertFalse(hasattr(gates, "PRD_GATED"))
        self.assertNotIn("create-requirements", gates.SUBJECT_GATES)
        # Nor did the refusal move into this skill: the architecture
        # precondition belongs to the project and doc-set skills (AC-6).
        body = flat(read(SKILL_PATH))
        self.assertNotIn("run /acs:create-architecture first", body)
        self.assertNotIn("run /acs:create-prd first", body)

    def test_it_requires_no_run_artifact_of_its_own(self):
        """A product skill is never a step of `ship` (2.4), so it has no run
        artifact to read -- it reads the repo's documents, and judges their
        absence itself rather than being refused for it. Each skill is
        independent: there is no per-skill manifest declaring what it reads,
        and it is nobody's leg."""
        skill_dir = os.path.dirname(SKILL_PATH)
        self.assertFalse(os.path.exists(os.path.join(skill_dir, "acs.yaml")))
        self.assertNotIn("create-requirements", acs_lib.SKILL_LEGS)
        body = read(SKILL_PATH)
        for token in ("acs.yaml", "reads.required", "leg_of"):
            self.assertNotIn(token, body)


class Mar143FilesExistCase(unittest.TestCase):
    """AC-1: the coordinator, its three agents (surveyor, author, reviewer),
    and hooks exist on disk at the expected paths."""

    def test_skill_md_exists(self):
        self.assertTrue(os.path.isfile(SKILL_PATH), SKILL_PATH)

    def test_agents_exist(self):
        for role in ("surveyor", "author", "reviewer"):
            path = os.path.join(PLUGIN, "agents", "create-requirements-%s.md" % role)
            self.assertTrue(os.path.isfile(path), path)

    def test_hooks_exist(self):
        for name in ("pre-create-requirements.py", "post-create-requirements.py"):
            path = os.path.join(HOOKS_DIR, name)
            self.assertTrue(os.path.isfile(path), path)

    def test_hooks_delegate_to_acs_lib_run_pre_post(self):
        pre = read(os.path.join(HOOKS_DIR, "pre-create-requirements.py"))
        post = read(os.path.join(HOOKS_DIR, "post-create-requirements.py"))
        self.assertIn("run_pre", pre)
        self.assertIn('"create-requirements"', pre)
        self.assertIn("run_post", post)
        self.assertIn('"create-requirements"', post)


class Mar143CountBumpCase(unittest.TestCase):
    """AC-1, AC-7(partial): registering the 15th HOOKED skill flipped the
    architecture doc-set counts in lockstep across c4-container.md and
    c4-component.md, consistent with HOOKED_SKILLS length 15 at MAR-143 time.

    MAR-156 deletes create-spec outright (HOOKED_SKILLS 15 -> 14): the
    "bumped" (MAR-143-era) and "stale" (pre-MAR-143) literal sets below swap
    roles -- MAR-143's own counts are now the stale ones, MAR-156's are
    current. The class keeps its historical name; only the counts move."""

    def _c4_container(self):
        return read(os.path.join(REPO_ROOT, "docs", "architecture", "hld", "c4-container.md"))

    def _c4_component(self):
        return read(os.path.join(REPO_ROOT, "docs", "architecture", "hld", "c4-component.md"))

    def test_hooked_skills_count_matches_the_registry(self):
        # 15 at MAR-156/MAR-160 time; the skills-independence refactor hooked
        # the five Build/Test skills, and the v0.5.0 redesign added
        # `review-code` and moved `run-e2e-tests` in -- it is a step of
        # ship.yaml with its own pre/post pair, and the "not really a pipeline
        # skill in its default mode" framing is gone (§3.11).
        self.assertEqual(len(acs_lib.HOOKED_SKILLS), 19)
        for added in ("review-code", "run-e2e-tests"):
            self.assertIn(added, acs_lib.HOOKED_SKILLS)

    def test_c4_container_bumped_counts_present(self):
        body = self._c4_container()
        # Derived, not pinned: a new skill directory moves the diagram
        # by itself rather than waiting for someone to notice.
        shipped = len([n for n in os.listdir(
            os.path.join(REPO_ROOT, "plugins", "acs", "skills"))
            if os.path.isdir(os.path.join(
                REPO_ROOT, "plugins", "acs", "skills", n))])
        agents = len([n for n in os.listdir(
            os.path.join(REPO_ROOT, "plugins", "acs", "agents")) if n.endswith(".md")])
        hooks_dir = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
        pre = len([n for n in os.listdir(hooks_dir) if n.startswith("pre-")])
        post = len([n for n in os.listdir(hooks_dir) if n.startswith("post-")])
        self.assertIn("%d x SKILL.md" % shipped, body)
        self.assertIn("%d x agent .md (all reachable)" % agents, body)
        self.assertIn("twelve authoring skills", body)
        self.assertIn("create-requirements", body)
        self.assertIn("dispatch + %d pre + %d post hooks" % (pre, post), body)

    def test_c4_container_stale_counts_absent(self):
        body = self._c4_container()
        for stale in (
            "23 x SKILL.md", "42 x agent .md (36 reachable)",
            "eleven triad-keeping skills", "dispatch + 14 pre + 14 post hooks",
        ):
            self.assertNotIn(stale, body, "stale form %r still in c4-container.md" % stale)

    def test_c4_component_bumped_counts_present(self):
        body = self._c4_component()
        self.assertIn("twelve authoring skills", body)
        self.assertIn("— **29 agents**", body)
        self.assertIn("32 agent files, all reachable", body)
        self.assertIn("create-requirements", body)

    def test_c4_component_stale_counts_absent(self):
        body = self._c4_component()
        for stale in (
            "eleven triad-keeping skills",
            "11 active triads (33 agents in triads)",
            "36 reachable agents",
        ):
            self.assertNotIn(stale, body, "stale form %r still in c4-component.md" % stale)


class Mar143CoordinatorContractCase(unittest.TestCase):
    """AC-1, AC-6: the coordinator recognizes all three modes, elicits
    greenfield interactively (updated for the landed greenfield mode), and
    threads the located write target to its agents as task constraints (found
    in the repo, else the `docs/requirements/` convention — ADR-0102; never a
    path read out of settings)."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)

    def test_declares_all_three_modes(self):
        for mode in ("brownfield", "greenfield", "amend"):
            self.assertIn(mode, self.body, "SKILL.md must name mode %r" % mode)

    def test_greenfield_elicits_not_deferred(self):
        # Greenfield is now a real elicitation mode, not a deferral.
        self.assertRegex(
            self.body, r"(?is)greenfield.{0,600}elicit",
            msg="the coordinator must state greenfield ELICITS requirements "
                "from the user (a real mode), not silently fall through to "
                "brownfield",
        )
        self.assertNotRegex(
            self.body, r"(?i)greenfield[\s\S]{0,600}MAR-144",
            msg="the old greenfield-deferred-to-MAR-144 language must be gone",
        )

    def test_g36_required_sections_constraint_declared(self):
        self.assertIn("required_sections", self.body)

    def test_g36_audience_style_profile_declared(self):
        self.assertIn("engineers (behavioral-contract prose)", self.body)

    def test_threads_located_requirements_dirs(self):
        body = flat(self.body)
        for name, default in (
            ("requirements_dir", "docs/requirements"),
            ("functional_dir", "docs/requirements/functional"),
            ("non_functional_dir", "docs/requirements/non-functional"),
        ):
            self.assertIn(
                '<constraint name="%s">%s</constraint>' % (name, default), body)
        self.assertIn(
            "Not found → `<requirements_dir>` = `docs/requirements`", body)
        self.assertNotIn("requirements_path", body)
        self.assertNotIn("requirements_layout", body)

    def test_ships_own_docs_only_pr(self):
        self.assertIn("gh pr create", self.body)
        self.assertIn("pr-conventions.py", self.body)

    def test_allocate_default_title(self):
        self.assertIn("Product requirements doc set", self.body)

    def test_result_document_states_keys(self):
        self.assertIn('"requirements"', self.body)
        self.assertIn('"pr"', self.body)


AGENTS_DIR = os.path.join(PLUGIN, "agents")


def slice_table(body, first_id):
    rows = {}
    for line in body.splitlines():
        m = re.match(r"^\| `([a-z-]+)` \| ([^|]+) \| (.+) \|$", line)
        if m:
            rows[m.group(1)] = ([int(n) for n in re.findall(r"(?:^|, )(\d+) ", m.group(2))],
                                m.group(3))
    assert first_id in rows, "slice table with %r row not found" % first_id
    return rows


class ParallelFanOutCase(unittest.TestCase):
    """Every phase fans out: surveyor slices over disjoint repo areas, one
    author per area file from iteration 1 plus an integration pass on the
    seams, reviewer slices over disjoint dimensions — each joined by
    `acs.py notes merge`, never by the coordinator merging prose."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.flat = flat(cls.body)

    def test_fan_out_spawns_in_one_message_and_joins_deterministically(self):
        self.assertIn("### Fan-out — slices, the join, the cap", self.body)
        self.assertIn("spawn N instances of the SAME agent in ONE message", self.flat)
        self.assertIn('slice="<id>"', self.body)
        self.assertIn("iter-<n>/<role>-<id>-message.xml", self.body)
        self.assertIn('hooks/scripts/acs.py" notes merge', self.body)
        self.assertIn("never prose-merging by you", self.flat)
        self.assertIn("`max_parallel = 4`", self.body)
        self.assertIn("beyond the cap, run the slices in waves of 4", self.flat)

    def test_survey_slices_partition_and_one_grouped_ask(self):
        self.assertIn("#### Survey slices — brownfield/amend over disjoint repo areas", self.body)
        self.assertIn("**two or more disjoint top-level areas**", self.flat)
        self.assertIn("Greenfield never slices", self.flat)
        self.assertIn("Slice `lead` owns", self.flat)
        self.assertIn("no path belongs to two slices", self.flat)
        self.assertIn("--out <partition>/steps/create-requirements/iter-1/authoring.md", self.flat)
        self.assertIn("ONE grouped clarification-ledger ask", self.flat)

    def test_author_slices_are_the_default_with_a_disjoint_file_partition(self):
        self.assertIn("#### Author slices — one author per area file, the default from iteration 1", self.body)
        self.assertIn("A slice owns exactly one area file of the confirmed outline", self.flat)
        self.assertIn("`fn-<basename>`", self.body)
        self.assertIn("`nfr-<basename>`", self.body)
        self.assertIn('<constraint name="files">', self.flat)
        self.assertIn("every path is listed in exactly one slice's `files`", self.flat)
        self.assertIn("no two slices can touch the same file", self.flat)
        self.assertIn("iter-<n>/author-<id>.json", self.body)
        self.assertIn("no `index.lock` contention", self.flat)

    def test_integration_pass_runs_before_the_reviewer_on_the_named_seams(self):
        self.assertIn('`slice="integration"`', self.body)
        self.assertIn("**Integration pass — after ALL slices finish, BEFORE the reviewer.**", self.flat)
        for seam in ("**shared glossary**", "**NFR cross-references**",
                     "**requirements README index**"):
            self.assertIn(seam, self.body)
        self.assertIn("never a slice's substance", self.flat)
        self.assertIn("iter-<n>/author-integration.json", self.body)
        self.assertIn("The pass is skipped when only one author ran", self.flat)
        integration = self.body.index("**Integration pass")
        review = self.body.index("### Review")
        slices = self.body.index("#### Author slices")
        self.assertLess(slices, integration)
        self.assertLess(integration, review)

    def test_survey_consumers_keep_a_synthesis_section(self):
        self.assertIn("**Synthesis of a sliced survey.**", self.flat)
        self.assertIn("`## Synthesis`", self.body)
        self.assertIn("never silently picks one side", self.flat)
        self.assertIn("the integration pass (below) checks that every slice used the same reconciled facts", self.flat)

    def test_reviewer_slices_cover_every_dimension_once_and_own_the_floor(self):
        rows = slice_table(self.body, "floor")
        self.assertEqual(sorted(rows), ["conformance", "evidence", "floor"])
        dims = sorted(d for ds, _ in rows.values() for d in ds)
        self.assertEqual(dims, list(range(1, 14)))
        owners = [sid for sid, (_, owns) in rows.items() if "structure_lint.py" in owns]
        self.assertEqual(owners, ["floor"])

    def test_reviewer_join_dedup_and_pass_rule(self):
        self.assertIn("--out <partition>/steps/create-requirements/iter-<n>/reviewer.md", self.flat)
        for sid in ("floor", "evidence", "conformance", "dedup"):
            self.assertIn("iter-<n>/reviewer-%s.md" % sid, self.body)
        self.assertIn("the same location and the same defect", self.flat)
        self.assertIn("keeping the one with the higher severity", self.flat)
        self.assertIn("the iteration passes only if EVERY slice returned "
                      "`status=\"completed\"` with zero blocking findings", self.flat)
        self.assertIn("never \"pass with a missing slice\"", self.flat)

    def test_resume_reruns_only_missing_slices(self):
        start = self.flat.index("## Resume & reconcile")
        window = self.flat[start:self.flat.index("## Reflection loop", start)]
        self.assertIn("re-run ONLY the slices whose own report is missing", window)
        self.assertIn("author-integration.json", window)

    def test_agents_carry_their_slice_sections(self):
        surveyor = flat(read(os.path.join(AGENTS_DIR, "create-requirements-surveyor.md")))
        self.assertIn("## When you are one slice", surveyor)
        self.assertIn("iter-1/authoring-<id>.md", surveyor)
        author = flat(read(os.path.join(AGENTS_DIR, "create-requirements-author.md")))
        self.assertIn("## When you are one slice", author)
        self.assertIn("## When you are the integration pass", author)
        self.assertIn("Write ONLY the paths in `files`", author)
        self.assertIn('phase="author" slice="integration"', author)
        self.assertIn("**Synthesis of a sliced survey**", author)
        reviewer = flat(read(os.path.join(AGENTS_DIR, "create-requirements-reviewer.md")))
        self.assertIn("## When you are one slice", reviewer)
        self.assertIn("Run ONLY the listed dimensions", reviewer)
        self.assertIn("iter-<n>/reviewer-<id>.md", reviewer)
        self.assertIn("**Judge the integrated result.**", reviewer)
        self.assertIn("police grounding", reviewer)


if __name__ == "__main__":
    unittest.main()
