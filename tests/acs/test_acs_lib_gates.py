"""Behavior tests for acs_lib.gates' pre-hook gate functions.

Originating tickets: MAR-173, MAR-75, then the skills-independence refactor.
A gate checks INPUTS (the ticket resolves, a required artifact or doc set
exists) and SAFETY BRAKES (the lock, a verifier that did not pass, a recorded
PR reference) -- never ORDER. `_require_completed` and every
predecessor-completed check are gone; the order lives in workflows/ship.yaml
and is advised, not enforced (tests/acs/test_gate_advisory.py). Covered here:
gate_create_prd's unconditional return, gate_create_architecture's PRD-found
return, gate_create_project's missing/found tech-stack.md branches,
_resolve_ticket_for_gate's archived and corrupt/missing-ticket branches,
gate_create_design without a create-ticket run, gate_code's epic refusal and
plan.md input, the five new Build/Test gates, gate_docs_sync as a pure
partition check, gate_create_pr as a brake only, gate_merge_pr's unchanged
readiness brake, the declared GATE_INPUTS classification,
tracker_cli_warning's github/jira not-found branches, and _tool_version's
nonexistent-binary branch.
"""

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

sys.path.insert(0, os.path.join(REPO_ROOT, "tests", "acs"))
from acs_case import AcsWorkspaceCase  # noqa: E402


def write(path, text=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


class GateCase(AcsWorkspaceCase):
    """A workspace fixture plus the ctx/payload shapes the gates take."""

    def ctx(self, **settings):
        merged = dict(lib.DEFAULT_SETTINGS)
        merged.update({"ticket_prefix": "SHOP"})
        merged.update(settings)
        return {
            "cwd": self.repo, "settings": merged,
            "workspace": self.ws, "repo_id": "acme-shop",
            "checkout_id": lib.checkout_id(self.repo),
            "checkout_root": self.repo,
        }

    def payload(self, ticket_id):
        return {"tool_input": {"args": ticket_id}}

    def ticket(self, ticket_id, ttype="task", **fields):
        tdir = self.tdir(ticket_id)
        os.makedirs(tdir, exist_ok=True)
        doc = {"id": ticket_id, "type": ttype}
        doc.update(fields)
        lib.save_ticket(tdir, doc)
        return tdir

    def partition_artifact(self, ticket_id, name, text="# artifact\n"):
        return write(os.path.join(self.tdir(ticket_id), name), text)

    def docs_artifact(self, ticket_id, name, text="# artifact\n"):
        return write(os.path.join(self.repo, "docs", "tickets", ticket_id, name), text)

    def record_run(self, skill, ticket_id, status, states=None):
        tdir = self.tdir(ticket_id)
        lib.append_in_progress_run(tdir, skill, ticket_id)
        lib.finalize_run(tdir, skill, ticket_id, {"status": status, "states": states or {}})

    def foreign_lock(self, ticket_id):
        """A live lock held by another checkout on another host: never stale
        inside LOCK_MAX_AGE_HOURS, so check_lock refuses it."""
        lib.write_json(lib.lock_path(self.tdir(ticket_id)), {
            "checkout_id": "other-checkout", "checkout_path": "/elsewhere/shop",
            "pid": 1, "hostname": "another-host", "created_at": lib.now_iso(),
        })


class TestOrderGatesAreGone(unittest.TestCase):
    """The refactor's one-line contract: no gate refuses on predecessor order."""

    def test_require_completed_no_longer_exists(self):
        self.assertFalse(hasattr(lib, "_require_completed"))
        self.assertFalse(hasattr(lib.gates, "_require_completed"))

    def test_no_gate_reads_the_run_ledger_for_completed_ness(self):
        for name in ("gates.py", "gate_inputs.py"):
            with open(os.path.join(SCRIPTS, "acs_lib", name), encoding="utf-8") as fh:
                src = fh.read()
            with self.subTest(module=name):
                self.assertNotIn("_require_completed(", src)
                self.assertNotIn("skill_completed(", src)


class TestGateCreatePrd(unittest.TestCase):
    """1561: returns None unconditionally."""

    def test_returns_none_unconditionally(self):
        self.assertIsNone(lib.gate_create_prd({}, {}))


class TestGateCreateArchitecture(unittest.TestCase):
    """1573: returns None when prd.md exists under the configured prd_path."""

    def test_returns_none_when_prd_exists(self):
        root = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, root, True)
        os.makedirs(os.path.join(root, "docs", "product"))
        open(os.path.join(root, "docs", "product", "prd.md"), "w").close()
        ctx = {"checkout_root": root, "settings": {}}
        self.assertIsNone(lib.gate_create_architecture(ctx, {}))


