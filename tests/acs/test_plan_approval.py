"""Deterministic plan-approval predicate, writer, and contract (MAR-73, slice
3 of MAR-69). Covers acs_lib.plan_approval_eligible's purity/determinism and
structural rules, plan-approval.py's writer behavior (drives it via
subprocess only -- never a Write of the record it produces), and the
create-impl-plan/SKILL.md + INTERNALS.md contract edits (the plan phase
and its approval subsection moved out of code/SKILL.md in the
skills-independence refactor; plan-approval.py itself is unchanged).

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
PLUGIN = os.path.join(REPO_ROOT, "src", "acs")
SCRIPTS_DIR = os.path.join(PLUGIN, "hooks", "scripts")
AGENTS_DIR = os.path.join(PLUGIN, "agents")
CODE_SKILL = os.path.join(PLUGIN, "skills", "code", "SKILL.md")
SKILLS = os.path.join(PLUGIN, "skills")
IMPL_PLAN_SKILL = os.path.join(PLUGIN, "skills", "create-impl-plan", "SKILL.md")
INTERNALS = os.path.join(PLUGIN, "docs", "INTERNALS.md")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _norm(text):
    return re.sub(r"\s+", " ", text)


#: A plan the predicate accepts. Deliberately SHORT and free-form above the
#: contract: §3.2 replaced the six-heading template with a machine-readable
#: minimum, so the fixture has to demonstrate that a plan written for a human
#: to read in one pass passes -- a fixture that kept the template would let
#: the template back in through the test.
CONFORMING_PLAN = """# Plan — SHOP-1: reject a malformed retry header

`RetryPolicy.parse` accepts a negative backoff and the worker then sleeps
forever. Validate at the boundary and reject, rather than clamping in the
worker, so the bad value is named where it enters.

Rejected: clamping to zero in `Worker.run`. It hides the caller's mistake and
the same bad config reaches the metrics.

Not doing: the retry-budget rework in SHOP-9. Out of scope here.

Tests first: `tests/retry/test_policy.py::test_negative_backoff_is_rejected`,
then the parse change. Every acceptance criterion maps to a test there.
Run `pytest tests/retry/ --cov=src/retry`; the coverage target is 90.

"""

#: The contract block CONFORMING_PLAN ends with. Kept separate so the writer
#: fixture below, which varies `delivery_path` per test, can append its own
#: without the plan carrying two.
CONFORMING_CONTRACT = """## Contract
delivery_path: small
owes:
  api_contract: false
  test_cases:   true
  e2e:          false
  reason: "internal parse change; no HTTP surface and no browser flow"

