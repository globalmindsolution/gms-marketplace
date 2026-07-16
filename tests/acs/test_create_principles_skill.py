"""MAR-117 spec 02 — /acs:create-principles skill, triad, and hook wrappers.

Prose-contract unit tests scoped to the new create-principles surface that the
shared tests/acs/test_skill_contracts.py suite does not already cover:
the planner's ADR-0012 block, the docs-only Delivery staging, the D2
single-file Output contract, the D1 PRD+architecture-only Inputs & mode, and
the two hook shims. This test does NOT re-run MAR-115's cross-file
byte-identity check across all six planners — that invariant lives in
tests/acs/test_doc_consistency_step.py and already covers this new
planner once it exists; here we only confirm the new planner carries the
canonical block.

Stdlib-only (os, re, unittest), mirroring the bounded-window `section()`
technique from test_doc_consistency_step.py and
test_init_quality_path.py.

Run:  python3 -m unittest tests.acs.test_mar117_create_principles_skill -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SKILLS = os.path.join(PLUGIN, "skills")
AGENTS = os.path.join(PLUGIN, "agents")
HOOKS = os.path.join(PLUGIN, "hooks", "scripts")

SKILL_PATH = os.path.join(SKILLS, "create-principles", "SKILL.md")
PLANNER_PATH = os.path.join(AGENTS, "create-principles-planner.md")

CANONICAL_HEADING = "### Design-time doc-consistency step (ADR 0012)"


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


class Mar117PlannerAdr0012BlockCase(unittest.TestCase):
    """AC-2: the new planner carries the canonical ADR-0012 block, scoped to
    this one file (the cross-file byte-identity check is MAR-115's scope)."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(PLANNER_PATH)
        cls.block = section(cls.body, CANONICAL_HEADING)

    def test_canonical_heading_present(self):
        self.assertIn(CANONICAL_HEADING, self.body)

    def test_upstream_and_downstream_named(self):
        self.assertIn("upstream", self.block)
        self.assertIn("downstream", self.block)

    def test_gap_and_staleness_named(self):
        self.assertIn("gap", self.block)
        self.assertIn("staleness", self.block)

    def test_finding_shape_keys_present(self):
        keys = ["kind", "upstream", "downstream", "description", "recommendation"]
        for key in keys:
            self.assertIn('"%s"' % key, self.block, "missing shape key %s" % key)
        self.assertIn('"gap"', self.block)
        self.assertIn('"staleness"', self.block)

    def test_existing_output_channel_referenced(self):
        self.assertTrue(
            "<questions>" in self.block or "clarification ledger" in self.block,
            "canonical block does not reference the existing output channel",
        )

    def test_d4_lifecycle_three_clauses(self):
        self.assertIn("user decides", self.block)
        self.assertIn("executor updates", self.block)
        self.assertIn("verifier confirms", self.block)


class Mar117DeliveryDocsOnlyCase(unittest.TestCase):
    """AC-3: Delivery stages only principles_path/ and asserts docs-only;
    frontmatter carries disallowed-tools: Edit, NotebookEdit."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.delivery = section(cls.body, "## Delivery")

    def test_delivery_stages_only_principles_path(self):
        self.assertIn("principles_path", self.delivery)

    def test_delivery_asserts_docs_only(self):
        self.assertIn("docs-only", self.delivery)

    def test_frontmatter_disallowed_tools(self):
        fm = self.body.split("---\n", 2)[1]
        self.assertRegex(fm, r"(?m)^disallowed-tools: Edit, NotebookEdit$")


class Mar117OutputContractSingleFileCase(unittest.TestCase):
    """D2: Output contract names exactly one file, principles.md — no second
    row (not create-quality's two-file shape)."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.output = section(cls.body, "## Output contract")

    def test_names_principles_md(self):
        self.assertIn("principles.md", self.output)

    def test_no_second_file_row(self):
        self.assertNotIn("coverage-policy.md", self.output)
        self.assertNotIn("test-strategy.md", self.output)
        # exactly one markdown table row for a file (the header row plus one
        # data row) - count pipe-delimited rows referencing a .md file.
        file_rows = re.findall(r"^\|\s*`?[\w.-]+\.md`?\s*\|", self.output, re.MULTILINE)
        self.assertEqual(
            len(file_rows), 1,
            "Output contract table must name exactly one file row: %r" % file_rows,
        )


class Mar117InputsModeNoStandardsCase(unittest.TestCase):
    """D1: Inputs & mode names prd_path + architecture_path only, no
    standards cross-read."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.inputs = section(cls.body, "## Inputs & mode")

    def test_names_prd_path(self):
        self.assertIn("prd_path", self.inputs)

    def test_names_architecture_path(self):
        self.assertIn("architecture_path", self.inputs)

    def test_no_standards_path_key(self):
        self.assertNotIn("standards_path", self.inputs)

    def test_standards_only_named_as_negated_dependency(self):
        # standards/ may be named ONLY within the sentence stating there is no
        # cross-read on it (D1: create-principles is upstream of standards/,
        # no reverse read) - the section as a whole must carry that negation.
        self.assertIn("standards/", self.inputs)
        self.assertTrue(
            "NOT" in self.inputs or "no cross-read" in self.inputs,
            "section names standards/ without a no-cross-read negation",
        )


class Mar117HookShimsCase(unittest.TestCase):
    """AC-4: both hook shims are 2-line run_pre/run_post("create-principles")
    calls, mirroring pre-/post-create-quality.py."""

    def test_pre_hook_calls_run_pre(self):
        body = read(os.path.join(HOOKS, "pre-create-principles.py"))
        self.assertIn("from acs_lib import run_pre", body)
        self.assertIn('run_pre("create-principles")', body)

    def test_post_hook_calls_run_post(self):
        body = read(os.path.join(HOOKS, "post-create-principles.py"))
        self.assertIn("from acs_lib import run_post", body)
        self.assertIn('run_post("create-principles")', body)


if __name__ == "__main__":
    unittest.main()
