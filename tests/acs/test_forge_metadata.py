"""MAR-525: PR-metadata fill and tracker sync are commands, not recipes.

`create-pr/SKILL.md` spent about 95 lines walking the model through label,
assignee, reviewer and Project-field writes; `create-ticket/SKILL.md` about 125
on the same shape for tracker sync. Every step is mechanical — a `gh` call, a
case-insensitive name match against the board's own field list, one finding when
the board does not define the field — and all of it was re-derived on every run.

Every case here is driven from a **recorded `gh` transcript**: the flows perform
no I/O of their own, so the arms that only fire when a board is missing a field,
or when one call in five fails, are exercised without a forge. That is what
makes the two failure policies checkable rather than described:

  * PR metadata fill is non-critical throughout — a failure is an `info`
    finding with the command, and the next sub-step still runs.
  * Tracker sync is critical per ticket, soft per batch — a failed issue
    creation is an `error` finding naming the ticket, and the batch continues.
"""

import json
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
sys.path.insert(0, SCRIPTS)

import acs_lib as lib  # noqa: E402

sys.path.insert(0, os.path.join(REPO_ROOT, "tests", "acs"))
from acs_case import AcsWorkspaceCase  # noqa: E402

SETTINGS = {"tracker": {"provider": "github",
                        "github": {"owner": "acme", "project_number": 7}}}

FIELDS = {"fields": [
    {"id": "f-status", "name": "Status", "dataType": "SINGLE_SELECT",
     "options": [{"id": "opt-progress", "name": "In Progress"},
                 {"id": "opt-review", "name": "In Review"}]},
    {"id": "f-type", "name": "Type", "dataType": "SINGLE_SELECT",
     "options": [{"id": "opt-task", "name": "Task"},
                 {"id": "opt-story", "name": "Story"}]},
]}
ITEMS = {"items": [{"id": "item-9", "projectId": "PVT_1",
                    "content": {"url": "https://example.invalid/issues/9"}}]}

RECORDED = {
    "gh issue create": (0, "https://example.invalid/issues/9\n", ""),
    "gh issue edit": (0, "", ""),
    "gh label create": (0, "", ""),
    "gh project item-add": (0, "", ""),
    "gh project item-list": (0, json.dumps(ITEMS), ""),
    "gh project field-list": (0, json.dumps(FIELDS), ""),
    "gh project item-edit": (0, "", ""),
}


def ticket(**over):
    doc = {"id": "SHOP-1", "type": "task", "title": "Bulk import"}
    doc.update(over)
    return doc


class RecordedRunnerTest(unittest.TestCase):
    """The seam the fixtures rest on."""

    def test_the_longest_matching_prefix_wins(self):
        """A fixture answers `gh project field-list` once and still tells
        `gh pr edit --add-label` from `gh pr edit --add-assignee`."""
        gh = lib.Gh(responses={"gh pr edit": (0, "generic", ""),
                               "gh pr edit 1 --add-label": (0, "specific", "")})
        self.assertEqual(gh(["gh", "pr", "edit", "1", "--add-label", "task"])[1], "specific")
        self.assertEqual(gh(["gh", "pr", "edit", "1", "--add-assignee", "@me"])[1], "generic")

    def test_an_unrecorded_call_fails_loudly_rather_than_silently_passing(self):
        gh = lib.Gh(responses={"gh pr edit": (0, "", "")})
        code, _out, err = gh(["gh", "project", "item-add", "7"])
        self.assertEqual(code, 1)
        self.assertIn("no recorded response", err)

    def test_every_call_is_recorded_in_order(self):
        gh = lib.Gh(responses={"gh": (0, "", "")})
        gh(["gh", "a"])
        gh(["gh", "b"])
        self.assertEqual(gh.calls, ["gh a", "gh b"])


