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
import shlex
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
sys.path.insert(0, SCRIPTS)

import acs_lib as lib  # noqa: E402

sys.path.insert(0, os.path.join(REPO_ROOT, "tests", "acs"))
from acs_case import AcsWorkspaceCase, tracker_body  # noqa: E402

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

    def setUp(self):
        """A REAL body file on disk.

        The recorded runner never opens `--body-file`, so these cases used to
        pass a path that did not exist — and so could not have caught a caller
        that never wrote one. The body is what the issue is made of; the
        fixture provides it the way the executor does."""
        self.body = tracker_body(self)
        self.workdir = os.path.dirname(self.body)

    def _bodies(self, *ids):
        return {ident: self.body for ident in ids}

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
                               [ticket(id="SHOP-1"), ticket(id="SHOP-2")],
                               self._bodies("SHOP-1", "SHOP-2"))
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
        out = lib.tracker_sync(gh, SETTINGS, [ticket()], self._bodies("SHOP-1"))
        self.assertEqual(out["synced"], {})
        self.assertEqual(out["failed"], ["SHOP-1"])

    def test_everything_after_the_create_is_non_critical(self):
        """Labels, assignee, milestone and Projects are best-effort: the ticket
        still syncs, and each failure is one info finding with its command."""
        gh = self._gh(**{"gh issue edit": (1, "", "no permission"),
                         "gh project item-add": (1, "", "no project")})
        out = lib.tracker_sync(gh, SETTINGS, [ticket(assignee="dana")],
                               self._bodies("SHOP-1"))
        self.assertEqual(out["failed"], [])
        self.assertEqual(out["synced"]["SHOP-1"]["key"], "9")
        self.assertTrue(all(f["severity"] == "info" for f in out["findings"]))
        self.assertTrue(all(f["command"] for f in out["findings"]))

    def test_the_external_reference_is_read_from_the_created_issues_url(self):
        gh = self._gh()
        external, _findings = lib.tracker_sync_one(gh, SETTINGS, ticket(), self.body)
        self.assertEqual(external, {"provider": "github", "key": "9",
                                    "url": "https://example.invalid/issues/9"})

    def test_labels_are_ensured_then_applied_together(self):
        gh = self._gh()
        lib.tracker_sync_one(gh, SETTINGS, ticket(), self.body)
        self.assertIn("gh label create ACS --description Created by the acs pipeline", gh.calls)
        self.assertIn("gh label create task --description Created by the acs pipeline", gh.calls)
        self.assertIn("gh issue edit 9 --add-label ACS,task", gh.calls)

    def test_a_null_assignee_and_no_milestone_are_silent(self):
        gh = self._gh()
        _external, findings = lib.tracker_sync_one(gh, SETTINGS, ticket(), self.body)
        self.assertFalse([c for c in gh.calls if "--add-assignee" in c])
        self.assertFalse([c for c in gh.calls if "--milestone" in c])
        self.assertFalse([f for f in findings if "assignee" in f["message"]])

    def test_the_ticket_status_is_the_boards_in_progress_column(self):
        gh = self._gh()
        lib.tracker_sync_one(gh, SETTINGS, ticket(), self.body)
        self.assertIn("--field-id f-status --single-select-option-id opt-progress",
                      " | ".join(gh.calls))

    def test_the_type_field_is_set_from_the_tickets_type(self):
        gh = self._gh()
        lib.tracker_sync_one(gh, SETTINGS, ticket(type="story"), self.body)
        self.assertIn("--field-id f-type --single-select-option-id opt-story",
                      " | ".join(gh.calls))

    def test_no_project_configured_is_a_no_op_not_a_finding(self):
        gh = self._gh()
        _external, findings = lib.tracker_sync_one(
            gh, {"tracker": {"github": {}}}, ticket(), self.body)
        self.assertFalse([c for c in gh.calls if c.startswith("gh project")])
        self.assertEqual(findings, [])


    def test_a_missing_body_file_is_a_failed_ticket_not_a_bodiless_issue(self):
        """The body is the issue. Handing `gh issue create` a path that is not
        there produced N opaque "did not sync" errors — one per ticket, each
        quoting whatever gh said — instead of one message naming the
        precondition the caller missed. And because the recorded transcript
        never opens the file, no fixture could tell the two apart."""
        gh = self._gh()
        external, findings = lib.tracker_sync_one(
            gh, SETTINGS, ticket(), os.path.join(self.workdir, "absent.md"))
        self.assertIsNone(external)
        self.assertEqual([f["severity"] for f in findings], ["error"])
        self.assertIn("absent.md", findings[0]["message"])
        self.assertEqual(gh.calls, [], "no issue is created without its body")

    def test_a_zero_exit_with_no_issue_url_is_a_failure_not_an_empty_key(self):
        """`gh issue create` exiting 0 without printing a URL was sliced
        blindly into key "": the ticket was reported SYNCED, the follow-up
        calls went out with empty arguments, and record-external persisted the
        empty key — which is exactly what `sync_candidates` reads to exclude a
        ticket from every future retry."""
        gh = self._gh(**{"gh issue create": (0, "Creating issue in acme/shop\n", "")})
        out = lib.tracker_sync(gh, SETTINGS, [ticket()], self._bodies("SHOP-1"))
        self.assertEqual(out["failed"], ["SHOP-1"])
        self.assertEqual(out["synced"], {})
        self.assertFalse([c for c in gh.calls if "--add-label" in c],
                         "nothing is edited when the issue number is unknown")

    def test_an_unexpected_exception_fails_one_ticket_not_the_batch(self):
        """"Reported without aborting the batch" held only for a non-zero gh
        exit. A raise walked out of the loop past the `synced` map the earlier
        tickets had already earned — so an issue that HAD been created was
        never recorded, and the next run created it again."""

        class Exploding(lib.Gh):
            def __call__(self, argv):
                if "explode" in argv:
                    raise RuntimeError("unexpected tracker shape")
                return lib.Gh.__call__(self, argv)

        gh = Exploding(responses=RECORDED)
        out = lib.tracker_sync(gh, SETTINGS,
                               [ticket(id="SHOP-1", title="explode"), ticket(id="SHOP-2")],
                               self._bodies("SHOP-1", "SHOP-2"))
        self.assertEqual(out["failed"], ["SHOP-1"])
        self.assertEqual(list(out["synced"]), ["SHOP-2"])
        errors = [f for f in out["findings"] if f["severity"] == "error"]
        self.assertEqual(len(errors), 1)
        self.assertIn("unexpected tracker shape", errors[0]["message"])

    def test_every_finding_names_the_ticket_it_came_from(self):
        """One flat list for the whole batch: two tickets failing the same
        best-effort step produced byte-identical entries the coordinator was
        nonetheless told to record per ticket."""
        gh = self._gh(**{"gh issue edit": (1, "", "no permission")})
        out = lib.tracker_sync(gh, SETTINGS,
                               [ticket(id="SHOP-1"), ticket(id="SHOP-2")],
                               self._bodies("SHOP-1", "SHOP-2"))
        self.assertTrue(out["findings"])
        self.assertEqual(sorted({f["ticket_id"] for f in out["findings"]}),
                         ["SHOP-1", "SHOP-2"])

    def test_the_milestone_comes_from_the_ticket_then_from_settings(self):
        """Both sources are declared — `ticket.schema.json` and
        `settings.tracker.milestone` — so the arm has something to read."""
        gh = self._gh()
        lib.tracker_sync_one(gh, SETTINGS, ticket(milestone="v1"), self.body)
        self.assertIn("gh issue edit 9 --milestone v1", gh.calls)

        gh = self._gh()
        settings = {"tracker": dict(SETTINGS["tracker"], milestone="Q3")}
        lib.tracker_sync_one(gh, settings, ticket(), self.body)
        self.assertIn("gh issue edit 9 --milestone Q3", gh.calls)

    def test_a_replayable_command_survives_a_round_trip_through_the_shell(self):
        """`command` is documented as ready to re-run, so it is executed by a
        human sooner or later. The executed calls were always argv, but this
        rendering was a bare join: a milestone of `Q3; rm -rf /tmp/x` produced
        a line that runs the `rm` when replayed."""
        gh = self._gh(**{"gh issue edit": (1, "", "no such milestone")})
        _external, findings = lib.tracker_sync_one(
            gh, SETTINGS, ticket(milestone="Q3 2026; touch pwned"), self.body)
        rendered = [f["command"] for f in findings if "--milestone" in (f["command"] or "")]
        self.assertEqual(len(rendered), 1)
        self.assertEqual(shlex.split(rendered[0]),
                         ["gh", "issue", "edit", "9", "--milestone", "Q3 2026; touch pwned"],
                         "re-running the line must issue the call that failed, "
                         "and nothing else")
        self.assertNotEqual(rendered[0],
                            "gh issue edit 9 --milestone Q3 2026; touch pwned",
                            "the bare join is a second command to the shell")

    def test_a_degraded_call_carries_the_hint_that_names_the_remedy(self):
        """ADR-0088 requires the hint on every degraded gh call. Without it a
        403 "GitHub access is not enabled for this session" — the one failure
        with a specific remedy — read the same as a mistyped label."""
        gh = self._gh(**{"gh issue edit": (1, "", lib.GH_ACCESS_DENIED_MARKER)})
        _external, findings = lib.tracker_sync_one(gh, SETTINGS, ticket(), self.body)
        self.assertTrue(findings)
        self.assertEqual(findings[0]["hint"], lib.GH_ACCESS_HINT)

        gh = self._gh(**{"gh issue edit": (1, "", "label not found")})
        _external, findings = lib.tracker_sync_one(gh, SETTINGS, ticket(), self.body)
        self.assertEqual(findings[0]["hint"], lib.GH_GENERIC_HINT)


