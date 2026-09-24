"""Tests for acs_lib's doc-bootstrap fan-out deterministic layer: the declared
dependency table and the pure fanout_batches eligibility/batching helper
(D4/D4.1/D4.3). Whether a set is already in the repo is the coordinator's
finding (`present`), not a disk probe of a configured path (ADR-0102).
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

SCHEMA_PATH = os.path.join(REPO_ROOT, "plugins", "acs", "schemas", "run.schema.json")

#: The pair, as an explicit request, for the tests that are about one pair.
PAIR = ["quality", "operations"]


def _ticket(title, ttype="task", status="open"):
    return {"title": title, "type": ttype, "status": status}


class PresentSetsTest(unittest.TestCase):
    """A set the coordinator found in the repo is not offered again, and a
    hard dependency is clear only when its set is present."""

    def test_a_present_set_is_not_eligible(self):
        batches = lib.fanout_batches({"tickets": {}}, candidates=PAIR, present=["quality"])
        self.assertEqual(batches, [["operations"]])

    def test_nothing_present_offers_every_candidate(self):
        batches = lib.fanout_batches({"tickets": {}}, candidates=PAIR)
        self.assertEqual(batches, [PAIR])

    def test_a_hard_dependency_is_clear_only_when_present(self):
        deps = {"quality": {"hard": ["operations"], "soft": []},
                "operations": {"hard": [], "soft": []}}
        with mock.patch.dict(lib.DOC_BOOTSTRAP_DEPENDENCIES, deps, clear=True):
            blocked = lib.fanout_batches({"tickets": {}}, candidates=PAIR)
            clear = lib.fanout_batches({"tickets": {}}, candidates=["quality"],
                                       present=["operations"])
        self.assertEqual(blocked, [["operations"]])
        self.assertEqual(clear, [["quality"]])

    def test_the_cli_takes_the_present_sets(self):
        out = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "acs.py"), "fanout", "batches", "--help"],
            capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("--present", out.stdout)


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
            lib.DOC_BOOTSTRAP_DEPENDENCIES["standards"]["soft"], ["principles"])

    def test_default_dir_resolved_via_the_declared_row(self):
        # Every doc set's default location is DECLARED on its DOC_SETS row and
        # the views are derived from it. It is where a NEW set is created; an
        # existing one is found, not configured (ADR-0102).
        for name in lib.DOC_BOOTSTRAP_DEPENDENCIES:
            with self.subTest(set=name):
                self.assertIn(name, lib.DOC_BOOTSTRAP_SENTINEL)
                self.assertEqual(lib.DOC_SET_DEFAULT_DIR[name],
                                 lib.DOC_SETS[name]["default_dir"])
                self.assertEqual(lib.DOC_SETS[name]["default_dir"], "docs/" + name)
                self.assertNotIn("settings_key", lib.DOC_SETS[name])

    def test_standards_and_principles_never_share_a_batch(self):
        # General-case semantics (AC-5): explicit candidates, since v1's
        # default gate excludes both of these skills (finding 2).
        batches = lib.fanout_batches({"tickets": {}},
            candidates=sorted(lib.DOC_BOOTSTRAP_DEPENDENCIES))
        for batch in batches:
            self.assertFalse({"standards", "principles"} <= set(batch))

    def test_soft_edge_alone_never_makes_a_candidate_ineligible(self):
        batches = lib.fanout_batches({"tickets": {}},
            candidates=sorted(lib.DOC_BOOTSTRAP_DEPENDENCIES))
        flat = [skill for batch in batches for skill in batch]
        self.assertIn("standards", flat)
        self.assertIn("principles", flat)


class SoftEdgeSymmetryTest(unittest.TestCase):
    """Finding 1: the soft-edge batching constraint must be UNDIRECTED -- it
    holds regardless of which side declares it and regardless of table order,
    not merely because of today's insertion order (AC-5)."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_reversed_soft_declaration_still_never_shares_a_batch(self):
        # Edge declared on principles instead of standards,
        # with the declaring side processed first -- exposes a check that
        # only ever consults the CURRENT candidate's own declared list.
        reversed_deps = {
            "principles": {"hard": [], "soft": ["standards"]},
            "standards": {"hard": [], "soft": []},
        }
        with mock.patch.dict(lib.DOC_BOOTSTRAP_DEPENDENCIES, reversed_deps, clear=True):
            batches = lib.fanout_batches({"tickets": {}},
                candidates=list(lib.DOC_BOOTSTRAP_DEPENDENCIES))
        for batch in batches:
            self.assertFalse({"standards", "principles"} <= set(batch))

    def test_soft_edge_invariant_survives_table_reordering(self):
        # Same declaration direction as production (standards -> principles),
        # but the table's insertion order -- and hence candidates order -- is
        # reversed relative to production (standards processed first).
        reordered_deps = {
            "standards": {"hard": [], "soft": ["principles"]},
            "principles": {"hard": [], "soft": []},
        }
        with mock.patch.dict(lib.DOC_BOOTSTRAP_DEPENDENCIES, reordered_deps, clear=True):
            batches = lib.fanout_batches({"tickets": {}},
                candidates=list(lib.DOC_BOOTSTRAP_DEPENDENCIES))
        for batch in batches:
            self.assertFalse({"standards", "principles"} <= set(batch))

    def test_symmetric_check_never_makes_either_side_ineligible(self):
        # Guard against over-correcting the symmetry fix into an eligibility
        # filter: both sides must still land in SOME batch.
        reversed_deps = {
            "principles": {"hard": [], "soft": ["standards"]},
            "standards": {"hard": [], "soft": []},
        }
        with mock.patch.dict(lib.DOC_BOOTSTRAP_DEPENDENCIES, reversed_deps, clear=True):
            batches = lib.fanout_batches({"tickets": {}},
                candidates=list(lib.DOC_BOOTSTRAP_DEPENDENCIES))
        flat = [skill for batch in batches for skill in batch]
        self.assertIn("standards", flat)
        self.assertIn("principles", flat)


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
        # only while /acs:quality and /acs:operations were the
        # sole user-facing doc commands.
        self.assertEqual(
            lib.DOC_BOOTSTRAP_FANOUT_V1,
            ("quality", "operations", "principles", "standards"))
        self.assertEqual(sorted(lib.DOC_BOOTSTRAP_FANOUT_V1),
                         sorted(lib.DOC_BOOTSTRAP_DEPENDENCIES))

    def test_default_batch_covers_every_configured_unshipped_leg(self):
        batches = lib.fanout_batches({"tickets": {}})
        flat = [skill for batch in batches for skill in batch]
        self.assertEqual(sorted(flat), ["operations", "principles",
                                        "quality", "standards"])

    def test_explicit_candidates_argument_covers_the_general_case(self):
        batches = lib.fanout_batches({"tickets": {}},
            candidates=sorted(lib.DOC_BOOTSTRAP_DEPENDENCIES))
        flat = [skill for batch in batches for skill in batch]
        self.assertEqual(sorted(flat), sorted(lib.DOC_BOOTSTRAP_DEPENDENCIES))

    def test_unknown_candidate_name_is_skipped_not_raised(self):
        batches = lib.fanout_batches({"tickets": {}},
            candidates=["quality", "not-a-skill"])
        self.assertEqual(batches, [["quality"]])


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
            lib.parse_fanout_for_arg("--for quality"), (["quality"], []))

    def test_the_former_leg_name_still_resolves_for_one_release(self):
        self.assertEqual(
            lib.parse_fanout_for_arg("--for create-quality"), (["quality"], []))
        self.assertEqual(lib.parse_doc_set_arg("create-standards,quality").candidates,
                         ["standards", "quality"])

    def test_a_delivery_ticket_id_is_a_resume_not_a_selection(self):
        request = lib.parse_doc_set_arg("SHOP-2")
        self.assertEqual(request.resume, "SHOP-2")
        self.assertIsNone(request.candidates)
        self.assertEqual(request.rejected, [])

    def test_an_open_ticket_matches_by_doc_set_or_title(self):
        by_field = {"tickets": {"MAR-1": {"title": "whatever", "type": "task",
                                          "status": "in_progress", "doc_set": "quality"}}}
        self.assertNotIn("quality", [s for b in lib.fanout_batches(by_field) for s in b])
        by_title = {"tickets": {"MAR-1": _ticket(lib.DOC_SET_TITLES["quality"])}}
        self.assertNotIn("quality", [s for b in lib.fanout_batches(by_title) for s in b])

    def test_comma_list_order_preserved(self):
        self.assertEqual(
            lib.parse_fanout_for_arg("--for quality,operations"),
            (["quality", "operations"], []))

    def test_every_doc_leg_is_now_an_accepted_for_name(self):
        # Was: principles is rejected as "not in v1's fan-out set".
        # The consolidation widened the declared set to all four legs, so each
        # one is accepted -- the rejection path below now only fires for a
        # name that is no doc set at all.
        for skill in lib.DOC_BOOTSTRAP_FANOUT_V1:
            with self.subTest(skill=skill):
                self.assertEqual(lib.parse_fanout_for_arg("--for %s" % skill), ([skill], []))

    def test_short_set_spelling_is_canonicalized(self):
        self.assertEqual(
            lib.parse_fanout_for_arg("--for principles"), (["principles"], []))

    def test_unknown_name_is_rejected(self):
        self.assertEqual(
            lib.parse_fanout_for_arg("--for not-a-skill"), ([], ["not-a-skill"]))

    def test_mixed_request_splits_candidates_and_rejected(self):
        self.assertEqual(
            lib.parse_fanout_for_arg("--for quality,not-a-skill"),
            (["quality"], ["not-a-skill"]))

    def test_whitespace_around_commas_never_drops_a_name(self):
        self.assertEqual(
            lib.parse_fanout_for_arg("--for  quality , operations "),
            (["quality", "operations"], []))

    def test_equals_form(self):
        self.assertEqual(
            lib.parse_fanout_for_arg("--for=operations"), (["operations"], []))

    def test_bare_flag_is_explicit_empty_selection(self):
        self.assertEqual(lib.parse_fanout_for_arg("--for"), ([], []))

    def test_unrelated_for_prefixed_flag_never_mistaken(self):
        self.assertEqual(lib.parse_fanout_for_arg("--for-ticket MAR-9"), (None, []))

    def test_name_list_stops_at_the_next_flag(self):
        self.assertEqual(
            lib.parse_fanout_for_arg("--for quality --verbose"),
            (["quality"], []))

    def test_duplicate_names_are_deduplicated(self):
        self.assertEqual(
            lib.parse_fanout_for_arg("--for quality,quality"),
            (["quality"], []))

    def test_rejected_names_never_reach_fanout_batches(self):
        candidates, rejected = lib.parse_fanout_for_arg(
            "--for quality,not-a-skill")
        self.assertEqual(rejected, ["not-a-skill"])
        batches = lib.fanout_batches({"tickets": {}}, candidates=candidates)
        flat = [skill for batch in batches for skill in batch]
        self.assertIn("quality", flat)
        self.assertNotIn("not-a-skill", flat)


