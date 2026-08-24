"""MAR-163 spec 01 — reconcile stale create-spec references in prd.md.

Falsifiable pin for the ADR-0066 retirement of /acs:create-spec (spec
authoring folded into /code's plan phase) plus the docs-sync ownership
extraction (ADR 0007's second amendment): prd.md's pipeline ladder, seat
table, G38/G39 goal cells, delivery-lane descriptions, the retired
stakes-bump promotion item, and the three conformance-chain statements no
longer name the deleted skill or the retired formats.spec_template key,
while the two frozen historical survivors (the G1 M2-0-spike evidence line
and the v0.1 skill-roster snapshot line) are preserved verbatim. Cross-pins
the doc claims against the settings schema and the docs-sync/code agent
files so the doc and the code cannot silently re-diverge.

Per clarification C-11, prd.md's four lane-neutral "15-dimension" cells
(:172, :177, :268, :606) are intentionally NOT scanned here — they are
correct as written and pinned green by
tests/acs/test_code_verifier_multi_lens.py's PrdDimensionConsistencyTest.

Stdlib-only (os, unittest). Run:
  python3 -m unittest tests.acs.test_prd_create_spec_references_retired -v
"""

import os
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PRD = os.path.join(REPO_ROOT, "docs", "product", "prd.md")
SETTINGS_SCHEMA = os.path.join(REPO_ROOT, "plugins", "acs", "schemas", "settings.schema.json")
DOCS_SYNC_EXECUTOR = os.path.join(REPO_ROOT, "plugins", "acs", "agents", "docs-sync-executor.md")
CODE_SKILL = os.path.join(REPO_ROOT, "plugins", "acs", "skills", "code", "SKILL.md")
SKILLS_DIR = os.path.join(REPO_ROOT, "plugins", "acs", "skills")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class PrdCreateSpecTwoSurvivorsTest(unittest.TestCase):
    """AC-7 gate. Exactly the two frozen historical create-spec references
    survive (C-4); no line number is asserted, since every edit above them
    shifts what follows (spec Decision D2) — each survivor is pinned by an
    anchor substring instead."""

    ANCHOR_A = "gate advanced exactly one step"  # G1's M2-0-spike evidence line, frozen (C-15)
    ANCHOR_B = "6 workflow (`create-design`, `create-spec`,"  # v0.1 skill-roster snapshot, frozen (C-4)

    @classmethod
    def setUpClass(cls):
        cls.hits = [line for line in read(PRD).splitlines() if "create-spec" in line]

    def test_exactly_two_survivors(self):
        self.assertEqual(len(self.hits), 2)

    def test_survivor_a_present(self):
        self.assertEqual(sum(1 for h in self.hits if self.ANCHOR_A in h), 1)

    def test_survivor_b_present(self):
        self.assertEqual(sum(1 for h in self.hits if self.ANCHOR_B in h), 1)


class PrdPipelineLadderTest(unittest.TestCase):
    """AC-1. The pipeline-order description names the shipped topology, in
    order, with no create-spec step."""

    @classmethod
    def setUpClass(cls):
        body = read(PRD)
        start = body.index("Today the pipeline runs the full")
        end = body.index("on **every** ticket", start) + len("on **every** ticket")
        cls.slice = body[start:end]

    def test_no_create_spec(self):
        self.assertNotIn("create-spec", self.slice)

    def test_steps_in_order(self):
        steps = ["create-ticket", "create-design", "code", "test", "docs-sync", "create-pr", "merge-pr"]
        indices = [self.slice.index(step) for step in steps]
        self.assertEqual(indices, sorted(indices))


class PrdAiProductBuilderRowTest(unittest.TestCase):
    """AC-2. The seat table's AI Product Builder row names /acs:code and
    /acs:docs-sync, not /acs:create-spec; G8's skill count stays cross-pinned
    against reality."""

    @classmethod
    def setUpClass(cls):
        cls.rows = [l for l in read(PRD).splitlines() if l.startswith("| **AI Product Builder**")]

    def test_row_unique(self):
        self.assertEqual(len(self.rows), 1)

    def test_row_names_code_and_docs_sync(self):
        row = self.rows[0]
        self.assertIn("/acs:code", row)
        self.assertIn("/acs:docs-sync", row)
        self.assertNotIn("/acs:create-spec", row)

    def test_skill_count_cross_pin(self):
        self.assertEqual(len(os.listdir(SKILLS_DIR)), 24)
        self.assertIn("**24**", read(PRD))


class PrdDeliveryLanesTest(unittest.TestCase):
    """AC-3. The TRIVIAL/STANDARD lane bullets no longer mention create-spec
    and describe the spec-authoring fold as universal across every lane."""

    @classmethod
    def setUpClass(cls):
        body = read(PRD)
        start = body.index("Four delivery lanes")
        end = body.index("**High-stakes floor:**", start)
        cls.slice = body[start:end]

    def test_no_create_spec(self):
        self.assertNotIn("create-spec", self.slice)

    def test_fold_described_as_universal(self):
        self.assertIn("universal", self.slice)


