"""MAR-121 spec 03 — flow doc, counts/consistency, eval trigger, CHANGELOG.

Prose-contract tests over the new standing Flow-1 doc
(`docs/architecture/lld/flows/standardize-project.md`), every count-bearing
architecture/requirements file this epic's final increment touches (repaired
to the post-121 totals 22 skills / 42 agent files / 36 reachable / eleven
triad-keeping skills; the skill total later advances 22->23 as MAR-129 adds
the unhooked /acs:release skill, agent counts unchanged), the `s04`
routing-eval case, and the durable CHANGELOG
entries (per-child MAR-121 + the epic-wide G10 summary line).

Stdlib-only (ast, os, re, unittest). Run:
  python3 -m unittest tests.acs.test_mar121_docs_flow_eval -v
"""

import ast
import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")

sys.path.insert(0, os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts"))
import mermaid_lint  # noqa: E402

FLOW_DOC = os.path.join(
    REPO_ROOT, "docs", "architecture", "lld", "flows", "standardize-project.md")


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


def window_to_next_h2(body, anchor_text):
    """Return the text from `anchor_text` (a plain string, not a heading) up
    to the next level-2 markdown heading, or end of file."""
    idx = body.find(anchor_text)
    if idx == -1:
        raise AssertionError("anchor %r not found" % anchor_text)
    nxt = re.search(r"(?m)^## \S", body[idx:])
    end = idx + nxt.start() if nxt else len(body)
    return body[idx:end]


def bullets(text):
    """Split a markdown section into top-level `- ` bullet blocks."""
    starts = [m.start() for m in re.finditer(r"(?m)^- ", text)]
    if not starts:
        return [text]
    starts.append(len(text))
    return [text[s:e] for s, e in zip(starts, starts[1:])]


class FlowDocTest(unittest.TestCase):
    """AC-8: the new Flow 1 standing doc exists, reproduces the design's
    sequence diagram verbatim (7 participants), and lints clean."""

    def test_flow_doc_exists(self):
        self.assertTrue(
            os.path.isfile(FLOW_DOC),
            "docs/architecture/lld/flows/standardize-project.md must exist")

    def test_flow_doc_has_sequence_diagram(self):
        body = read(FLOW_DOC)
        m = re.search(r"```mermaid\n(.*?)```", body, re.DOTALL)
        self.assertIsNotNone(m, "flow doc must have a fenced ```mermaid block")
        first_line = next(
            (ln.strip() for ln in m.group(1).splitlines() if ln.strip()), "")
        self.assertEqual(first_line, "sequenceDiagram")

    def test_flow_doc_names_all_seven_participants(self):
        body = read(FLOW_DOC)
        for participant in ("Dev", "CC", "SP", "PL", "EX", "VF", "Repo"):
            self.assertIn(
                participant, body,
                "flow doc must name participant %r" % participant)

    def test_flow_doc_states_never_trust_contract(self):
        body = read(FLOW_DOC)
        self.assertIn("git diff --name-status", body)
        self.assertIn("never trust", body.lower())

    def test_flow_doc_mermaid_lints_clean(self):
        findings = mermaid_lint.lint_file(FLOW_DOC)
        self.assertEqual(
            findings, [], "flow doc mermaid block must lint clean: %r" % (findings,))


class SkillsMdCountAndTriadProseTest(unittest.TestCase):
    """AC-9: skills.md intro count bump, new standardize-project section,
    and the pre-existing 'six' triad-prose drift repaired to 'eleven'. The
    intro count advances 23->24 and the triad-prose word eleven->twelve as
    MAR-143 registers create-requirements (a HOOKED product skill) into the
    product/triad enumeration — these assertions track the current epic
    state, not a frozen MAR-121 snapshot."""

    def _skills_req(self):
        return read(os.path.join(REPO_ROOT, "docs", "requirements", "functional", "skills.md"))

    def test_intro_reads_twentyfive_not_twentyfour(self):
        body = self._skills_req()
        intro = body[:600]
        self.assertIn("Twenty-five skills", intro,
                      "skills.md intro must read 'Twenty-five skills'")
        self.assertNotIn("Twenty-three skills", intro,
                         "skills.md intro must NOT still read 'Twenty-three skills'")

    def test_standardize_project_section_exists_not_product_level(self):
        body = self._skills_req()
        m = re.search(r"(?m)^## .*standardize-project.*$", body)
        self.assertIsNotNone(
            m, "skills.md must have a '## .../standardize-project' section")
        heading_line = m.group(0)
        self.assertNotIn(
            "(product-level)", heading_line,
            "the standardize-project section heading must NOT be tagged "
            "(product-level) — it is not a <set>_path doc-set producer")
        window = section(body, heading_line)
        for token in (
            "principles_path", "standards_path", "hld/project-structure.md",
            "additive",
        ):
            self.assertIn(token, window,
                          "standardize-project section must mention %r" % token)
        self.assertTrue(
            "recommended_follow_ups" in window or "recommended follow-up" in window,
            "standardize-project section must mention recommended_follow_ups "
            "or 'recommended follow-up'")

    def test_workflow_product_skills_bullet_reads_twelve(self):
        body = self._skills_req()
        window = window_to_next_h2(body, "Every **workflow** skill MUST:")
        self.assertIn("Twelve", window)
        self.assertNotIn("Eleven **workflow/product skills**", window)
        self.assertNotIn("Six **workflow/product skills**", window)
        for name in (
            "docs-sync", "code", "create-prd", "create-design",
            "create-architecture", "create-project", "create-quality",
            "create-operations", "create-principles", "create-standards",
            "standardize-project", "create-requirements",
        ):
            self.assertIn(name, window,
                          "the workflow/product skills bullet must name %r" % name)

    def test_models_config_bullet_reads_twelve_triad_keeping(self):
        body = self._skills_req()
        self.assertIn("the twelve\n  triad-keeping skills only", body)
        self.assertNotIn("the eleven\n  triad-keeping skills only", body)
        self.assertNotIn("the six\n  triad-keeping skills only", body)


class C4CountAndListFilesTest(unittest.TestCase):
    """AC-9: the C4/architecture count files read the current-epic totals
    (23 skills post-MAR-156 / 42 agent files / 36 reachable / eleven triads /
    11 active triads (33 agents in triads)) — the pre-121 strings are absent.
    The skill total advanced 22->23 with MAR-129's unhooked /acs:release skill,
    23->24 with MAR-143's create-requirements (a HOOKED skill, so the
    agent/triad figures advanced too: 42->45 agents, 36->39 reachable,
    eleven->twelve triads), then 24->23 with MAR-156's create-spec deletion
    (a HOOKED skill removed: 45->42 agents, 39->36 reachable, twelve->eleven
    triads)."""

    def test_c4_container_skill_and_agent_counts(self):
        body = read(os.path.join(REPO_ROOT, "docs", "architecture", "hld", "c4-container.md"))
        self.assertIn("25 x SKILL.md", body)
        self.assertNotIn("21 x SKILL.md", body)
        self.assertIn("45 x agent .md (39 reachable)", body)
        self.assertNotIn("39 x agent .md (33 reachable)", body)

    def test_c4_container_triad_skill_list_names_all_twelve(self):
        body = read(os.path.join(REPO_ROOT, "docs", "architecture", "hld", "c4-container.md"))
        self.assertNotIn("ten triad-keeping skills", body)
        self.assertNotIn("eleven triad-keeping skills", body)
        m = re.search(r"triad for the twelve triad-keeping skills \(([^)]*)\)", body)
        self.assertIsNotNone(
            m, "c4-container.md must state 'twelve triad-keeping skills' with "
               "the enumerated list")
        enumerated = m.group(1)
        for suffix in (
            "prd", "architecture", "project", "quality", "operations",
            "principles", "standards", "design", "standardize-project",
            "create-requirements",
        ):
            self.assertIn(
                suffix, enumerated,
                "c4-container.md triad-skill prose must name -%s" % suffix)
        self.assertIn("code", body)

    def test_c4_component_triad_and_reachable_counts(self):
        body = read(os.path.join(REPO_ROOT, "docs", "architecture", "hld", "c4-component.md"))
        self.assertIn("twelve triad-keeping skills", body)
        self.assertNotIn("eleven triad-keeping skills", body)
        self.assertIn("standardize-project", body)
        self.assertIn("12 active triads (36 agents", body)
        self.assertNotIn("11 active triads (33 agents", body)
        self.assertIn("39 reachable agents", body)
        self.assertNotIn("36 reachable agents", body)

    def test_tech_stack_skill_and_agent_counts(self):
        body = read(os.path.join(REPO_ROOT, "docs", "architecture", "hld", "tech-stack.md"))
        self.assertIn("acs Skills (25)", body)
        self.assertNotIn("acs Skills (21)", body)
        self.assertIn("45 files, 39 reachable", body)
        self.assertNotIn("39 files, 33 reachable", body)
        self.assertIn("twelve triad-keeping skills (36 agents)", body)
        self.assertNotIn("eleven triad-keeping skills (33 agents)", body)

    def test_overview_and_hook_gated_name_standardize_project(self):
        overview = read(os.path.join(REPO_ROOT, "docs", "architecture", "hld", "overview.md"))
        self.assertNotIn("ten triad-keeping skills", overview)
        window = section(overview, "## Quality attributes (drive the design)")
        self.assertIn("twelve triad-keeping skills", window)
        self.assertIn("standardize-project", window)

        hook_gated = read(os.path.join(
            REPO_ROOT, "docs", "architecture", "lld", "flows", "hook-gated-skill-run.md"))
        self.assertNotIn("ten triad-keeping skills", hook_gated)
        self.assertIn("twelve triad-keeping skills", hook_gated)
        self.assertIn("standardize-project", hook_gated)


class S04SkillTriggersCaseTest(unittest.TestCase):
    """AC-9: one new standardize-project routing CASE, structurally parsed
    (no paid model call); the pre-existing 18/16-vs-21-entries drift is
    repaired straight to 22/20, later advanced to 23/21 by the /acs:release
    routing case, then back to 22/20 as the create-spec case is retired.
    Header/summary/prose count slots are asserted by deriving the expected
    values from the live CASES/NEGATIVE lists rather than pinning literals,
    so a future case-list change cascades to zero test edits here."""

    def _source(self):
        path = os.path.join(REPO_ROOT, "evals", "acs", "scenarios", "s04_skill_triggers.py")
        return read(path)

    def _list(self, name):
        tree = ast.parse(self._source())
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name for t in node.targets
            ):
                return ast.literal_eval(node.value)
        raise AssertionError("%s list not found in s04_skill_triggers.py" % name)

    def _cases(self):
        return self._list("CASES")

    def _negative(self):
        return self._list("NEGATIVE")

    def test_standardize_project_case_present_and_internally_consistent(self):
        cases = self._cases()
        matches = [c for c in cases if c[0] == "standardize-project"]
        self.assertTrue(
            matches,
            "s04 CASES must contain an entry labeled 'standardize-project'")
        case = matches[0]
        self.assertEqual(
            case[-1], "standardize-project",
            "the 'standardize-project' CASE's expected-skill (last element) "
            "must be 'standardize-project'")
        self.assertNotIn(
            "standardize", case[2],
            "the probe request must describe brownfield audit intent "
            "without naming the skill")

    def test_no_create_spec_routing_case(self):
        for case in self._cases():
            self.assertNotEqual(case[0], "create-spec",
                                "s04 CASES must not carry a create-spec label")
            self.assertNotEqual(case[-1], "create-spec",
                                "s04 CASES must not route to create-spec")
        for case in self._negative():
            self.assertNotEqual(case[0], "create-spec")
            self.assertNotEqual(case[-1], "create-spec")
        self.assertNotIn(
            "create-spec", self._source(),
            "s04 source must not mention the deleted create-spec skill")

        # No eval scenario anywhere references the deleted skill (AC-1,
        # scope extension): scan the whole scenarios package, not just s04.
        scenarios_dir = os.path.join(REPO_ROOT, "evals", "acs", "scenarios")
        for name in sorted(os.listdir(scenarios_dir)):
            if not name.endswith(".py"):
                continue
            with open(os.path.join(scenarios_dir, name), encoding="utf-8") as fh:
                body = fh.read()
            self.assertNotIn(
                "create-spec", body,
                "%s still references the deleted create-spec skill" % name)

    def test_header_and_summary_counts_match_case_lists(self):
        source = self._source()
        total = len(self._cases())
        user_only = len(self._negative())
        described = total - user_only

        header = source.split("\n")[0]
        m = re.search(r"all (\d+) skills", header)
        self.assertIsNotNone(m, "s04 header must state 'all N skills'")
        self.assertEqual(int(m.group(1)), total)

        m = re.search(r'"summary":\s*"([^"]*)"', source)
        self.assertIsNotNone(m, "META[\"summary\"] must be present")
        summary = m.group(1)
        m2 = re.search(r"all (\d+) \((\d+) by description, (\d+) user-only", summary)
        self.assertIsNotNone(
            m2, "summary must state 'all N (M by description, K user-only'")
        self.assertEqual(
            (int(m2.group(1)), int(m2.group(2)), int(m2.group(3))),
            (total, described, user_only))

    def test_docstring_prose_counts_match_case_lists(self):
        source = self._source()
        total = len(self._cases())
        user_only = len(self._negative())
        described = total - user_only

        described_hits = re.findall(r"(\d+) model-invocable skills", source)
        self.assertTrue(described_hits,
                        "s04 prose must state 'N model-invocable skills'")
        for value in described_hits:
            self.assertEqual(int(value), described)

        user_only_hits = re.findall(r"(\d+) user-only skills", source)
        self.assertTrue(user_only_hits,
                        "s04 prose must state 'N user-only skills'")
        for value in user_only_hits:
            self.assertEqual(int(value), user_only)