class ProjectFillArmsTest(unittest.TestCase):
    """The arms that only fire when a board is missing something.

    The module header claims every arm is exercised from recorded output,
    "including the ones that only fire when a board lacks a field". These are
    those arms; before them the claim was measurably false."""

    def fill(self, fields=None, items=None, ticket_doc=None, **over):
        responses = {"gh project item-add": (0, "", ""),
                     "gh project item-list": (0, json.dumps(items if items is not None
                                                            else ITEMS), ""),
                     "gh project field-list": (0, json.dumps(fields if fields is not None
                                                             else FIELDS), ""),
                     "gh project item-edit": (0, "", "")}
        responses.update(over)
        gh = lib.Gh(responses=responses)
        findings = []
        item = lib.project_fill(gh, SETTINGS, ticket_doc or ticket(),
                                "https://example.invalid/issues/9",
                                lib.TICKET_STATUS_OPTIONS, "project", findings)
        return gh, item, findings

    def _messages(self, findings):
        return " | ".join(f["message"] for f in findings)

    def test_a_project_that_lists_no_item_leaves_the_fields_unset(self):
        _gh, item, findings = self.fill(items={"items": []})
        self.assertIsNone(item)
        self.assertIn("lists no item", self._messages(findings))

    def test_a_failed_field_list_keeps_the_item_and_stops_there(self):
        gh, item, findings = self.fill(**{"gh project field-list": (1, "", "denied")})
        self.assertEqual(item, "item-9", "the item was added; only its fields are unset")
        self.assertIn("listing the Project's fields failed", self._messages(findings))
        self.assertFalse([c for c in gh.calls if c.startswith("gh project item-edit")])

    def test_a_board_with_no_status_field_is_one_finding_naming_it(self):
        _gh, _item, findings = self.fill(fields={"fields": [f for f in FIELDS["fields"]
                                                            if f["name"] != "Status"]})
        self.assertIn("defines no Status field", self._messages(findings))

    def test_a_status_field_defining_none_of_the_wanted_options_says_why(self):
        fields = {"fields": [{"id": "f-status", "name": "Status",
                              "dataType": "SINGLE_SELECT",
                              "options": [{"id": "opt-done", "name": "Done"}]}]}
        _gh, _item, findings = self.fill(fields=fields)
        message = self._messages(findings)
        self.assertIn("defines none of", message)
        self.assertIn("cannot be created through the gh CLI", message,
                      "the finding must say what the operator has to do instead")

    def test_a_type_field_without_the_tickets_option_is_one_finding(self):
        fields = {"fields": [{"id": "f-type", "name": "Type", "dataType": "SINGLE_SELECT",
                              "options": [{"id": "opt-task", "name": "Task"}]}]}
        _gh, _item, findings = self.fill(fields=fields,
                                         ticket_doc=ticket(type="story"))
        self.assertIn("Type field defines no option 'Story'", self._messages(findings))

    def test_a_group_b_single_select_missing_the_value_is_one_finding(self):
        """The board defines Priority, but not the option this ticket carries.
        Writing the nearest option would be a wrong value; writing nothing
        without saying so would be a silent one."""
        fields = {"fields": [{"id": "f-priority", "name": "Priority",
                              "dataType": "SINGLE_SELECT",
                              "options": [{"id": "opt-high", "name": "High"}]}]}
        gh, _item, findings = self.fill(fields=fields,
                                        ticket_doc=ticket(priority="critical"))
        self.assertIn("Priority field defines no option 'critical'",
                      self._messages(findings))
        self.assertFalse([c for c in gh.calls if "f-priority" in c])

    def test_a_group_b_field_the_board_types_wrongly_is_never_written(self):
        fields = {"fields": [{"id": "f-points", "name": "Story Points",
                              "dataType": "DATE"}]}
        gh, _item, findings = self.fill(fields=fields,
                                        ticket_doc=ticket(story_points=3))
        self.assertIn("which 3 cannot be written to", self._messages(findings))
        self.assertFalse([c for c in gh.calls if "f-points" in c])

    def test_a_project_that_is_not_configured_is_a_silent_no_op(self):
        gh = lib.Gh(responses={"gh": (0, "", "")})
        findings = []
        self.assertIsNone(lib.project_fill(gh, {}, ticket(), "u",
                                           lib.TICKET_STATUS_OPTIONS, "project", findings))
        self.assertEqual((gh.calls, findings), ([], []))

    def test_a_field_list_that_is_not_json_leaves_every_field_unset(self):
        """gh printing something that is not JSON is a missing field list, not
        a crash: the item stays, and the Status arm reports it."""
        _gh, item, findings = self.fill(**{"gh project field-list": (0, "<html>503</html>", "")})
        self.assertEqual(item, "item-9")
        self.assertIn("defines no Status field", self._messages(findings))


