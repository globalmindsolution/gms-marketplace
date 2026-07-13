"""MAR-127 (E2E-3) — documentation-conformance guards for the read-only G13
e2e-integrity metric validation. spec 01's own deliverable is a validation
record plus doc reconciliation, not executable code (Decision E1); these are
the mechanically-checkable marker-presence + no-new-mechanism + ADR-indexed
guards named in spec 01's Test plan.

Run:  python3 -m unittest tests.acs.test_mar127_e2e_metric_docs -v
"""

import os
import re
import subprocess
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
PRD_PATH = os.path.join(REPO_ROOT, "docs", "product", "prd.md")
ROADMAP_PATH = os.path.join(REPO_ROOT, "docs", "product", "roadmap.md")
TESTING_STRATEGY_PATH = os.path.join(REPO_ROOT, "docs", "quality", "testing-strategy.md")
WORKFLOW_PATH = os.path.join(REPO_ROOT, "docs", "requirements", "workflow.md")
ADR_PATH = os.path.join(REPO_ROOT, "docs", "adr",
                        "0049-e2e-3-read-only-g13-metric-validation.md")
ADR_README_PATH = os.path.join(REPO_ROOT, "docs", "adr", "README.md")
METRICS_AGGREGATE_PATH = os.path.join(PLUGIN, "hooks", "scripts", "metrics_aggregate.py")
SETTINGS_SCHEMA_PATH = os.path.join(PLUGIN, "schemas", "settings.schema.json")
SKILLS_DIR = os.path.join(PLUGIN, "skills")
ARCHITECTURE_DIR = os.path.join(REPO_ROOT, "docs", "architecture")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def section(body, heading):
    m = re.search(r"(?m)^" + re.escape(heading) + r".*$", body)
    if m is None:
        raise AssertionError("heading %r not found" % heading)
    start = m.start()
    level = len(heading) - len(heading.lstrip("#"))
    nxt = re.search(r"(?m)^#{1,%d} \S" % level, body[m.end():])
    end = m.end() + nxt.start() if nxt else len(body)
    return body[start:end]


def find_line_containing(body, needle):
    for line in body.splitlines():
        if needle in line:
            return line
    raise AssertionError("no line found containing %r" % needle)


