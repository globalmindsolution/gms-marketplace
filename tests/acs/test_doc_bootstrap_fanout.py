"""Tests for acs_lib's doc-bootstrap fan-out deterministic layer: the declared
dependency table, the sentinel-file doc-set presence predicate, and the pure
fanout_batches eligibility/batching helper (D4/D4.1/D4.2/D4.3).
"""

import json
import os
import shutil
import subprocess
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

    def test_declared_fanout_set_is_all_four_doc_legs(self):
        # The design-phase consolidation widened the declared eligible set to
        # every doc-bootstrap leg (ONE constant edit; the other three tables
        # already covered four). The v1 pair assertion this replaces was true
        # only while /acs:create-quality and /acs:create-operations were the
        # sole user-facing doc commands.
        self.assertEqual(
            lib.DOC_BOOTSTRAP_FANOUT_V1,
            ("create-quality", "create-operations", "create-principles", "create-standards"))
        self.assertEqual(sorted(lib.DOC_BOOTSTRAP_FANOUT_V1),
                         sorted(lib.DOC_BOOTSTRAP_DEPENDENCIES))

    def test_default_batch_covers_every_configured_unshipped_leg(self):
        batches = lib.fanout_batches(ALL_SETTINGS, {"tickets": {}}, self.root)
        flat = [skill for batch in batches for skill in batch]
        self.assertEqual(sorted(flat), ["create-operations", "create-principles",
                                        "create-quality", "create-standards"])

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