class TestGateCreateProject(unittest.TestCase):
    """1577-1583: raises GateError when hld/tech-stack.md is missing;
    1584: returns None when it exists."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.root, True)
        self.ctx = {"checkout_root": self.root, "settings": {}}

    def test_raises_when_tech_stack_missing(self):
        with self.assertRaises(lib.GateError) as ctx:
            lib.gate_create_project(self.ctx, {})
        self.assertIn("tech-stack.md", str(ctx.exception))

    def test_returns_none_when_tech_stack_exists(self):
        hld = os.path.join(self.root, "docs", "architecture", "hld")
        os.makedirs(hld)
        open(os.path.join(hld, "tech-stack.md"), "w").close()
        self.assertIsNone(lib.gate_create_project(self.ctx, {}))


class TestResolveTicketForGate(GateCase):
    """1606: raises for an archived ticket; 1611: raises for a corrupt/missing
    ticket.json."""

    def test_raises_for_archived_ticket(self):
        tdir = os.path.join(lib.archive_dir(self.ws, "acme-shop"), "SHOP-1")
        os.makedirs(tdir)
        with self.assertRaises(lib.GateError) as ctx:
            lib._resolve_ticket_for_gate(self.ctx(), self.payload("SHOP-1"), "create-design")
        self.assertIn("archived", str(ctx.exception))

    def test_raises_for_missing_ticket_json(self):
        os.makedirs(self.tdir("SHOP-2"))
        with self.assertRaises(lib.GateError) as ctx:
            lib._resolve_ticket_for_gate(self.ctx(), self.payload("SHOP-2"), "create-design")
        self.assertIn("ticket.json", str(ctx.exception))

    def test_raises_for_a_missing_partition_pointing_at_create_ticket(self):
        with self.assertRaises(lib.GateError) as ctx:
            lib._resolve_ticket_for_gate(self.ctx(), self.payload("SHOP-3"), "code")
        self.assertIn("run /acs:create-ticket first", str(ctx.exception))


class TestGateCreateDesign(GateCase):
    """Input only: the ticket resolves and is flagged needs_design. The
    create-ticket-completed check is dropped -- a partition with no run ledger
    at all passes."""

    def test_passes_with_no_create_ticket_run_recorded(self):
        self.ticket("SHOP-3", needs_design=True)
        self.assertFalse(lib.skill_completed(self.tdir("SHOP-3"), "create-ticket"))
        self.assertEqual(lib.gate_create_design(self.ctx(), self.payload("SHOP-3")), "SHOP-3")

    def test_passes_when_the_create_ticket_run_is_recorded_failed(self):
        self.ticket("SHOP-3", needs_design=True)
        self.record_run("create-ticket", "SHOP-3", "failed")
        self.assertEqual(lib.gate_create_design(self.ctx(), self.payload("SHOP-3")), "SHOP-3")

    def test_passes_when_the_create_ticket_run_is_recorded_in_progress(self):
        self.ticket("SHOP-3", needs_design=True)
        lib.append_in_progress_run(self.tdir("SHOP-3"), "create-ticket", "SHOP-3")
        self.assertEqual(lib.gate_create_design(self.ctx(), self.payload("SHOP-3")), "SHOP-3")

    def test_still_refuses_a_ticket_not_flagged_needs_design(self):
        self.ticket("SHOP-3", needs_design=False)
        with self.assertRaises(lib.GateError) as ctx:
            lib.gate_create_design(self.ctx(), self.payload("SHOP-3"))
        self.assertIn("needs_design", str(ctx.exception))


class TestGateCodeEpicRefusal(GateCase):
    """1648: refuses type=='epic' tickets with a breakdown-direction
    GateError; non-epic tickets (including COMPLEX-lane and parentless
    tasks, and stories whose parent is an epic) pass through once a plan
    exists."""

    def test_epic_ticket_is_refused_with_breakdown_direction(self):
        self.ticket("SHOP-4", "epic")
        with self.assertRaises(lib.GateError) as ctx:
            lib.gate_code(self.ctx(), self.payload("SHOP-4"))
        msg = str(ctx.exception)
        self.assertIn("SHOP-4", msg)
        self.assertIn("epic", msg)
        self.assertIn("/acs:create-design", msg)
        self.assertIn("/acs:create-ticket", msg)
        self.assertIn("child", msg)
        # design.md:813-818 (D6-B): create-design must be routed to BEFORE
        # the fan-out breakdown command, not just co-occur with it.
        self.assertLess(
            msg.index("/acs:create-design"), msg.index("/acs:create-ticket"),
            "the create-design step must precede the fan-out breakdown "
            "command in the GateError message")

    def test_epic_is_refused_before_the_plan_is_looked_for(self):
        self.ticket("SHOP-4", "epic")
        with self.assertRaises(lib.GateError) as ctx:
            lib.gate_code(self.ctx(), self.payload("SHOP-4"))
        self.assertNotIn("plan.md", str(ctx.exception))

    def test_epic_refusal_surfaces_as_exit_2_through_the_pre_hook(self):
        self.ticket("SHOP-5", "epic")
        result = self.pre("code", "SHOP-5")
        self.assertEqual(result.returncode, 2)
        self.assertIn("epic", result.stderr)

    def test_non_epic_large_size_ticket_is_not_refused(self):
        self.ticket("SHOP-6", size="large")
        self.partition_artifact("SHOP-6", "plan.md")
        self.assertEqual(lib.gate_code(self.ctx(), self.payload("SHOP-6")), "SHOP-6")

    def test_task_with_null_parent_and_no_design_still_passes(self):
        self.ticket("SHOP-7", parent=None)
        self.partition_artifact("SHOP-7", "plan.md")
        self.assertEqual(lib.gate_code(self.ctx(), self.payload("SHOP-7")), "SHOP-7")

    def test_story_child_of_epic_is_not_refused(self):
        self.ticket("SHOP-8", "story", parent="SHOP-1")
        self.partition_artifact("SHOP-8", "plan.md")
        self.assertEqual(lib.gate_code(self.ctx(), self.payload("SHOP-8")), "SHOP-8")


class TestGateCodePlanInput(GateCase):
    """code lost its plan phase to create-impl-plan, so it REQUIRES the plan
    artifact: docs-tree folder first, then the partition, then the legacy
    phases/code/plan.md the old plan phase wrote."""

    def test_refuses_without_a_plan_pointing_at_create_impl_plan(self):
        self.ticket("SHOP-10")
        with self.assertRaises(lib.GateError) as ctx:
            lib.gate_code(self.ctx(), self.payload("SHOP-10"))
        msg = str(ctx.exception)
        self.assertIn("plan.md", msg)
        self.assertIn("run /acs:create-impl-plan SHOP-10 first", msg)

    def test_the_refusal_surfaces_as_exit_2_through_the_pre_hook(self):
        self.ticket("SHOP-10")
        result = self.pre("code", "SHOP-10")
        self.assertEqual(result.returncode, 2)
        self.assertIn("/acs:create-impl-plan SHOP-10", result.stderr)

    def test_a_plan_in_the_docs_tree_folder_passes(self):
        self.ticket("SHOP-10")
        self.docs_artifact("SHOP-10", "plan.md")
        self.assertEqual(lib.gate_code(self.ctx(), self.payload("SHOP-10")), "SHOP-10")

    def test_a_plan_under_a_custom_tickets_path_passes(self):
        self.ticket("SHOP-10")
        write(os.path.join(self.repo, "planning", "SHOP-10", "plan.md"))
        ctx = self.ctx(artifacts={"tickets_path": "planning"})
        self.assertEqual(lib.gate_code(ctx, self.payload("SHOP-10")), "SHOP-10")

    def test_a_plan_in_the_partition_passes(self):
        self.ticket("SHOP-10")
        self.partition_artifact("SHOP-10", "plan.md")
        self.assertEqual(lib.gate_code(self.ctx(), self.payload("SHOP-10")), "SHOP-10")

    def test_the_legacy_phases_code_plan_still_passes(self):
        self.ticket("SHOP-10")
        write(os.path.join(self.tdir("SHOP-10"), "phases", "code", "plan.md"))
        self.assertEqual(lib.LEGACY_ARTIFACT_PATHS["plan.md"],
                         (os.path.join("phases", "code", "plan.md"),))
        self.assertEqual(lib.gate_code(self.ctx(), self.payload("SHOP-10")), "SHOP-10")

    def test_tickets_path_null_ignores_the_docs_tree(self):
        self.ticket("SHOP-10")
        self.docs_artifact("SHOP-10", "plan.md")
        ctx = self.ctx(artifacts={"tickets_path": None})
        with self.assertRaises(lib.GateError):
            lib.gate_code(ctx, self.payload("SHOP-10"))
        self.partition_artifact("SHOP-10", "plan.md")
        self.assertEqual(lib.gate_code(ctx, self.payload("SHOP-10")), "SHOP-10")

    def test_the_pre_hook_passes_once_a_plan_exists(self):
        self.ticket("SHOP-10")
        self.partition_artifact("SHOP-10", "plan.md")
        result = self.pre("code", "SHOP-10")
        self.assertEqual(result.returncode, 0, result.stderr)


class TestGateAnalyzeTicket(GateCase):
    """Input: the ticket resolves; epics refused."""

    def test_passes_for_a_fresh_task(self):
        self.ticket("SHOP-11")
        self.assertEqual(lib.gate_analyze_ticket(self.ctx(), self.payload("SHOP-11")), "SHOP-11")

    def test_refuses_an_epic(self):
        self.ticket("SHOP-11", "epic")
        with self.assertRaises(lib.GateError) as ctx:
            lib.gate_analyze_ticket(self.ctx(), self.payload("SHOP-11"))
        msg = str(ctx.exception)
        self.assertIn("epic", msg)
        self.assertLess(msg.index("/acs:create-design"), msg.index("/acs:create-ticket"))
        self.assertIn("/acs:analyze-ticket", msg)

    def test_refuses_an_unresolvable_ticket(self):
        with self.assertRaises(lib.GateError) as ctx:
            lib.gate_analyze_ticket(self.ctx(), {})
        self.assertIn("ticket id", str(ctx.exception))


class TestGateCreateImplPlan(GateCase):
    """Input: the ticket resolves; not an epic. No analysis is required --
    a plan may be authored without one (the analysis is read when present)."""

    def test_passes_without_an_analysis(self):
        self.ticket("SHOP-12")
        self.assertEqual(lib.gate_create_impl_plan(self.ctx(), self.payload("SHOP-12")), "SHOP-12")

    def test_refuses_an_epic(self):
        self.ticket("SHOP-12", "epic")
        with self.assertRaises(lib.GateError) as ctx:
            lib.gate_create_impl_plan(self.ctx(), self.payload("SHOP-12"))
        self.assertIn("epic", str(ctx.exception))
        self.assertIn("/acs:create-impl-plan", str(ctx.exception))


class TestGateCreateApiContract(GateCase):
    """Input: plan.md exists AND analysis.md declares api_surface: true; each
    miss points at its producer."""

    ANALYSIS_API = "---\nticket: SHOP-13\napi_surface: true\n---\n# Analysis\n"
    ANALYSIS_NO_API = "---\nticket: SHOP-13\napi_surface: false\n---\n# Analysis\n"

    def setUp(self):
        super().setUp()
        self.ticket("SHOP-13")

    def test_refuses_without_a_plan_pointing_at_create_impl_plan(self):
        self.partition_artifact("SHOP-13", "analysis.md", self.ANALYSIS_API)
        with self.assertRaises(lib.GateError) as ctx:
            lib.gate_create_api_contract(self.ctx(), self.payload("SHOP-13"))
        self.assertIn("run /acs:create-impl-plan SHOP-13 first", str(ctx.exception))

    def test_refuses_without_an_analysis_pointing_at_analyze_ticket(self):
        self.partition_artifact("SHOP-13", "plan.md")
        with self.assertRaises(lib.GateError) as ctx:
            lib.gate_create_api_contract(self.ctx(), self.payload("SHOP-13"))
        self.assertIn("run /acs:analyze-ticket SHOP-13 first", str(ctx.exception))

    def test_refuses_when_the_analysis_found_no_api_surface(self):
        self.partition_artifact("SHOP-13", "plan.md")
        self.partition_artifact("SHOP-13", "analysis.md", self.ANALYSIS_NO_API)
        with self.assertRaises(lib.GateError) as ctx:
            lib.gate_create_api_contract(self.ctx(), self.payload("SHOP-13"))
        self.assertIn("api_surface", str(ctx.exception))
        self.assertIn("/acs:analyze-ticket SHOP-13", str(ctx.exception))

    def test_passes_with_a_plan_and_an_api_surface_analysis(self):
        self.partition_artifact("SHOP-13", "plan.md")
        self.partition_artifact("SHOP-13", "analysis.md", self.ANALYSIS_API)
        self.assertEqual(lib.gate_create_api_contract(self.ctx(), self.payload("SHOP-13")), "SHOP-13")

    def test_reads_both_artifacts_from_the_docs_tree(self):
        self.docs_artifact("SHOP-13", "plan.md")
        self.docs_artifact("SHOP-13", "analysis.md", self.ANALYSIS_API)
        self.assertEqual(lib.gate_create_api_contract(self.ctx(), self.payload("SHOP-13")), "SHOP-13")

    def test_a_corrupt_analysis_front_matter_refuses_naming_the_line(self):
        self.partition_artifact("SHOP-13", "plan.md")
        self.partition_artifact("SHOP-13", "analysis.md", "---\nticket: {a: 1}\n---\n")
        with self.assertRaises(lib.GateError) as ctx:
            lib.gate_create_api_contract(self.ctx(), self.payload("SHOP-13"))
        self.assertIn("front matter", str(ctx.exception))
        self.assertIn(":2", str(ctx.exception))


class TestGateCreateTestDocs(GateCase):
    """Input: the ticket resolves (partition, active, unlocked) -- nothing else."""

    def test_passes_for_a_fresh_ticket_with_no_plan_or_analysis(self):
        self.ticket("SHOP-14")
        self.assertEqual(lib.gate_create_test_docs(self.ctx(), self.payload("SHOP-14")), "SHOP-14")

    def test_refuses_a_locked_partition(self):
        self.ticket("SHOP-14")
        self.foreign_lock("SHOP-14")
        with self.assertRaises(lib.GateError) as ctx:
            lib.gate_create_test_docs(self.ctx(), self.payload("SHOP-14"))
        self.assertIn("lock", str(ctx.exception).lower())


class TestE2eCaseCount(unittest.TestCase):
    """test-cases.md's e2e rows: front matter `e2e_cases` when integer, else
    body lines naming a TC-n id and typed e2e (a table cell, or the token on
    a list item)."""

    def _file(self, text):
        root = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, root, True)
        return write(os.path.join(root, "test-cases.md"), text)

    def test_counts_table_rows_and_list_items_typed_e2e(self):
        path = self._file(
            "---\nticket: SHOP-1\ncases: 4\n---\n"
            "| id | ac | type |\n|---|---|---|\n"
            "| TC-1 | AC-1 | unit |\n"
            "| TC-2 | AC-1 | e2e |\n"
            "- TC-3 (AC-2, E2E): checkout end to end\n"
            "- TC-4 (AC-2, integration): create-e2e-tests writes it\n"
            "type unit|integration|e2e legend line without an id\n")
        self.assertEqual(lib.e2e_case_count(path), 2)

    def test_a_table_row_mentioning_e2e_in_prose_is_not_typed_e2e(self):
        path = self._file("| TC-5 | AC-1 | unit | the e2e flag parses |\n")
        self.assertEqual(lib.e2e_case_count(path), 0)

    def test_front_matter_e2e_cases_wins_when_declared(self):
        path = self._file("---\nticket: SHOP-1\ncases: 3\ne2e_cases: 3\n---\n| TC-1 | e2e |\n")
        self.assertEqual(lib.e2e_case_count(path), 3)

    def test_a_non_integer_declaration_falls_back_to_the_body(self):
        path = self._file("---\ne2e_cases: true\n---\n| TC-1 | e2e |\n")
        self.assertEqual(lib.e2e_case_count(path), 1)

    def test_no_front_matter_counts_the_body(self):
        self.assertEqual(lib.e2e_case_count(self._file("# Cases\n\n| TC-9 | AC-1 | e2e |\n")), 1)
        self.assertEqual(lib.e2e_case_count(self._file("# Cases\n\n| TC-9 | AC-1 | unit |\n")), 0)

    def test_a_corrupt_front_matter_is_a_gate_error(self):
        with self.assertRaises(lib.GateError):
            lib.e2e_case_count(self._file("---\ncases: {a: 1}\n---\n"))


class TestGateCreateE2eTests(GateCase):
    """Input: e2e configured AND test-cases.md lists at least one e2e case."""

    E2E = {"suites": {"e2e": {"command": "npm run e2e"}}}
    CASES_E2E = "---\nticket: SHOP-15\ncases: 2\n---\n| TC-1 | AC-1 | unit |\n| TC-2 | AC-1 | e2e |\n"
    CASES_NO_E2E = "---\nticket: SHOP-15\ncases: 1\n---\n| TC-1 | AC-1 | unit |\n"

    def setUp(self):
        super().setUp()
        self.ticket("SHOP-15")

    def test_refuses_without_an_e2e_suite_configured(self):
        self.partition_artifact("SHOP-15", "test-cases.md", self.CASES_E2E)
        with self.assertRaises(lib.GateError) as ctx:
            lib.gate_create_e2e_tests(self.ctx(), self.payload("SHOP-15"))
        self.assertIn("e2e", str(ctx.exception))
        self.assertIn("/acs:setup", str(ctx.exception))

    def test_refuses_without_test_cases_pointing_at_create_test_docs(self):
        with self.assertRaises(lib.GateError) as ctx:
            lib.gate_create_e2e_tests(self.ctx(**self.E2E), self.payload("SHOP-15"))
        self.assertIn("run /acs:create-test-docs SHOP-15 first", str(ctx.exception))

    def test_refuses_when_no_case_is_typed_e2e(self):
        self.partition_artifact("SHOP-15", "test-cases.md", self.CASES_NO_E2E)
        with self.assertRaises(lib.GateError) as ctx:
            lib.gate_create_e2e_tests(self.ctx(**self.E2E), self.payload("SHOP-15"))
        self.assertIn("no e2e case", str(ctx.exception))

    def test_passes_with_a_suite_and_an_e2e_case(self):
        self.partition_artifact("SHOP-15", "test-cases.md", self.CASES_E2E)
        self.assertEqual(lib.gate_create_e2e_tests(self.ctx(**self.E2E), self.payload("SHOP-15")),
                         "SHOP-15")

    def test_the_deprecated_e2e_alias_counts_as_configured(self):
        self.docs_artifact("SHOP-15", "test-cases.md", self.CASES_E2E)
        ctx = self.ctx(e2e={"command": "make e2e"})
        self.assertEqual(lib.gate_create_e2e_tests(ctx, self.payload("SHOP-15")), "SHOP-15")


class TestGateDocsSync(GateCase):
    """Partition and lock only: no code run, a failed post-code test step, a
    code run recorded failed -- none of these is the gate's concern."""

    def setUp(self):
        super().setUp()
        self.ticket("SHOP-16")

    def test_passes_with_no_code_run_at_all(self):
        self.assertEqual(lib.gate_docs_sync(self.ctx(), self.payload("SHOP-16")), "SHOP-16")

    def test_passes_with_the_test_step_recorded_failed(self):
        self.record_run("code", "SHOP-16", "completed")
        lib.update_pipeline(self.tdir("SHOP-16"), "SHOP-16", "test", "failed", summary="cap reached")
        self.assertEqual(lib.gate_docs_sync(self.ctx(), self.payload("SHOP-16")), "SHOP-16")

    def test_passes_with_a_failed_code_run(self):
        self.record_run("code", "SHOP-16", "failed")
        self.assertEqual(lib.gate_docs_sync(self.ctx(), self.payload("SHOP-16")), "SHOP-16")

    def test_still_refuses_a_foreign_lock(self):
        self.foreign_lock("SHOP-16")
        with self.assertRaises(lib.GateError):
            lib.gate_docs_sync(self.ctx(), self.payload("SHOP-16"))