### Executor tasks & file map
- task 1: src/retry/policy.py, tests/retry/test_policy.py
"""

PLAN_PROSE = CONFORMING_PLAN
CONFORMING_PLAN = PLAN_PROSE + CONFORMING_CONTRACT


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

    def test_a_plan_with_no_contract_block_fails(self):
        mutated = CONFORMING_PLAN.replace("## Contract", "## Notes", 1)
        eligible, evaluation = lib.plan_approval_eligible(
            mutated, {"test_coverage_percent": 90})
        self.assertFalse(eligible)
        self.assertIn("missing-section: Contract", evaluation["failures"])

    def test_a_contract_with_no_delivery_path_fails(self):
        mutated = CONFORMING_PLAN.replace("delivery_path: small\n", "", 1)
        eligible, evaluation = lib.plan_approval_eligible(
            mutated, {"test_coverage_percent": 90})
        self.assertFalse(eligible)
        self.assertIn("contract: delivery_path is not declared",
                      evaluation["failures"])

    def test_an_unknown_delivery_path_fails(self):
        mutated = CONFORMING_PLAN.replace("delivery_path: small",
                                          "delivery_path: enormous", 1)
        eligible, evaluation = lib.plan_approval_eligible(
            mutated, {"test_coverage_percent": 90})
        self.assertFalse(eligible)
        self.assertTrue(
            any(f.startswith("contract: delivery_path:") for f in evaluation["failures"]),
            evaluation["failures"])

    def test_an_unknown_owes_key_fails(self):
        mutated = CONFORMING_PLAN.replace("  e2e:          false",
                                          "  e2e:          false\n  telemetry: true", 1)
        eligible, evaluation = lib.plan_approval_eligible(
            mutated, {"test_coverage_percent": 90})
        self.assertFalse(eligible)
        self.assertTrue(
            any(f.startswith("contract:") for f in evaluation["failures"]),
            evaluation["failures"])

    def test_a_missing_file_map_fails(self):
        mutated = CONFORMING_PLAN.replace("### Executor tasks & file map",
                                          "### Files", 1)
        eligible, evaluation = lib.plan_approval_eligible(
            mutated, {"test_coverage_percent": 90})
        self.assertFalse(eligible)
        self.assertIn("missing-section: Executor tasks & file map",
                      evaluation["failures"])

    def test_an_empty_file_map_fails(self):
        """The guard enforces the map on every Write, so an empty one is an
        unguarded run rather than a tidy plan."""
        mutated = CONFORMING_PLAN.replace(
            "- task 1: src/retry/policy.py, tests/retry/test_policy.py\n", "")
        eligible, evaluation = lib.plan_approval_eligible(
            mutated, {"test_coverage_percent": 90})
        self.assertFalse(eligible)
        self.assertIn("empty-section: Executor tasks & file map",
                      evaluation["failures"])

    def test_no_heading_template_is_required(self):
        """The whole point of §3.2: a plan is graded on what it says, not on
        carrying a heading per section whether or not it has content."""
        for retired in lib.RETIRED_PLAN_SECTIONS:
            with self.subTest(section=retired):
                # As a HEADING, not as a word: "Out of scope" appears in the
                # fixture's prose ("Out of scope here."), which is exactly the
                # freedom the template removal buys.
                self.assertNotIn("## %s" % retired, CONFORMING_PLAN)
                self.assertNotIn("### %s" % retired, CONFORMING_PLAN)
        eligible, evaluation = lib.plan_approval_eligible(
            CONFORMING_PLAN, {"test_coverage_percent": 90})
        self.assertTrue(eligible, evaluation["failures"])

    def test_coverage_target_absent_fails(self):
        mutated = CONFORMING_PLAN.replace(
            "the coverage target is 90", "the coverage target is 80")
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

    def test_fold_active_is_accepted_and_ignored(self):
        """The spec fold has no separate section set any more -- the plan IS
        the spec content -- but plan-approval.py still passes the argument, so
        the parameter stays and must change nothing."""
        for value in (True, False, None):
            with self.subTest(fold_active=value):
                eligible, evaluation = lib.plan_approval_eligible(
                    CONFORMING_PLAN, {"test_coverage_percent": 90},
                    fold_active=value)
                self.assertTrue(eligible, evaluation["failures"])
        self.assertEqual(
            lib.plan_approval_eligible(CONFORMING_PLAN, None, fold_active=True),
            lib.plan_approval_eligible(CONFORMING_PLAN, None, fold_active=False))

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
        """A ticket already judged onto the `standard` delivery path.

        Approval binds per path (ADR-0095) and the path is READ, never derived:
        a ticket that has not been classified is one nothing is waiting on, so
        the script no-ops on it. Recording the path is what a fixture owes."""
        tid = self.new_ticket("Plan approval", "task")
        self._classify(tid, "standard")
        return tid

    def _classify(self, ticket, path, reason="fixture: a plan of that shape"):
        """The path is no longer recorded on the ticket by a workflow writer:
        the PLAN records it, in its `## Contract` block (§3.2), because the
        plan is what knows the shape of the change. So classifying a fixture
        means writing the block."""
        self._path, self._reason = path, reason

    def _contract(self):
        """The block AND the file map: the predicate requires both, and a
        fixture that supplied only the block would be testing a plan no
        executor could be checked against."""
        return ("\n## Contract\ndelivery_path: %s\nowes:\n  api_contract: false\n"
                "  test_cases: true\n  e2e: false\n  reason: \"%s\"\n"
                "\n### Executor tasks & file map\n"
                "- task 1: src/retry/policy.py, tests/retry/test_policy.py\n"
                % (getattr(self, "_path", "standard"),
                   getattr(self, "_reason", "fixture")))

    def _plan_dir(self, ticket):
        self.ensure_run(ticket)
        return os.path.join(self.rdir(ticket), "steps", "create-impl-plan")

    def _write_plan(self, ticket, text, filename="plan.md"):
        # The plan carries its `## Contract` block, so the bytes on disk are
        # the prose PLUS the block -- and `plan_sha256` hashes the whole file.
        text = text + self._contract()
        self._last_plan_text = text
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
        """The approval mirrors into the PLAN step's state, beside the plan it
        approves -- not into code's."""
        return lib.read_json(lib.step_state_path(self.rdir(ticket), "create-impl-plan"))

    def test_writes_record_on_the_standard_path(self):
        tid = self._new_standard_ticket()
        self._write_plan(tid, PLAN_PROSE)
        out = self.run_script("plan-approval.py", "--run", tid)
        self.assertEqual(out.returncode, 0, out.stderr)
        record = self._read_record(tid)
        self.assertTrue(record["eligible"])
        self.assertEqual(record["plan_path"], "steps/create-impl-plan/plan.md")
        self.assertEqual(record["writer"], "plan-approval.py")

    def test_record_carries_predicate_inputs_and_checks(self):
        tid = self._new_standard_ticket()
        self._write_plan(tid, PLAN_PROSE)
        self.run_script("plan-approval.py", "--run", tid)
        record = self._read_record(tid)
        predicate = record["predicate"]
        self.assertEqual(predicate["function"], "acs_lib.plan_approval_eligible")
        for key in ("coverage_target", "file_map_heading", "contract_keys",
                    "plan_sha256", "plan_chars"):
            self.assertIn(key, predicate["inputs"])
        for check in ("contract_present", "delivery_path_declared",
                      "file_map_non_empty", "coverage_target_stated"):
            self.assertIn(check, predicate["checks"])

    def test_record_digest_matches_plan_bytes(self):
        tid = self._new_standard_ticket()
        plan_path = self._write_plan(tid, PLAN_PROSE)
        self.run_script("plan-approval.py", "--run", tid)
        record = self._read_record(tid)
        with open(plan_path, "rb") as fh:
            expected = hashlib.sha256(fh.read()).hexdigest()
        self.assertEqual(record["plan_sha256"], expected)

    def test_second_run_same_digest_does_not_rewrite(self):
        tid = self._new_standard_ticket()
        self._write_plan(tid, PLAN_PROSE)
        self.run_script("plan-approval.py", "--run", tid)
        with open(self._record_path(tid), "rb") as fh:
            before = fh.read()
        out2 = self.run_script("plan-approval.py", "--run", tid)
        self.assertEqual(out2.returncode, 0, out2.stderr)
        self.assertEqual(json.loads(out2.stdout).get("skipped"), "already-approved")
        with open(self._record_path(tid), "rb") as fh:
            after = fh.read()
        self.assertEqual(before, after)

    def test_revised_plan_writes_record_for_new_digest(self):
        tid = self._new_standard_ticket()
        self._write_plan(tid, PLAN_PROSE)
        self.run_script("plan-approval.py", "--run", tid)
        revised = PLAN_PROSE.replace("Not doing:", "Also not doing:")
        self._write_plan(tid, revised)
        out = self.run_script("plan-approval.py", "--run", tid)
        self.assertEqual(out.returncode, 0, out.stderr)
        record = self._read_record(tid)
        expected = hashlib.sha256(self._last_plan_text.encode("utf-8")).hexdigest()
        self.assertEqual(record["plan_sha256"], expected)

    def test_state_field_true_after_approval(self):
        tid = self._new_standard_ticket()
        self._write_plan(tid, PLAN_PROSE)
        self.run_script("plan-approval.py", "--run", tid)
        state = self._state(tid)
        self.assertTrue((state or {}).get("states", {}).get("plan_approved"))

    def test_state_field_false_when_ineligible(self):
        tid = self._new_standard_ticket()
        self._write_plan(tid, "not a conforming plan at all")
        self.run_script("plan-approval.py", "--run", tid)
        state = self._state(tid)
        self.assertFalse((state or {}).get("states", {}).get("plan_approved"))

    def test_ineligible_plan_writes_no_record(self):
        tid = self._new_standard_ticket()
        self._write_plan(tid, "not a conforming plan at all")
        out = self.run_script("plan-approval.py", "--run", tid)
        self.assertEqual(out.returncode, 0, out.stderr)
        payload = json.loads(out.stdout)
        self.assertTrue(payload["failures"])
        self.assertFalse(os.path.exists(
            os.path.join(self._plan_dir(tid), "plan-approval.json")))

    def test_missing_plan_artifact_is_not_eligible(self):
        tid = self._new_standard_ticket()
        self.ensure_run(tid)
        out = self.run_script("plan-approval.py", "--run", tid)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertFalse(os.path.exists(
            os.path.join(self._plan_dir(tid), "plan-approval.json")))
        state = self._state(tid)
        self.assertFalse((state or {}).get("states", {}).get("plan_approved"))

    def test_a_cheap_path_writes_no_record(self):
        for path in ("trivial", "small"):
            with self.subTest(path=path):
                tid = self.new_ticket("Small fix", "task")
                self._classify(tid, path)
                self._write_plan(tid, PLAN_PROSE)
                out = self.run_script("plan-approval.py", "--run", tid)
                self.assertEqual(out.returncode, 0, out.stderr)
                payload = json.loads(out.stdout)
                self.assertEqual(payload.get("skipped"), "delivery_path")
                self.assertEqual(payload.get("delivery_path"), path)
                self.assertFalse(payload["plan_approved"])
                self.assertFalse(os.path.exists(
                    os.path.join(self._plan_dir(tid), "plan-approval.json")))

    def test_an_unclassified_plan_is_not_due_an_approval(self):
        """A plan with no `## Contract` block has not been judged, which means
        nothing downstream is waiting on an approval. Not an error -- not due."""
        tid = self.new_ticket("Unclassified", "task")
        self.ensure_run(tid)
        d = self._plan_dir(tid)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "plan.md"), "w", encoding="utf-8") as fh:
            fh.write(PLAN_PROSE)   # deliberately WITHOUT a Contract block
        out = self.run_script("plan-approval.py", "--run", tid)
        self.assertEqual(out.returncode, 0, out.stderr)
        payload = json.loads(out.stdout)
        self.assertEqual(payload.get("skipped"), "unclassified")
        self.assertIsNone(payload.get("delivery_path"))
        self.assertFalse(os.path.exists(
            os.path.join(self._plan_dir(tid), "plan-approval.json")))

    def test_the_path_is_read_from_the_plan_never_from_the_ticket(self):
        """The judgement lives in the PLAN's `## Contract` block (§3.2) -- the
        plan is what knows the shape of the change. A stale `lane` left on a
        ticket by a pre-ADR-0095 partition must not steer anything."""
        tid = self._new_standard_ticket()
        self._write_plan(tid, PLAN_PROSE)
        ticket_path = os.path.join(self.tdir(tid), "ticket.json")
        if os.path.exists(ticket_path):
            with open(ticket_path, encoding="utf-8") as fh:
                ticket = json.load(fh)
            ticket["lane"] = "TRIVIAL"          # inert data since ADR-0095
            with open(ticket_path, "w", encoding="utf-8") as fh:
                json.dump(ticket, fh)
        out = self.run_script("plan-approval.py", "--run", tid)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertTrue(os.path.exists(
            os.path.join(self._plan_dir(tid), "plan-approval.json")))

    def test_a_specs_dir_changes_nothing(self):
        """`_fold_active` still resolves from `specs/` and is still passed,
        but the predicate ignores it: the plan IS the spec content, so a
        `specs/` directory is neither a second source nor a second shape. The
        SAME plan must be eligible with real spec content beside it, with a
        non-.md file beside it, and with no specs/ at all."""
        foldless = PLAN_PROSE

        tid_a = self._new_standard_ticket()
        self._write_plan(tid_a, foldless)
        specs_a = os.path.join(self.rdir(tid_a), "specs")
        os.makedirs(specs_a, exist_ok=True)
        with open(os.path.join(specs_a, "01-x.md"), "w", encoding="utf-8") as fh:
            fh.write("real spec content")
        out_a = self.run_script("plan-approval.py", "--run", tid_a)
        self.assertEqual(out_a.returncode, 0, out_a.stderr)
        self.assertTrue(json.loads(out_a.stdout)["eligible"], out_a.stdout)

        tid_b = self._new_standard_ticket()
        self._write_plan(tid_b, foldless)
        specs_b = os.path.join(self.rdir(tid_b), "specs")
        os.makedirs(specs_b, exist_ok=True)
        with open(os.path.join(specs_b, "readme.txt"), "w", encoding="utf-8") as fh:
            fh.write("plain text, not markdown")
        out_b = self.run_script("plan-approval.py", "--run", tid_b)
        self.assertEqual(out_b.returncode, 0, out_b.stderr)
        self.assertTrue(json.loads(out_b.stdout)["eligible"], out_b.stdout)

        tid_c = self._new_standard_ticket()
        self._write_plan(tid_c, foldless)
        out_c = self.run_script("plan-approval.py", "--run", tid_c)
        self.assertEqual(out_c.returncode, 0, out_c.stderr)
        self.assertTrue(json.loads(out_c.stdout)["eligible"], out_c.stdout)

    def test_an_unreadable_spec_file_is_still_harmless(self):
        tid = self._new_standard_ticket()
        self._write_plan(tid, PLAN_PROSE)
        specs_dir = os.path.join(self.rdir(tid), "specs")
        os.makedirs(specs_dir, exist_ok=True)
        os.symlink(os.path.join(specs_dir, "does-not-exist.md"),
                  os.path.join(specs_dir, "00-broken.md"))
        out = self.run_script("plan-approval.py", "--run", tid)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertTrue(json.loads(out.stdout)["eligible"], out.stdout)

    def test_explicit_plan_argument_is_used(self):
        tid = self._new_standard_ticket()
        alt_path = self._write_plan(tid, PLAN_PROSE, filename="alt-plan.md")
        out = self.run_script("plan-approval.py", "--run", tid, "--plan", alt_path)
        self.assertEqual(out.returncode, 0, out.stderr)
        record = self._read_record(tid)
        self.assertEqual(record["plan_path"], "steps/create-impl-plan/alt-plan.md")

    def test_escaping_plan_argument_is_rejected(self):
        tid = self._new_standard_ticket()
        outside_dir = tempfile.mkdtemp(prefix="acs-plan-approval-escape-")
        self.addCleanup(shutil.rmtree, outside_dir, True)
        evil_path = os.path.join(outside_dir, "evil-plan.md")
        with open(evil_path, "w", encoding="utf-8") as fh:
            fh.write(PLAN_PROSE)
        out = self.run_script("plan-approval.py", "--run", tid, "--plan", evil_path)
        self.assertEqual(out.returncode, 2)
        self.assertEqual(out.stdout, "")
        self.assertNotIn("Traceback", out.stderr)
        self.assertFalse(os.path.exists(
            os.path.join(self._plan_dir(tid), "plan-approval.json")))

    def test_unresolvable_ticket_exits_two_with_clean_stderr(self):
        out = self.run_script("plan-approval.py")
        self.assertEqual(out.returncode, 2)
        self.assertEqual(out.stdout, "")
        self.assertNotIn("Traceback", out.stderr)

    def test_gate_error_on_non_git_cwd_exits_two(self):
        nongit = tempfile.mkdtemp(prefix="acs-plan-approval-nongit-")
        self.addCleanup(shutil.rmtree, nongit, True)
        out = self.run_script("plan-approval.py", "--run", "SHOP-1", cwd=nongit)
        self.assertEqual(out.returncode, 2)
        self.assertEqual(out.stdout, "")
        self.assertNotIn("Traceback", out.stderr)

    def test_only_hook_script_names_the_record(self):
        hits = []
        for fname in sorted(os.listdir(SCRIPTS_DIR)):
            if not fname.endswith(".py"):
                continue
            if "plan-approval.json" in _read(os.path.join(SCRIPTS_DIR, fname)):
                hits.append(fname)
        self.assertEqual(hits, ["plan-approval.py"])

    def test_no_agent_file_writes_the_record(self):
        """ADR 0076 D-2 constrains the WRITER, not every mention: no agent
        file may co-locate `plan-approval.json`/`plan_approved` with a
        `Write` instruction -- narrowed from the original blanket "no
        mention at all" per 0076's own Consequences (0076:74-77), which
        hands this exact amendment to slice 4 / MAR-74, so that
        `code-verifier.md` can READ the record (AC-1) without becoming its
        writer."""
        for dirpath, _dirnames, filenames in os.walk(AGENTS_DIR):
            for fname in filenames:
                if not fname.endswith(".md"):
                    continue
                body = _read(os.path.join(dirpath, fname))
                norm_body = _norm(body)
                for literal in ("plan-approval.json", "plan_approved"):
                    for m in re.finditer(re.escape(literal), norm_body):
                        window = norm_body[max(0, m.start() - 250):m.end() + 250]
                        self.assertFalse(
                            "Write" in window,
                            "%s must not co-locate a Write instruction with "
                            "%r" % (fname, literal))

    def test_skill_forbids_subagent_write_of_the_record(self):
        # The prohibition sits where the record is DESCRIBED: create-impl-plan
        # publishes the plan the approval hashes, and is the skill a reader
        # arrives at asking who writes the record.
        norm_body = _norm(_read(IMPL_PLAN_SKILL))
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

    @unittest.skip("code-verifier.md left with the verifier (§3.5); the "
                   "record's reader is now the pre-hook's brake, pinned above")
    def test_verifier_agent_reads_but_never_writes_the_record(self):
        """D-2 constrains the writer, not the reader: code-verifier.md is
        positively asserted to READ plan-approval.json (dimension 15,
        MAR-74), while still never co-locating it with a Write
        instruction -- the writer-only guard applies here identically to
        `test_no_agent_file_writes_the_record` above."""
        body = _read(CODE_VERIFIER)
        self.assertIn("plan-approval.json", body)
        norm_body = _norm(body)
        for m in re.finditer(re.escape("plan-approval.json"), norm_body):
            window = norm_body[max(0, m.start() - 250):m.end() + 250]
            self.assertFalse(
                "Write" in window,
                "code-verifier.md must not co-locate a Write instruction "
                "with plan-approval.json")