class ForFlagParsingTest(unittest.TestCase):
    """Finding 1: parse_fanout_for_arg partitions /acs:create-docs's legacy
    `--for` argument against the declared fan-out set BEFORE fanout_batches
    ever sees the request, so a name outside DOC_BOOTSTRAP_FANOUT_V1 is
    rejected, never silently skipped. Since the design-phase consolidation the
    declared set is all four legs, so only a name that is no doc set at all is
    rejected here."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_no_flag_returns_none_candidates(self):
        for args_text in ("", None):
            with self.subTest(args_text=args_text):
                self.assertEqual(lib.parse_fanout_for_arg(args_text), (None, []))

    def test_single_v1_name_is_accepted(self):
        self.assertEqual(
            lib.parse_fanout_for_arg("--for create-quality"), (["create-quality"], []))

    def test_comma_list_order_preserved(self):
        self.assertEqual(
            lib.parse_fanout_for_arg("--for create-quality,create-operations"),
            (["create-quality", "create-operations"], []))

    def test_every_doc_leg_is_now_an_accepted_for_name(self):
        # Was: create-principles is rejected as "not in v1's fan-out set".
        # The consolidation widened the declared set to all four legs, so each
        # one is accepted -- the rejection path below now only fires for a
        # name that is no doc set at all.
        for skill in lib.DOC_BOOTSTRAP_FANOUT_V1:
            with self.subTest(skill=skill):
                self.assertEqual(lib.parse_fanout_for_arg("--for %s" % skill), ([skill], []))

    def test_short_set_spelling_is_canonicalized(self):
        self.assertEqual(
            lib.parse_fanout_for_arg("--for principles"), (["create-principles"], []))

    def test_unknown_name_is_rejected(self):
        self.assertEqual(
            lib.parse_fanout_for_arg("--for not-a-skill"), ([], ["not-a-skill"]))

    def test_mixed_request_splits_candidates_and_rejected(self):
        self.assertEqual(
            lib.parse_fanout_for_arg("--for create-quality,not-a-skill"),
            (["create-quality"], ["not-a-skill"]))

    def test_whitespace_around_commas_never_drops_a_name(self):
        self.assertEqual(
            lib.parse_fanout_for_arg("--for  create-quality , create-operations "),
            (["create-quality", "create-operations"], []))

    def test_equals_form(self):
        self.assertEqual(
            lib.parse_fanout_for_arg("--for=create-operations"), (["create-operations"], []))

    def test_bare_flag_is_explicit_empty_selection(self):
        self.assertEqual(lib.parse_fanout_for_arg("--for"), ([], []))

    def test_unrelated_for_prefixed_flag_never_mistaken(self):
        self.assertEqual(lib.parse_fanout_for_arg("--for-ticket MAR-9"), (None, []))

    def test_name_list_stops_at_the_next_flag(self):
        self.assertEqual(
            lib.parse_fanout_for_arg("--for create-quality --verbose"),
            (["create-quality"], []))

    def test_duplicate_names_are_deduplicated(self):
        self.assertEqual(
            lib.parse_fanout_for_arg("--for create-quality,create-quality"),
            (["create-quality"], []))

    def test_rejected_names_never_reach_fanout_batches(self):
        candidates, rejected = lib.parse_fanout_for_arg(
            "--for create-quality,not-a-skill")
        self.assertEqual(rejected, ["not-a-skill"])
        batches = lib.fanout_batches(
            PAIR_SETTINGS, {"tickets": {}}, self.root, candidates=candidates)
        flat = [skill for batch in batches for skill in batch]
        self.assertIn("create-quality", flat)
        self.assertNotIn("not-a-skill", flat)


class PositionalDocSetArgTest(unittest.TestCase):
    """The design-phase consolidation's argument contract for
    /acs:create-docs: a positional, comma-separated `<set|all>` selector,
    parsed in acs_lib beside parse_fanout_for_arg (never in skill prose). Both
    the short spelling (`quality`) and the full skill name (`create-quality`)
    resolve; an unknown set refuses the whole run with a message naming the
    accepted spellings; the legacy `--for` form still parses, once, with a
    deprecation notice for stderr."""

    ALL_LEGS = ["create-quality", "create-operations",
                "create-principles", "create-standards"]

    def test_no_argument_defers_to_the_declared_default(self):
        for args_text in ("", "   ", None):
            with self.subTest(args_text=args_text):
                request = lib.parse_doc_set_arg(args_text)
                self.assertIsNone(request.candidates)
                self.assertEqual(request.rejected, [])
                self.assertEqual(request.notices, [])

    def test_all_selects_every_declared_leg_in_declared_order(self):
        request = lib.parse_doc_set_arg("all")
        self.assertEqual(request.candidates, list(lib.DOC_BOOTSTRAP_FANOUT_V1))
        self.assertEqual(request.candidates, self.ALL_LEGS)
        self.assertEqual((request.rejected, request.notices), ([], []))

    def test_single_set(self):
        request = lib.parse_doc_set_arg("quality")
        self.assertEqual(request.candidates, ["create-quality"])
        self.assertEqual((request.rejected, request.notices), ([], []))

    def test_several_sets_comma_separated_order_preserved(self):
        request = lib.parse_doc_set_arg("standards,quality,operations")
        self.assertEqual(request.candidates,
                         ["create-standards", "create-quality", "create-operations"])
        self.assertEqual(request.rejected, [])

    def test_whitespace_and_duplicates_never_break_the_list(self):
        request = lib.parse_doc_set_arg(" quality , quality ,operations ")
        self.assertEqual(request.candidates, ["create-quality", "create-operations"])

    def test_create_prefixed_spelling_resolves_to_the_same_leg(self):
        for token in ("create-quality", "create-operations",
                      "create-principles", "create-standards"):
            with self.subTest(token=token):
                self.assertEqual(lib.parse_doc_set_arg(token).candidates, [token])
        mixed = lib.parse_doc_set_arg("create-principles,standards")
        self.assertEqual(mixed.candidates, ["create-principles", "create-standards"])

    def test_unknown_set_is_refused_with_a_message_naming_the_spellings(self):
        request = lib.parse_doc_set_arg("qualtiy")
        self.assertEqual(request.rejected, ["qualtiy"])
        self.assertEqual(request.candidates, [],
                         "an unknown set refuses the whole run -- never a partial fan-out")
        joined = " ".join(request.notices)
        self.assertIn("qualtiy", joined)
        for spelling in ("all", "quality", "operations", "principles", "standards"):
            self.assertIn(spelling, joined,
                          "the refusal must name every accepted spelling")

    def test_an_unknown_set_beside_a_known_one_refuses_the_whole_run(self):
        request = lib.parse_doc_set_arg("quality,nope")
        self.assertEqual(request.rejected, ["nope"])
        self.assertEqual(request.candidates, [])

    def test_all_may_not_be_combined_with_a_set(self):
        request = lib.parse_doc_set_arg("all,quality")
        self.assertEqual(request.candidates, [])
        self.assertRegex(" ".join(request.notices), r"(?i)all.{0,40}(cannot|never) be combined")

    def test_legacy_for_form_still_parses_and_says_the_new_spelling_once(self):
        request = lib.parse_doc_set_arg("--for create-quality,create-operations")
        self.assertEqual(request.candidates, ["create-quality", "create-operations"])
        self.assertEqual(request.rejected, [])
        self.assertEqual(len(request.notices), 1,
                         "the deprecation note is said once, not per name")
        note = request.notices[0]
        self.assertIn("--for", note)
        self.assertRegex(note, r"(?i)deprecat|spelling now")

    def test_legacy_for_form_accepts_the_short_spelling_too(self):
        request = lib.parse_doc_set_arg("--for principles")
        self.assertEqual(request.candidates, ["create-principles"])
        self.assertEqual(len(request.notices), 1)

    def test_legacy_for_form_rejects_a_non_doc_set_name(self):
        request = lib.parse_doc_set_arg("--for not-a-skill")
        self.assertEqual(request.rejected, ["not-a-skill"])
        self.assertEqual(request.candidates, [])

    def test_bare_legacy_flag_selects_nothing_and_says_so(self):
        request = lib.parse_doc_set_arg("--for")
        self.assertEqual((request.candidates, request.rejected), ([], []))
        self.assertRegex(" ".join(request.notices), r"(?i)at least one")

    def test_candidates_feed_fanout_batches_unchanged(self):
        request = lib.parse_doc_set_arg("all")
        batches = lib.fanout_batches(
            ALL_SETTINGS, {"tickets": {}}, self.root, candidates=request.candidates)
        flat = [skill for batch in batches for skill in batch]
        self.assertEqual(sorted(flat), sorted(self.ALL_LEGS))

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.root, True)


class DeclaredBatchOrderTest(unittest.TestCase):
    """The widened fan-out set must still batch `create-principles` before
    `create-standards`, and that ordering must come from the declared soft
    edge in DOC_BOOTSTRAP_DEPENDENCIES -- not from a hard-coded name pair
    inside fanout_batches or from the skill's prose."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.root, True)

    def _batches(self, **kwargs):
        return lib.fanout_batches(ALL_SETTINGS, {"tickets": {}}, self.root, **kwargs)

    def test_principles_batches_before_standards_on_the_default_set(self):
        batches = self._batches()
        index = {skill: n for n, batch in enumerate(batches) for skill in batch}
        self.assertLess(index["create-principles"], index["create-standards"])

    def test_dropping_the_declared_soft_edge_puts_all_four_in_one_batch(self):
        # The anti-hard-code probe: with no soft edge declared, nothing may
        # keep principles and standards apart. A fanout_batches that special-
        # cased the pair (or an order baked into DOC_BOOTSTRAP_FANOUT_V1's
        # consumers) would still split them here and fail.
        edgeless = {skill: {"hard": [], "soft": []}
                    for skill in lib.DOC_BOOTSTRAP_DEPENDENCIES}
        with mock.patch.dict(lib.DOC_BOOTSTRAP_DEPENDENCIES, edgeless, clear=True):
            batches = self._batches()
        self.assertEqual(len(batches), 1, batches)
        self.assertEqual(sorted(batches[0]), sorted(lib.DOC_BOOTSTRAP_FANOUT_V1))

    def test_a_declared_edge_between_any_other_pair_splits_that_pair_instead(self):
        # Same probe from the other side: move the edge to quality/operations
        # and the split follows the table there, while principles/standards
        # -- no longer edged -- are free to share a batch.
        moved = {
            "create-quality": {"hard": [], "soft": ["create-operations"]},
            "create-operations": {"hard": [], "soft": []},
            "create-principles": {"hard": [], "soft": []},
            "create-standards": {"hard": [], "soft": []},
        }
        with mock.patch.dict(lib.DOC_BOOTSTRAP_DEPENDENCIES, moved, clear=True):
            batches = self._batches()
        for batch in batches:
            self.assertFalse({"create-quality", "create-operations"} <= set(batch))
        shared = [batch for batch in batches
                  if {"create-principles", "create-standards"} <= set(batch)]
        self.assertTrue(shared, batches)


