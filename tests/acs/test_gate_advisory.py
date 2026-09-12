"""The out-of-order ADVISORY the pre-hook prints in place of the order gates.

Since the skills-independence refactor no gate refuses a skill for running
before its predecessor; the order lives in workflows/ship.yaml. When a hooked
skill runs out of that declared order -- one of its step's `needs` is not
satisfied for the ticket per pipeline-state.json -- the pre-hook prints ONE
stderr line naming the position and continues with exit 0:

    acs: <skill> normally follows <needs> in ship.yaml; <need> has not completed for <ID>

Suppressed when settings.workflow.advisories is false. Read through
acs_lib.workflow.resolve (the consumer override when present) and
workflow.pending_needs (which never writes the ledger). Never a refusal.

Run:  python3 -m unittest tests.acs.test_gate_advisory -v
"""

import contextlib
import io
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import AcsWorkspaceCase, SCRIPTS  # noqa: E402

sys.path.insert(0, SCRIPTS)
import acs_lib as lib  # noqa: E402


def advisory_lines(stderr):
    return [line for line in stderr.splitlines()
            if line.startswith("acs: ") and lib.ADVISORY_MARK in line]


class AdvisoryCase(AcsWorkspaceCase):
    """A minted task ticket, ledger seeders, and both hook paths."""

    def setUp(self):
        super().setUp()
        self.ticket = self.new_ticket("Widget", "task")

    def step(self, step_id, status, ticket=None):
        ticket = ticket or self.ticket
        lib.update_pipeline(self.tdir(ticket), ticket, step_id, status)

    def plan(self, ticket=None):
        tdir = self.tdir(ticket or self.ticket)
        with open(os.path.join(tdir, "plan.md"), "w", encoding="utf-8") as fh:
            fh.write("# plan\n")

    def override(self, text):
        path = lib.override_workflow_path(self.repo)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def in_process(self, skill, ticket=None):
        """run_pre_payload without the dispatcher -- the same call dispatch.py
        makes once a skill is in HOOKED_SKILLS; returns (exit_code, stderr)."""
        payload = {"cwd": self.repo, "tool_name": "Skill",
                   "tool_input": {"skill": "acs:" + skill, "args": ticket or self.ticket}}
        buffer = io.StringIO()
        with contextlib.redirect_stderr(buffer):
            code = lib.run_pre_payload(skill, payload, record_marker=False)
        return code, buffer.getvalue()

    def ledger(self, ticket=None):
        ticket = ticket or self.ticket
        return lib.load_pipeline(self.tdir(ticket), ticket)["steps"]


