"""Tests for acs_lib's doc-bootstrap fan-out deterministic layer: the declared
dependency table, the sentinel-file doc-set presence predicate, and the pure
fanout_batches eligibility/batching helper (D4/D4.1/D4.2/D4.3).
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
sys.path.insert(0, SCRIPTS)

import acs_lib as lib  # noqa: E402

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

SCHEMA_PATH = os.path.join(REPO_ROOT, "plugins", "acs", "schemas", "pipeline-state.schema.json")

# v1 scope only: principles/standards deliberately unconfigured so the
# eligible set is exactly the pair (D7-A).
PAIR_SETTINGS = {
    "quality_path": "docs/quality",
    "operations_path": "docs/operations",
    "principles_path": None,
    "standards_path": None,
}

# All four doc-bootstrap paths configured, for exercising the soft-edge
# batching rule between create-standards and create-principles.
ALL_SETTINGS = {
    "quality_path": "docs/quality",
    "operations_path": "docs/operations",
    "principles_path": "docs/principles",
    "standards_path": "docs/standards",
}


def _touch(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").close()


def _ticket(title, ttype="task", status="open"):
    return {"title": title, "type": ttype, "status": status}


class DocSetPresentOnDiskTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_present_when_sentinel_file_exists(self):
        _touch(os.path.join(self.root, "docs/quality/test-strategy.md"))
        self.assertTrue(lib.doc_set_present_on_disk(self.root, PAIR_SETTINGS, "create-quality"))

    def test_absent_when_directory_exists_but_sentinel_missing(self):
        # This repo's own live case (design.md D4.2): a populated directory
        # that never actually produced the skill's own output file.
        _touch(os.path.join(self.root, "docs/quality/README.md"))
        self.assertFalse(lib.doc_set_present_on_disk(self.root, PAIR_SETTINGS, "create-quality"))

    def test_absent_when_path_unconfigured(self):
        _touch(os.path.join(self.root, "docs/quality/test-strategy.md"))
        settings = dict(PAIR_SETTINGS, quality_path=None)
        self.assertFalse(lib.doc_set_present_on_disk(self.root, settings, "create-quality"))

    def test_absent_when_checkout_root_missing(self):
        missing_root = os.path.join(self.root, "does-not-exist")
        self.assertFalse(lib.doc_set_present_on_disk(missing_root, PAIR_SETTINGS, "create-quality"))


class DeclaredDependencyTest(unittest.TestCase):
    """AC-5: the dependency is declared in a table, not inferred, and a soft
    edge only ever constrains batching, never eligibility on its own."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_all_hard_lists_are_empty_today(self):
        for skill, deps in lib.DOC_BOOTSTRAP_DEPENDENCIES.items():
            with self.subTest(skill=skill):
                self.assertEqual(deps["hard"], [])

    def test_standards_declares_soft_edge_on_principles(self):
        self.assertEqual(
            lib.DOC_BOOTSTRAP_DEPENDENCIES["create-standards"]["soft"], ["create-principles"])

    def test_settings_key_resolved_via_explicit_map_not_string_building(self):
        # Every doc-bootstrap skill has its own explicit-map entry -- proof
        # the settings-key lookup goes through DOC_BOOTSTRAP_SETTINGS_KEY
        # rather than being derived from the skill name (e.g. "create-quality"
        # -> "quality_path" is not "create-quality_path").
        for skill in lib.DOC_BOOTSTRAP_DEPENDENCIES:
            with self.subTest(skill=skill):
                self.assertIn(skill, lib.DOC_BOOTSTRAP_SETTINGS_KEY)
                self.assertIn(skill, lib.DOC_BOOTSTRAP_SENTINEL)
                self.assertFalse(lib.DOC_BOOTSTRAP_SETTINGS_KEY[skill].startswith(skill))

    def test_standards_and_principles_never_share_a_batch(self):
        # General-case semantics (AC-5): explicit candidates, since v1's
        # default gate excludes both of these skills (finding 2).
        batches = lib.fanout_batches(
            ALL_SETTINGS, {"tickets": {}}, self.root,
            candidates=sorted(lib.DOC_BOOTSTRAP_DEPENDENCIES))
        for batch in batches:
            self.assertFalse({"create-standards", "create-principles"} <= set(batch))

    def test_soft_edge_alone_never_makes_a_candidate_ineligible(self):
        batches = lib.fanout_batches(
            ALL_SETTINGS, {"tickets": {}}, self.root,
            candidates=sorted(lib.DOC_BOOTSTRAP_DEPENDENCIES))
        flat = [skill for batch in batches for skill in batch]
        self.assertIn("create-standards", flat)
        self.assertIn("create-principles", flat)


