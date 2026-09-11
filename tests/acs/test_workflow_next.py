"""`acs.py workflow next` -- the walk /acs:ship loops over -- table-driven
over ledger states.

The contract (brief section 2.5): a step is satisfied when its ledger status
is `completed`, or `skipped` because its `when` is false (recorded as
`steps.<id>.status = "skipped"` with the reason); a step is READY when every
`needs` entry is satisfied, it is not itself satisfied, and its `when` holds;
a needed step recorded failed / interrupted / in_progress / handed_off is
simply ready again; `ready` lists ready steps in file order; `mode` is
`parallel` when more than one is ready, none exclusive and max_parallel > 1
(`ready` cut to max_parallel), else `single` with exactly the first ready
step; `requires` false on a ready step -> `blocked_by` with a human pointer;
`done` once stop_after completed; an epic is refused with `{error: "epic"}`
and exit 2; an unknown ticket exits 2.

Run:  python3 -m unittest tests.acs.test_workflow_next -v
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import AcsWorkspaceCase  # noqa: E402

import acs_lib as lib  # noqa: E402

TICKET = "SHOP-1"
EPIC = "SHOP-9"

ANALYSIS_API = "---\nticket: SHOP-1\nready_for_planning: true\napi_surface: true\n---\n# Analysis\n"
ANALYSIS_NO_API = "---\nticket: SHOP-1\napi_surface: false\n---\n# Analysis\n"


class WorkflowNextCase(AcsWorkspaceCase):
    """Fixture: a task ticket partition plus helpers to seed the ledger."""

    def setUp(self):
        super().setUp()
        self.ticket(TICKET, "task")

    def ticket(self, ticket_id, ttype, **fields):
        tdir = self.tdir(ticket_id)
        os.makedirs(tdir, exist_ok=True)
        doc = lib.new_ticket_doc(ticket_id, "Widget %s" % ticket_id, ttype)
        doc.update(fields)
        lib.save_ticket(tdir, doc)
        return tdir

    def step(self, step_id, status, ticket_id=TICKET):
        lib.update_pipeline(self.tdir(ticket_id), ticket_id, step_id, status)

    def run_recorded(self, skill, status, ticket_id=TICKET):
        tdir = self.tdir(ticket_id)
        lib.append_in_progress_run(tdir, skill, ticket_id)
        lib.finalize_run(tdir, skill, ticket_id, {"status": status})

    def artifact(self, name, text, ticket_id=TICKET, docs_tree=False):
        if docs_tree:
            folder = os.path.join(self.repo, "docs", "tickets", ticket_id)
        else:
            folder = self.tdir(ticket_id)
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, name), "w", encoding="utf-8") as fh:
            fh.write(text)

    def override(self, text):
        path = lib.override_workflow_path(self.repo)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def wctx(self, ticket_id=TICKET):
        return lib.ticket_context(lib.build_context(self.repo), ticket_id)

    def next(self, ticket_id=TICKET, **kw):
        return lib.next_steps(self.wctx(ticket_id), **kw)

    def ledger(self, ticket_id=TICKET):
        return lib.load_pipeline(self.tdir(ticket_id), ticket_id)["steps"]

    def ready_ids(self, out):
        return [entry["step"] for entry in out["ready"]]


class TestFreshAndResumed(WorkflowNextCase):

    def test_fresh_ticket_starts_at_analyze_ticket(self):
        out = self.next()
        self.assertEqual(out["ticket"], TICKET)
        self.assertEqual(out["mode"], "single")
        self.assertEqual(self.ready_ids(out), ["analyze-ticket"])
        self.assertFalse(out["done"])
        self.assertIsNone(out["blocked_by"])
        entry = out["ready"][0]
        self.assertEqual(entry["skill"], "analyze-ticket")
        self.assertIn("entry step", entry["reason"])
        self.assertEqual(sorted(entry), ["args", "boundary", "exclusive", "on_fail", "on_replan",
                                         "reason", "skill", "step"])
        self.assertEqual((entry["args"], entry["boundary"], entry["on_fail"], entry["on_replan"],
                          entry["exclusive"]), (None, None, None, None, False))
        self.assertEqual(out["workflow"]["source"], "default")
        self.assertEqual(out["statuses"]["analyze-ticket"], None)

    def test_output_keys_match_the_contract(self):
        self.assertEqual(sorted(self.next()), ["blocked_by", "done", "mode", "ready", "statuses",
                                               "ticket", "workflow"])

    def test_analyze_completed_makes_the_plan_ready(self):
        self.step("analyze-ticket", "completed")
        out = self.next()
        self.assertEqual(self.ready_ids(out), ["create-impl-plan"])
        self.assertIn("analyze-ticket completed", out["ready"][0]["reason"])

    def test_resumed_with_code_completed_and_no_e2e(self):
        """No e2e configured: create-e2e-tests is skipped (when false), so is
        run-e2e-tests (post_code_test_active false), and docs-sync alone is ready."""
        for sid in ("analyze-ticket", "create-impl-plan", "create-test-docs", "code"):
            self.step(sid, "completed")
        self.artifact("analysis.md", ANALYSIS_NO_API)
        out = self.next()
        self.assertEqual(out["mode"], "single")
        self.assertEqual(self.ready_ids(out), ["docs-sync"])
        ledger = self.ledger()
        self.assertEqual(ledger["create-api-contract"]["status"], "skipped")
        self.assertEqual(ledger["create-api-contract"]["reason"], "when: api_surface_changed is false")
        self.assertEqual(ledger["create-api-contract"]["when"], "api_surface_changed")
        self.assertEqual(ledger["create-e2e-tests"]["status"], "skipped")
        self.assertEqual(ledger["run-e2e-tests"]["status"], "skipped")
        self.assertEqual(out["statuses"]["run-e2e-tests"], "skipped")
        self.step("docs-sync", "completed")
        out = self.next()
        self.assertEqual(self.ready_ids(out), ["create-pr"])
        self.assertIn("run-e2e-tests skipped", out["ready"][0]["reason"])

    def test_done_after_create_pr(self):
        for sid in ("analyze-ticket", "create-impl-plan", "create-test-docs", "code",
                    "docs-sync", "create-pr"):
            self.step(sid, "completed")
        out = self.next()
        self.assertTrue(out["done"])
        self.assertEqual(out["ready"], [])
        self.assertEqual(out["mode"], "single")

    def test_the_test_alias_ledger_key_satisfies_run_e2e_tests(self):
        """Today's /acs:test records `steps.test`; run-e2e-tests reads it through phases.yaml's alias."""
        self.write_settings({"ticket_prefix": "SHOP", "e2e": {"command": "npm run e2e"}})
        for sid in ("analyze-ticket", "create-impl-plan", "create-test-docs", "code",
                    "create-e2e-tests", "docs-sync"):
            self.step(sid, "completed")
        self.step("test", "completed")
        out = self.next()
        self.assertEqual(self.ready_ids(out), ["create-pr"])
        self.assertEqual(out["statuses"]["run-e2e-tests"], "completed")


class TestRerunStates(WorkflowNextCase):

    def _seed_to_code(self):
        for sid in ("analyze-ticket", "create-impl-plan", "create-test-docs"):
            self.step(sid, "completed")

    def test_each_non_completed_status_makes_the_step_ready_again(self):
        self._seed_to_code()
        for status in ("failed", "interrupted", "in_progress", "handed_off"):
            with self.subTest(status=status):
                self.step("code", status)
                out = self.next()
                self.assertEqual(self.ready_ids(out), ["code"])
                self.assertIn("last run recorded %s" % status, out["ready"][0]["reason"])
                self.assertIn("ready again", out["ready"][0]["reason"])

    def test_code_carries_its_boundary_replan_and_exclusive_flags(self):
        self._seed_to_code()
        entry = self.next()["ready"][0]
        self.assertEqual(entry["step"], "code")
        self.assertEqual(entry["boundary"], "full_verify_stop")
        self.assertEqual(entry["on_replan"], "create-impl-plan")
        self.assertTrue(entry["exclusive"])

    def test_a_failed_needed_step_blocks_its_dependants_and_is_ready_itself(self):
        self.step("analyze-ticket", "failed")
        out = self.next()
        self.assertEqual(self.ready_ids(out), ["analyze-ticket"])


class TestDesignRequirement(WorkflowNextCase):

    def _child_of_pending_epic(self):
        self.ticket(EPIC, "epic")  # needs_design true by construction
        lib.save_ticket(self.tdir(TICKET), dict(lib.load_ticket(self.tdir(TICKET)), parent=EPIC))
        self.step("analyze-ticket", "completed")

    def test_child_with_pending_parent_design_is_blocked(self):
        self._child_of_pending_epic()
        out = self.next()
        self.assertEqual(out["ready"], [])
        self.assertEqual(out["mode"], "single")
        self.assertEqual(out["blocked_by"]["step"], "create-impl-plan")
        self.assertEqual(out["blocked_by"]["predicate"], "design_approved")
        self.assertIn("run /acs:create-design %s" % EPIC, out["blocked_by"]["pointer"])
        self.assertIn("first", out["blocked_by"]["pointer"])

    def test_design_md_alone_is_not_approval(self):
        self._child_of_pending_epic()
        self.artifact("design.md", "# Design\n", ticket_id=EPIC)
        self.assertIsNotNone(self.next()["blocked_by"])

    def test_ledger_alone_is_not_approval(self):
        self._child_of_pending_epic()
        self.run_recorded("create-design", "completed", ticket_id=EPIC)
        self.assertIsNotNone(self.next()["blocked_by"])

    def test_partition_design_plus_completed_run_unblocks(self):
        self._child_of_pending_epic()
        self.artifact("design.md", "# Design\n", ticket_id=EPIC)
        self.run_recorded("create-design", "completed", ticket_id=EPIC)
        out = self.next()
        self.assertIsNone(out["blocked_by"])
        self.assertEqual(self.ready_ids(out), ["create-impl-plan"])

    def test_docs_tree_design_plus_completed_run_unblocks(self):
        self._child_of_pending_epic()
        self.artifact("design.md", "# Design\n", ticket_id=EPIC, docs_tree=True)
        self.run_recorded("create-design", "completed", ticket_id=EPIC)
        self.assertEqual(self.ready_ids(self.next()), ["create-impl-plan"])

    def test_a_failed_design_run_does_not_approve(self):
        self._child_of_pending_epic()
        self.artifact("design.md", "# Design\n", ticket_id=EPIC)
        self.run_recorded("create-design", "failed", ticket_id=EPIC)
        self.assertIsNotNone(self.next()["blocked_by"])

    def test_own_needs_design_ticket_points_at_itself(self):
        lib.save_ticket(self.tdir(TICKET), dict(lib.load_ticket(self.tdir(TICKET)), needs_design=True))
        self.step("analyze-ticket", "completed")
        out = self.next()
        self.assertEqual(out["blocked_by"]["pointer"], "run /acs:create-design %s first" % TICKET)
        self.artifact("design.md", "# Design\n")
        self.run_recorded("create-design", "completed")
        self.assertIsNone(self.next()["blocked_by"])

    def test_predicates_are_callable_directly(self):
        wctx = self.wctx()
        self.assertTrue(lib.design_approved(wctx))
        self.assertFalse(lib.api_surface_changed(wctx))
        self.assertFalse(lib.e2e_configured(wctx))
        self.assertFalse(lib.post_code_test_active(wctx))
        self.assertEqual(lib.post_code_test_fix_loops_cap(wctx), 2)
        self.assertEqual(sorted(lib.PREDICATES), ["api_surface_changed", "design_approved",
                                                   "e2e_configured", "post_code_test_active"])


class TestWhenSkips(WorkflowNextCase):

    def _seed_to_api_contract(self):
        self.step("analyze-ticket", "completed")
        self.step("create-impl-plan", "completed")

    def test_when_false_is_recorded_as_skipped_and_unblocks_dependants(self):
        self._seed_to_api_contract()
        out = self.next()
        self.assertEqual(self.ready_ids(out), ["create-test-docs"])
        self.assertIn("create-api-contract skipped", out["ready"][0]["reason"])
        entry = self.ledger()["create-api-contract"]
        self.assertEqual(entry["status"], "skipped")
        self.assertEqual(entry["summary"], "when: api_surface_changed is false")
        self.assertIn("ended_at", entry)

    def test_dry_run_records_nothing(self):
        self._seed_to_api_contract()
        out = self.next(record_skips=False)
        self.assertEqual(self.ready_ids(out), ["create-test-docs"])
        self.assertNotIn("create-api-contract", self.ledger())

    def test_api_surface_true_in_the_partition_makes_the_contract_ready(self):
        self._seed_to_api_contract()
        self.artifact("analysis.md", ANALYSIS_API)
        self.assertEqual(self.ready_ids(self.next()), ["create-api-contract"])

    def test_api_surface_true_in_the_docs_tree_wins(self):
        self._seed_to_api_contract()
        self.artifact("analysis.md", ANALYSIS_NO_API)
        self.artifact("analysis.md", ANALYSIS_API, docs_tree=True)
        self.assertEqual(self.ready_ids(self.next()), ["create-api-contract"])

    def test_opting_out_of_the_docs_tree_reads_only_the_partition(self):
        self.write_settings({"ticket_prefix": "SHOP", "artifacts": {"tickets_path": None}})
        self._seed_to_api_contract()
        self.artifact("analysis.md", ANALYSIS_API, docs_tree=True)
        self.assertEqual(self.ready_ids(self.next()), ["create-test-docs"])

    def test_a_skipped_step_whose_when_now_holds_is_ready_again(self):
        self._seed_to_api_contract()
        self.next()
        self.assertEqual(self.ledger()["create-api-contract"]["status"], "skipped")
        self.artifact("analysis.md", ANALYSIS_API)
        out = self.next()
        self.assertEqual(self.ready_ids(out), ["create-api-contract"])
        self.assertIn("previously skipped", out["ready"][0]["reason"])

    def test_a_recorded_skip_is_not_rewritten(self):
        self._seed_to_api_contract()
        self.next()
        first = self.ledger()["create-api-contract"]
        self.next()
        self.assertEqual(self.ledger()["create-api-contract"], first)

    def test_corrupt_front_matter_is_refused_with_its_line(self):
        self._seed_to_api_contract()
        self.artifact("analysis.md", "---\nticket: SHOP-1\napi_surface: {yes}\n---\n")
        with self.assertRaises(lib.WorkflowError) as ctx:
            self.next()
        self.assertEqual(ctx.exception.line, 3)
        self.assertIn("front matter", str(ctx.exception))


class TestParallelism(WorkflowNextCase):

    def _seed_to_code_completed(self):
        for sid in ("analyze-ticket", "create-impl-plan", "create-test-docs", "code"):
            self.step(sid, "completed")

    def test_e2e_configured_makes_both_test_and_docs_steps_ready_in_parallel(self):
        self.write_settings({"ticket_prefix": "SHOP", "e2e": {"command": "npm run e2e"}})
        self._seed_to_code_completed()
        out = self.next()
        self.assertEqual(out["mode"], "parallel")
        self.assertEqual(self.ready_ids(out), ["create-e2e-tests", "docs-sync"])
        self.assertEqual(out["workflow"]["max_parallel"], 2)
        self.assertNotIn("run-e2e-tests", self.ledger())

    def test_suites_e2e_also_counts_as_configured(self):
        self.write_settings({"ticket_prefix": "SHOP", "suites": {"e2e": {"command": "make e2e"}}})
        self._seed_to_code_completed()
        self.assertEqual(self.ready_ids(self.next()), ["create-e2e-tests", "docs-sync"])

    def test_run_e2e_tests_follows_with_rendered_args_and_the_resolved_cap(self):
        self.write_settings({"ticket_prefix": "SHOP", "e2e": {"command": "npm run e2e"},
                             "post_code_test": {"fix_loops_cap": 5}})
        self._seed_to_code_completed()
        self.step("create-e2e-tests", "completed")
        self.step("docs-sync", "completed")
        out = self.next()
        self.assertEqual(self.ready_ids(out), ["run-e2e-tests"])
        entry = out["ready"][0]
        self.assertEqual(entry["args"], "--for-ticket %s" % TICKET)
        self.assertEqual(entry["on_fail"], {"relay_to": "code", "max_loops": 5})

    def test_the_fix_loops_cap_defaults_to_two(self):
        self.write_settings({"ticket_prefix": "SHOP", "post_code_test": {"enabled": True}})
        self._seed_to_code_completed()
        self.step("docs-sync", "completed")
        out = self.next()
        # No e2e config: create-e2e-tests is skipped, yet the explicit enabled
        # flag keeps run-e2e-tests active.
        self.assertEqual(self.ledger()["create-e2e-tests"]["status"], "skipped")
        self.assertEqual(self.ready_ids(out), ["run-e2e-tests"])
        self.assertEqual(out["ready"][0]["on_fail"]["max_loops"], 2)

    def test_post_code_test_disabled_skips_the_run_even_with_e2e(self):
        self.write_settings({"ticket_prefix": "SHOP", "e2e": {"command": "npm run e2e"},
                             "post_code_test": {"enabled": False}})
        self._seed_to_code_completed()
        self.step("create-e2e-tests", "completed")
        self.step("docs-sync", "completed")
        out = self.next()
        self.assertEqual(self.ledger()["run-e2e-tests"]["status"], "skipped")
        self.assertEqual(self.ready_ids(out), ["create-pr"])

    def test_a_failed_leg_is_ready_again_after_its_sibling_completed(self):
        self.write_settings({"ticket_prefix": "SHOP", "e2e": {"command": "npm run e2e"}})
        self._seed_to_code_completed()
        self.step("create-e2e-tests", "failed")
        self.step("docs-sync", "completed")
        out = self.next()
        self.assertEqual(out["mode"], "single")
        self.assertEqual(self.ready_ids(out), ["create-e2e-tests"])
        self.assertIn("last run recorded failed", out["ready"][0]["reason"])

    THREE_ENTRY = ("version: 1\nname: fan\nstop_after: c\nmax_parallel: %d\nsteps:\n"
                   "  - id: a\n    skill: analyze-ticket\n"
                   "  - id: b\n    skill: create-test-docs\n%s"
                   "  - id: c\n    skill: docs-sync\n")

    def test_ready_is_truncated_to_max_parallel(self):
        self.override(self.THREE_ENTRY % (2, ""))
        out = self.next()
        self.assertEqual(out["mode"], "parallel")
        self.assertEqual(self.ready_ids(out), ["a", "b"])
        self.assertEqual(out["workflow"]["source"], "override")

    def test_max_parallel_one_means_single(self):
        self.override(self.THREE_ENTRY % (1, ""))
        out = self.next()
        self.assertEqual(out["mode"], "single")
        self.assertEqual(self.ready_ids(out), ["a"])

    def test_an_exclusive_step_forces_single_mode_in_file_order(self):
        self.override(self.THREE_ENTRY % (3, "    exclusive: true\n"))
        out = self.next()
        self.assertEqual(out["mode"], "single")
        self.assertEqual(self.ready_ids(out), ["a"])
        self.step("a", "completed")
        out = self.next()
        self.assertEqual(out["mode"], "single")
        self.assertEqual(self.ready_ids(out), ["b"])
        self.assertTrue(out["ready"][0]["exclusive"])
        self.step("b", "completed")
        self.assertEqual(self.ready_ids(self.next()), ["c"])

    def test_all_three_in_parallel_when_max_parallel_allows(self):
        self.override(self.THREE_ENTRY % (3, ""))
        out = self.next()
        self.assertEqual(self.ready_ids(out), ["a", "b", "c"])


class TestRefusals(WorkflowNextCase):

    def test_epic_is_refused_with_the_payload(self):
        self.ticket(EPIC, "epic")
        with self.assertRaises(lib.WorkflowError) as ctx:
            self.next(EPIC)
        self.assertEqual(ctx.exception.payload["error"], "epic")
        self.assertEqual(ctx.exception.payload["ticket"], EPIC)
        self.assertIn("/acs:create-design %s" % EPIC, ctx.exception.payload["pointer"])
        self.assertIn("--fan-out", ctx.exception.payload["pointer"])

    def test_unknown_ticket_is_refused(self):
        with self.assertRaises(lib.WorkflowError) as ctx:
            self.wctx("SHOP-404")
        self.assertIn("no workspace partition for SHOP-404", str(ctx.exception))
        self.assertIn("/acs:create-ticket", str(ctx.exception))

    def test_corrupt_ticket_is_refused(self):
        tdir = self.tdir("SHOP-5")
        os.makedirs(tdir)
        with self.assertRaises(lib.WorkflowError):
            self.wctx("SHOP-5")

    def test_archived_ticket_is_refused(self):
        archived = os.path.join(lib.archive_dir(self.ws, "acme-shop"), "SHOP-6")
        os.makedirs(archived)
        lib.save_ticket(archived, lib.new_ticket_doc("SHOP-6", "Old", "task"))
        with self.assertRaises(lib.WorkflowError) as ctx:
            self.wctx("SHOP-6")
        self.assertIn("archived", str(ctx.exception))

    def test_an_invalid_override_is_refused_with_its_line(self):
        self.override("version: 1\nname: bad\nsteps:\n  - id: a\n    skill: merge-pr\n")
        with self.assertRaises(lib.WorkflowError) as ctx:
            self.next()
        self.assertEqual(ctx.exception.line, 5)


class TestPendingNeeds(WorkflowNextCase):
    """What the pre-hook advisory reads: a hand-invoked skill's unsatisfied
    predecessors, without touching the ledger."""

    def test_docs_sync_on_a_fresh_ticket_waits_for_code(self):
        self.assertEqual(lib.pending_needs(self.wctx(), "docs-sync"),
                         [{"step": "code", "skill": "code", "status": None}])
        self.assertEqual(self.ledger(), {})

    def test_an_entry_skill_has_no_pending_needs(self):
        self.assertEqual(lib.pending_needs(self.wctx(), "analyze-ticket"), [])

    def test_satisfied_needs_are_not_pending(self):
        for sid in ("analyze-ticket", "create-impl-plan", "create-test-docs", "code"):
            self.step(sid, "completed")
        self.assertEqual(lib.pending_needs(self.wctx(), "docs-sync"), [])

    def test_a_failed_need_is_reported_with_its_status(self):
        self.step("analyze-ticket", "failed")
        self.assertEqual(lib.pending_needs(self.wctx(), "create-impl-plan"),
                         [{"step": "analyze-ticket", "skill": "analyze-ticket", "status": "failed"}])

    def test_the_alias_resolves_to_its_target(self):
        self.assertEqual(lib.pending_needs(self.wctx(), "test"),
                         [{"step": "create-e2e-tests", "skill": "create-e2e-tests", "status": None}])

    def test_a_skill_outside_the_workflow_has_nothing_pending(self):
        self.assertEqual(lib.pending_needs(self.wctx(), "create-ticket"), [])

    def test_a_skipped_need_is_not_pending_but_is_never_recorded_here(self):
        self.step("analyze-ticket", "completed")
        self.step("create-impl-plan", "completed")
        self.assertEqual(lib.pending_needs(self.wctx(), "create-test-docs"), [])
        self.assertNotIn("create-api-contract", self.ledger())


class TestCli(WorkflowNextCase):

    def acs(self, *args, **kwargs):
        return self.run_script("acs.py", *args, **kwargs)

    def test_next_prints_the_walk(self):
        res = self.acs("workflow", "next", "--ticket", TICKET)
        self.assertEqual(res.returncode, 0, res.stderr)
        out = json.loads(res.stdout)
        self.assertTrue(out["ok"])
        self.assertEqual(out["mode"], "single")
        self.assertEqual([e["step"] for e in out["ready"]], ["analyze-ticket"])
        self.assertEqual(out["ticket"], TICKET)
        self.assertFalse(out["done"])
        self.assertIsNone(out["blocked_by"])

    def test_next_records_skips_unless_dry_run(self):
        self.step("analyze-ticket", "completed")
        self.step("create-impl-plan", "completed")
        res = self.acs("workflow", "next", "--ticket", TICKET, "--dry-run")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertNotIn("create-api-contract", self.ledger())
        res = self.acs("workflow", "next", "--ticket", TICKET)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(self.ledger()["create-api-contract"]["status"], "skipped")

    def test_next_refuses_an_epic_with_json_and_exit_two(self):
        self.ticket(EPIC, "epic")
        res = self.acs("workflow", "next", "--ticket", EPIC)
        self.assertEqual(res.returncode, 2)
        out = json.loads(res.stdout)
        self.assertEqual(out["error"], "epic")
        self.assertIn("/acs:create-design %s" % EPIC, out["pointer"])
        self.assertIn("acs workflow next:", res.stderr)

    def test_next_refuses_an_unknown_ticket_with_exit_two(self):
        res = self.acs("workflow", "next", "--ticket", "SHOP-404")
        self.assertEqual(res.returncode, 2)
        self.assertEqual(res.stdout, "")
        self.assertIn("SHOP-404", res.stderr)

    def test_next_resolves_the_ticket_from_the_branch_when_omitted(self):
        import subprocess
        # An unborn branch has no name to read; the fixture repo needs a commit first.
        subprocess.run(["git", "-C", self.repo, "-c", "user.name=t", "-c", "user.email=t@example.com",
                        "commit", "-q", "--allow-empty", "-m", "init"], check=True)
        subprocess.run(["git", "-C", self.repo, "checkout", "-q", "-b", "task/%s-widget" % TICKET],
                       check=True)
        res = self.acs("workflow", "next")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(json.loads(res.stdout)["ticket"], TICKET)

    def test_blocked_by_reaches_the_cli(self):
        self.ticket(EPIC, "epic")
        lib.save_ticket(self.tdir(TICKET), dict(lib.load_ticket(self.tdir(TICKET)), parent=EPIC))
        self.step("analyze-ticket", "completed")
        out = json.loads(self.acs("workflow", "next", "--ticket", TICKET).stdout)
        self.assertEqual(out["ready"], [])
        self.assertEqual(out["blocked_by"]["predicate"], "design_approved")


if __name__ == "__main__":
    unittest.main()