class PositionalDocSetArgTest(unittest.TestCase):
    """The design-phase consolidation's argument contract for
    /acs:create-docs: a positional, comma-separated `<set|all>` selector,
    parsed in acs_lib beside parse_fanout_for_arg (never in skill prose). Both
    the short spelling (`quality`) and the former leg name (`create-quality`)
    resolve; an unknown set refuses the whole run with a message naming the
    accepted spellings; the legacy `--for` form still parses, once, with a
    deprecation notice for stderr."""

    ALL_LEGS = ["quality", "operations",
                "principles", "standards"]

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
        self.assertEqual(request.candidates, ["quality"])
        self.assertEqual((request.rejected, request.notices), ([], []))

    def test_several_sets_comma_separated_order_preserved(self):
        request = lib.parse_doc_set_arg("standards,quality,operations")
        self.assertEqual(request.candidates,
                         ["standards", "quality", "operations"])
        self.assertEqual(request.rejected, [])

    def test_whitespace_and_duplicates_never_break_the_list(self):
        request = lib.parse_doc_set_arg(" quality , quality ,operations ")
        self.assertEqual(request.candidates, ["quality", "operations"])

    def test_create_prefixed_spelling_resolves_to_the_same_leg(self):
        for token in ("quality", "operations",
                      "principles", "standards"):
            with self.subTest(token=token):
                self.assertEqual(lib.parse_doc_set_arg(token).candidates, [token])
        mixed = lib.parse_doc_set_arg("principles,standards")
        self.assertEqual(mixed.candidates, ["principles", "standards"])

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
        request = lib.parse_doc_set_arg("--for quality,operations")
        self.assertEqual(request.candidates, ["quality", "operations"])
        self.assertEqual(request.rejected, [])
        self.assertEqual(len(request.notices), 1,
                         "the deprecation note is said once, not per name")
        note = request.notices[0]
        self.assertIn("--for", note)
        self.assertRegex(note, r"(?i)deprecat|spelling now")

    def test_legacy_for_form_accepts_the_short_spelling_too(self):
        request = lib.parse_doc_set_arg("--for principles")
        self.assertEqual(request.candidates, ["principles"])
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
        batches = lib.fanout_batches({"tickets": {}}, candidates=request.candidates)
        flat = [skill for batch in batches for skill in batch]
        self.assertEqual(sorted(flat), sorted(self.ALL_LEGS))

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.root, True)