class FieldResolutionTest(unittest.TestCase):
    """The board's spelling wins; our preference only decides between two
    spellings the board itself defines."""

    def test_field_names_match_case_insensitively(self):
        fields = lib.project_fields(FIELDS)
        self.assertEqual(lib.match_field(fields, ("status",))["id"], "f-status")
        self.assertEqual(lib.match_field(fields, ("  STATUS  ",))["id"], "f-status")
        self.assertIsNone(lib.match_field(fields, ("Priority",)))

    def test_preference_order_decides_between_two_defined_spellings(self):
        fields = [{"id": "a", "name": "Estimate"}, {"id": "b", "name": "Points"}]
        self.assertEqual(lib.match_field(fields, ("Story Points", "Points", "Estimate"))["id"],
                         "b", "Points precedes Estimate in the table")

    def test_a_bare_list_and_an_enveloped_list_both_parse(self):
        """gh has shipped both shapes; accepting both is cheaper than pinning a
        gh version in a comment nobody updates."""
        self.assertEqual(len(lib.project_fields(FIELDS["fields"])), 2)
        self.assertEqual(len(lib.project_fields(FIELDS)), 2)
        self.assertEqual(lib.project_fields(None), [])

    def test_options_match_case_insensitively_and_in_preference_order(self):
        status = lib.match_field(lib.project_fields(FIELDS), ("Status",))
        self.assertEqual(lib.match_option(status, "in review")["id"], "opt-review")
        self.assertIsNone(lib.match_option(status, "Done"))
        self.assertEqual(lib.first_matching_option(status, ("Done", "In Review"))["id"],
                         "opt-review")
        self.assertIsNone(lib.first_matching_option(status, ("Done", "Shipped")))

    def test_an_item_is_found_by_its_url_ignoring_a_trailing_slash(self):
        items = lib.project_items(ITEMS)
        self.assertEqual(lib.find_item_for_url(items, "https://example.invalid/issues/9/")["id"],
                         "item-9")
        self.assertIsNone(lib.find_item_for_url(items, "https://example.invalid/issues/10"))


class TrackerSyncBatchTest(unittest.TestCase):
    """Critical per ticket, soft per batch — the rule create-ticket already had
    and could only state."""

    def _gh(self, **over):
        responses = dict(RECORDED)
        responses.update(over)
        return lib.Gh(responses=responses)

    def test_a_ticket_that_fails_to_create_never_stops_the_others(self):
        calls = {"n": 0}

        class Flaky(lib.Gh):
            def __call__(self, argv):
                if argv[:3] == ["gh", "issue", "create"]:
                    calls["n"] += 1
                    if calls["n"] == 1:
                        self.calls.append(" ".join(argv))
                        return 1, "", "GitHub access is not enabled for this session"
                return lib.Gh.__call__(self, argv)

        gh = Flaky(responses=RECORDED)
        out = lib.tracker_sync(gh, SETTINGS,
                               [ticket(id="SHOP-1"), ticket(id="SHOP-2")], {})
        self.assertEqual(out["failed"], ["SHOP-1"])
        self.assertEqual(sorted(out["synced"]), ["SHOP-2"])

        failure = [f for f in out["findings"] if f["severity"] == "error"]
        self.assertEqual(len(failure), 1)
        self.assertIn("SHOP-1", failure[0]["message"])
        self.assertFalse(failure[0]["replayable"],
                         "a failed issue creation is not blindly replayable")
        self.assertIn(lib.GH_ACCESS_HINT.splitlines()[0].strip(), failure[0]["message"],
                      "the canonical hint must ride along with the error")

    def test_a_failed_ticket_keeps_its_external_unset_so_it_can_be_retried(self):
        gh = self._gh(**{"gh issue create": (1, "", "boom")})
        out = lib.tracker_sync(gh, SETTINGS, [ticket()], {})
        self.assertEqual(out["synced"], {})
        self.assertEqual(out["failed"], ["SHOP-1"])

    def test_everything_after_the_create_is_non_critical(self):
        """Labels, assignee, milestone and Projects are best-effort: the ticket
        still syncs, and each failure is one info finding with its command."""
        gh = self._gh(**{"gh issue edit": (1, "", "no permission"),
                         "gh project item-add": (1, "", "no project")})
        out = lib.tracker_sync(gh, SETTINGS, [ticket(assignee="dana")], {})
        self.assertEqual(out["failed"], [])
        self.assertEqual(out["synced"]["SHOP-1"]["key"], "9")
        self.assertTrue(all(f["severity"] == "info" for f in out["findings"]))
        self.assertTrue(all(f["command"] for f in out["findings"]))

    def test_the_external_reference_is_read_from_the_created_issues_url(self):
        gh = self._gh()
        external, _findings = lib.tracker_sync_one(gh, SETTINGS, ticket(), "body.md")
        self.assertEqual(external, {"provider": "github", "key": "9",
                                    "url": "https://example.invalid/issues/9"})

    def test_labels_are_ensured_then_applied_together(self):
        gh = self._gh()
        lib.tracker_sync_one(gh, SETTINGS, ticket(), "body.md")
        self.assertIn("gh label create ACS --description Created by the acs pipeline", gh.calls)
        self.assertIn("gh label create task --description Created by the acs pipeline", gh.calls)
        self.assertIn("gh issue edit 9 --add-label ACS,task", gh.calls)

    def test_a_null_assignee_and_no_milestone_are_silent(self):
        gh = self._gh()
        _external, findings = lib.tracker_sync_one(gh, SETTINGS, ticket(), "body.md")
        self.assertFalse([c for c in gh.calls if "--add-assignee" in c])
        self.assertFalse([c for c in gh.calls if "--milestone" in c])
        self.assertFalse([f for f in findings if "assignee" in f["message"]])

    def test_the_ticket_status_is_the_boards_in_progress_column(self):
        gh = self._gh()
        lib.tracker_sync_one(gh, SETTINGS, ticket(), "body.md")
        self.assertIn("--field-id f-status --single-select-option-id opt-progress",
                      " | ".join(gh.calls))

    def test_the_type_field_is_set_from_the_tickets_type(self):
        gh = self._gh()
        lib.tracker_sync_one(gh, SETTINGS, ticket(type="story"), "body.md")
        self.assertIn("--field-id f-type --single-select-option-id opt-story",
                      " | ".join(gh.calls))

    def test_no_project_configured_is_a_no_op_not_a_finding(self):
        gh = self._gh()
        _external, findings = lib.tracker_sync_one(
            gh, {"tracker": {"github": {}}}, ticket(), "body.md")
        self.assertFalse([c for c in gh.calls if c.startswith("gh project")])
        self.assertEqual(findings, [])


