"""Parallel fan-out prose for /acs:create-architecture and /acs:create-tech-design.

Pins the coordinator-owned fan-out each skill now runs: the partition rule for
its parallel writers or research slices, the one-message spawn, the
deterministic `acs.py notes merge` join, the sliced-judge pass rule, the cap,
and the judge's dimension slicing (every dimension in exactly one slice, each
deterministic lint in exactly one slice). Also pins the agents' "When you are
one slice" contract and the slice-aware resume rule.

Stdlib-only. Run:  python3 -m unittest tests.acs.test_architecture_design_fanout -v
"""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import skill_text  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SKILLS = os.path.join(PLUGIN, "skills")
AGENTS = os.path.join(PLUGIN, "agents")


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def flat(text):
    """Collapse whitespace so a phrase wrapped across lines still matches."""
    return re.sub(r"\s+", " ", text)


def slice_table(body, first_slice):
    """{slice id: row text} for the markdown table whose first data row is
    `first_slice`."""
    lines = body.splitlines()
    start = next(i for i, line in enumerate(lines)
                 if re.match(r"^\s*\| `%s` \|" % re.escape(first_slice), line))
    rows = {}
    for line in lines[start:]:
        match = re.match(r"^\s*\| `([a-z0-9]+)`[^|]*\|(.*)\|\s*$", line)
        if not match:
            break
        rows[match.group(1)] = match.group(2)
    return rows


def agent_dimensions(agent_body):
    """{number: name} from a judge agent's numbered check-dimension list."""
    dims = {}
    for match in re.finditer(r"(?m)^(\d+)\. (?:\*\*([a-z-]+)\*\*|`([a-z-]+)`)", agent_body):
        dims[int(match.group(1))] = match.group(2) or match.group(3)
    return dims


class JudgeSlicingMixin:
    """Shared checks over a sliced-judge table."""

    def assert_dimensions_partitioned(self, rows, agent_body):
        dims = agent_dimensions(agent_body)
        self.assertTrue(dims, "no numbered dimensions found in the judge agent")
        seen = {}
        for slice_id, row in rows.items():
            for number, name in re.findall(r"(\d+) ([a-z-]+)", row):
                number = int(number)
                self.assertNotIn(number, seen,
                                 "dimension %d is in slices %s and %s"
                                 % (number, seen.get(number), slice_id))
                seen[number] = slice_id
                self.assertEqual(dims.get(number), name,
                                 "slice %s names dimension %d %r; the agent calls it %r"
                                 % (slice_id, number, name, dims.get(number)))
        self.assertEqual(set(seen), set(dims),
                         "every judge dimension must sit in exactly one slice")
        self.assertTrue(2 <= len(rows) <= 3, "a sliced judge runs 2-3 slices")

    def assert_lint_in_one_slice(self, rows, lint, owner):
        holders = [sid for sid, row in rows.items() if lint in row]
        self.assertEqual(holders, [owner],
                         "%s must run in exactly one slice (%s)" % (lint, owner))