class PrMetadataFillArmsTest(unittest.TestCase):
    """Non-critical THROUGHOUT: each of the four sub-steps can fail on its own
    without stopping the next, and a failed one is never reported as applied."""

    RESPONSES = {"gh pr edit": (0, "", ""),
                 "gh pr diff": (0, "src/a.py\n", ""),
                 "gh label create": (0, "", ""),
                 "gh api user": (0, "alice\n", ""),
                 "gh project item-add": (0, "", ""),
                 "gh project item-list": (0, json.dumps(
                     {"items": [{"id": "item-4", "projectId": "PVT_1",
                                 "content": {"url": "u"}}]}), ""),
                 "gh project field-list": (0, json.dumps(FIELDS), ""),
                 "gh project item-edit": (0, "", "")}

    def _fill(self, ticket_doc=None, **over):
        responses = dict(self.RESPONSES)
        responses.update(over)
        gh = lib.Gh(responses=responses)
        out = lib.pr_metadata_fill(
            gh, SETTINGS, ticket_doc or ticket(), {"number": 42, "url": "u"}, "/repo",
            author="alice",
            resolver=lambda root, files: {"owners": ["@bob"], "reason": "matched"})
        return gh, out

    def test_the_whole_pass_applies_every_sub_step(self):
        _gh, out = self._fill()
        self.assertEqual(out["applied"],
                         ["assignee", "label:task", "reviewers:@bob", "project-item:item-4"])

    def test_a_ticket_with_no_type_skips_the_label_and_keeps_going(self):
        gh, out = self._fill(ticket_doc={"id": "SHOP-1"})
        self.assertFalse([c for c in gh.calls if "--add-label" in c])
        self.assertNotIn("label:task", out["applied"])
        self.assertIn("reviewers:@bob", out["applied"],
                      "a skipped sub-step must not stop the ones after it")

    def test_a_failed_label_write_is_a_finding_and_not_an_applied_step(self):
        _gh, out = self._fill(**{"gh pr edit 42 --add-label": (1, "", "denied")})
        self.assertNotIn("label:task", out["applied"])
        self.assertIn("reviewers:@bob", out["applied"])
        self.assertTrue(any(f.get("error") == "denied" for f in out["findings"]))

    def test_a_failed_reviewer_request_is_a_finding_and_not_an_applied_step(self):
        _gh, out = self._fill(**{"gh pr edit 42 --add-reviewer": (1, "", "denied")})
        self.assertNotIn("reviewers:@bob", out["applied"])
        self.assertIn("project-item:item-4", out["applied"])
        self.assertTrue(all(f["severity"] == "info" for f in out["findings"]))

    def test_a_project_that_never_resolves_an_item_applies_no_project_step(self):
        _gh, out = self._fill(**{"gh project item-list": (1, "", "denied")})
        self.assertFalse([a for a in out["applied"] if a.startswith("project-item")])
        self.assertIn("reviewers:@bob", out["applied"])