class ChangelogMar121EntryTest(unittest.TestCase):
    """AC-9: durable-invariant CHANGELOG entry — never pins the literal
    '[Unreleased]' or a dated version string as a fixed anchor."""

    def _changelog(self):
        return read(os.path.join(PLUGIN, "CHANGELOG.md"))

    def _mar121_section(self):
        body = self._changelog()
        spans = [m.start() for m in re.finditer(r"## \[[^\]]*\]", body)] + [len(body)]
        for start, end in zip(spans, spans[1:]):
            candidate = body[start:end]
            if "(MAR-121)" in candidate:
                return candidate
        raise AssertionError("CHANGELOG.md must contain '(MAR-121)' inside a section span")

    def test_changelog_mar121_entry_in_topmost_section(self):
        section_text = self._mar121_section()
        heading = section_text[:section_text.index("\n")] if "\n" in section_text else section_text
        self.assertRegex(
            heading, r"## \[(Unreleased|\d+\.\d+\.\d+)\]",
            "the '(MAR-121)' entry must live under [Unreleased] or a dated "
            "semver release heading (release cuts legitimately graduate it)")
        self.assertIn("standardize-project", section_text)
        self.assertTrue(
            "recommended_follow_ups" in section_text
            or "recommended follow-up" in section_text,
            "the MAR-121 CHANGELOG entry must mention recommended_follow_ups "
            "or 'recommended follow-up'")


class ChangelogEpicSummaryLineTest(unittest.TestCase):
    """AC-9: a distinct epic-wide summary bullet co-occurs G10 with all
    three new skill names — not satisfiable by the per-child bullet alone."""

    def test_epic_summary_bullet_names_g10_and_all_three_skills(self):
        changelog = ChangelogMar121EntryTest()
        section_text = changelog._mar121_section()
        blocks = bullets(section_text)
        required = ("G10", "create-principles", "create-standards", "standardize-project")
        matches = [b for b in blocks if all(tok in b for tok in required)]
        self.assertTrue(
            matches,
            "one CHANGELOG bullet must co-occur G10 with create-principles, "
            "create-standards, and standardize-project (the epic-wide "
            "summary line, distinct from the per-child MAR-121 entry)")


if __name__ == "__main__":
    unittest.main()
