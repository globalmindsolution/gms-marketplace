"""MAR-118 spec 02 — /acs:create-standards skill, triad, and hook wrappers.

Prose-contract unit tests scoped to the new create-standards surface that the
shared tests/acs/test_skill_contracts.py suite does not already cover:
the planner's ADR-0012 block, the docs-only Delivery staging, the D2
three-file Output contract (inverse of MAR-117's single-file case), the D1
upstream principles_path/principles/ read (inverse of MAR-117's
no-standards-cross-read case) plus its graceful-degradation language, the
Start refusal guard scoped only to standards_path, and the two hook shims.
This test does NOT re-run MAR-115's cross-file byte-identity check across all
planners — that invariant lives in tests/acs/test_doc_consistency_step.py
and already covers this new planner once it exists; here we only confirm the
new planner carries the canonical block.

Stdlib-only (os, re, unittest), mirroring the bounded-window `section()`
technique from test_doc_consistency_step.py and
test_create_principles_skill.py.

Run:  python3 -m unittest tests.acs.test_mar118_create_standards_skill -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SKILLS = os.path.join(PLUGIN, "skills")
AGENTS = os.path.join(PLUGIN, "agents")
HOOKS = os.path.join(PLUGIN, "hooks", "scripts")

SKILL_PATH = os.path.join(SKILLS, "create-standards", "SKILL.md")
PLANNER_PATH = os.path.join(AGENTS, "create-standards-planner.md")

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


class Mar118PlannerAdr0012BlockCase(unittest.TestCase):
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


class Mar118DeliveryDocsOnlyCase(unittest.TestCase):
    """AC-3: Delivery stages only standards_path/ and asserts docs-only;
    frontmatter carries disallowed-tools: Edit, NotebookEdit."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.delivery = section(cls.body, "## Delivery")

    def test_delivery_stages_only_standards_path(self):
        self.assertIn("standards_path", self.delivery)

    def test_delivery_asserts_docs_only(self):
        self.assertIn("docs-only", self.delivery)

    def test_frontmatter_disallowed_tools(self):
        fm = self.body.split("---\n", 2)[1]
        self.assertRegex(fm, r"(?m)^disallowed-tools: Edit, NotebookEdit$")


class Mar118OutputContractThreeFilesCase(unittest.TestCase):
    """D2 (INVERSE of MAR-117's single-file case): Output contract names
    exactly three files -- coding-standards.md, conventions.md,
    review-checklist.md -- mirroring create-operations' multi-file shape,
    never a fourth file."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.output = section(cls.body, "## Output contract")

    def test_names_coding_standards_md(self):
        self.assertIn("coding-standards.md", self.output)

    def test_names_conventions_md(self):
        self.assertIn("conventions.md", self.output)

    def test_names_review_checklist_md(self):
        self.assertIn("review-checklist.md", self.output)

    def test_exactly_three_file_rows(self):
        # exactly three markdown table rows naming a .md file (the header
        # row plus three data rows) - count pipe-delimited rows referencing
        # a .md file, mirroring create-operations' multi-file shape.
        file_rows = re.findall(r"^\|\s*`?[\w.-]+\.md`?\s*\|", self.output, re.MULTILINE)
        self.assertEqual(
            len(file_rows), 3,
            "Output contract table must name exactly three file rows: %r" % file_rows,
        )

    def test_no_fourth_file_named(self):
        self.assertNotIn("principles.md", self.output)
        self.assertNotIn("release-process.md", self.output)
        self.assertNotIn("runbooks.md", self.output)


class Mar118InputsUpstreamPrinciplesCase(unittest.TestCase):
    """D1 (INVERSE of MAR-117's Mar117InputsModeNoStandardsCase): Inputs &
    mode names prd_path, architecture_path, AND principles_path/principles/
    as an upstream input -- the positive assertion, mirror image of
    MAR-117's negative one."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.inputs = section(cls.body, "## Inputs & mode")

    def test_names_prd_path(self):
        self.assertIn("prd_path", self.inputs)

    def test_names_architecture_path(self):
        self.assertIn("architecture_path", self.inputs)

    def test_names_principles_path_as_upstream(self):
        self.assertIn("principles_path", self.inputs)
        self.assertIn("principles/", self.inputs)


class Mar118GracefulDegradationCase(unittest.TestCase):
    """R-5: a null/absent principles_path makes the principles grounding
    step N/A and the run PROCEEDS -- never a hard block."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)

    def test_graceful_degradation_language_present(self):
        self.assertIsNotNone(
            re.search(
                r"(?s)principles_path.{0,600}(N/A|proceed|never a.{0,20}block)"
                r"|(N/A|proceed|never a.{0,20}block).{0,600}principles_path",
                self.body,
            ),
            "SKILL.md must co-locate a principles_path null/absent condition "
            "with N/A / proceed / never-a-block language",
        )


class Mar118StartRefusesOnlyOnStandardsCase(unittest.TestCase):
    """R-5: the Start section's refusal guard is keyed ONLY to
    standards_path == null, never to principles_path."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.start = section(cls.body, "## Start")

    def test_start_refuses_on_standards_path_null(self):
        self.assertIsNotNone(
            re.search(r"standards_path.{0,80}(is\s+)?`?null`?", self.start, re.DOTALL),
            "Start section must carry the settings.standards_path-null STOP guard",
        )
        self.assertIn("STOP", self.start)

    def test_start_does_not_refuse_on_principles_path(self):
        # Case-SENSITIVE "STOP" (the guard's imperative shape, e.g. "is
        # `null`: STOP") deliberately excludes the lowercase "do NOT refuse
        # or stop" negation sentence D1 requires nearby -- that sentence
        # explicitly states the guard does NOT apply to principles_path, so
        # it must not trip this negative check.
        self.assertIsNone(
            re.search(r"STOP.{0,120}principles_path.{0,40}null", self.start),
            "Start section must NOT carry a principles_path-keyed STOP guard",
        )
        self.assertIsNone(
            re.search(r"principles_path.{0,40}null.{0,120}STOP", self.start),
            "Start section must NOT carry a principles_path-keyed STOP guard",
        )


class Mar118HookShimsCase(unittest.TestCase):
    """AC-4: both hook shims are 2-line run_pre/run_post("create-standards")
    calls, mirroring pre-/post-create-principles.py."""

    def test_pre_hook_calls_run_pre(self):
        body = read(os.path.join(HOOKS, "pre-create-standards.py"))
        self.assertIn("from acs_lib import run_pre", body)
        self.assertIn('run_pre("create-standards")', body)

    def test_post_hook_calls_run_post(self):
        body = read(os.path.join(HOOKS, "post-create-standards.py"))
        self.assertIn("from acs_lib import run_post", body)
        self.assertIn('run_post("create-standards")', body)


if __name__ == "__main__":
    unittest.main()