class SoftEdgeSymmetryTest(unittest.TestCase):
    """Finding 1: the soft-edge batching constraint must be UNDIRECTED -- it
    holds regardless of which side declares it and regardless of table order,
    not merely because of today's insertion order (AC-5)."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_reversed_soft_declaration_still_never_shares_a_batch(self):
        # Edge declared on create-principles instead of create-standards,
        # with the declaring side processed first -- exposes a check that
        # only ever consults the CURRENT candidate's own declared list.
        reversed_deps = {
            "create-principles": {"hard": [], "soft": ["create-standards"]},
            "create-standards": {"hard": [], "soft": []},
        }
        with mock.patch.dict(lib.DOC_BOOTSTRAP_DEPENDENCIES, reversed_deps, clear=True):
            batches = lib.fanout_batches(
                ALL_SETTINGS, {"tickets": {}}, self.root,
                candidates=list(lib.DOC_BOOTSTRAP_DEPENDENCIES))
        for batch in batches:
            self.assertFalse({"create-standards", "create-principles"} <= set(batch))

    def test_soft_edge_invariant_survives_table_reordering(self):
        # Same declaration direction as production (standards -> principles),
        # but the table's insertion order -- and hence candidates order -- is
        # reversed relative to production (standards processed first).
        reordered_deps = {
            "create-standards": {"hard": [], "soft": ["create-principles"]},
            "create-principles": {"hard": [], "soft": []},
        }
        with mock.patch.dict(lib.DOC_BOOTSTRAP_DEPENDENCIES, reordered_deps, clear=True):
            batches = lib.fanout_batches(
                ALL_SETTINGS, {"tickets": {}}, self.root,
                candidates=list(lib.DOC_BOOTSTRAP_DEPENDENCIES))
        for batch in batches:
            self.assertFalse({"create-standards", "create-principles"} <= set(batch))

    def test_symmetric_check_never_makes_either_side_ineligible(self):
        # Guard against over-correcting the symmetry fix into an eligibility
        # filter: both sides must still land in SOME batch.
        reversed_deps = {
            "create-principles": {"hard": [], "soft": ["create-standards"]},
            "create-standards": {"hard": [], "soft": []},
        }
        with mock.patch.dict(lib.DOC_BOOTSTRAP_DEPENDENCIES, reversed_deps, clear=True):
            batches = lib.fanout_batches(
                ALL_SETTINGS, {"tickets": {}}, self.root,
                candidates=list(lib.DOC_BOOTSTRAP_DEPENDENCIES))
        flat = [skill for batch in batches for skill in batch]
        self.assertIn("create-standards", flat)
        self.assertIn("create-principles", flat)


class V1FanoutGateTest(unittest.TestCase):
    """Finding 2: fanout_batches defaults to the declared v1 fan-out set
    (DOC_BOOTSTRAP_FANOUT_V1), not every configured doc-bootstrap skill; the
    general case stays reachable via an explicit candidates argument, and an
    unknown candidate name is skipped rather than raised."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_declared_v1_set_is_exactly_the_pair(self):
        self.assertEqual(lib.DOC_BOOTSTRAP_FANOUT_V1, ("create-quality", "create-operations"))

    def test_default_batch_excludes_non_v1_skills_even_when_configured_and_unshipped(self):
        batches = lib.fanout_batches(ALL_SETTINGS, {"tickets": {}}, self.root)
        flat = [skill for batch in batches for skill in batch]
        self.assertEqual(sorted(flat), ["create-operations", "create-quality"])

    def test_explicit_candidates_argument_covers_the_general_case(self):
        batches = lib.fanout_batches(
            ALL_SETTINGS, {"tickets": {}}, self.root,
            candidates=sorted(lib.DOC_BOOTSTRAP_DEPENDENCIES))
        flat = [skill for batch in batches for skill in batch]
        self.assertEqual(sorted(flat), sorted(lib.DOC_BOOTSTRAP_DEPENDENCIES))

    def test_unknown_candidate_name_is_skipped_not_raised(self):
        batches = lib.fanout_batches(
            PAIR_SETTINGS, {"tickets": {}}, self.root,
            candidates=["create-quality", "not-a-skill"])
        self.assertEqual(batches, [["create-quality"]])