class CreateArchitectureFanOutTest(JudgeSlicingMixin, unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.skill = read(os.path.join(SKILLS, "create-architecture", "SKILL.md"))
        cls.flat = flat(cls.skill)
        cls.architect = read(os.path.join(AGENTS, "create-architecture-architect.md"))
        cls.reviewer = read(os.path.join(AGENTS, "create-architecture-reviewer.md"))

    def test_write_slices_one_per_hld_file_group(self):
        """ADR-0125 (amending ADR-0121's single writer): the write pass fans out
        by HLD file group, every slice writing from the notes that pinned the
        shared vocabulary; only the groups with a file to write run."""
        self.assertIn("one architect per **HLD file group**", self.flat)
        rows = {}
        for line in self.skill.splitlines():
            m = re.match(r"^\| `(write-[a-z]+)` \| (.+) \|$", line)
            if m:
                rows[m.group(1)] = re.findall(r"`hld/([a-z0-9-]+)\.md`", m.group(2))
        self.assertEqual(rows, {
            "write-context": ["overview", "c4-context", "capability-map"],
            "write-structure": ["c4-container", "c4-component", "deployment",
                                "project-structure"],
            "write-data": ["data-model", "integration-map", "data-flow"],
            "write-conventions": ["tech-stack", "cross-cutting"]})
        files = [f for group in rows.values() for f in group]
        self.assertEqual(len(files), len(set(files)), "a file in two groups")
        self.assertIn("the notes pinned", self.flat)
        self.assertIn('<constraint name="files">', self.skill)
        for gone in ("spawn ONE write architect", "no seams to reconcile",
                     '<constraint name="owns">', "min(3, number of flows) contiguous groups"):
            self.assertNotIn(gone, self.flat)

    def test_the_cap_is_the_setting(self):
        self.assertIn("at most `settings.parallel.max_agents` (default 4), waves of that "
                      "size beyond it", self.flat)

    def test_writes_only_the_enabled_hld_types(self):
        contract = flat(self.skill.split("## Output contract", 1)[1].split("\n## ", 1)[0])
        self.assertIn("`settings.design.hld_types`", contract)
        self.assertIn("never touches `lld/`", contract)
        self.assertIn('<constraint name="hld_types">', self.skill)

    def test_survey_sliced_over_disjoint_areas(self):
        for phrase in ("two or more disjoint top-level areas",
                       "one `prd` slice plus one slice per area",
                       '<constraint name="area">',
                       "iter-1/authoring-<id>.md",
                       "ONE grouped clarification-ledger interaction"):
            self.assertIn(phrase, self.flat)

    def test_one_message_spawn_and_cap(self):
        self.assertIn("the SAME agent spawned N times in ONE message", self.flat)
        self.assertIn("at most `settings.parallel.max_agents` (default 4) instances per "
                      "message", self.flat)
        self.assertIn("waves of that size", self.flat)

    def test_notes_merge_join(self):
        self.assertIn('acs.py" notes merge', self.skill)
        self.assertIn("--out <partition>/steps/create-architecture/iter-<n>/authoring.md",
                      self.skill)
        self.assertIn("acs.py notes merge --out iter-<n>/reviewer.md", self.flat)
        self.assertIn("never merge prose by hand", self.flat)

    def test_sliced_reviewer_pass_rule(self):
        for phrase in ("passes only if EVERY reviewer slice returned "
                       '`status="completed"` with zero blocking findings',
                       "Any slice's blocking finding blocks",
                       "ALL slices' findings go verbatim",
                       'never "pass with a missing slice"'):
            self.assertIn(phrase, self.flat)

    def test_reviewer_dimension_slices(self):
        rows = slice_table(self.skill, "coverage")
        self.assertEqual(set(rows), {"coverage", "diagrams", "coherence"})
        self.assert_dimensions_partitioned(rows, self.reviewer)
        self.assert_lint_in_one_slice(rows, "mermaid_lint.py", "diagrams")
        self.assert_lint_in_one_slice(rows, "structure_lint.py", "coherence")
        self.assertIn('<constraint name="dimensions">', self.skill)

    def test_resume_reruns_only_missing_slices(self):
        self.assertIn("re-run ONLY the slices whose own report is missing", self.flat)

    def test_integration_pass_runs_alone_only_on_a_reported_seam(self):
        """The code-standard pattern: ONE integration architect after the last
        wave, and only when a write slice reports a seam -- a name it needed
        that another group owns."""
        self.assertIn("no slice reported a seam → skip the integration pass", self.flat)
        self.assertIn("any seam → spawn ONE more architect, alone, with "
                      '`slice="integration"`', self.flat)
        self.assertIn("iter-<n>/architect-integration.json", self.flat)
        self.assertIn("The reviewer's `coherence` slice still judges cross-file naming",
                      self.flat)
        body = flat(self.architect)
        self.assertIn("## When you are the integration pass", self.architect)
        self.assertIn("record a **seam** in your report", body)
        self.assertIn("iter-<n>/architect-integration.json", body)

    def test_survey_consumers_synthesize(self):
        self.assertIn("MUST reconcile them for the facts its files use", self.flat)
        self.assertIn("under a `## Synthesis` heading", self.flat)
        self.assertIn("never silently picks one", self.flat)
        self.assertIn("## Synthesis", self.architect)
        self.assertIn("never silently pick one", flat(self.architect))

    def test_reviewer_findings_deduplicated(self):
        for phrase in ("drop a finding that cites the same location and the same defect "
                       "as another slice's finding, keeping the higher severity",
                       "append a `## De-duplicated findings` section"):
            self.assertIn(phrase, self.flat)

    def test_architect_slice_contract(self):
        body = flat(self.architect)
        self.assertIn("## When you are one slice", self.architect)
        for phrase in ("iter-<n>/architect-<id>.json", "iter-<n>/authoring-<id>.md",
                       'phase="architect" slice="<id>"',
                       "never invent a container/component name"):
            self.assertIn(phrase, body)
        self.assertNotIn("architect-<k>", body)

    def test_reviewer_slice_contract(self):
        section = self.reviewer.split("## When you are one slice", 1)[1].split("\n## ", 1)[0]
        body = flat(section)
        for phrase in ('<constraint name="dimensions">', "iter-<n>/reviewer-<id>.md",
                       "police grounding in every slice",
                       "`mermaid_lint.py` only when dimension 4 is yours",
                       "`structure_lint.py` only when dimension 9 is yours"):
            self.assertIn(phrase, body)


class CreateTechDesignFanOutTest(JudgeSlicingMixin, unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # ADR-0135: the procedure moved into references/ behind pointers, so
        # the pins read the skill's contract text, not which file says it.
        cls.skill = skill_text.skill_contract("create-tech-design")
        cls.flat = flat(cls.skill)
        cls.designer = read(os.path.join(AGENTS, "create-tech-design-designer.md"))
        cls.reviewer = read(os.path.join(AGENTS, "create-tech-design-reviewer.md"))

    def test_option_research_partition_rule(self):
        for phrase in ("when the scope notes list two or more major decisions",
                       "One designer per major decision",
                       "The partition is by decision",
                       "a research slice researches ONLY its own decision",
                       "so the slices cannot overlap",
                       '<constraint name="decision">'):
            self.assertIn(phrase, self.flat)
        self.assertNotIn("research-<topic>", self.flat)

    def test_draft_stays_single_writer(self):
        self.assertIn("`tech-design.md` is ONE document and cannot be split into disjoint files",
                      self.flat)
        self.assertIn("the write never fans out", self.flat)

    def test_one_message_spawn_and_cap(self):
        self.assertIn("the SAME agent spawned N times in ONE message", self.flat)
        self.assertIn("at most `settings.parallel.max_agents` (default 4) instances per "
                      "message", self.flat)
        self.assertIn("waves of that size", self.flat)

    def test_notes_merge_join(self):
        self.assertIn('acs.py" notes merge', self.skill)
        self.assertIn("--out <partition>/steps/create-tech-design/iter-1/authoring.md", self.skill)
        self.assertIn("acs.py notes merge --out iter-<n>/reviewer.md", self.flat)

    def test_grouped_ask_across_passes(self):
        self.assertIn("in ONE grouped interaction", self.flat)

    def test_sliced_reviewer_pass_rule(self):
        for phrase in ("passes only if EVERY reviewer slice returned "
                       '`status="completed"` with zero blocking findings',
                       "any slice's blocking finding blocks",
                       "ALL slices' findings go verbatim",
                       'never "pass with a missing slice"'):
            self.assertIn(phrase, self.flat)

    def test_reviewer_dimension_slices(self):
        rows = slice_table(self.skill, "decision")
        self.assertEqual(set(rows), {"decision", "conformance", "form"})
        self.assertIn("lld-consistency", rows["conformance"])
        self.assert_dimensions_partitioned(rows, self.reviewer)
        self.assert_lint_in_one_slice(rows, "mermaid_lint.py", "form")
        self.assert_lint_in_one_slice(rows, "structure_lint.py", "form")

    def test_resume_reruns_only_missing_slices(self):
        self.assertIn("re-run ONLY the slices whose own report is missing", self.flat)

    def test_draft_designer_synthesizes_the_research(self):
        for phrase in ("so it MUST synthesize them, not just read their join",
                       "under a `## Synthesis` heading in `iter-1/authoring-synthesis.md`",
                       "never silently picks one",
                       "iter-1/authoring-synthesis.md`), so iteration 1's notes"):
            self.assertIn(phrase, self.flat)
        designer = flat(self.designer)
        self.assertIn("MUST synthesize them", designer)
        self.assertIn("never silently pick one", designer)

    def test_no_integration_pass_for_the_single_draft_writer(self):
        self.assertIn("with one writer there is no integration pass to run "
                      "(it is skipped when only one writer ran)", self.flat)

    def test_reviewer_findings_deduplicated(self):
        for phrase in ("drop a finding that cites the same location and the same defect "
                       "as another slice's finding",
                       "keeping the higher severity",
                       "append a `## De-duplicated findings` section"):
            self.assertIn(phrase, self.flat)

    def test_designer_slice_contract(self):
        body = flat(self.designer)
        self.assertIn("## Which pass you run", self.designer)
        for phrase in ("iter-1/authoring-scope.md", "iter-1/authoring-<id>.md",
                       "iter-<n>/designer-<id>.json", 'phase="designer" slice="<id>"'):
            self.assertIn(phrase, body)
        self.assertNotIn("designer-<K>", body)

    def test_reviewer_slice_contract(self):
        section = self.reviewer.split("## When you are one slice", 1)[1].split("\n## ", 1)[0]
        body = flat(section)
        for phrase in ('<constraint name="dimensions">', "iter-<n>/reviewer-<id>.md",
                       "police grounding in every slice",
                       "`mermaid_lint.py` only when dimension 5 (`completeness`) is yours",
                       "`structure_lint.py` only when dimension 6 (`structure`) is yours"):
            self.assertIn(phrase, body)


if __name__ == "__main__":
    unittest.main()