class PrdNoDivergenceMentionTest(unittest.TestCase):
    """AC-4 (C-5). No line pairs create-spec with a divergence mention —
    discharged by asserted absence, not a prose edit; a future regression
    that reintroduces such a line fails this test."""

    def test_no_line_has_both(self):
        for line in read(PRD).splitlines():
            if "create-spec" in line:
                self.assertNotIn("diverg", line)


class PrdStakesBumpRetiredTest(unittest.TestCase):
    """AC-5. The create-spec-planner stakes-bump promotion item is retired in
    place, naming ADR 0066, with no create-spec token surviving."""

    @classmethod
    def setUpClass(cls):
        body = read(PRD)
        start = body.index("stakes-bump")
        end = body.index("- **Headless unattended runner**", start)
        cls.slice = body[start:end]

    def test_no_create_spec(self):
        self.assertNotIn("create-spec", self.slice)

    def test_marked_retired(self):
        self.assertIn("retired", self.slice.lower())

    def test_names_adr_0066(self):
        self.assertIn("0066", self.slice)


class PrdG38AudienceStyleTest(unittest.TestCase):
    """AC-6 (C-8/C-9/D1). G38's goal row and feature bullet land the shipped
    blocking audience-style dimension and the docs-sync citation-extraction
    clause, without the retired create-spec/spec_template tokens."""

    @classmethod
    def setUpClass(cls):
        body = read(PRD)
        row_start = body.index("| G38 —")
        cls.row = body[row_start:body.index("\n", row_start)]
        bullet_start = body.index("- **Readable, audience-aware generated docs")
        bullet_end = body.index("- **Configurable design templates", bullet_start)
        cls.bullet = body[bullet_start:bullet_end]

    def test_row_no_retired_tokens(self):
        self.assertNotIn("create-spec", self.row)
        self.assertNotIn("spec_template", self.row)

    def test_bullet_no_retired_tokens(self):
        self.assertNotIn("create-spec", self.bullet)
        self.assertNotIn("spec_template", self.bullet)

    def test_row_and_bullet_name_docs_sync(self):
        self.assertIn("docs-sync", self.row)
        self.assertIn("docs-sync", self.bullet)


class PrdG39DesignTemplateTest(unittest.TestCase):
    """AC-6 (C-7/D1). G39's goal row, feature bullet, and the C-24 constraint
    are narrowed to the design-template half only, with the retirement fact
    (ADR 0066) pinned present rather than merely inferred from an absence."""

    @classmethod
    def setUpClass(cls):
        body = read(PRD)
        row_start = body.index("| G39 —")
        cls.row = body[row_start:body.index("\n", row_start)]
        bullet_start = body.index("- **Configurable design templates")
        bullet_end = body.index("**Could have**", bullet_start)
        cls.bullet = body[bullet_start:bullet_end]
        c24_start = body.index("configurable design templates mirror `pr_description_template`")
        c24_end = body.index("\n", body.index("Serves **G39**.", c24_start))
        cls.c24 = body[c24_start:c24_end]

    def test_no_retired_tokens(self):
        for slice_ in (self.row, self.bullet, self.c24):
            self.assertNotIn("create-spec", slice_)
            self.assertNotIn("spec_template", slice_)

    def test_design_template_and_adr_present(self):
        for slice_ in (self.row, self.bullet, self.c24):
            self.assertIn("design_template", slice_)
            self.assertIn("0066", slice_)

    def test_schema_cross_pin(self):
        schema = read(SETTINGS_SCHEMA)
        self.assertNotIn("spec_template", schema)
        self.assertIn("design_template", schema)

    def test_sidecar_cross_pin(self):
        self.assertIn(".evidence.md", read(DOCS_SYNC_EXECUTOR))
        self.assertNotIn(".evidence.md", read(CODE_SKILL))


class PrdConformanceChainTest(unittest.TestCase):
    """C-6(b). The three conformance-chain statements drop the stale
    "-> specs" hop, matching the canonical chain
    (contracts.md:137, workflow.md:286). Per C-11, the sibling "15-dimension"
    drift claim is NOT reconciled here — those four cells are correct as
    written and stay out of this test's scope."""

    def test_no_chain_arrow_to_specs(self):
        body = read(PRD)
        self.assertNotIn("→ specs", body)
        self.assertNotIn("specs →", body)


class PrdSpecTemplateTokenGoneTest(unittest.TestCase):
    """D1. The retired settings key spec_template is absent from prd.md at
    file scope — forces all three sites (G39 row, G39 bullet, C-24) edited,
    not just the ones a narrower slice-scoped check would catch."""

    def test_spec_template_absent(self):
        self.assertNotIn("spec_template", read(PRD))


if __name__ == "__main__":
    unittest.main()