class PureResolversTest(unittest.TestCase):
    """The two degenerate inputs the resolvers are asked for in practice."""

    def test_a_null_value_matches_no_option(self):
        """A ticket whose `priority` is null must not match an option named
        "None" — a null value is expected data, not a value to write."""
        field = {"options": [{"id": "opt-none", "name": "None"}]}
        self.assertIsNone(lib.match_option(field, None))

    def test_a_bare_item_list_parses_like_an_enveloped_one(self):
        self.assertEqual(len(lib.project_items(ITEMS["items"])), 1)
        self.assertEqual(lib.project_items(None), [])

    def test_the_real_codeowners_resolver_is_what_runs_without_an_injection(self):
        """Every other case injects `resolver`; this is the one that proves the
        default is wired to the real module rather than to nothing."""
        gh = lib.Gh(responses={"gh pr diff": (0, "src/a.py\n", "")})
        findings = []
        workdir = tracker_body(self)  # any empty checkout: no CODEOWNERS in it
        owners = lib.reviewers_for(gh, 42, os.path.dirname(workdir), "alice", findings)
        self.assertEqual(owners, [])
        self.assertTrue(any("No CODEOWNERS file found" in f["message"] for f in findings),
                        findings)


class ReviewerAuthorTest(unittest.TestCase):
    """The author is dropped from their own reviewer set — or nobody is
    requested at all, because the owners are comma-joined into ONE call that
    GitHub rejects when it names the author."""

    OWNERS = {"owners": ["@alice", "@bob"], "reason": "matched"}

    def _fill(self, author=None, resolved=None, **over):
        responses = {"gh pr edit": (0, "", ""),
                     "gh pr diff": (0, "src/a.py\n", ""),
                     "gh label create": (0, "", ""),
                     "gh api user": (0, "alice\n", "")}
        responses.update(over)
        gh = lib.Gh(responses=responses)
        out = lib.pr_metadata_fill(
            gh, {}, ticket(), {"number": 42, "url": "u"}, "/repo", author=author,
            resolver=lambda root, files: dict(resolved or self.OWNERS))
        return gh, out

    def test_the_author_is_dropped_however_their_login_is_spelled(self):
        for spelling in ("alice", "@alice", "Alice", "@me"):
            gh, _out = self._fill(author=spelling)
            requested = [c for c in gh.calls if "--add-reviewer" in c]
            self.assertEqual(requested, ["gh pr edit 42 --add-reviewer @bob"],
                             "author spelled %r" % spelling)

    def test_an_absent_author_is_resolved_rather_than_compared_against_none(self):
        """`--author` is optional and was never defaulted, so the common
        invocation compared every owner against None and dropped nobody."""
        gh, _out = self._fill(author=None)
        self.assertIn("gh api user --jq .login", gh.calls)
        self.assertEqual([c for c in gh.calls if "--add-reviewer" in c],
                         ["gh pr edit 42 --add-reviewer @bob"])

    def test_an_unresolvable_author_is_a_finding_not_a_silent_self_request(self):
        gh, out = self._fill(author=None, **{"gh api user": (1, "", "not logged in")})
        messages = [f["message"] for f in out["findings"]]
        self.assertTrue(any("author could not be resolved" in m for m in messages), messages)
        self.assertEqual([c for c in gh.calls if "--add-reviewer" in c],
                         ["gh pr edit 42 --add-reviewer @alice,@bob"],
                         "the request is still attempted; it is the operator's call")

    def test_the_author_being_the_only_owner_is_its_own_reason(self):
        _gh, out = self._fill(author="alice",
                              resolved={"owners": ["@alice"], "reason": "matched"})
        self.assertTrue(any("Only eligible reviewer is the PR author" in f["message"]
                            for f in out["findings"]))

    def test_no_pattern_matched_is_distinguished_from_no_codeowners_file(self):
        _gh, out = self._fill(author="alice",
                              resolved={"owners": [], "reason": "no_pattern_matched"})
        self.assertTrue(any("No CODEOWNERS pattern matched" in f["message"]
                            for f in out["findings"]))
        _gh, out = self._fill(author="alice", resolved={"owners": [], "reason": "elsewhere"})
        self.assertTrue(any("No CODEOWNERS owner resolved" in f["message"]
                            for f in out["findings"]))

    def test_a_failed_pr_diff_requests_nobody_rather_than_everybody(self):
        gh, _out = self._fill(author="alice", **{"gh pr diff": (1, "", "denied")})
        self.assertFalse([c for c in gh.calls if "--add-reviewer" in c])


