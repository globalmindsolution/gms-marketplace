"""MAR-120 spec 01 — /acs:create-architecture gains hld/project-structure.md.

Prose-contract tests pinning the producer-only change: the SKILL.md
Output-contract row, the planner/executor/verifier triad enumerations, the
two doc updates, the negative scope guard (no acs skill/agent added, no
hand-authored project-structure.md in this repo, no shipped template), and
the AC-5 additivity/re-run guard.

Stdlib-only (os, re, unittest), mirroring the bounded-window `section()`
technique from test_mar118_create_standards_skill.py and the durable-invariant
CHANGELOG pattern from test_mar118_docs_eval.py's ChangelogMar118EntryTest.

Run:  python3 -m unittest tests.acs.test_mar120_create_architecture_project_structure -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SKILLS = os.path.join(PLUGIN, "skills")
AGENTS = os.path.join(PLUGIN, "agents")
DOCS = os.path.join(REPO_ROOT, "docs")

SKILL_PATH = os.path.join(SKILLS, "create-architecture", "SKILL.md")
PLANNER_PATH = os.path.join(AGENTS, "create-architecture-planner.md")
EXECUTOR_PATH = os.path.join(AGENTS, "create-architecture-executor.md")
VERIFIER_PATH = os.path.join(AGENTS, "create-architecture-verifier.md")
SKILLS_MD_PATH = os.path.join(DOCS, "requirements", "functional", "skills.md")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def section(body, heading):
    """Return the text of a markdown section: from the line whose start is
    `heading` (matched at line-start) up to the next same-or-higher-level
    heading (or end of file)."""
    m = re.search(r"(?m)^" + re.escape(heading) + r".*$", body)
    if m is None:
        raise AssertionError("heading %r not found" % heading)
    start = m.start()
    level = len(heading) - len(heading.lstrip("#"))
    nxt = re.search(r"(?m)^#{1,%d} \S" % level, body[m.end():])
    end = m.end() + nxt.start() if nxt else len(body)
    return body[start:end]


def bullet(body, label):
    """Return the text of a top-level `- **<label>** ...` bullet, up to the
    next `- **...**` bullet (or end of file)."""
    m = re.search(r"(?m)^- \*\*" + re.escape(label) + r"\*\*.*$", body)
    if m is None:
        raise AssertionError("bullet %r not found" % label)
    start = m.start()
    nxt = re.search(r"(?m)^- \*\*", body[m.end():])
    end = m.end() + nxt.start() if nxt else len(body)
    return body[start:end]


def dimension(body, name):
    """Return the text of a numbered `N. **<name>** ...` dimension item, up
    to the next `N+1. **...**` item (or end of file)."""
    m = re.search(r"(?m)^\d+\.\s+\*\*" + re.escape(name) + r"\*\*.*$", body)
    if m is None:
        raise AssertionError("dimension %r not found" % name)
    start = m.start()
    nxt = re.search(r"(?m)^\d+\.\s+\*\*", body[m.end():])
    end = m.end() + nxt.start() if nxt else len(body)
    return body[start:end]


class SkillOutputContractRowTest(unittest.TestCase):
    """AC-1: SKILL.md Output-contract row names project-structure.md with
    flowchart, directory-tree, and the C4-derivation language, co-located on
    the same row."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.output = section(cls.body, "## Output contract")

    def test_row_present_and_carries_all_markers(self):
        m = re.search(r"(?m)^\|\s*`hld/project-structure\.md`.*$", self.output)
        self.assertIsNotNone(
            m, "no Output-contract row starting with `hld/project-structure.md`")
        row = m.group(0)
        for marker in ("flowchart", "directory-tree", "derived"):
            self.assertIn(marker, row, "row missing marker %r: %r" % (marker, row))

    def test_result_json_example_includes_project_structure(self):
        finish = section(self.body, "## Finish")
        self.assertIn("project-structure.md", finish)


