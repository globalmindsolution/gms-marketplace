"""Deterministic plan-approval predicate, writer, and contract (MAR-73, slice
3 of MAR-69). Covers acs_lib.plan_approval_eligible's purity/determinism and
structural rules, plan-approval.py's writer behavior (drives it via
subprocess only -- never a Write of the record it produces), and the
code/SKILL.md + INTERNALS.md contract edits.

Every prose assertion is by file plus whitespace-normalized substring/regex,
never by line number -- the house style of tests/acs/test_code_loop_topology.py
and tests/acs/test_lane_conditional_planning.py.

Run:
  python3 -m unittest tests.acs.test_plan_approval -v
"""

import hashlib
import inspect
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

TESTS_ACS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS_ACS)

import acs_case  # noqa: E402
from acs_case import lib  # noqa: E402

MODULE_FILENAME = "plan-approval.py"

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SCRIPTS_DIR = os.path.join(PLUGIN, "hooks", "scripts")
AGENTS_DIR = os.path.join(PLUGIN, "agents")
CODE_SKILL = os.path.join(PLUGIN, "skills", "code", "SKILL.md")
CODE_VERIFIER = os.path.join(AGENTS_DIR, "code-verifier.md")
INTERNALS = os.path.join(PLUGIN, "docs", "INTERNALS.md")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _norm(text):
    return re.sub(r"\s+", " ", text)


CONFORMING_PLAN = """## Spec analysis

Spec analysis content.

### Scope

Scope content.

### Approach

Approach content.

### API/data changes

API content.

### Test plan

Coverage target: `settings.test_coverage_percent` = 90.

no separate /acs:create-spec invocation and no separate create-spec planner subagent

every ticket.acceptance_criteria entry maps to at least one test the folded plan will write

### Out of scope

Out of scope content.

## Executor tasks & file map

File map content.

## Test strategy

Strategy content.

## Documentation map

Documentation content.

## Risks

Risk content.

## Verifier checklist

Checklist content.
"""


class PlanApprovalPredicatePurityTest(unittest.TestCase):
    """AC-4: no fixture -- pure unit tests, mirroring how derive_lane/verify_depth
    are tested."""

    def test_predicate_performs_no_io(self):
        def _raise(*_a, **_kw):
            raise AssertionError("plan_approval_eligible must not touch I/O")

        with mock.patch("builtins.open", side_effect=_raise), \
                mock.patch("os.listdir", side_effect=_raise), \
                mock.patch("os.path.exists", side_effect=_raise), \
                mock.patch("subprocess.run", side_effect=_raise):
            eligible, _evaluation = lib.plan_approval_eligible(
                CONFORMING_PLAN, {"test_coverage_percent": 90})
        self.assertTrue(eligible)

    def test_predicate_needs_no_clock(self):
        with mock.patch.object(lib, "now_iso", side_effect=AssertionError("no clock")):
            _eligible, evaluation = lib.plan_approval_eligible(
                CONFORMING_PLAN, {"test_coverage_percent": 90})
        dumped = json.dumps(evaluation)
        self.assertNotIn("approved_at", dumped)
        self.assertNotIn("now_iso", dumped)

    def test_predicate_is_deterministic(self):
        r1 = lib.plan_approval_eligible(CONFORMING_PLAN, {"test_coverage_percent": 90})
        r2 = lib.plan_approval_eligible(CONFORMING_PLAN, {"test_coverage_percent": 90})
        self.assertEqual(r1, r2)

    def test_predicate_signature_takes_plain_values(self):
        params = tuple(inspect.signature(lib.plan_approval_eligible).parameters)
        self.assertEqual(params, ("plan_text", "settings", "fold_active"))
        for name in params:
            self.assertNotIn("path", name)