class PlanPathReadTest(acs_case.AcsWorkspaceCase):
    """`acs.py plan path` -- the plan's Contract block, read and printed.

    ADR 0001's rule is that a skill reaches Python through a CLI. `/acs:code`
    broke it in one direction: it open-coded `build_context` ->
    `current_run_id` -> `plan_contract.read` in a heredoc inside its SKILL.md
    because no command answered "what path was this plan judged onto?".
    Redesign SS4.8 names that command `acs plan path`; these are its pins.

    The verb READS. Every test below asserts it wrote nothing, because the
    moment this command can write, the path has two writers and a resumed run
    can split across two rigors -- the exact failure ADR-0095 exists to
    prevent."""

    def _plan_dir(self, ticket):
        self.ensure_run(ticket)
        return os.path.join(self.rdir(ticket), "steps", "create-impl-plan")

    def _write_plan(self, ticket, contract, filename="plan.md"):
        d = self._plan_dir(ticket)
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, filename)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(PLAN_PROSE + contract)
        return path

    CONTRACT = ("\n## Contract\ndelivery_path: small\nowes:\n"
                "  api_contract: false\n  test_cases: true\n  e2e: false\n"
                '  reason: "CLI-only change"\n'
                "\n### Executor tasks & file map\n"
                "- task 1: src/retry/policy.py\n")

    def _path_out(self, ticket, *extra):
        out = self.run_script("plan-approval.py", "path", "--run", ticket, *extra)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def test_prints_the_judged_path_and_the_owes_flags(self):
        tid = self.new_ticket("Plan path", "task")
        self._write_plan(tid, self.CONTRACT)
        doc = self._path_out(tid)
        self.assertEqual(doc["delivery_path"], "small")
        self.assertEqual(doc["owes"], {"api_contract": False,
                                       "test_cases": True, "e2e": False})
        self.assertEqual(doc["contract_errors"], [])
        self.assertTrue(doc["plan"].endswith("steps/create-impl-plan/plan.md"))

    def test_writes_nothing(self):
        """The read must not create the approval record, and must not mirror
        `plan_approved` into the step. `check` is the only writer."""
        tid = self.new_ticket("Plan path", "task")
        self._write_plan(tid, self.CONTRACT)
        before = sorted(os.listdir(self._plan_dir(tid)))
        self._path_out(tid)
        self.assertEqual(sorted(os.listdir(self._plan_dir(tid))), before)
        self.assertFalse(os.path.exists(
            os.path.join(self._plan_dir(tid), "plan-approval.json")))

    def test_an_unjudged_plan_prints_null_rather_than_guessing(self):
        """Silence is not a default path. A plan with no Contract block is a
        plan that is not ready to dispatch, and saying so IS the answer -- the
        alternative, falling back to a path, is a second judge."""
        tid = self.new_ticket("Plan path", "task")
        self._write_plan(tid, "\n### Executor tasks & file map\n- task 1: a.py\n")
        doc = self._path_out(tid)
        self.assertIsNone(doc["delivery_path"])
        self.assertEqual(doc["owes"],
                         {"api_contract": None, "test_cases": None, "e2e": None})

    def test_a_missing_plan_is_reported_not_raised(self):
        tid = self.new_ticket("Plan path", "task")
        self.ensure_run(tid)
        doc = self._path_out(tid)
        self.assertIsNone(doc["plan"])
        self.assertIsNone(doc["delivery_path"])

    def test_an_unparseable_contract_is_distinguishable_from_an_absent_one(self):
        """`delivery_path: null` alone cannot tell a caller which of the two it
        has; `contract_errors` is what separates them."""
        tid = self.new_ticket("Plan path", "task")
        self._write_plan(tid, "\n## Contract\ndelivery_path: enormous\n"
                              "\n### Executor tasks & file map\n- task 1: a.py\n")
        doc = self._path_out(tid)
        self.assertIsNone(doc["delivery_path"])
        self.assertTrue(doc["contract_errors"], doc)

    def test_escaping_plan_argument_is_rejected_on_the_read_too(self):
        tid = self.new_ticket("Plan path", "task")
        self.ensure_run(tid)
        outside_dir = tempfile.mkdtemp(prefix="acs-plan-path-escape-")
        self.addCleanup(shutil.rmtree, outside_dir, True)
        evil_path = os.path.join(outside_dir, "evil-plan.md")
        with open(evil_path, "w", encoding="utf-8") as fh:
            fh.write(PLAN_PROSE + self.CONTRACT)
        out = self.run_script("plan-approval.py", "path", "--run", tid,
                              "--plan", evil_path)
        self.assertEqual(out.returncode, 2)
        self.assertEqual(out.stdout, "")
        self.assertNotIn("Traceback", out.stderr)

    def test_the_default_verb_is_still_check(self):
        """`acs.py plan check` forwards an EMPTY argv after dropping the verb,
        so a positional with no default would have broken every existing
        caller."""
        tid = self.new_ticket("Plan path", "task")
        self._write_plan(tid, self.CONTRACT)
        out = self.run_script("plan-approval.py", "--run", tid)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout)["skipped"], "delivery_path")

    def test_an_unknown_verb_is_refused(self):
        tid = self.new_ticket("Plan path", "task")
        self.ensure_run(tid)
        out = self.run_script("plan-approval.py", "judge", "--run", tid)
        self.assertNotEqual(out.returncode, 0)