class SyncCandidatesTest(unittest.TestCase):
    """create-ticket's "tickets to sync" rule, as a filter."""

    def test_an_already_synced_ticket_is_excluded(self):
        """A --fan-out run's root is an already-synced epic; re-applying the
        set literally would re-create its issue as a duplicate."""
        tickets = [ticket(id="EPIC-1", external={"provider": "github", "key": "3"}),
                   ticket(id="SHOP-2")]
        self.assertEqual([t["id"] for t in lib.sync_candidates(tickets, ())], ["SHOP-2"])

    def test_a_product_flow_delivery_ticket_is_excluded(self):
        titles = ("Product definition (PRD)", "Product architecture doc set")
        tickets = [ticket(id="P-1", title="Product definition (PRD)"), ticket(id="SHOP-2")]
        self.assertEqual([t["id"] for t in lib.sync_candidates(tickets, titles)], ["SHOP-2"])

    def test_the_shipped_product_titles_are_what_gets_excluded(self):
        self.assertIn("Product definition (PRD)", lib.PRODUCT_TICKET_TITLES.values())


class ForgeCliTest(AcsWorkspaceCase):
    """`acs.py pr metadata fill` / `acs.py tracker sync`, driven the way a
    SKILL.md drives them, with the gh transcript replayed from a file."""

    def setUp(self):
        super().setUp()
        self.write_settings({"ticket_prefix": "SHOP", "test_coverage_percent": 90,
                             "tracker": {"provider": "github",
                                         "github": {"owner": "acme", "project_number": 7}}})
        self.ticket = self.new_ticket("Bulk import", "task")
        self.replay = os.path.join(self.tmp, "gh.json")
        recorded = dict(RECORDED)
        recorded["gh pr edit"] = (0, "", "")
        recorded["gh pr diff"] = (0, "src/a.py\n", "")
        recorded["gh pr view"] = (0, "https://example.invalid/pull/42\n", "")
        with open(self.replay, "w", encoding="utf-8") as fh:
            json.dump({k: list(v) for k, v in recorded.items()}, fh)

    def _mark_synced(self):
        tdir = self.tdir(self.ticket)
        doc = lib.load_ticket(tdir)
        doc["external"] = {"provider": "github", "key": "9"}
        lib.save_ticket(tdir, doc)

    def test_pr_metadata_fill_is_a_no_op_for_an_unsynced_ticket(self):
        out = self.run_script("acs.py", "pr", "metadata", "fill", "--ticket", self.ticket, "--pr", "42",
                              "--gh-replay", self.replay)
        self.assertEqual(out.returncode, 0, out.stderr)
        body = json.loads(out.stdout)
        self.assertTrue(body["skipped"])
        self.assertEqual(body["findings"], [])

    def test_pr_metadata_fill_runs_the_whole_pass_for_a_synced_ticket(self):
        self._mark_synced()
        out = self.run_script("acs.py", "pr", "metadata", "fill", "--ticket", self.ticket, "--pr", "42",
                              "--author", "@me-login", "--gh-replay", self.replay)
        self.assertEqual(out.returncode, 0, out.stderr)
        body = json.loads(out.stdout)
        self.assertFalse(body["skipped"])
        calls = " | ".join(body["calls"])
        self.assertIn("gh pr edit 42 --add-assignee @me", calls)
        self.assertIn("gh pr edit 42 --add-label task", calls)
        self.assertIn("gh project item-add 7 --owner acme", calls)

    def test_exit_zero_means_the_pass_ran_not_that_every_field_landed(self):
        self._mark_synced()
        with open(self.replay, "w", encoding="utf-8") as fh:
            json.dump({"gh": [1, "", "everything is broken"]}, fh)
        out = self.run_script("acs.py", "pr", "metadata", "fill", "--ticket", self.ticket, "--pr", "42",
                              "--gh-replay", self.replay)
        self.assertEqual(out.returncode, 0, out.stderr)
        body = json.loads(out.stdout)
        self.assertTrue(body["findings"])
        self.assertTrue(all(f["severity"] == "info" for f in body["findings"]))

    def test_tracker_sync_dry_run_reports_the_set_and_writes_nothing(self):
        out = self.run_script("acs.py", "tracker", "sync", "--ticket", self.ticket,
                              "--dry-run")
        self.assertEqual(out.returncode, 0, out.stderr)
        body = json.loads(out.stdout)
        self.assertEqual(body["would_sync"], [self.ticket])
        self.assertEqual(body["synced"], {})

    def test_tracker_sync_excludes_an_already_synced_ticket(self):
        self._mark_synced()
        body = json.loads(self.run_script("acs.py", "tracker", "sync", "--ticket",
                                          self.ticket, "--dry-run").stdout)
        self.assertEqual(body["would_sync"], [])
        self.assertEqual(body["excluded"], [self.ticket])

    def test_tracker_sync_runs_the_batch_from_the_replay(self):
        out = self.run_script("acs.py", "tracker", "sync", "--ticket", self.ticket,
                              "--gh-replay", self.replay)
        self.assertEqual(out.returncode, 0, out.stderr)
        body = json.loads(out.stdout)
        self.assertEqual(body["synced"][self.ticket]["key"], "9")
        self.assertEqual(body["failed"], [])

    def test_tracker_sync_is_a_no_op_for_a_local_provider(self):
        self.write_settings({"ticket_prefix": "SHOP", "test_coverage_percent": 90})
        out = self.run_script("acs.py", "tracker", "sync", "--ticket", self.ticket)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertTrue(json.loads(out.stdout)["skipped"])

    def test_tracker_sync_refuses_an_unknown_ticket(self):
        out = self.run_script("acs.py", "tracker", "sync", "--ticket", "SHOP-999")
        self.assertEqual(out.returncode, 2)
        self.assertIn("no active partition for SHOP-999", out.stderr)


if __name__ == "__main__":
    unittest.main()