class DeclaredBatchOrderTest(unittest.TestCase):
    """The widened fan-out set must still batch `principles` before
    `standards`, and that ordering must come from the declared soft
    edge in DOC_BOOTSTRAP_DEPENDENCIES -- not from a hard-coded name pair
    inside fanout_batches or from the skill's prose."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.root, True)

    def _batches(self, **kwargs):
        return lib.fanout_batches({"tickets": {}}, **kwargs)

    def test_principles_batches_before_standards_on_the_default_set(self):
        batches = self._batches()
        index = {skill: n for n, batch in enumerate(batches) for skill in batch}
        self.assertLess(index["principles"], index["standards"])

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
            "quality": {"hard": [], "soft": ["operations"]},
            "operations": {"hard": [], "soft": []},
            "principles": {"hard": [], "soft": []},
            "standards": {"hard": [], "soft": []},
        }
        with mock.patch.dict(lib.DOC_BOOTSTRAP_DEPENDENCIES, moved, clear=True):
            batches = self._batches()
        for batch in batches:
            self.assertFalse({"quality", "operations"} <= set(batch))
        shared = [batch for batch in batches
                  if {"principles", "standards"} <= set(batch)]
        self.assertTrue(shared, batches)


class FanoutBatchesTest(unittest.TestCase):
    """AC-1: the pair batches together exactly when neither is in the repo
    and neither has an open delivery ticket."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_pair_batched_when_absent_and_no_open_ticket(self):
        batches = lib.fanout_batches({"tickets": {}}, candidates=PAIR)
        self.assertIn(["quality", "operations"], batches)

    def test_present_doc_set_makes_skill_ineligible(self):
        batches = lib.fanout_batches({"tickets": {}}, candidates=PAIR, present=["quality"])
        flat = [skill for batch in batches for skill in batch]
        self.assertNotIn("quality", flat)
        self.assertIn("operations", flat)

    def test_open_delivery_ticket_makes_skill_ineligible(self):
        tickets_index = {
            "tickets": {"MAR-1": _ticket(lib.DOC_SET_TITLES["quality"])},
        }
        batches = lib.fanout_batches(tickets_index, candidates=PAIR)
        flat = [skill for batch in batches for skill in batch]
        self.assertNotIn("quality", flat)
        self.assertIn("operations", flat)

    def test_done_delivery_ticket_does_not_block_eligibility(self):
        tickets_index = {
            "tickets": {
                "MAR-1": _ticket(lib.DOC_SET_TITLES["quality"], status="done"),
            },
        }
        batches = lib.fanout_batches(tickets_index)
        flat = [skill for batch in batches for skill in batch]
        self.assertIn("quality", flat)