class PlannerTargetDocSetTest(unittest.TestCase):
    """AC-4: planner's Target doc set names project-structure.md
    (flowchart/directory-tree/C4-derived); Verifier checklist covers it."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(PLANNER_PATH)
        cls.target = bullet(cls.body, "Target doc set")
        cls.checklist = bullet(cls.body, "Verifier checklist")

    def test_target_doc_set_names_project_structure_as_flowchart(self):
        self.assertIn("hld/project-structure.md", self.target)
        self.assertIn("flowchart", self.target)

    def test_target_doc_set_names_c4_derivation(self):
        self.assertIn("C4", self.target)

    def test_verifier_checklist_covers_project_structure(self):
        self.assertIn("project-structure.md", self.checklist)


class ExecutorDoingTheWorkTest(unittest.TestCase):
    """AC-2: executor's doc-set list names project-structure.md as a
    flowchart and states the C4 container/component derivation requirement."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(EXECUTOR_PATH)
        cls.doing = section(cls.body, "## Doing the work")

    def test_names_project_structure_as_flowchart(self):
        self.assertIn("hld/project-structure.md", self.doing)
        self.assertIn("flowchart", self.doing)

    def test_states_c4_derivation_requirement(self):
        self.assertTrue(
            "hld/c4-container.md" in self.doing and "hld/c4-component.md" in self.doing,
            "Doing the work section must name both hld/c4-container.md and "
            "hld/c4-component.md as the C4 traceability source")


class VerifierDimensionsTest(unittest.TestCase):
    """AC-3: verifier dimension-1 doc-set-completeness names
    project-structure.md; exactly one C4-traceability clause, in
    internal-consistency, not duplicated in hld-lld-consistency."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(VERIFIER_PATH)
        cls.dim1 = dimension(cls.body, "doc-set-completeness")
        cls.dim5 = dimension(cls.body, "internal-consistency")
        cls.dim7 = dimension(cls.body, "hld-lld-consistency")

    def test_dimension1_names_project_structure(self):
        self.assertIn("hld/project-structure.md", self.dim1)

    def test_c4_traceability_clause_in_internal_consistency(self):
        self.assertIn("project-structure", self.dim5)
        self.assertTrue(
            "c4-container" in self.dim5 or "c4-component" in self.dim5,
            "internal-consistency dimension must reference the C4 views by name")

    def test_c4_traceability_clause_not_duplicated_in_hld_lld_consistency(self):
        self.assertNotIn("project-structure", self.dim7)


class SkillsMdSectionTest(unittest.TestCase):
    """AC-6: docs/requirements/functional/skills.md's /create-architecture section names
    the new output."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILLS_MD_PATH)
        cls.sec = section(cls.body, "## `/create-architecture` (product-level)")

    def test_names_project_structure(self):
        self.assertIn("hld/project-structure.md", self.sec)


class ChangelogMar120EntryTest(unittest.TestCase):
    """AC-6: durable-invariant CHANGELOG entry — never pins the literal
    '[Unreleased]' or a dated version string as a fixed anchor (mirrors
    ChangelogMar118EntryTest)."""

    def _changelog(self):
        return read(os.path.join(PLUGIN, "CHANGELOG.md"))

    def test_changelog_mar120_entry_in_durable_section(self):
        body = self._changelog()
        spans = [m.start() for m in re.finditer(r"## \[[^\]]*\]", body)] + [len(body)]
        section_text = None
        for start, end in zip(spans, spans[1:]):
            candidate = body[start:end]
            if "(MAR-120)" in candidate:
                section_text = candidate
                break
        self.assertIsNotNone(
            section_text,
            "CHANGELOG.md must contain '(MAR-120)' inside a section span")
        heading = section_text[:section_text.index("\n")] if "\n" in section_text else section_text
        self.assertRegex(
            heading, r"## \[(Unreleased|\d+\.\d+\.\d+)\]",
            "the '(MAR-120)' entry must live under [Unreleased] or a dated "
            "semver release heading (release cuts legitimately graduate it)")
        self.assertIsNotNone(
            re.search(r"project-structure\.md", section_text),
            "the MAR-120 CHANGELOG entry must mention project-structure.md")
        self.assertIsNotNone(
            re.search(r"create-architecture", section_text),
            "the MAR-120 CHANGELOG entry must mention create-architecture")