class PlanApprovalPredicateRulesTest(unittest.TestCase):
    """AC-2: structural rules, inputs, digest, serializability."""

    def test_conforming_plan_is_eligible(self):
        eligible, evaluation = lib.plan_approval_eligible(
            CONFORMING_PLAN, {"test_coverage_percent": 90})
        self.assertTrue(eligible, evaluation["failures"])
        self.assertEqual(evaluation["failures"], [])

    def test_missing_required_section_fails(self):
        for name in lib.PLAN_REQUIRED_SECTIONS:
            heading = "## %s" % name
            self.assertIn(heading, CONFORMING_PLAN)
            mutated = CONFORMING_PLAN.replace(
                heading, "## Renamed %s" % name, 1)
            eligible, evaluation = lib.plan_approval_eligible(
                mutated, {"test_coverage_percent": 90})
            with self.subTest(section=name):
                self.assertFalse(eligible)
                self.assertIn("missing-section: %s" % name, evaluation["failures"])

    def test_empty_required_section_fails(self):
        mutated = CONFORMING_PLAN.replace(
            "## Risks\n\nRisk content.\n", "## Risks\n\n")
        eligible, evaluation = lib.plan_approval_eligible(
            mutated, {"test_coverage_percent": 90})
        self.assertFalse(eligible)
        self.assertIn("empty-section: Risks", evaluation["failures"])

    def test_empty_fold_section_fails(self):
        mutated = CONFORMING_PLAN.replace(
            "### Out of scope\n\nOut of scope content.\n",
            "### Out of scope\n\n")
        eligible, evaluation = lib.plan_approval_eligible(
            mutated, {"test_coverage_percent": 90})
        self.assertFalse(eligible)
        self.assertIn("empty-section: Out of scope", evaluation["failures"])

    def test_missing_fold_section_fails(self):
        mutated = CONFORMING_PLAN.replace("### Scope", "### Renamed Scope", 1)
        eligible, evaluation = lib.plan_approval_eligible(
            mutated, {"test_coverage_percent": 90})
        self.assertFalse(eligible)
        self.assertIn("missing-section: Scope", evaluation["failures"])

    def test_out_of_order_fold_sections_fail(self):
        scope_block = "### Scope\n\nScope content.\n\n"
        approach_block = "### Approach\n\nApproach content.\n\n"
        self.assertIn(scope_block, CONFORMING_PLAN)
        self.assertIn(approach_block, CONFORMING_PLAN)
        mutated = CONFORMING_PLAN.replace(
            scope_block + approach_block, approach_block + scope_block, 1)
        eligible, evaluation = lib.plan_approval_eligible(
            mutated, {"test_coverage_percent": 90})
        self.assertFalse(eligible)
        self.assertTrue(
            any(f.startswith("section-order:") for f in evaluation["failures"]),
            evaluation["failures"])

    def test_ambiguous_section_name_does_not_false_block_order(self):
        """A tracked fold-section name (e.g. "Out of scope") that also
        occurs earlier in the doc as a legitimate nested subheading under an
        unrelated section must not resolve to that decoy occurrence for the
        order check. structure_lint's own `ambiguous` relaxation excludes
        any name matching more than one heading from the order check
        entirely, "so an ambiguous list can never false-block a conforming
        doc" (structure_lint.py:19-23, 72-81, 100-108)."""
        anchor = "## Spec analysis\n\nSpec analysis content.\n\n"
        decoy = "#### Out of scope\n\nNested mention under Spec analysis, not the fold section.\n\n"
        self.assertIn(anchor, CONFORMING_PLAN)
        mutated = CONFORMING_PLAN.replace(anchor, anchor + decoy, 1)
        self.assertIn("\n#### Out of scope\n", mutated)
        self.assertIn("\n### Out of scope\n", mutated)
        eligible, evaluation = lib.plan_approval_eligible(
            mutated, {"test_coverage_percent": 90})
        self.assertTrue(eligible, evaluation["failures"])
        self.assertFalse(
            any(f.startswith("section-order:") for f in evaluation["failures"]),
            evaluation["failures"])

    def test_missing_mandatory_clause_fails(self):
        for clause in lib.PLAN_FOLD_CLAUSES:
            self.assertIn(clause, CONFORMING_PLAN)
            mutated = CONFORMING_PLAN.replace(clause, "", 1)
            eligible, evaluation = lib.plan_approval_eligible(
                mutated, {"test_coverage_percent": 90})
            with self.subTest(clause=clause):
                self.assertFalse(eligible)
                self.assertTrue(
                    any(f.startswith("missing-clause:") for f in evaluation["failures"]),
                    evaluation["failures"])

    def test_line_wrapped_clause_still_matches(self):
        clause = lib.PLAN_FOLD_CLAUSES[0]
        words = clause.split(" ")
        mid = len(words) // 2
        wrapped = " ".join(words[:mid]) + "\n" + " ".join(words[mid:])
        mutated = CONFORMING_PLAN.replace(clause, wrapped, 1)
        eligible, evaluation = lib.plan_approval_eligible(
            mutated, {"test_coverage_percent": 90})
        self.assertTrue(eligible, evaluation["failures"])

    def test_coverage_target_absent_fails(self):
        mutated = CONFORMING_PLAN.replace(
            "Coverage target: `settings.test_coverage_percent` = 90.",
            "Coverage target: `settings.test_coverage_percent` = 80.")
        eligible, evaluation = lib.plan_approval_eligible(
            mutated, {"test_coverage_percent": 90})
        self.assertFalse(eligible)
        self.assertTrue(
            any(f.startswith("coverage-target-not-stated:") for f in evaluation["failures"]),
            evaluation["failures"])

    def test_blank_plan_fails(self):
        eligible, evaluation = lib.plan_approval_eligible(
            "   \n\n  ", {"test_coverage_percent": 90})
        self.assertFalse(eligible)
        self.assertIn("empty-plan", evaluation["failures"])

    def test_fold_inactive_skips_fold_checks(self):
        text = (
            "## Spec analysis\n\nContent.\n\n"
            "## Executor tasks & file map\n\nContent.\n\n"
            "## Test strategy\n\nCoverage target 90 stated here.\n\n"
            "## Documentation map\n\nContent.\n\n"
            "## Risks\n\nContent.\n\n"
            "## Verifier checklist\n\nContent.\n"
        )
        eligible, evaluation = lib.plan_approval_eligible(
            text, {"test_coverage_percent": 90}, fold_active=False)
        self.assertTrue(eligible, evaluation["failures"])
        self.assertTrue(evaluation["checks"]["fold_sections_ok"])
        self.assertTrue(evaluation["checks"]["mandatory_clauses_ok"])

    def test_settings_none_uses_default_coverage_target(self):
        eligible, evaluation = lib.plan_approval_eligible(CONFORMING_PLAN, None)
        self.assertTrue(eligible, evaluation["failures"])
        self.assertEqual(evaluation["inputs"]["coverage_target"],
                         lib.DEFAULT_SETTINGS["test_coverage_percent"])

    def test_inputs_carry_sha256_of_the_text(self):
        _eligible, evaluation = lib.plan_approval_eligible(
            CONFORMING_PLAN, {"test_coverage_percent": 90})
        expected = hashlib.sha256(CONFORMING_PLAN.encode("utf-8")).hexdigest()
        self.assertEqual(evaluation["inputs"]["plan_sha256"], expected)
        _eligible2, evaluation2 = lib.plan_approval_eligible(
            CONFORMING_PLAN + "x", {"test_coverage_percent": 90})
        self.assertNotEqual(evaluation["inputs"]["plan_sha256"],
                            evaluation2["inputs"]["plan_sha256"])

    def test_coverage_target_none_in_settings_fails_without_crashing(self):
        eligible, evaluation = lib.plan_approval_eligible(
            CONFORMING_PLAN, {"test_coverage_percent": None})
        self.assertFalse(eligible)
        self.assertFalse(evaluation["checks"]["coverage_target_stated"])

    def test_float_coverage_target_matches_integer_display(self):
        eligible, evaluation = lib.plan_approval_eligible(
            CONFORMING_PLAN, {"test_coverage_percent": 90.0})
        self.assertTrue(eligible, evaluation["failures"])

    def test_evaluation_is_json_serializable(self):
        _eligible, evaluation = lib.plan_approval_eligible(
            CONFORMING_PLAN, {"test_coverage_percent": 90})
        json.dumps(evaluation)  # must not raise