class RunSchemaProductStepsTest(unittest.TestCase):
    """BS-1 (AC-4 area): a run whose steps are the product-level skills must
    validate.

    It used to be asserted against a closed `steps.propertyNames.enum`.
    v0.5.0 opened `steps` (4.3): the schema validates SHAPE, step names
    validate against the resolved workflow and skill names against the skill
    directories, so a product-level name reaching the ledger is admitted by
    being a skill rather than by being in a schema. `flow: product` went with
    the enum -- a run has a SUBJECT now -- so the document below is a real
    one."""

    PRODUCT_STEP_NAMES = ["create-docs", "create-requirements"]

    def setUp(self):
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            self.schema = json.load(fh)

    def test_steps_is_open_rather_than_enumerated(self):
        steps = self.schema["properties"]["steps"]
        self.assertNotIn("propertyNames", steps)
        self.assertIn("additionalProperties", steps)

    def test_every_product_level_step_name_is_a_real_skill(self):
        for name in self.PRODUCT_STEP_NAMES:
            with self.subTest(name=name):
                self.assertIn(name, lib.HOOKED_SKILLS)

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed in this env")
    def test_schema_accepts_a_run_with_these_steps(self):
        document = {
            "run_id": "MAR-101",
            "workflow": "ship",
            "workflow_version": 3,
            "subject": {"kind": "ticket", "ticket_id": "MAR-101"},
            "status": "in_progress",
            "cursor": None,
            "steps": {
                name: {"status": "completed"} for name in self.PRODUCT_STEP_NAMES
            },
            "loops": {},
            "totals": {},
        }
        validator = jsonschema.Draft202012Validator(self.schema)
        errors = list(validator.iter_errors(document))
        self.assertEqual(errors, [], "run schema errors: %r" % (errors,))