class ScopeGuardTest(unittest.TestCase):
    """AC-7/AC-8: MAR-120's own diff added no acs skill/agent (verified by
    git history) and does not hand-author project-structure.md or ship a
    template. The skill/agent-count doc lines legitimately advance as later,
    unrelated producer children land (MAR-121: 21->22 skills, 39->42 agent
    files, 33->36 reachable, ten->eleven triads; MAR-129: 22->23 skills for
    the new unhooked /acs:release skill, agent counts unchanged; MAR-143:
    23->24 skills for the new HOOKED create-requirements skill, 42->45 agent
    files, 36->39 reachable, eleven->twelve triads) — these assertions track
    the current epic state, not a frozen MAR-120 snapshot."""

    def test_c4_container_counts_unchanged(self):
        body = read(os.path.join(DOCS, "architecture", "hld", "c4-container.md"))
        self.assertIn("24 x SKILL.md", body)
        self.assertIn("45 x agent .md (39 reachable)", body)

    def test_tech_stack_counts_unchanged(self):
        body = read(os.path.join(DOCS, "architecture", "hld", "tech-stack.md"))
        self.assertIn("acs Skills (24)", body)
        self.assertIn("45 files, 39 reachable", body)

    def test_triad_keeping_phrase_unchanged(self):
        overview = read(os.path.join(DOCS, "architecture", "hld", "overview.md"))
        hook_flow = read(
            os.path.join(DOCS, "architecture", "lld", "flows", "hook-gated-skill-run.md"))
        self.assertIn("twelve triad-keeping skills", overview)
        self.assertIn("twelve triad-keeping skills", hook_flow)

    def test_no_project_structure_doc_hand_authored(self):
        self.assertFalse(
            os.path.exists(os.path.join(DOCS, "architecture", "hld", "project-structure.md")),
            "docs/architecture/hld/project-structure.md must not be hand-authored by MAR-120")

    def test_no_shipped_template(self):
        templates_dir = os.path.join(PLUGIN, "templates")
        for root, _dirs, files in os.walk(templates_dir):
            for fname in files:
                self.assertFalse(
                    fname.startswith("project-structure"),
                    "unexpected shipped template %s" % os.path.join(root, fname))


class SkillAdditivityGuardTest(unittest.TestCase):
    """AC-5: pre-existing Output-contract rows survive (table now 10 rows);
    Re-run additive phrase preserved verbatim."""

    PRE_EXISTING = [
        "hld/overview.md", "hld/c4-context.md", "hld/c4-container.md",
        "hld/c4-component.md", "hld/data-model.md", "hld/deployment.md",
        "hld/tech-stack.md", "lld/flows/", "lld/contracts.md",
    ]

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.output = section(cls.body, "## Output contract")
        cls.inputs = section(cls.body, "## Inputs & mode")

    def test_pre_existing_rows_survive_alongside_new_row(self):
        for name in self.PRE_EXISTING:
            self.assertIn(name, self.output, "%s dropped from Output contract" % name)
        self.assertIn("hld/project-structure.md", self.output)

    def test_output_contract_has_exactly_ten_data_rows(self):
        rows = re.findall(r"(?m)^\| `", self.output)
        self.assertEqual(
            len(rows), 10,
            "expected 10 Output-contract data rows (9 pre-existing + 1 new), found %d: %r"
            % (len(rows), rows))

    def test_rerun_additive_phrase_preserved(self):
        self.assertIn("keep the same file set, update content in place", self.inputs)


if __name__ == "__main__":
    unittest.main()