class PlanApprovalWriterTest(acs_case.AcsWorkspaceCase):
    """AC-1, AC-3 -- drives plan-approval.py via subprocess only (never Write)."""

    def _new_standard_ticket(self):
        return self.new_ticket("Plan approval", "task")

    def _plan_dir(self, ticket):
        return os.path.join(self.tdir(ticket), "phases", "code")

    def _write_plan(self, ticket, text, filename="plan.md"):
        d = self._plan_dir(ticket)
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, filename)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def _record_path(self, ticket):
        return os.path.join(self._plan_dir(ticket), "plan-approval.json")

    def _read_record(self, ticket):
        with open(self._record_path(ticket), encoding="utf-8") as fh:
            return json.load(fh)

    def _state(self, ticket):
        return lib.read_json(lib.state_path(self.tdir(ticket), "code"))

    def test_writes_record_on_standard_lane(self):
        tid = self._new_standard_ticket()
        self._write_plan(tid, CONFORMING_PLAN)
        out = self.run_script("plan-approval.py", "--ticket", tid)
        self.assertEqual(out.returncode, 0, out.stderr)
        record = self._read_record(tid)
        self.assertTrue(record["eligible"])
        self.assertEqual(record["plan_path"], "phases/code/plan.md")
        self.assertEqual(record["writer"], "plan-approval.py")

    def test_record_carries_predicate_inputs_and_checks(self):
        tid = self._new_standard_ticket()
        self._write_plan(tid, CONFORMING_PLAN)
        self.run_script("plan-approval.py", "--ticket", tid)
        record = self._read_record(tid)
        predicate = record["predicate"]
        self.assertEqual(predicate["function"], "acs_lib.plan_approval_eligible")
        for key in ("coverage_target", "fold_active", "required_sections",
                    "fold_sections", "mandatory_clauses", "plan_sha256", "plan_chars"):
            self.assertIn(key, predicate["inputs"])
        self.assertIn("required_sections_ok", predicate["checks"])

    def test_record_digest_matches_plan_bytes(self):
        tid = self._new_standard_ticket()
        plan_path = self._write_plan(tid, CONFORMING_PLAN)
        self.run_script("plan-approval.py", "--ticket", tid)
        record = self._read_record(tid)
        with open(plan_path, "rb") as fh:
            expected = hashlib.sha256(fh.read()).hexdigest()
        self.assertEqual(record["plan_sha256"], expected)

    def test_second_run_same_digest_does_not_rewrite(self):
        tid = self._new_standard_ticket()
        self._write_plan(tid, CONFORMING_PLAN)
        self.run_script("plan-approval.py", "--ticket", tid)
        with open(self._record_path(tid), "rb") as fh:
            before = fh.read()
        out2 = self.run_script("plan-approval.py", "--ticket", tid)
        self.assertEqual(out2.returncode, 0, out2.stderr)
        self.assertEqual(json.loads(out2.stdout).get("skipped"), "already-approved")
        with open(self._record_path(tid), "rb") as fh:
            after = fh.read()
        self.assertEqual(before, after)

    def test_revised_plan_writes_record_for_new_digest(self):
        tid = self._new_standard_ticket()
        self._write_plan(tid, CONFORMING_PLAN)
        self.run_script("plan-approval.py", "--ticket", tid)
        revised = CONFORMING_PLAN.replace("Risk content.", "Risk content, revised.")
        self._write_plan(tid, revised)
        out = self.run_script("plan-approval.py", "--ticket", tid)
        self.assertEqual(out.returncode, 0, out.stderr)
        record = self._read_record(tid)
        expected = hashlib.sha256(revised.encode("utf-8")).hexdigest()
        self.assertEqual(record["plan_sha256"], expected)

    def test_state_field_true_after_approval(self):
        tid = self._new_standard_ticket()
        self._write_plan(tid, CONFORMING_PLAN)
        self.run_script("plan-approval.py", "--ticket", tid)
        state = self._state(tid)
        self.assertTrue(state["states"]["plan_approved"])

    def test_state_field_false_when_ineligible(self):
        tid = self._new_standard_ticket()
        self._write_plan(tid, "not a conforming plan at all")
        self.run_script("plan-approval.py", "--ticket", tid)
        state = self._state(tid)
        self.assertFalse(state["states"]["plan_approved"])

    def test_ineligible_plan_writes_no_record(self):
        tid = self._new_standard_ticket()
        self._write_plan(tid, "not a conforming plan at all")
        out = self.run_script("plan-approval.py", "--ticket", tid)
        self.assertEqual(out.returncode, 0, out.stderr)
        payload = json.loads(out.stdout)
        self.assertTrue(payload["failures"])
        self.assertFalse(os.path.exists(
            os.path.join(self.tdir(tid), "phases", "code", "plan-approval.json")))

    def test_missing_plan_artifact_is_not_eligible(self):
        tid = self._new_standard_ticket()
        out = self.run_script("plan-approval.py", "--ticket", tid)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertFalse(os.path.exists(
            os.path.join(self.tdir(tid), "phases", "code", "plan-approval.json")))
        state = self._state(tid)
        self.assertFalse(state["states"]["plan_approved"])

    def test_fast_lane_writes_no_record(self):
        tid = self.new_ticket("Trivial fix", "task", "--size", "trivial")
        self._write_plan(tid, CONFORMING_PLAN)
        out = self.run_script("plan-approval.py", "--ticket", tid)
        self.assertEqual(out.returncode, 0, out.stderr)
        payload = json.loads(out.stdout)
        self.assertEqual(payload.get("skipped"), "lane")
        self.assertFalse(payload["plan_approved"])
        self.assertFalse(os.path.exists(
            os.path.join(self.tdir(tid), "phases", "code", "plan-approval.json")))

    def test_lane_is_recomputed_not_read_from_ticket_json(self):
        tid = self._new_standard_ticket()
        self._write_plan(tid, CONFORMING_PLAN)
        ticket_path = os.path.join(self.tdir(tid), "ticket.json")
        with open(ticket_path, encoding="utf-8") as fh:
            ticket = json.load(fh)
        self.assertEqual(ticket["size"], "standard")
        ticket["lane"] = "TRIVIAL"
        with open(ticket_path, "w", encoding="utf-8") as fh:
            json.dump(ticket, fh)
        out = self.run_script("plan-approval.py", "--ticket", tid)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertTrue(os.path.exists(
            os.path.join(self.tdir(tid), "phases", "code", "plan-approval.json")))

    def test_fold_active_detected_from_specs_dir(self):
        foldless = (
            "## Spec analysis\n\nContent.\n\n"
            "## Executor tasks & file map\n\nContent.\n\n"
            "## Test strategy\n\nCoverage target 90 stated here.\n\n"
            "## Documentation map\n\nContent.\n\n"
            "## Risks\n\nContent.\n\n"
            "## Verifier checklist\n\nContent.\n"
        )

        tid_a = self._new_standard_ticket()
        self._write_plan(tid_a, foldless)
        specs_a = os.path.join(self.tdir(tid_a), "specs")
        os.makedirs(specs_a, exist_ok=True)
        with open(os.path.join(specs_a, "01-x.md"), "w", encoding="utf-8") as fh:
            fh.write("real spec content")
        out_a = self.run_script("plan-approval.py", "--ticket", tid_a)
        self.assertEqual(out_a.returncode, 0, out_a.stderr)
        self.assertTrue(json.loads(out_a.stdout)["eligible"], out_a.stdout)

        tid_b = self._new_standard_ticket()
        self._write_plan(tid_b, foldless)
        specs_b = os.path.join(self.tdir(tid_b), "specs")
        os.makedirs(specs_b, exist_ok=True)
        # A non-.md file in specs/ must never itself flip fold_active.
        with open(os.path.join(specs_b, "readme.txt"), "w", encoding="utf-8") as fh:
            fh.write("plain text, not markdown")
        out_b = self.run_script("plan-approval.py", "--ticket", tid_b)
        self.assertEqual(out_b.returncode, 0, out_b.stderr)
        self.assertFalse(json.loads(out_b.stdout)["eligible"])

    def test_fold_active_skips_unreadable_spec_file(self):
        tid = self._new_standard_ticket()
        self._write_plan(tid, CONFORMING_PLAN)
        specs_dir = os.path.join(self.tdir(tid), "specs")
        os.makedirs(specs_dir, exist_ok=True)
        os.symlink(os.path.join(specs_dir, "does-not-exist.md"),
                  os.path.join(specs_dir, "00-broken.md"))
        out = self.run_script("plan-approval.py", "--ticket", tid)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertTrue(json.loads(out.stdout)["eligible"], out.stdout)

    def test_explicit_plan_argument_is_used(self):
        tid = self._new_standard_ticket()
        alt_path = self._write_plan(tid, CONFORMING_PLAN, filename="alt-plan.md")
        out = self.run_script("plan-approval.py", "--ticket", tid, "--plan", alt_path)
        self.assertEqual(out.returncode, 0, out.stderr)
        record = self._read_record(tid)
        self.assertEqual(record["plan_path"], "phases/code/alt-plan.md")

    def test_escaping_plan_argument_is_rejected(self):
        tid = self._new_standard_ticket()
        outside_dir = tempfile.mkdtemp(prefix="acs-plan-approval-escape-")
        self.addCleanup(shutil.rmtree, outside_dir, True)
        evil_path = os.path.join(outside_dir, "evil-plan.md")
        with open(evil_path, "w", encoding="utf-8") as fh:
            fh.write(CONFORMING_PLAN)
        out = self.run_script("plan-approval.py", "--ticket", tid, "--plan", evil_path)
        self.assertEqual(out.returncode, 2)
        self.assertEqual(out.stdout, "")
        self.assertNotIn("Traceback", out.stderr)
        self.assertFalse(os.path.exists(
            os.path.join(self.tdir(tid), "phases", "code", "plan-approval.json")))

    def test_unresolvable_ticket_exits_two_with_clean_stderr(self):
        out = self.run_script("plan-approval.py")
        self.assertEqual(out.returncode, 2)
        self.assertEqual(out.stdout, "")
        self.assertNotIn("Traceback", out.stderr)

    def test_gate_error_on_non_git_cwd_exits_two(self):
        nongit = tempfile.mkdtemp(prefix="acs-plan-approval-nongit-")
        self.addCleanup(shutil.rmtree, nongit, True)
        out = self.run_script("plan-approval.py", "--ticket", "SHOP-1", cwd=nongit)
        self.assertEqual(out.returncode, 2)
        self.assertEqual(out.stdout, "")
        self.assertNotIn("Traceback", out.stderr)

    def test_archived_partition_is_refused(self):
        tid = self._new_standard_ticket()
        self._write_plan(tid, CONFORMING_PLAN)
        tdir = self.tdir(tid)
        archived_dir = os.path.join(lib.archive_dir(self.ws, "acme-shop"), tid)
        os.makedirs(os.path.dirname(archived_dir), exist_ok=True)
        shutil.move(tdir, archived_dir)
        out = self.run_script("plan-approval.py", "--ticket", tid)
        self.assertEqual(out.returncode, 2)
        self.assertNotIn("Traceback", out.stderr)

    def test_corrupt_ticket_json_exits_two(self):
        tid = self._new_standard_ticket()
        self._write_plan(tid, CONFORMING_PLAN)
        ticket_path = os.path.join(self.tdir(tid), "ticket.json")
        with open(ticket_path, "w", encoding="utf-8") as fh:
            fh.write("{not valid json")
        out = self.run_script("plan-approval.py", "--ticket", tid)
        self.assertEqual(out.returncode, 2)
        self.assertNotIn("Traceback", out.stderr)