class TestGateCreatePr(GateCase):
    """Brake only: refuse when the ticket HAS a code run whose verifier did
    not pass; a ticket with no code run passes; docs-sync is not consulted."""

    def setUp(self):
        super().setUp()
        self.ticket("SHOP-17")

    def test_passes_with_no_code_run_at_all(self):
        self.assertEqual(lib.gate_create_pr(self.ctx(), self.payload("SHOP-17")), "SHOP-17")

    def test_refuses_a_code_run_whose_verifier_did_not_pass(self):
        self.record_run("code", "SHOP-17", "completed", states={"verifier_passed": False})
        with self.assertRaises(lib.GateError) as ctx:
            lib.gate_create_pr(self.ctx(), self.payload("SHOP-17"))
        self.assertIn("verifier_passed", str(ctx.exception))
        self.assertIn("/acs:code SHOP-17", str(ctx.exception))

    def test_refuses_a_code_run_that_never_recorded_a_verdict(self):
        self.record_run("code", "SHOP-17", "failed")
        with self.assertRaises(lib.GateError) as ctx:
            lib.gate_create_pr(self.ctx(), self.payload("SHOP-17"))
        self.assertIn("verifier_passed", str(ctx.exception))

    def test_passes_once_the_verifier_passed_without_docs_sync(self):
        self.record_run("code", "SHOP-17", "completed", states={"verifier_passed": True})
        self.assertFalse(lib.skill_completed(self.tdir("SHOP-17"), "docs-sync"))
        self.assertEqual(lib.gate_create_pr(self.ctx(), self.payload("SHOP-17")), "SHOP-17")