class CheckoutRootResolutionTest(unittest.TestCase):
    """Finding 3: the Start snippet must resolve fanout_batches's
    checkout_root via lib.checkout_root(cwd), never the raw cwd -- otherwise
    a run started from a repo subdirectory reads an already-shipped doc set
    as absent and wrongly re-offers it."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.root, True)
        subprocess.run(["git", "init", "-q", self.root], check=True, capture_output=True)

    def test_shipped_doc_set_is_seen_from_a_subdirectory_only_via_checkout_root(self):
        _touch(os.path.join(self.root, "docs/quality/test-strategy.md"))
        sub = os.path.join(self.root, "sub", "dir")
        os.makedirs(sub)

        settings = {"quality_path": "docs/quality", "operations_path": "docs/operations"}

        # Buggy form: raw cwd (a subdirectory) is passed straight to
        # fanout_batches -- the sentinel file is looked up relative to the
        # subdirectory, so it is never found, and create-quality is wrongly
        # re-offered even though it already shipped.
        buggy = lib.fanout_batches(settings, {"tickets": {}}, sub)
        self.assertEqual(buggy, [["create-quality", "create-operations"]])

        # Fixed form: the Start snippet must resolve checkout_root(cwd) first.
        fixed = lib.fanout_batches(settings, {"tickets": {}}, lib.checkout_root(sub))
        self.assertEqual(fixed, [["create-operations"]])


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