class PlanApprovalWriterIsTheOnlyWriterTest(unittest.TestCase):
    """AC-1 'via the hook script only'."""

    def test_only_hook_script_names_the_record(self):
        hits = []
        for fname in sorted(os.listdir(SCRIPTS_DIR)):
            if not fname.endswith(".py"):
                continue
            if "plan-approval.json" in _read(os.path.join(SCRIPTS_DIR, fname)):
                hits.append(fname)
        self.assertEqual(hits, ["plan-approval.py"])

    def test_no_agent_file_names_the_record(self):
        for dirpath, _dirnames, filenames in os.walk(AGENTS_DIR):
            for fname in filenames:
                if not fname.endswith(".md"):
                    continue
                body = _read(os.path.join(dirpath, fname))
                self.assertNotIn("plan-approval.json", body, fname)
                self.assertNotIn("plan_approved", body, fname)

    def test_skill_forbids_subagent_write_of_the_record(self):
        norm_body = _norm(_read(CODE_SKILL))
        found = False
        for m in re.finditer(re.escape("plan-approval.json"), norm_body):
            window = norm_body[max(0, m.start() - 250):m.end() + 250]
            if "Write" in window and ("never" in window.lower() or "only" in window.lower()):
                found = True
                break
        self.assertTrue(
            found,
            "no bounded window around plan-approval.json co-locates a "
            "Write-tool prohibition and never/only")

    def test_verifier_agent_does_not_anchor_on_approval(self):
        body = _read(CODE_VERIFIER)
        self.assertNotIn("plan-approval", body)
        self.assertNotIn("plan_approved", body)