class TestGateMergePrUnchanged(GateCase):
    """The readiness brake stays: a merge needs a PR reference recorded by a
    completed run."""

    def test_refuses_without_a_recorded_pr_reference(self):
        self.ticket("SHOP-18")
        with self.assertRaises(lib.GateError) as ctx:
            lib.gate_merge_pr(self.ctx(), self.payload("SHOP-18"))
        self.assertIn("no PR reference recorded", str(ctx.exception))

    def test_passes_with_a_completed_create_pr_run_carrying_the_reference(self):
        self.ticket("SHOP-18")
        self.record_run("create-pr", "SHOP-18", "completed",
                        states={"pr": {"number": 7, "url": "https://github.com/acme/shop/pull/7"}})
        self.assertEqual(lib.gate_merge_pr(self.ctx(), self.payload("SHOP-18")), "SHOP-18")


class TestTrackerCliWarning(unittest.TestCase):
    """1779: warns for provider github with no gh; 1781: warns for provider
    jira with no acli."""

    def test_warns_for_github_without_gh(self):
        with mock.patch("shutil.which", return_value=None):
            msg = lib.tracker_cli_warning({"tracker": {"provider": "github"}})
        self.assertIn("gh", msg)

    def test_warns_for_jira_without_acli(self):
        with mock.patch("shutil.which", return_value=None):
            msg = lib.tracker_cli_warning({"tracker": {"provider": "jira"}})
        self.assertIn("acli", msg)