class FanoutBatchesTest(unittest.TestCase):
    """AC-1: the pair batches together exactly when both are configured,
    unshipped, and have no open delivery ticket."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_pair_batched_when_configured_unshipped_and_no_open_ticket(self):
        batches = lib.fanout_batches(PAIR_SETTINGS, {"tickets": {}}, self.root)
        self.assertIn(["create-quality", "create-operations"], batches)

    def test_shipped_doc_set_makes_skill_ineligible(self):
        _touch(os.path.join(self.root, "docs/quality/test-strategy.md"))
        batches = lib.fanout_batches(PAIR_SETTINGS, {"tickets": {}}, self.root)
        flat = [skill for batch in batches for skill in batch]
        self.assertNotIn("create-quality", flat)
        self.assertIn("create-operations", flat)

    def test_open_delivery_ticket_makes_skill_ineligible(self):
        tickets_index = {
            "tickets": {"MAR-1": _ticket(lib.DELIVERY_TICKET_TITLES["create-quality"])},
        }
        batches = lib.fanout_batches(PAIR_SETTINGS, tickets_index, self.root)
        flat = [skill for batch in batches for skill in batch]
        self.assertNotIn("create-quality", flat)
        self.assertIn("create-operations", flat)

    def test_done_delivery_ticket_does_not_block_eligibility(self):
        tickets_index = {
            "tickets": {
                "MAR-1": _ticket(lib.DELIVERY_TICKET_TITLES["create-quality"], status="done"),
            },
        }
        batches = lib.fanout_batches(PAIR_SETTINGS, tickets_index, self.root)
        flat = [skill for batch in batches for skill in batch]
        self.assertIn("create-quality", flat)

    def test_unconfigured_path_is_never_eligible(self):
        settings = dict(PAIR_SETTINGS, operations_path=None)
        batches = lib.fanout_batches(settings, {"tickets": {}}, self.root)
        flat = [skill for batch in batches for skill in batch]
        self.assertNotIn("create-operations", flat)


class PipelineStateSchemaProductStepsTest(unittest.TestCase):
    """BS-1 (AC-4 area): the steps enum must accept the product-level step
    names acs_lib.update_pipeline already writes for flow: "product" runs."""

    PRODUCT_STEP_NAMES = [
        "create-quality", "create-operations", "create-principles",
        "create-standards", "create-requirements",
    ]

    def setUp(self):
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            self.schema = json.load(fh)

    def test_enum_includes_every_product_level_step_name(self):
        enum = self.schema["properties"]["steps"]["propertyNames"]["enum"]
        for name in self.PRODUCT_STEP_NAMES:
            with self.subTest(name=name):
                self.assertIn(name, enum)

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed in this env")
    def test_schema_accepts_a_product_flow_document_with_these_steps(self):
        document = {
            "ticket_id": "MAR-101",
            "flow": "product",
            "steps": {
                name: {"status": "completed"} for name in self.PRODUCT_STEP_NAMES
            },
        }
        validator = jsonschema.Draft202012Validator(self.schema)
        errors = list(validator.iter_errors(document))
        self.assertEqual(errors, [], "pipeline-state schema errors: %r" % (errors,))