def _base_ref():
    """`origin/main` is preferred over a local `main`: a long-lived worktree's
    local `main` can go stale (as observed on this repo), and diffing against
    a stale base would fold already-merged sibling changes into the range,
    producing a false AC-3 failure."""
    for ref in ("origin/main", "main"):
        result = subprocess.run(
            ["git", "rev-parse", "--verify", ref],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        if result.returncode == 0:
            return ref
    return None


def range_diff_names(*paths):
    base = _base_ref()
    out = subprocess.run(
        ["git", "diff", "--name-only", "%s...HEAD" % base, "--", *paths],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    return out.stdout.strip()


class TestPrdG13Annotation(unittest.TestCase):
    """[AC-1, AC-2, AC-4] prd.md's G13 line carries an honest-state dogfood
    validation annotation."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(PRD_PATH)
        cls.line = find_line_containing(cls.body, "G13 — Enforceable e2e integrity")

    def test_prd_g13_has_dogfood_validation_marker(self):
        self.assertIn("First validated", self.line)
        self.assertIn("MAR-127", self.line)

    def test_annotation_states_gate_not_wired(self):
        self.assertIsNotNone(
            re.search(r"(?i)not.*wired", self.line),
            "the G13 annotation must state the gate is configured but not "
            "yet wired, not an unqualified pass",
        )

    def test_annotation_names_e2e_impact_mechanism(self):
        self.assertIn("code-verifier", self.line)
        self.assertIsNotNone(re.search(r"(?i)e2e[- ]impact", self.line))


class TestRoadmapValidatedMarker(unittest.TestCase):
    """[AC-4] roadmap.md's E2E-3 bullet is marked validated."""

    def test_e2e_integrity_wave_marked_validated(self):
        body = read(ROADMAP_PATH)
        line = find_line_containing(body, "E2E-3 — Measured e2e integrity")
        self.assertIsNotNone(re.search(r"(?i)validated", line))
        self.assertIn("MAR-127", line)


class TestNoNewMechanism(unittest.TestCase):
    """[AC-3] no new metrics mechanism, settings key, runtime-skill change,
    or architecture change ships with this spec (Decision E1)."""

    def setUp(self):
        # This guard diffs the changeset against origin/main. A shallow CI
        # checkout (actions/checkout fetch-depth 1, detached HEAD) resolves
        # neither origin/main nor main, so the guard runs where a base ref
        # exists (developer checkouts + the acs code-verifier) and skips —
        # rather than errors — in a base-less checkout.
        if _base_ref() is None:
            self.skipTest("no base ref (origin/main or main) to diff against")
        # This guard is scoped to MAR-127's OWN branch, where ADR 0049 is
        # part of the diff. On main (0049 already merged) or on any later
        # branch — e.g. MAR-129, which legitimately touches skills/**  and
        # docs/architecture/** for unrelated reasons — 0049 is not in the
        # diff, so the guard is inert rather than a false failure.
        if range_diff_names(ADR_PATH) == "":
            self.skipTest(
                "no-new-mechanism guard is scoped to MAR-127's own branch; "
                "this branch does not introduce ADR 0049")

    def test_metrics_aggregate_unchanged(self):
        self.assertEqual(range_diff_names(METRICS_AGGREGATE_PATH), "",
                          "metrics_aggregate.py must be unchanged (E2 rejected)")

    def test_settings_schema_unchanged(self):
        self.assertEqual(range_diff_names(SETTINGS_SCHEMA_PATH), "",
                          "settings.schema.json must gain no new key")

    def test_no_runtime_skill_touched(self):
        self.assertEqual(range_diff_names(SKILLS_DIR), "",
                          "no plugins/acs/skills/** file may change")

    def test_architecture_untouched(self):
        self.assertEqual(range_diff_names(ARCHITECTURE_DIR), "",
                          "no docs/architecture/** file may change")


class TestD1AttributionFix(unittest.TestCase):
    """[AC-5] prd.md no longer attributes e2e branch-protection wiring to
    /acs:standardize-project; /acs:init is named as the wiring owner; the
    OPT-IN invariant sentence is preserved verbatim."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(PRD_PATH)
        cls.sp_line = find_line_containing(
            cls.body, "brownfield standardization (separate from")
        cls.c2_line = find_line_containing(
            cls.body, "brownfield standardization is additive-only (C-2)")

    def test_standardize_project_bullet_no_longer_attributes_wiring(self):
        self.assertNotIn(
            "wiring it as a required e2e merge-gate status check", self.sp_line)

    def test_c2_constraint_no_longer_attributes_wiring(self):
        self.assertNotIn(
            "opt-in wiring of a required e2e merge-gate status check", self.c2_line)

    def test_init_named_as_wiring_owner(self):
        self.assertIn("/acs:init", self.sp_line)
        self.assertIn("/acs:init", self.c2_line)

    def test_optin_invariant_sentence_preserved(self):
        self.assertIn(
            "The e2e layer stays OPT-IN: a repo with `settings.e2e` unset "
            "has no e2e suite and no e2e merge gate; the gate is configured "
            "only on explicit opt-in.",
            self.body,
        )


class TestAdr0049(unittest.TestCase):
    """ADR 0049 for Decision E1 exists, is Accepted, and records E1 + the E2
    rejection rationale."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(ADR_PATH)

    def test_status_accepted(self):
        self.assertIn("**Status**: Accepted", self.body)

    def test_records_e1_and_e2_rejection(self):
        self.assertIsNotNone(re.search(r"(?i)read-only", self.body))
        self.assertIsNotNone(re.search(r"(?i)existing artifacts", self.body))
        self.assertIn("metrics_aggregate.py", self.body)
        self.assertIsNotNone(re.search(r"(?i)rejected|not built", self.body))


class TestAdrReadmeIndex(unittest.TestCase):
    """ADR 0049 is indexed in docs/adr/README.md."""

    def test_0049_row_present(self):
        body = read(ADR_README_PATH)
        m = re.search(r"(?m)^\| \[0049\].*$", body)
        self.assertIsNotNone(m, "docs/adr/README.md must have a row for ADR 0049")
        row = m.group(0)
        self.assertIn("0049-e2e-3-read-only-g13-metric-validation.md", row)
        self.assertIn("Accepted", row)


class TestTestingStrategyNote(unittest.TestCase):
    """[AC-1, AC-2, AC-6] the standing G13 validation-record home names both
    sub-metrics and the ticket that first ran the procedure."""

    def test_g13_procedure_note_present(self):
        body = read(TESTING_STRATEGY_PATH)
        sec = section(body, "## G13 e2e-integrity validation")
        self.assertIn("G13", sec)
        self.assertIn("MAR-127", sec)
        self.assertIsNotNone(re.search(r"(?i)sub-metric \(a\)", sec))
        self.assertIsNotNone(re.search(r"(?i)sub-metric \(b\)", sec))


class TestRequirementsWorkflowNote(unittest.TestCase):
    """[AC-4/AC-6 support] the living-requirements doc records the G13
    read-only validation, per the task's doc-map constraint."""

    def test_g13_readonly_note_present(self):
        body = read(WORKFLOW_PATH)
        self.assertIn("G13", body)
        self.assertIsNotNone(re.search(r"(?i)read-only", body))


if __name__ == "__main__":
    unittest.main()