class TestToolVersion(unittest.TestCase):
    """1819-1820: returns None for a non-existent binary."""

    def test_returns_none_for_nonexistent_binary(self):
        self.assertIsNone(lib._tool_version("acs-definitely-not-a-real-binary-xyz"))


class TestArchitectureDependentGateTable(unittest.TestCase):
    """MAR-522: ARCHITECTURE_DEPENDENT_SKILLS is the declared set of producers
    whose only precondition is the architecture doc set. Without this, the tuple
    is a comment -- it can drift from GATES with nothing failing."""

    def test_every_declared_skill_is_registered_and_shares_the_one_check(self):
        for skill in lib.ARCHITECTURE_DEPENDENT_SKILLS:
            with self.subTest(skill=skill):
                gate = lib.GATES[skill]
                self.assertEqual(gate.__name__, "gate_" + skill.replace("-", "_"))
                # It delegates rather than re-implementing: calling it with a
                # context whose checkout has no architecture set must raise the
                # shared helper's own message, not a copy of it.
                tmp = tempfile.mkdtemp()
                self.addCleanup(shutil.rmtree, tmp, True)
                ctx = {"checkout_root": tmp, "settings": {}}
                with self.assertRaises(lib.GateError) as caught:
                    gate(ctx, {})
                self.assertIn("expected hld/tech-stack.md", str(caught.exception))

    def test_the_two_inlining_gates_now_share_it_too(self):
        """gate_create_project and gate_standardize_project each carried a
        byte-identical copy of the check body before MAR-522."""
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        ctx = {"checkout_root": tmp, "settings": {}}
        for gate in (lib.gate_create_project, lib.gate_standardize_project):
            with self.subTest(gate=gate.__name__):
                with self.assertRaises(lib.GateError) as caught:
                    gate(ctx, {})
                self.assertIn("expected hld/tech-stack.md", str(caught.exception))