class CodeSkillReachesPythonThroughTheCliTest(unittest.TestCase):
    """ADR 0001: a skill reaches Python through a CLI, never a heredoc.

    `code/SKILL.md` is the skill this rule was broken in, so it is the one
    pinned here; the pin is on the ABSENCE of an interpreter heredoc, not on
    the command's wording, because the failure mode is "a skill grew its own
    Python again", not "the command was renamed"."""

    def test_code_skill_has_no_embedded_python_heredoc(self):
        body = _read(CODE_SKILL)
        self.assertNotIn("python3 - <<", body)

    def test_code_skill_resolves_the_path_through_acs_py(self):
        body = _norm(_read(CODE_SKILL))
        self.assertIn('acs.py" plan path', body)


class PlanApprovalContractTest(unittest.TestCase):
    """AC-3 + call site. The call site moved with the plan phase: the
    subsection now lives in create-impl-plan/SKILL.md (the deeper prose pins
    are in tests/acs/test_create_impl_plan.py::PlanApprovalContractTest)."""

    @classmethod
    def setUpClass(cls):
        cls.skill_body = _read(IMPL_PLAN_SKILL)
        cls.internals_body = _read(INTERNALS)
        cls.leg_bodies = {leg: _read(os.path.join(SKILLS, leg, "SKILL.md"))
                          for leg in ("code-standard", "code-complex")}

    def test_skill_finish_example_carries_plan_approved(self):
        """create-impl-plan still RECORDS the key -- always false, because the
        path it would be judged against does not exist yet (ADR-0095)."""
        idx_plan_path = self.skill_body.index('"plan_path"')
        idx_plan_approved = self.skill_body.index('"plan_approved": false,')
        self.assertGreater(idx_plan_approved, idx_plan_path)
        self.assertLess(idx_plan_approved - idx_plan_path, 200)

    def test_skill_canonical_states_bullet_names_plan_approved(self):
        start = self.skill_body.index("Canonical `states` keys")
        end = self.skill_body.index("2. Run the post-hook")
        self.assertIn("plan_approved", self.skill_body[start:end])

    def test_internals_row_names_plan_approved(self):
        """Either skill's row may carry it while the docs sweep lands: the
        record is written on a create-impl-plan run and mirrored into
        code-state.json by plan-approval.py, which is unchanged."""
        rows = [self.internals_body[m:self.internals_body.index("\n", m)]
                for m in (self.internals_body.index("| code |"),)]
        idx = self.internals_body.find("| create-impl-plan |")
        if idx >= 0:
            rows.append(self.internals_body[idx:self.internals_body.index("\n", idx)])
        self.assertTrue(
            any("plan_approved" in row for row in rows),
            "INTERNALS.md must record plan_approved on the code or the "
            "create-impl-plan states row")

    def test_subsection_sits_after_execute_and_before_docs_only(self):
        """The approval note's position is the pin, not which sibling follows
        it. It was bound to `### Plan revocation` while that subsection sat
        between approval and `### Docs-only tickets`; revocation has since
        moved into `references/not-a-first-run.md`, so docs-only is the next
        heading again and the slice below is exactly the approval note."""
        plan_idx = self.skill_body.index("### Execute (per iteration) — survey, then author the plan")
        approval_idx = self.skill_body.index("### Plan approval")
        docs_only_idx = self.skill_body.index("### Docs-only tickets")
        self.assertGreater(approval_idx, plan_idx)
        self.assertLess(approval_idx, docs_only_idx)

    def test_the_plan_skill_says_approval_happens_later_and_why(self):
        """The reason is the load-bearing part: create-impl-plan produces the
        artifact the delivery path is judged FROM, so it cannot know whether
        approval is owed. A reader who misses that will put the call back."""
        start = self.skill_body.index("### Plan approval")
        end = self.skill_body.index("### Docs-only tickets")
        section_norm = _norm(self.skill_body[start:end])
        self.assertRegex(section_norm, r"(?i)`standard` and `complex` delivery paths")
        self.assertRegex(section_norm, r"(?i)before any path exists")
        self.assertRegex(section_norm, r"(?i)artifact the path\s+is judged FROM|"
                                       r"artifact the path is judged FROM")

    def test_no_leg_runs_the_writer_itself(self):
        """The call site left the legs entirely. A brake a coordinator applies
        to ITSELF is a brake the coordinator can forget: the pre-hook refuses
        `code` on the deep paths when the approval is absent or its
        `plan_sha256` is stale (§5), before the leg is ever invoked."""
        for leg in ("code-trivial", "code-small", "code-standard", "code-complex"):
            with self.subTest(leg=leg):
                self.assertNotIn("plan-approval.py",
                                 _read(os.path.join(SKILLS, leg, "SKILL.md")))

    def test_each_deep_leg_says_approval_is_enforced_and_what_makes_it_stale(self):
        for leg, body in self.leg_bodies.items():
            with self.subTest(leg=leg):
                norm_leg = _norm(body)
                self.assertRegex(norm_leg, r"(?i)Plan approval.{0,40}\*\*Enforced\.\*\*")
                self.assertIn("plan_sha256", norm_leg)
                self.assertIn("An edited plan is an unapproved plan", norm_leg)

    def test_the_cheap_legs_say_approval_is_not_required(self):
        for leg in ("code-trivial", "code-small"):
            with self.subTest(leg=leg):
                body = _norm(_read(os.path.join(SKILLS, leg, "SKILL.md")))
                self.assertIn("Plan approval is not required", body)

    def test_subsection_avoids_forbidden_literals(self):
        start = self.skill_body.index("### Plan approval")
        end = self.skill_body.index("### Docs-only tickets")
        section = self.skill_body[start:end]
        self.assertNotIn("create-spec", section)
        self.assertNotIn("hld/data-model.md", section)


if __name__ == "__main__":
    unittest.main()