class PlanApprovalContractTest(unittest.TestCase):
    """AC-3 + call site."""

    @classmethod
    def setUpClass(cls):
        cls.skill_body = _read(CODE_SKILL)
        cls.internals_body = _read(INTERNALS)

    def test_skill_finish_example_carries_plan_approved(self):
        idx_verifier_passed = self.skill_body.index('"verifier_passed": true,')
        idx_plan_approved = self.skill_body.index('"plan_approved": true,')
        self.assertGreater(idx_plan_approved, idx_verifier_passed)
        self.assertLess(idx_plan_approved - idx_verifier_passed, 200)

    def test_skill_canonical_states_bullet_names_plan_approved(self):
        start = self.skill_body.index("Canonical `states` keys")
        end = self.skill_body.index("Advisory documentation findings")
        self.assertIn("plan_approved", self.skill_body[start:end])

    def test_internals_code_row_names_plan_approved(self):
        row_start = self.internals_body.index("| code |")
        row_end = self.internals_body.index("\n", row_start)
        self.assertIn("plan_approved", self.internals_body[row_start:row_end])

    def test_subsection_sits_between_plan_and_docs_only(self):
        plan_idx = self.skill_body.index("### Plan (once, before the loop)")
        approval_idx = self.skill_body.index("### Plan approval")
        docs_only_idx = self.skill_body.index("### Docs-only tickets")
        self.assertGreater(approval_idx, plan_idx)
        self.assertLess(approval_idx, docs_only_idx)

    def test_subsection_is_lane_qualified_and_non_gating(self):
        start = self.skill_body.index("### Plan approval")
        end = self.skill_body.index("### Docs-only tickets")
        section_norm = _norm(self.skill_body[start:end])
        self.assertRegex(section_norm, r"(?i)STANDARD/COMPLEX")
        self.assertRegex(section_norm, r"(?i)TRIVIAL/SMALL.{0,80}no-ops?")
        self.assertRegex(section_norm, r"(?i)nothing gates.{0,60}this release")

    def test_subsection_carries_the_exact_command(self):
        start = self.skill_body.index("### Plan approval")
        end = self.skill_body.index("### Docs-only tickets")
        self.assertIn("hooks/scripts/plan-approval.py", self.skill_body[start:end])

    def test_subsection_avoids_forbidden_literals(self):
        start = self.skill_body.index("### Plan approval")
        end = self.skill_body.index("### Docs-only tickets")
        section = self.skill_body[start:end]
        self.assertNotIn("create-spec", section)
        self.assertNotIn("E2", section)
        self.assertNotIn("hld/data-model.md", section)


if __name__ == "__main__":
    unittest.main()