class TestGateInputsTable(GateCase):
    """GATE_INPUTS is the declared classification of what each gate checks --
    none / prd / architecture / ticket -- asserted against GATES so a new gate
    must say which input it needs, and so no class is an ORDER check."""

    def test_the_classes_partition_gates_exactly(self):
        declared = [skill for skills in lib.GATE_INPUTS.values() for skill in skills]
        self.assertEqual(sorted(declared), sorted(lib.GATES),
                         "every gate is classified exactly once")
        self.assertEqual(len(declared), len(set(declared)), "no gate sits in two classes")
        self.assertEqual(sorted(lib.GATE_INPUTS), ["architecture", "none", "prd", "ticket"])

    def test_every_gate_is_named_after_its_skill(self):
        for skill, gate in lib.GATES.items():
            with self.subTest(skill=skill):
                self.assertEqual(gate.__name__, "gate_" + skill.replace("-", "_"))
                self.assertIs(getattr(lib, gate.__name__), gate)

    def test_none_gates_pass_with_no_context_at_all(self):
        for skill in lib.GATE_INPUTS["none"]:
            with self.subTest(skill=skill):
                self.assertIsNone(lib.GATES[skill]({}, {}))

    def test_prd_gates_need_only_the_prd_file(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        ctx = {"checkout_root": tmp, "settings": {}}
        for skill in lib.GATE_INPUTS["prd"]:
            with self.subTest(skill=skill):
                with self.assertRaises(lib.GateError) as caught:
                    lib.GATES[skill](ctx, {})
                self.assertIn("run /acs:create-prd first", str(caught.exception))
                write(os.path.join(tmp, "docs", "product", "prd.md"))
                self.assertIsNone(lib.GATES[skill](ctx, {}))

    def test_architecture_gates_need_only_the_doc_set(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        ctx = {"checkout_root": tmp, "settings": {}}
        for skill in lib.GATE_INPUTS["architecture"]:
            with self.subTest(skill=skill):
                with self.assertRaises(lib.GateError) as caught:
                    lib.GATES[skill](ctx, {})
                self.assertIn("expected hld/tech-stack.md", str(caught.exception))
        write(os.path.join(tmp, "docs", "architecture", "hld", "tech-stack.md"))
        for skill in lib.GATE_INPUTS["architecture"]:
            with self.subTest(skill=skill, present=True):
                self.assertIsNone(lib.GATES[skill](ctx, {}))

    def test_ticket_gates_share_the_one_resolution(self):
        """Every ticket-scoped gate refuses an unresolvable ticket with
        _resolve_ticket_for_gate's own message and refuses an archived one."""
        archived = os.path.join(lib.archive_dir(self.ws, "acme-shop"), "SHOP-90")
        os.makedirs(archived)
        for skill in lib.GATE_INPUTS["ticket"]:
            with self.subTest(skill=skill):
                with self.assertRaises(lib.GateError) as caught:
                    lib.GATES[skill](self.ctx(), {})
                self.assertIn("could not resolve a ticket id for /%s" % skill, str(caught.exception))
                with self.assertRaises(lib.GateError) as caught:
                    lib.GATES[skill](self.ctx(), self.payload("SHOP-90"))
                self.assertIn("archived", str(caught.exception))

    def test_ticket_gates_return_the_ticket_id_when_they_pass(self):
        """The id is what run_pre_payload hands the advisory."""
        self.ticket("SHOP-91")
        for skill in ("create-test-docs", "analyze-ticket", "create-impl-plan", "docs-sync", "create-pr"):
            with self.subTest(skill=skill):
                self.assertEqual(lib.GATES[skill](self.ctx(), self.payload("SHOP-91")), "SHOP-91")

    def test_every_hooked_skill_has_a_classified_gate(self):
        for skill in lib.HOOKED_SKILLS:
            with self.subTest(skill=skill):
                self.assertIn(skill, lib.GATES)


class TestPluginRoot(unittest.TestCase):
    """plugin_root() is the ONE function body the MAR-522 split had to change
    (three nested dirnames became four, since the code moved a directory
    deeper). It feeds build_context()["plugin_root"], which resolve_template
    uses to find every builtin template -- so a one-off returns a real-looking
    path and every rendered PR body silently loses its template."""

    def test_it_points_at_the_plugin_directory_that_contains_the_kernel(self):
        root = lib.plugin_root()
        self.assertTrue(os.path.isfile(os.path.join(root, ".claude-plugin", "plugin.json")),
                        "plugin_root() must contain .claude-plugin/plugin.json, got %s" % root)
        self.assertTrue(os.path.isdir(os.path.join(root, "hooks", "scripts", "acs_lib")),
                        "plugin_root() must contain the acs_lib package, got %s" % root)
        self.assertEqual(os.path.basename(root), "acs")

    def test_a_builtin_template_resolves_from_it(self):
        """The consequence a wrong plugin_root would produce, asserted directly."""
        for name in sorted(lib.BUILTIN_TEMPLATES):
            with self.subTest(template=name):
                path = lib.resolve_template(name, None, lib.plugin_root())
                self.assertIsNotNone(path, "%s must resolve under plugin_root()" % name)
                # resolve_template returns the path unchecked for a builtin, so
                # a wrong plugin_root yields a real-looking path to nothing.
                self.assertTrue(os.path.isfile(path),
                                "%s resolved to a non-existent file: %s" % (name, path))


if __name__ == "__main__":
    unittest.main()