class RealSubprocessRunnerTest(unittest.TestCase):
    """The runner's un-recorded half — the one that actually shells out."""

    def test_a_command_that_is_not_on_path_is_127_not_an_exception(self):
        code, out, err = lib.Gh()(["acs-no-such-binary-4f2a"])
        self.assertEqual((code, out), (127, ""))
        self.assertIn("not on PATH", err)

    def test_a_real_command_returns_its_own_output_and_code(self):
        code, out, _err = lib.Gh()([sys.executable, "-c", "print('hi')"])
        self.assertEqual((code, out.strip()), (0, "hi"))


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

    def _write_body(self, text="## Description\n\nBulk import.\n"):
        """What the executor charter now tells the executor to do before the
        sync runs. Nothing else in the pipeline writes this file."""
        path = os.path.join(self.tdir(self.ticket), "tracker-body.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

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
        self._write_body()
        out = self.run_script("acs.py", "tracker", "sync", "--ticket", self.ticket,
                              "--gh-replay", self.replay)
        self.assertEqual(out.returncode, 0, out.stderr)
        body = json.loads(out.stdout)
        self.assertEqual(body["synced"][self.ticket]["key"], "9")
        self.assertEqual(body["failed"], [])

    def test_tracker_sync_without_a_written_body_fails_the_ticket_and_says_so(self):
        """The precondition, end to end. `--gh-replay` never opens the body
        file, so this case used to pass against a partition that had none —
        which is exactly why nothing noticed that the executor charter did not
        instruct writing it."""
        out = self.run_script("acs.py", "tracker", "sync", "--ticket", self.ticket,
                              "--gh-replay", self.replay)
        self.assertEqual(out.returncode, 0, out.stderr)
        body = json.loads(out.stdout)
        self.assertEqual(body["failed"], [self.ticket])
        self.assertEqual(body["synced"], {})
        message = " | ".join(f["message"] for f in body["findings"])
        self.assertIn("tracker-body.md", message)
        self.assertIn("does not exist", message)

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