class TestAdvisoryThroughTheHook(AdvisoryCase):
    """dispatch.py pre -> run_pre_payload -> the gate, then the advisory."""

    def test_docs_sync_before_code_passes_with_exactly_one_advisory_line(self):
        result = self.pre("docs-sync", self.ticket)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(advisory_lines(result.stderr), [
            "acs: docs-sync normally follows code in ship.yaml; code has not completed for %s"
            % self.ticket])

    def test_in_order_prints_no_advisory(self):
        self.step("code", "completed")
        result = self.pre("docs-sync", self.ticket)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(advisory_lines(result.stderr), [])

    def test_create_pr_names_every_declared_need_and_the_pending_ones(self):
        """A fresh ticket, no e2e: docs-sync and run-e2e-tests are both
        declared needs and both are pending (run-e2e-tests transitively)."""
        result = self.pre("create-pr", self.ticket)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(advisory_lines(result.stderr), [
            "acs: create-pr normally follows docs-sync and run-e2e-tests in ship.yaml; "
            "docs-sync and run-e2e-tests have not completed for %s" % self.ticket])

    def test_only_the_pending_needs_are_named(self):
        """code completed and no e2e configured: the e2e steps are skipped
        (satisfied), so docs-sync is the one need still pending."""
        self.step("code", "completed")
        result = self.pre("create-pr", self.ticket)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(advisory_lines(result.stderr), [
            "acs: create-pr normally follows docs-sync and run-e2e-tests in ship.yaml; "
            "docs-sync has not completed for %s" % self.ticket])

    def test_a_need_recorded_failed_reads_as_not_completed(self):
        self.step("code", "failed")
        result = self.pre("docs-sync", self.ticket)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(advisory_lines(result.stderr)), 1)
        self.assertIn("code has not completed for %s" % self.ticket, result.stderr)

    def test_a_need_recorded_in_progress_reads_as_not_completed(self):
        self.step("code", "in_progress")
        result = self.pre("docs-sync", self.ticket)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("code has not completed for %s" % self.ticket, result.stderr)

    def test_code_run_out_of_order_advises_after_its_own_input_check(self):
        """The plan input still refuses; once it exists, code runs with the advisory."""
        result = self.pre("code", self.ticket)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(advisory_lines(result.stderr), [])
        self.plan()
        result = self.pre("code", self.ticket)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(advisory_lines(result.stderr), [
            "acs: code normally follows create-test-docs in ship.yaml; "
            "create-test-docs has not completed for %s" % self.ticket])

    def test_a_refusal_never_carries_an_advisory(self):
        """The brake wins: a code run whose verifier did not pass is refused,
        and the advisory is not printed on the refusal path."""
        self.start("code", self.ticket)
        self.post("code", self.ticket, {"status": "completed", "states": {"verifier_passed": False}})
        result = self.pre("create-pr", self.ticket)
        self.assertEqual(result.returncode, 2)
        self.assertIn("verifier_passed", result.stderr)
        self.assertEqual(advisory_lines(result.stderr), [])

    def test_suppressed_when_settings_workflow_advisories_is_false(self):
        self.write_settings({"ticket_prefix": "SHOP", "test_coverage_percent": 90,
                             "workflow": {"advisories": False}})
        result = self.pre("docs-sync", self.ticket)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(advisory_lines(result.stderr), [])

    def test_the_default_setting_is_on(self):
        self.assertEqual(lib.DEFAULT_SETTINGS["workflow"], {"advisories": True})
        settings, _sources = lib.load_settings(self.repo)
        self.assertIs(settings["workflow"]["advisories"], True)

    def test_the_advisory_never_writes_the_ledger(self):
        """pending_needs walks without recording skips: a hand-run docs-sync
        must not leave create-api-contract or the e2e steps marked skipped."""
        before = json.dumps(self.ledger(), sort_keys=True)
        self.pre("docs-sync", self.ticket)
        self.assertEqual(json.dumps(self.ledger(), sort_keys=True), before)

    def test_merge_pr_is_not_a_ship_step_so_it_never_advises(self):
        self.start("create-pr", self.ticket)
        self.post("create-pr", self.ticket, {"status": "completed",
                                             "states": {"pr": {"number": 7, "url": "https://github.com/acme/shop/pull/7"}}})
        result = self.pre("merge-pr", self.ticket)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(advisory_lines(result.stderr), [])

    def test_create_design_is_design_work_so_it_never_advises(self):
        epic = self.new_ticket("Wishlist", "epic")
        result = self.pre("create-design", epic)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(advisory_lines(result.stderr), [])


class TestAdvisoryFollowsTheOverride(AdvisoryCase):
    """The consumer's .acs/workflows/ship.yaml replaces the default: the
    advisory names ITS step ids and needs."""

    def test_override_step_ids_are_what_the_line_names(self):
        self.override("version: 1\nname: custom\nstop_after: build\nsteps:\n"
                      "  - id: analyze\n    skill: analyze-ticket\n"
                      "  - id: build\n    skill: code\n    needs: [analyze]\n")
        self.plan()
        result = self.pre("code", self.ticket)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(advisory_lines(result.stderr), [
            "acs: code normally follows analyze in ship.yaml; analyze has not completed for %s"
            % self.ticket])
        self.step("analyze", "completed")
        result = self.pre("code", self.ticket)
        self.assertEqual(advisory_lines(result.stderr), [])

    def test_a_skill_the_override_does_not_name_prints_nothing(self):
        self.override("version: 1\nname: custom\nstop_after: build\nsteps:\n"
                      "  - id: build\n    skill: code\n")
        result = self.pre("docs-sync", self.ticket)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(advisory_lines(result.stderr), [])

    def test_an_entry_step_prints_nothing(self):
        code, stderr = self.in_process("analyze-ticket")
        self.assertEqual(code, 0, stderr)
        self.assertEqual(advisory_lines(stderr), [])

    def test_a_broken_override_yields_no_advisory_and_no_refusal(self):
        """Advice, not enforcement: a workflow that cannot be read is
        `acs.py workflow validate`'s to report, never the hook's to block on."""
        self.override("version: 1\nsteps: [\n")
        result = self.pre("docs-sync", self.ticket)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(advisory_lines(result.stderr), [])


