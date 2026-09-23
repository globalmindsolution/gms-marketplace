"""MAR-121 spec 03 — flow doc, counts/consistency, eval trigger, CHANGELOG.

Prose-contract tests over the new standing Flow-1 doc
(`docs/architecture/lld/flows/standardize-project.md`), every count-bearing
architecture/requirements file this epic's final increment touches (repaired
to the post-121 totals 22 skills / 42 agent files / 36 reachable / eleven
triad-keeping skills; the skill total later advances 22->23 as MAR-129 adds
the unhooked /acs:release skill, agent counts unchanged), the routing
routing-eval case, and the durable CHANGELOG
entries (per-child MAR-121 + the epic-wide G10 summary line).

Stdlib-only (ast, os, re, unittest). Run:
  python3 -m unittest tests.acs.test_mar121_docs_flow_eval -v
"""

import ast
import json
import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")

sys.path.insert(0, os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval_cases  # noqa: E402  (the case files are the probe set)
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

    def test_flow_doc_names_all_six_participants(self):
        # Seven until ADR-0092 retired the planner: the audit and the frozen
        # allowlist are iteration 1's executor's, recorded in its authoring
        # notes, so no PL participant remains to draw.
        body = read(FLOW_DOC)
        for participant in ("Dev", "CC", "SP", "EX", "VF", "Repo"):
            self.assertIn(
                "participant %s as" % participant if participant != "Dev" else "actor Dev as",
                body,
                "flow doc must name participant %r" % participant)
        self.assertNotIn("standardize-project-planner", body)
        self.assertNotIn('phase="plan"', body)
        self.assertIn("iter-1-authoring.md", body)

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

    #: The intro states the count in WORDS, so the check spells the number
    #: derived from disk rather than pinning one literal that goes stale on
    #: every skill added or retired.
    WORDS = {23: "Twenty-three", 24: "Twenty-four", 25: "Twenty-five",
             26: "Twenty-six", 27: "Twenty-seven", 28: "Twenty-eight",
             29: "Twenty-nine", 30: "Thirty", 31: "Thirty-one",
             32: "Thirty-two", 33: "Thirty-three", 34: "Thirty-four"}

    def test_intro_count_matches_the_skill_directories_on_disk(self):
        shipped = len([
            name for name in os.listdir(os.path.join(PLUGIN, "skills"))
            if os.path.isfile(os.path.join(PLUGIN, "skills", name, "SKILL.md"))
        ])
        word = self.WORDS.get(shipped)
        self.assertIsNotNone(word, "extend WORDS for %d skills" % shipped)
        body = self._skills_req()
        intro = body[:600]
        self.assertIn("%s skills" % word, intro,
                      "skills.md intro must read '%s skills'" % word)
        for other, stale in self.WORDS.items():
            if other == shipped:
                continue
            self.assertNotIn("%s skills in total" % stale, intro,
                             "skills.md intro must NOT still read %r" % stale)

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

    def test_workflow_product_skills_bullet_reads_nine(self):
        body = self._skills_req()
        window = window_to_next_h2(body, "Every **workflow** skill MUST:")
        self.assertIn("Nine **workflow/product skills**", window)
        self.assertNotIn("Eleven **workflow/product skills**", window)
        self.assertNotIn("Six **workflow/product skills**", window)
        for name in (
            "docs-sync", "code", "create-prd", "create-design",
            "create-architecture", "create-project", "create-docs",
            "standardize-project", "create-requirements",
        ):
            self.assertIn(name, window,
                          "the workflow/product skills bullet must name %r" % name)

    def test_models_config_bullet_reads_twelve_triad_keeping(self):
        body = self._skills_req()
        self.assertIn("the fourteen\n  reflection-loop skills only", body)
        self.assertNotIn("the twelve\n  triad-keeping skills only", body)
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
        # Derived, not pinned: a new skill directory moves the diagram
        # by itself rather than waiting for someone to notice.
        shipped = len([n for n in os.listdir(
            os.path.join(REPO_ROOT, "plugins", "acs", "skills"))
            if os.path.isdir(os.path.join(
                REPO_ROOT, "plugins", "acs", "skills", n))])
        self.assertIn("%d x SKILL.md" % shipped, body)
        self.assertNotIn("21 x SKILL.md", body)
        agents = len([n for n in os.listdir(
            os.path.join(REPO_ROOT, "plugins", "acs", "agents")) if n.endswith(".md")])
        self.assertIn("%d x agent .md (all reachable)" % agents, body)
        self.assertNotIn("43 x agent .md (all reachable)", body)
        self.assertNotIn("39 x agent .md (33 reachable)", body)

    def test_c4_container_triad_skill_list_names_all_twelve(self):
        body = read(os.path.join(REPO_ROOT, "docs", "architecture", "hld", "c4-container.md"))
        self.assertNotIn("ten triad-keeping skills", body)
        self.assertNotIn("eleven triad-keeping skills", body)
        self.assertNotIn("twelve triad-keeping skills", body)
        m = re.search(r"pair for the twelve authoring skills \(([^)]*)\)", body)
        self.assertIsNotNone(
            m, "c4-container.md must state 'twelve authoring skills' with "
               "the enumerated list")
        enumerated = m.group(1)
        for suffix in (
            "prd", "architecture", "project", "design", "create-requirements",
            "standardize-project", "docs-sync", "analyze-requirements",
            "create-impl-plan", "api-contract", "test-docs", "e2e-tests",
        ):
            self.assertIn(
                suffix, enumerated,
                "c4-container.md triad-skill prose must name -%s" % suffix)
        self.assertIn("code", body)

    def test_c4_component_triad_and_reachable_counts(self):
        body = read(os.path.join(REPO_ROOT, "docs", "architecture", "hld", "c4-component.md"))
        self.assertIn("twelve authoring skills", body)
        self.assertNotIn("twelve triad-keeping skills", body)
        self.assertNotIn("eleven triad-keeping skills", body)
        self.assertIn("standardize-project", body)
        self.assertIn("12 authoring pairs (24 agents", body)
        self.assertNotIn("12 active triads (36 agents", body)
        self.assertNotIn("11 active triads (33 agents", body)
        self.assertIn("31 agent files, all reachable", body)
        self.assertNotIn("43 agent files, all reachable", body)
        self.assertNotIn("36 reachable agents", body)

    def test_tech_stack_skill_and_agent_counts(self):
        body = read(os.path.join(REPO_ROOT, "docs", "architecture", "hld", "tech-stack.md"))
        # Derived, not pinned: a new skill directory moves this count by
        # itself rather than waiting for someone to notice the doc is stale.
        shipped = len([n for n in os.listdir(os.path.join(REPO_ROOT, "plugins", "acs", "skills"))
                       if os.path.isdir(os.path.join(REPO_ROOT, "plugins", "acs", "skills", n))])
        self.assertIn("acs Skills (%d)" % shipped, body)
        self.assertNotIn("acs Skills (21)", body)
        agents = len([n for n in os.listdir(
            os.path.join(REPO_ROOT, "plugins", "acs", "agents")) if n.endswith(".md")])
        self.assertIn("%d files, all reachable" % agents, body)
        self.assertNotIn("43 files, all reachable", body)
        self.assertNotIn("39 files, 33 reachable", body)
        self.assertIn("twelve authoring skills (24 agents)", body)
        self.assertNotIn("twelve triad-keeping skills (36 agents)", body)
        self.assertNotIn("eleven triad-keeping skills (33 agents)", body)

    def test_overview_and_hook_gated_name_standardize_project(self):
        overview = read(os.path.join(REPO_ROOT, "docs", "architecture", "hld", "overview.md"))
        self.assertNotIn("ten triad-keeping skills", overview)
        window = section(overview, "## Quality attributes (drive the design)")
        self.assertIn("twelve authoring skills", window)
        self.assertNotIn("twelve triad-keeping skills", window)
        self.assertIn("standardize-project", window)

        hook_gated = read(os.path.join(
            REPO_ROOT, "docs", "architecture", "lld", "flows", "hook-gated-skill-run.md"))
        self.assertNotIn("ten triad-keeping skills", hook_gated)
        self.assertNotIn("twelve triad-keeping skills", hook_gated)
        self.assertIn("twelve authoring skills", hook_gated)
        self.assertIn("standardize-project", hook_gated)


class RoutingProbeCaseTest(unittest.TestCase):
    """AC-9: standardize-project's routing cases (no paid model call).

    These parsed s04_skill_triggers.py's CASES/NEGATIVE lists, then read a
    routing dataset; both are gone, and the case files under plugins/acs/evals/
    are the probe set, read through tests/acs/eval_cases.py. The rule carried
    through every move: counts the suite states about itself are DERIVED here
    and never pinned, so a case change cascades to zero test edits. Applied to
    the old dataset it found the description claiming 24 natural-language
    probes when there were 26; the suite's README is where those counts live
    now, so that is what is held to them."""

    README = os.path.join(PLUGIN, "evals", "README.md")

    @staticmethod
    def _probes():
        return eval_cases.probe_dicts()

    @staticmethod
    def _skill(probe):
        return probe["skill"].split(":", 1)[1]

    def test_standardize_project_case_present_and_internally_consistent(self):
        probes = self._probes()
        positives = [p for p in probes
                     if p["must_route"] and self._skill(p) == "standardize-project"]
        self.assertTrue(positives, "the suite must carry a standardize-project positive")
        # ADR 0091 made this an internal leg, so its positive probe is the
        # explicit command, and the description that used to be the positive is
        # now the NEGATIVE -- the one that must NOT auto-route. The no-naming
        # rule follows the description to where it lives.
        self.assertEqual(
            positives[0]["prompt"].strip(), "/acs:standardize-project",
            "an internal leg's positive probe is the explicit command")
        negatives = [p for p in probes
                     if not p["must_route"] and self._skill(p) == "standardize-project"]
        self.assertTrue(negatives, "an internal leg needs a no-auto-route negative case")
        self.assertNotIn(
            "standardize", negatives[0]["prompt"],
            "the probe request must describe brownfield audit intent "
            "without naming the skill")

    def test_no_create_spec_routing_case(self):
        for probe in self._probes():
            self.assertNotEqual(self._skill(probe), "create-spec",
                                "no case may route to the deleted create-spec")
        # Nothing anywhere in the eval suite may mention the deleted skill
        # (AC-1, scope extension): scan every file of it, not just the graders.
        for dirpath, dirnames, filenames in os.walk(eval_cases.EVALS):
            dirnames[:] = [d for d in dirnames if d != "results"]
            for name in filenames:
                path = os.path.join(dirpath, name)
                with open(path, encoding="utf-8") as fh:
                    self.assertNotIn(
                        "create-spec", fh.read(),
                        "%s references the deleted create-spec skill"
                        % os.path.relpath(path, REPO_ROOT))

    def test_readme_tag_counts_match_the_cases(self):
        """The README's tag table is part of the suite: a stale count there is
        how a reader forms a wrong belief about what it covers."""
        with open(self.README, encoding="utf-8") as fh:
            readme = fh.read()
        cases = eval_cases.all_cases()
        for tag in ("routing", "description", "explicit", "negative", "control",
                    "artifacts"):
            n = len([c for c in cases if tag in c.tags])
            with self.subTest(tag=tag):
                self.assertRegex(
                    readme, r"\| `%s` \| [^|]*?\b%d\b" % (re.escape(tag), n),
                    "README's %r row does not state the real count %d" % (tag, n))

    def test_readme_does_not_claim_more_coverage_than_the_cases_carry(self):
        shipped = set(eval_cases.shipped_skills())
        probed = {self._skill(p) for p in self._probes()}
        self.assertEqual(probed, shipped,
                         "every shipped skill must have a case before the "
                         "suite may be described as covering them")


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