class TestNewSkillsAdviseInProcess(AdvisoryCase):
    """The five new Build/Test gates hand their ticket id to the advisory."""

    def test_create_impl_plan_before_analyze_ticket(self):
        code, stderr = self.in_process("create-impl-plan")
        self.assertEqual(code, 0, stderr)
        self.assertEqual(advisory_lines(stderr), [
            "acs: create-impl-plan normally follows analyze-ticket in ship.yaml; "
            "analyze-ticket has not completed for %s" % self.ticket])

    def test_create_test_docs_names_both_needs(self):
        code, stderr = self.in_process("create-test-docs")
        self.assertEqual(code, 0, stderr)
        self.assertEqual(advisory_lines(stderr), [
            "acs: create-test-docs normally follows create-impl-plan and create-api-contract "
            "in ship.yaml; create-impl-plan and create-api-contract have not completed for %s"
            % self.ticket])

    def test_create_test_docs_in_order_is_quiet(self):
        for sid in ("analyze-ticket", "create-impl-plan", "create-api-contract"):
            self.step(sid, "completed")
        code, stderr = self.in_process("create-test-docs")
        self.assertEqual(code, 0, stderr)
        self.assertEqual(advisory_lines(stderr), [])

    def test_a_skipped_need_counts_as_satisfied(self):
        """No API surface: create-api-contract is skipped (when false), so a
        create-test-docs run after the plan is in order."""
        for sid in ("analyze-ticket", "create-impl-plan"):
            self.step(sid, "completed")
        code, stderr = self.in_process("create-test-docs")
        self.assertEqual(code, 0, stderr)
        self.assertEqual(advisory_lines(stderr), [])


class TestAdvisoryHelpers(AdvisoryCase):
    """workflow_advisory(ctx, skill, ticket_id, tdir=None, ticket=None) and the
    pure renderer."""

    def test_render_advisory_format(self):
        self.assertEqual(
            lib.render_advisory("docs-sync", "MAR-12", ["code"], ["code"]),
            "acs: docs-sync normally follows code in ship.yaml; code has not completed for MAR-12")
        self.assertEqual(
            lib.render_advisory("create-pr", "MAR-12", ["docs-sync", "run-e2e-tests"], ["docs-sync"]),
            "acs: create-pr normally follows docs-sync and run-e2e-tests in ship.yaml; "
            "docs-sync has not completed for MAR-12")
        self.assertEqual(
            lib.render_advisory("x", "MAR-1", ["a", "b", "c"], ["a", "b", "c"]),
            "acs: x normally follows a, b and c in ship.yaml; a, b and c have not completed for MAR-1")

    def test_helper_returns_the_line_or_none(self):
        ctx = lib.build_context(self.repo)
        self.assertEqual(
            lib.workflow_advisory(ctx, "docs-sync", self.ticket),
            "acs: docs-sync normally follows code in ship.yaml; code has not completed for %s"
            % self.ticket)
        self.step("code", "completed")
        self.assertIsNone(lib.workflow_advisory(ctx, "docs-sync", self.ticket))

    def test_helper_accepts_a_preloaded_partition_and_ticket(self):
        ctx = lib.build_context(self.repo)
        tdir = self.tdir(self.ticket)
        line = lib.workflow_advisory(ctx, "docs-sync", self.ticket, tdir=tdir,
                                     ticket=lib.load_ticket(tdir))
        self.assertIn("code has not completed", line)

    def test_helper_is_none_for_a_missing_ticket_or_unknown_skill(self):
        ctx = lib.build_context(self.repo)
        self.assertIsNone(lib.workflow_advisory(ctx, "docs-sync", "SHOP-999"))
        self.assertIsNone(lib.workflow_advisory(ctx, "merge-pr", self.ticket))
        self.assertIsNone(lib.workflow_advisory(ctx, "create-design", self.ticket))

    def test_helper_honours_the_setting_on_the_context(self):
        ctx = lib.build_context(self.repo)
        ctx["settings"] = dict(ctx["settings"], workflow={"advisories": False})
        self.assertIsNone(lib.workflow_advisory(ctx, "docs-sync", self.ticket))

    def test_the_test_alias_key_satisfies_run_e2e_tests_for_the_advisory(self):
        """Today's /acs:test records steps.test; through phases.yaml's alias
        that satisfies create-pr's run-e2e-tests need."""
        self.write_settings({"ticket_prefix": "SHOP", "test_coverage_percent": 90,
                             "e2e": {"command": "npm run e2e"}})
        for sid in ("code", "docs-sync", "create-e2e-tests"):
            self.step(sid, "completed")
        ctx = lib.build_context(self.repo)
        self.assertIn("run-e2e-tests has not completed",
                      lib.workflow_advisory(ctx, "create-pr", self.ticket))
        self.step("test", "completed")
        self.assertIsNone(lib.workflow_advisory(ctx, "create-pr", self.ticket))

    def test_acs_gate_cli_prints_the_advisory_and_exits_zero(self):
        result = self.run_script("acs.py", "gate", "--skill", "docs-sync", "--ticket", self.ticket)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["ok"], True)
        self.assertEqual(len(advisory_lines(result.stderr)), 1)


if __name__ == "__main__":
    unittest.main()
