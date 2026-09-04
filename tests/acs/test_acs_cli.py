"""MAR-521 — contract tests for acs.py, the single deterministic entry point.

Every subcommand is driven the way a SKILL.md drives it: as a subprocess, with
flags in and one JSON object out. What is asserted is the CONTRACT — the keys a
coordinator reads, the exit code it branches on, and the refusal text it
surfaces — not the internals of the acs_lib function underneath, which have
their own tests.

Failure paths are first-class here. A CLI that exists so the model stops
improvising Python is only worth having if its refusals are as predictable as
its successes, so each group pins what happens on a missing partition, a
malformed document, an unknown name, and a guarded field.

Run:  python3 -m unittest tests.acs.test_acs_cli -v
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import AcsWorkspaceCase, SCRIPTS  # noqa: E402

sys.path.insert(0, SCRIPTS)
import acs_lib as lib  # noqa: E402


class AcsCliCase(AcsWorkspaceCase):
    """Fixture: the shared workspace, plus acs.py invocation helpers."""

    def acs(self, *args, **kwargs):
        return self.run_script("acs.py", *args, **kwargs)

    def ok_json(self, res):
        """Assert exit 0 and return the parsed stdout object."""
        self.assertEqual(res.returncode, 0, "%s\n%s" % (res.stdout, res.stderr))
        return json.loads(res.stdout)

    def refusal(self, res, *fragments):
        """Assert the documented refusal shape: exit 2, reason on stderr."""
        self.assertEqual(res.returncode, 2, "expected exit 2, got %d\n%s"
                         % (res.returncode, res.stdout))
        for fragment in fragments:
            self.assertIn(fragment, res.stderr)
        return res.stderr


class TestContext(AcsCliCase):

    def test_context_resolves_the_workspace_view(self):
        out = self.ok_json(self.acs("context"))
        self.assertTrue(out["ok"])
        self.assertEqual(out["repo_id"], "acme-shop")
        self.assertEqual(out["workspace"], self.ws)
        self.assertEqual(out["checkout_root"], self.repo)
        self.assertEqual(out["settings"]["ticket_prefix"], "SHOP")
        self.assertTrue(out["index_path"].endswith("tickets-index.json"))

    def test_context_with_a_ticket_adds_its_partition(self):
        ticket = self.new_ticket("Add a widget", "task")
        out = self.ok_json(self.acs("context", "--ticket", ticket))
        self.assertEqual(out["ticket_id"], ticket)
        self.assertEqual(out["partition"], self.tdir(ticket))
        self.assertFalse(out["archived"])


class TestGate(AcsCliCase):

    def test_an_open_gate_exits_zero(self):
        out = self.ok_json(self.acs("gate", "--skill", "create-prd"))
        self.assertEqual(out, {"ok": True, "skill": "create-prd", "exit_code": 0})

    def test_a_ticket_is_passed_through_to_the_gate(self):
        ticket = self.new_ticket("Add a widget", "task")
        out = self.ok_json(self.acs("gate", "--skill", "create-prd", "--ticket", ticket))
        self.assertTrue(out["ok"])

    def test_an_unknown_skill_is_refused_not_silently_passed(self):
        self.refusal(self.acs("gate", "--skill", "not-a-skill"), "unknown skill")

    def test_a_blocked_gate_reports_ok_false_and_exit_two(self):
        # gate_create_architecture requires a PRD; the fixture repo has none.
        res = self.acs("gate", "--skill", "create-architecture")
        self.assertEqual(res.returncode, 2)
        self.assertEqual(json.loads(res.stdout)["ok"], False)


class TestLanePureCommands(AcsCliCase):

    def test_derive_returns_the_lane_depth_ceiling_triple(self):
        out = self.ok_json(self.acs("lane", "derive", "--size", "large",
                                    "--stakes", "high", "--type", "task"))
        self.assertEqual(out["lane"], "COMPLEX")
        self.assertEqual(out["depth"], "full")
        self.assertEqual(out["ceiling"], lib.VERIFY_ITERATION_CAP["full"])
        self.assertEqual(out["rank"], lib.lane_rank("COMPLEX"))

    def test_derive_agrees_with_the_library_across_the_axis_grid(self):
        """The CLI must not re-derive anything: for every axis pair it reports
        exactly what derive_lane reports."""
        for size in ("trivial", "small", "standard", "large"):
            for stakes in ("low", "normal", "high"):
                out = self.ok_json(self.acs("lane", "derive", "--size", size,
                                            "--stakes", stakes, "--type", "task"))
                self.assertEqual(out["lane"], lib.derive_lane(size, stakes, False, "task"),
                                 msg="size=%s stakes=%s" % (size, stakes))

    def test_rank_exposes_the_ordering_escalation_compares_on(self):
        out = self.ok_json(self.acs("lane", "rank", "--lane", "STANDARD"))
        self.assertEqual(out, {"lane": "STANDARD", "rank": lib.lane_rank("STANDARD")})

    def test_escalate_reports_a_raise(self):
        out = self.ok_json(self.acs("lane", "escalate", "--current-lane", "SMALL",
                                    "--size", "large", "--stakes", "normal", "--type", "task"))
        self.assertTrue(out["escalated"])
        self.assertEqual(out["lane"], "COMPLEX")
        self.assertEqual(out["from_lane"], "SMALL")

    def test_escalate_holds_when_the_candidate_is_not_higher(self):
        out = self.ok_json(self.acs("lane", "escalate", "--current-lane", "COMPLEX",
                                    "--size", "trivial", "--stakes", "low", "--type", "task"))
        self.assertFalse(out["escalated"])
        self.assertEqual(out["lane"], "COMPLEX")

    def test_an_unknown_size_is_rejected_by_the_parser(self):
        res = self.acs("lane", "derive", "--size", "enormous", "--stakes", "low")
        self.assertEqual(res.returncode, 2)
        self.assertIn("invalid choice", res.stderr)


class TestStakes(AcsCliCase):

    def test_recommend_matches_a_high_stakes_glob(self):
        out = self.ok_json(self.acs("stakes", "recommend", "--path", "auth/login.py"))
        self.assertEqual(out, {"stakes": "high", "paths_considered": 1})

    def test_recommend_returns_normal_for_ordinary_paths(self):
        out = self.ok_json(self.acs("stakes", "recommend", "--path", "README.md"))
        self.assertEqual(out["stakes"], "normal")

    def test_recommend_reads_a_changed_file_set_from_stdin(self):
        out = self.ok_json(self.acs("stakes", "recommend", "--paths-from", "-",
                                    stdin="README.md\nauth/token.py\n"))
        self.assertEqual(out["stakes"], "high")
        self.assertEqual(out["paths_considered"], 2)

    def test_recommend_reads_a_changed_file_set_from_a_file(self):
        listing = os.path.join(self.tmp, "changed.txt")
        with open(listing, "w", encoding="utf-8") as fh:
            fh.write("docs/readme.md\npayments/charge.py\n")
        out = self.ok_json(self.acs("stakes", "recommend", "--paths-from", listing))
        self.assertEqual(out["stakes"], "high")
        self.assertEqual(out["paths_considered"], 2)

    def test_recommend_refuses_an_unreadable_paths_file(self):
        self.refusal(self.acs("stakes", "recommend", "--paths-from", "/nope/missing.txt"),
                     "cannot read")

    def test_guard_takes_the_higher_of_each_axis(self):
        out = self.ok_json(self.acs("stakes", "guard", "--current-size", "small",
                                    "--current-stakes", "normal", "--proposed-stakes", "high"))
        self.assertEqual(out["size"], "small")
        self.assertEqual(out["stakes"], "high")
        self.assertTrue(out["changed"])

    def test_guard_never_lowers_a_confirmed_axis(self):
        out = self.ok_json(self.acs("stakes", "guard", "--current-size", "large",
                                    "--current-stakes", "high", "--proposed-size", "trivial",
                                    "--proposed-stakes", "low"))
        self.assertEqual(out["size"], "large")
        self.assertEqual(out["stakes"], "high")
        self.assertFalse(out["changed"])


class TestTicket(AcsCliCase):

    def setUp(self):
        super(TestTicket, self).setUp()
        self.ticket = self.new_ticket("Add a widget", "task")

    def test_show_returns_the_partition_and_the_document(self):
        out = self.ok_json(self.acs("ticket", "show", "--ticket", self.ticket))
        self.assertEqual(out["ticket_id"], self.ticket)
        self.assertEqual(out["ticket"]["id"], self.ticket)
        self.assertEqual(out["partition"], self.tdir(self.ticket))

    def test_show_refuses_an_unknown_ticket(self):
        """A ticket that does not exist and one that is archived are different
        situations, and the shared resolver says which (MAR-521 review)."""
        self.refusal(self.acs("ticket", "show", "--ticket", "SHOP-4242"),
                     "no partition for SHOP-4242")

    def test_save_writes_the_document_and_reindexes(self):
        doc = self.ok_json(self.acs("ticket", "show", "--ticket", self.ticket))["ticket"]
        doc["description"] = "a clarified description"
        out = self.ok_json(self.acs("ticket", "save", "--ticket", self.ticket,
                                    stdin=json.dumps(doc)))
        self.assertTrue(out["ok"])
        self.assertTrue(out["indexed"])
        self.assertEqual(lib.load_ticket(self.tdir(self.ticket))["description"],
                         "a clarified description")
        index = lib.read_json(lib.index_path(self.ws, "acme-shop"))
        self.assertIn(self.ticket, json.dumps(index))

    def test_save_refuses_to_move_an_axis_behind_the_escalation_guard(self):
        doc = self.ok_json(self.acs("ticket", "show", "--ticket", self.ticket))["ticket"]
        doc["stakes"] = "high"
        self.refusal(self.acs("ticket", "save", "--ticket", self.ticket,
                              stdin=json.dumps(doc)), "stakes", "lane apply")

    def test_save_refuses_a_document_for_a_different_ticket(self):
        doc = self.ok_json(self.acs("ticket", "show", "--ticket", self.ticket))["ticket"]
        doc["id"] = "SHOP-999"
        self.refusal(self.acs("ticket", "save", "--ticket", self.ticket,
                              stdin=json.dumps(doc)), "does not match")

    def test_save_refuses_malformed_json(self):
        self.refusal(self.acs("ticket", "save", "--ticket", self.ticket, stdin="{not json"),
                     "invalid JSON")

    def test_save_refuses_empty_stdin_rather_than_writing_nothing(self):
        self.refusal(self.acs("ticket", "save", "--ticket", self.ticket, stdin=""),
                     "got nothing")

    def test_save_refuses_a_json_document_that_is_not_an_object(self):
        self.refusal(self.acs("ticket", "save", "--ticket", self.ticket, stdin="[1, 2]"),
                     "got list")


class TestLaneApply(AcsCliCase):
    """The on-trigger escalation sequence: guard, escalate, persist, then audit."""

    def setUp(self):
        super(TestLaneApply, self).setUp()
        self.ticket = self.new_ticket("Add a widget", "task", "--size", "small")
        self.tpath = self.tdir(self.ticket)

    def start_run(self):
        lib.append_in_progress_run(self.tpath, "code", self.ticket)

    def test_a_raise_persists_axes_lane_and_a_thirteen_field_event(self):
        self.start_run()
        out = self.ok_json(self.acs("lane", "apply", "--ticket", self.ticket,
                                    "--proposed-size", "large", "--trigger", "verifier_finding"))
        self.assertTrue(out["escalated"])
        self.assertTrue(out["event_recorded"])
        self.assertEqual(out["lane"], "COMPLEX")

        ticket = lib.load_ticket(self.tpath)
        self.assertEqual((ticket["size"], ticket["lane"]), ("large", "COMPLEX"))

        events = lib.last_run(lib.load_state(self.tpath, "code"))["escalations"]
        self.assertEqual(len(events), 1)
        self.assertEqual(set(events[0]), {
            "ts", "from_lane", "to_lane", "from_size", "from_stakes", "to_size",
            "to_stakes", "trigger", "source", "ceiling_before", "ceiling_after",
            "direction", "confirmation_ref"})
        self.assertEqual(events[0]["direction"], "up")
        self.assertIsNone(events[0]["confirmation_ref"])
        self.assertEqual(events[0]["trigger"], "verifier_finding")

    def test_a_second_apply_is_a_no_op_so_a_resumed_run_records_nothing_twice(self):
        self.start_run()
        self.ok_json(self.acs("lane", "apply", "--ticket", self.ticket,
                              "--proposed-size", "large", "--trigger", "verifier_finding"))
        out = self.ok_json(self.acs("lane", "apply", "--ticket", self.ticket,
                                    "--proposed-size", "large", "--trigger", "verifier_finding"))
        self.assertFalse(out["escalated"])
        self.assertFalse(out["event_recorded"])
        self.assertEqual(len(lib.last_run(lib.load_state(self.tpath, "code"))["escalations"]), 1)

    def test_a_proposal_that_does_not_raise_writes_nothing(self):
        self.start_run()
        before = lib.load_ticket(self.tpath)
        out = self.ok_json(self.acs("lane", "apply", "--ticket", self.ticket,
                                    "--proposed-size", "trivial", "--trigger", "verifier_finding"))
        self.assertFalse(out["escalated"])
        self.assertEqual(lib.load_ticket(self.tpath), before)

    def test_the_axis_guard_runs_before_escalation(self):
        """A proposal below the current axis cannot lower it, so it cannot
        lower the lane either."""
        self.start_run()
        self.ok_json(self.acs("lane", "apply", "--ticket", self.ticket,
                              "--proposed-size", "large", "--trigger", "t"))
        out = self.ok_json(self.acs("lane", "apply", "--ticket", self.ticket,
                                    "--proposed-size", "trivial", "--trigger", "t"))
        self.assertEqual(out["size"], "large")
        self.assertEqual(lib.load_ticket(self.tpath)["size"], "large")

    def test_an_unrecordable_event_still_leaves_the_lane_applied_and_says_so(self):
        """No run entry means record_escalation_event refuses. The axes are
        already durable by then — that ordering is deliberate, so the CLI
        reports the applied state and fails loudly rather than silently."""
        res = self.acs("lane", "apply", "--ticket", self.ticket,
                       "--proposed-size", "large", "--trigger", "verifier_finding")
        self.assertEqual(res.returncode, 2)
        out = json.loads(res.stdout)
        self.assertTrue(out["escalated"])
        self.assertFalse(out["event_recorded"])
        self.assertIn("escalation event was not recorded", res.stderr)
        self.assertEqual(lib.load_ticket(self.tpath)["lane"], "COMPLEX")

    def test_apply_refuses_an_unknown_ticket(self):
        self.refusal(self.acs("lane", "apply", "--ticket", "SHOP-4242",
                              "--proposed-size", "large", "--trigger", "t"),
                     "no partition for SHOP-4242")


class TestLaneDeescalate(AcsCliCase):

    def setUp(self):
        super(TestLaneDeescalate, self).setUp()
        self.ticket = self.new_ticket("Add a widget", "task", "--size", "large")
        self.tpath = self.tdir(self.ticket)
        lib.append_in_progress_run(self.tpath, "code", self.ticket)

    def answered_ref(self):
        self.run_script("clarify.py", "add", "--skill", "code", "--ticket", self.ticket,
                        "--question", "Lower the size?")
        out = self.run_script("clarify.py", "answer", "--id", "C-1", "--ticket", self.ticket,
                              "--answer", "yes, small is right")
        self.assertEqual(out.returncode, 0, out.stderr)
        return "C-1"

    def test_an_answered_clarification_lowers_the_axes_and_records_direction_down(self):
        ref = self.answered_ref()
        out = self.ok_json(self.acs("lane", "deescalate", "--ticket", self.ticket,
                                    "--size", "small", "--stakes", "low", "--clarify-ref", ref))
        self.assertEqual(out["size"], "small")
        self.assertEqual(out["from"]["size"], "large")
        event = lib.last_run(lib.load_state(self.tpath, "code"))["escalations"][-1]
        self.assertEqual(event["direction"], "down")
        self.assertEqual(event["confirmation_ref"], ref)

    def test_an_unresolved_clarify_ref_is_refused_with_no_write(self):
        before = lib.load_ticket(self.tpath)
        self.refusal(self.acs("lane", "deescalate", "--ticket", self.ticket, "--size", "small",
                              "--stakes", "low", "--clarify-ref", "C-99"),
                     "does not resolve")
        self.assertEqual(lib.load_ticket(self.tpath), before)

    def test_the_clarify_ref_is_not_optional(self):
        res = self.acs("lane", "deescalate", "--ticket", self.ticket,
                       "--size", "small", "--stakes", "low")
        self.assertEqual(res.returncode, 2)
        self.assertIn("--clarify-ref", res.stderr)


class TestPhaseValidate(AcsCliCase):

    def test_a_complete_result_document_validates(self):
        out = self.ok_json(self.acs("phase", "validate", "--skill", "code",
                                    stdin=json.dumps({"status": "completed"})))
        self.assertTrue(out["ok"])
        self.assertEqual(out["errors"], [])

    def test_a_document_without_a_status_is_reported_not_defaulted(self):
        out = self.ok_json(self.acs("phase", "validate", "--skill", "code",
                                    stdin=json.dumps({"summary": "done"})))
        self.assertFalse(out["ok"])
        self.assertIn("status is absent", out["errors"][0])

    def test_an_unknown_status_is_reported(self):
        out = self.ok_json(self.acs("phase", "validate", "--skill", "code",
                                    stdin=json.dumps({"status": "finished"})))
        self.assertFalse(out["ok"])
        self.assertIn("not one of", out["errors"][0])

    def test_in_progress_does_not_finalize_a_run(self):
        out = self.ok_json(self.acs("phase", "validate", "--skill", "code",
                                    stdin=json.dumps({"status": "in_progress"})))
        self.assertFalse(out["ok"])

    def test_a_result_file_is_read_from_disk(self):
        path = os.path.join(self.tmp, "result.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"status": "failed"}, fh)
        out = self.ok_json(self.acs("phase", "validate", "--skill", "code",
                                    "--result-file", path))
        self.assertTrue(out["ok"])
        self.assertEqual(out["status"], "failed")

    def test_a_missing_result_file_is_refused(self):
        self.refusal(self.acs("phase", "validate", "--skill", "code",
                              "--result-file", "/nope/result.json"),
                     "missing or not a JSON object")


class TestSmallSurfaces(AcsCliCase):

    def test_slug_matches_the_library(self):
        text = "Introduce the acs CLI as the single deterministic entry point"
        out = self.ok_json(self.acs("slug", "--text", text))
        self.assertEqual(out["slug"], lib.slugify(text, 40))

    def test_slug_honours_max_len(self):
        out = self.ok_json(self.acs("slug", "--text", "a very long ticket title here",
                                    "--max-len", "10"))
        self.assertLessEqual(len(out["slug"]), 10)

    def test_doctor_reports_the_toolchain(self):
        out = self.ok_json(self.acs("doctor"))
        self.assertTrue(out["ok"])
        self.assertIsInstance(out["toolchain"], list)
        self.assertIsInstance(out["missing"], list)

    def test_fanout_batches_returns_the_library_verdict(self):
        out = self.ok_json(self.acs("fanout", "batches"))
        self.assertIn("batches", out)


class TestDelegation(AcsCliCase):
    """The front door must be behaviourally identical to the entry point it
    fronts — same stdout, same exit code — or the two drift apart the moment a
    skill picks one over the other."""

    def setUp(self):
        super(TestDelegation, self).setUp()
        self.ticket = self.new_ticket("Add a widget", "task")

    @staticmethod
    def _volatile(text):
        """Blank the timestamps/ids two runs cannot share, so the REST of the
        payload is compared rather than skipped."""
        import re
        return re.sub(r'"(started_at|ended_at|updated_at|created_at|ts)": "[^"]*"',
                      r'"\1": "<ts>"', text)

    def test_finish_matches_pipeline_step(self):
        """Each invocation gets its OWN ticket: pipeline-step is a writer, so
        running both against one partition compares a first write with a second
        and can pass or fail for reasons unrelated to delegation."""
        other = self.new_ticket("Add a widget", "task")
        common = ("--skill", "test", "--status", "completed")
        through_front_door = self.acs("finish", "--ticket", self.ticket, *common)
        direct = self.run_script("pipeline-step.py", "--ticket", other, *common)
        self.assertEqual(through_front_door.returncode, direct.returncode)
        self.assertEqual(
            self._volatile(through_front_door.stdout).replace(self.ticket, "<t>"),
            self._volatile(direct.stdout).replace(other, "<t>"),
            "the front door must print exactly what the delegate prints")
        self.assertTrue(json.loads(through_front_door.stdout)["written"])

    def test_start_matches_skill_start(self):
        other = self.new_ticket("Add a widget", "task")
        through_front_door = self.acs("start", "--skill", "code", "--ticket", self.ticket)
        direct = self.run_script("skill-start.py", "--skill", "code", "--ticket", other)
        self.assertEqual(through_front_door.returncode, direct.returncode)
        self.assertEqual(
            self._volatile(through_front_door.stdout).replace(self.ticket, "<t>"),
            self._volatile(direct.stdout).replace(other, "<t>"),
            "stdout must match too — comparing only the exit code would let the "
            "front door print nothing and still pass")

    def test_plan_check_drops_the_verb_before_delegating(self):
        """`acs.py plan check` reads as a verb pair; plan-approval.py takes
        flags only, so the verb must not reach it as an argument."""
        through_front_door = self.acs("plan", "check", "--ticket", self.ticket)
        direct = self.run_script("plan-approval.py", "--ticket", self.ticket)
        self.assertEqual(through_front_door.returncode, direct.returncode)
        self.assertEqual(through_front_door.stdout, direct.stdout)

    def test_plan_without_the_verb_still_delegates(self):
        self.assertEqual(self.acs("plan", "--ticket", self.ticket).returncode,
                         self.run_script("plan-approval.py", "--ticket", self.ticket).returncode)


class TestEveryNamedFunctionIsReachable(AcsCliCase):
    """The ticket's second acceptance criterion, as a test: a coordinator must
    be able to reach every acs_lib function a SKILL.md tells it to call, without
    writing Python. Each name below is checked by RUNNING the subcommand that
    covers it, so the mapping cannot rot into a comment."""

    COVERAGE = {
        "derive_lane": ("lane", "derive", "--size", "small", "--stakes", "low"),
        "lane_rank": ("lane", "rank", "--lane", "SMALL"),
        "escalate_lane": ("lane", "escalate", "--current-lane", "SMALL",
                          "--size", "small", "--stakes", "low"),
        "guard_axes": ("stakes", "guard", "--current-size", "small",
                       "--current-stakes", "low"),
        "recommend_stakes": ("stakes", "recommend", "--path", "README.md"),
        "slugify": ("slug", "--text", "a title"),
        "check_toolchain": ("doctor",),
        "build_context": ("context",),
        "fanout_batches": ("fanout", "batches"),
    }

    def test_each_named_function_has_a_working_subcommand(self):
        for function, argv in sorted(self.COVERAGE.items()):
            with self.subTest(function=function):
                res = self.acs(*argv)
                self.assertEqual(res.returncode, 0,
                                 "%s: %s\n%s" % (function, res.stdout, res.stderr))
                json.loads(res.stdout)  # the stdout contract: one JSON object

    def test_the_writers_are_reachable_only_through_their_audited_commands(self):
        """save_ticket, update_pipeline, update_index and
        record_escalation_event are named by SKILL.md as ONE persistence
        sequence, so they are exposed as the three commands that perform it
        whole — `lane apply`, `lane deescalate`, `ticket save` — and never as
        four separate writes a caller could half-perform."""
        lane_help = self.acs("lane", "--help")
        self.assertEqual(lane_help.returncode, 0)
        for command in ("apply", "deescalate"):
            self.assertIn(command, lane_help.stdout)
        self.assertIn("save", self.acs("ticket", "--help").stdout)
        for orphan in ("save-ticket", "update-index", "update-pipeline",
                       "record-escalation-event"):
            self.assertNotIn(orphan, self.acs("--help").stdout,
                             msg="%s must not be a standalone write" % orphan)

    def test_a_group_without_a_subcommand_prints_usage_and_exits_two(self):
        """`acs.py lane` names a group, not a command. It must say so rather
        than exiting 0 having done nothing."""
        res = self.acs("lane")
        self.assertEqual(res.returncode, 2)
        self.assertIn("usage", res.stderr.lower())
        self.assertEqual(res.stdout, "")

    def test_help_lists_every_group(self):
        res = self.acs("--help")
        self.assertEqual(res.returncode, 0)
        for group in ("context", "gate", "lane", "stakes", "ticket", "phase",
                      "slug", "fanout", "doctor", "start", "finish", "plan"):
            self.assertIn(group, res.stdout)


class TestReviewFixes(AcsCliCase):
    """MAR-521 review: behaviours the original contract tests never posed —
    a partial document, an absent axis, a failed audit write, a real session
    marker. Each of these was a defect that shipped green."""

    def test_gate_does_not_touch_the_session_marker(self):
        """`gate` answers "would this pass?" — it is not a PreToolUse event.
        Routing it through the hook path rewrote the marker with null
        session_id/transcript_path, costing the NEXT run its cost attribution."""
        ctx = lib.build_context(self.repo)
        marker_path = lib.session_marker_path(self.ws, "acme-shop", ctx["checkout_id"])
        os.makedirs(os.path.dirname(marker_path), exist_ok=True)
        real = {"session_id": "REAL-SESSION", "transcript_path": "/x/t.jsonl",
                "cwd": self.repo, "checkout_id": ctx["checkout_id"],
                "hook_event_name": "PreToolUse", "skill": "acs:code",
                "updated_at": lib.now_iso()}
        lib.write_json(marker_path, real)

        self.ok_json(self.acs("gate", "--skill", "create-prd"))
        self.assertEqual(lib.read_json(marker_path), real,
                         "gate must leave the real session marker untouched")

    def test_ticket_save_is_a_patch_not_a_replacement(self):
        ticket = self.new_ticket("Add a widget", "task")
        before = lib.load_ticket(self.tdir(ticket))
        out = self.ok_json(self.acs("ticket", "save", "--ticket", ticket,
                                    stdin=json.dumps({"description": "clarified"})))
        self.assertEqual(out["fields_written"], ["description"])
        after = lib.load_ticket(self.tdir(ticket))
        self.assertEqual(after["description"], "clarified")
        for key in ("id", "title", "type", "status", "needs_design"):
            self.assertEqual(after.get(key), before.get(key),
                             "%s must survive a partial save" % key)

    def test_ticket_save_keeps_the_index_row_populated(self):
        """The wholesale overwrite blanked title/type/status in the index, which
        gate_code and fanout_batches read."""
        ticket = self.new_ticket("Add a widget", "task")
        self.ok_json(self.acs("ticket", "save", "--ticket", ticket,
                              stdin=json.dumps({"description": "clarified"})))
        index = lib.read_json(lib.index_path(self.ws, "acme-shop")) or {}
        row = json.dumps(index)
        self.assertIn("Add a widget", row)
        self.assertNotIn('"title": null', row)

    def test_lane_apply_does_not_invent_an_absent_axis(self):
        """guard_axes floors an absent axis at the lowest rank; a rigor-RAISING
        path must not use that to write size: trivial."""
        ticket = self.new_ticket("Add a widget", "task", "--size", "small")
        tpath = self.tdir(ticket)
        doc = lib.load_ticket(tpath)
        doc.pop("size", None)
        lib.save_ticket(tpath, doc)
        lib.append_in_progress_run(tpath, "code", ticket)

        out = self.ok_json(self.acs("lane", "apply", "--ticket", ticket,
                                    "--proposed-stakes", "high", "--trigger", "b"))
        self.assertIsNone(out["size"])
        self.assertNotIn("size", lib.load_ticket(tpath))
        if out["escalated"]:
            event = lib.last_run(lib.load_state(tpath, "code"))["escalations"][-1]
            self.assertIsNone(event["to_size"])

    def test_lane_apply_no_op_reports_the_disk_state_not_the_proposal(self):
        """A caller branching on out["stakes"] must not read a raise that was
        never persisted."""
        ticket = self.new_ticket("Add a widget", "task")   # standard/normal
        tpath = self.tdir(ticket)
        lib.append_in_progress_run(tpath, "code", ticket)
        out = self.ok_json(self.acs("lane", "apply", "--ticket", ticket,
                                    "--proposed-stakes", "high", "--trigger", "b"))
        self.assertFalse(out["escalated"])
        self.assertEqual(out["stakes"], lib.load_ticket(tpath).get("stakes"))
        self.assertEqual(out["proposed_stakes"], "high")
        self.assertIsNone(out["event"], "the documented `event` key must be present")

    def test_lane_deescalate_reports_a_write_that_landed_without_its_event(self):
        """confirm_deescalation persists BEFORE recording its event. With no run
        entry the event write fails — and the axes are already lowered, so a bare
        exit-2 refusal would hide a durable rigor-lowering write."""
        ticket = self.new_ticket("Add a widget", "task", "--size", "large")
        tpath = self.tdir(ticket)
        self.run_script("clarify.py", "add", "--skill", "code", "--ticket", ticket,
                        "--question", "Lower it?")
        self.run_script("clarify.py", "answer", "--id", "C-1", "--ticket", ticket,
                        "--answer", "yes")
        res = self.acs("lane", "deescalate", "--ticket", ticket, "--size", "small",
                       "--stakes", "low", "--clarify-ref", "C-1")
        self.assertEqual(res.returncode, 2)
        out = json.loads(res.stdout)
        self.assertTrue(out["applied"])
        self.assertFalse(out["event_recorded"])
        self.assertIn("LOWERED", res.stderr)
        self.assertEqual(lib.load_ticket(tpath)["size"], "small")

    def test_context_says_whether_the_partition_exists(self):
        out = self.ok_json(self.acs("context", "--ticket", "SHOP-4242"))
        self.assertFalse(out["exists"],
                         "find_ticket_partition returns a path for a ticket that "
                         "exists nowhere; the output must say so")
        ticket = self.new_ticket("Add a widget", "task")
        self.assertTrue(self.ok_json(self.acs("context", "--ticket", ticket))["exists"])

    def test_context_reports_the_keys_it_advertises(self):
        out = self.ok_json(self.acs("context"))
        for key in ("checkout_id", "repo_dir", "index_path", "plugin_root"):
            self.assertIn(key, out)

    def test_doctor_ok_is_a_verdict_not_a_constant(self):
        out = self.ok_json(self.acs("doctor"))
        self.assertEqual(out["ok"], not out["missing_required"])
        for row in out["toolchain"]:
            if row.get("kind") == "required" and not row.get("present"):
                self.assertIn(row["name"], out["missing_required"])

    def test_a_group_prints_its_own_subcommands_not_the_root_help(self):
        res = self.acs("lane")
        self.assertEqual(res.returncode, 2)
        self.assertIn("acs.py lane", res.stderr)
        for sub in ("derive", "escalate", "apply", "deescalate"):
            self.assertIn(sub, res.stderr)
        self.assertNotIn("doctor", res.stderr, "that is the ROOT help, not lane's")


class TestReviewFixesRoundTwo(AcsCliCase):
    """A review of the fixes above caught two regressions IN them, both
    reproduced live. These pin the corrected behaviour."""

    def test_apply_carrying_no_signal_writes_nothing(self):
        """Nulling the axes before escalate_lane changed the DERIVATION, not
        just the persistence: derive_lane(None, ...) returns its STANDARD
        default, so a call with no proposal at all escalated SMALL -> STANDARD,
        wrote three files and raised the verify ceiling 1 -> 3."""
        ticket = self.new_ticket("Add a widget", "task", "--size", "small")
        tpath = self.tdir(ticket)
        doc = lib.load_ticket(tpath)
        doc.pop("size", None)
        doc["lane"], doc["stakes"] = "SMALL", "normal"
        lib.save_ticket(tpath, doc)
        lib.append_in_progress_run(tpath, "code", ticket)
        before = lib.load_ticket(tpath)

        out = self.ok_json(self.acs("lane", "apply", "--ticket", ticket, "--trigger", "b"))
        self.assertFalse(out["escalated"])
        self.assertEqual(out["ceiling_before"], out["ceiling_after"])
        self.assertEqual(lib.load_ticket(tpath), before)
        self.assertEqual(lib.last_run(lib.load_state(tpath, "code")).get("escalations", []), [])

    def test_a_real_raise_still_fires_without_inventing_the_absent_axis(self):
        """The guard must not have been bought by disabling escalation."""
        ticket = self.new_ticket("Add a widget", "task", "--size", "small")
        tpath = self.tdir(ticket)
        doc = lib.load_ticket(tpath)
        doc.pop("size", None)
        doc["lane"], doc["stakes"] = "SMALL", "normal"
        lib.save_ticket(tpath, doc)
        lib.append_in_progress_run(tpath, "code", ticket)

        out = self.ok_json(self.acs("lane", "apply", "--ticket", ticket,
                                    "--proposed-stakes", "high", "--trigger", "b"))
        self.assertTrue(out["escalated"])
        self.assertIsNone(out["size"])
        self.assertNotIn("size", lib.load_ticket(tpath))

    def test_deescalate_refusal_at_the_target_values_is_a_plain_refusal(self):
        """`applied` must mean "the ticket changed", not "the ticket now holds
        the requested values" — which is also true when the call refused before
        writing a byte, firing the loudest alarm in the system for nothing."""
        ticket = self.new_ticket("Add a widget", "task", "--size", "small")
        tpath = self.tdir(ticket)
        doc = lib.load_ticket(tpath)
        doc.update({"size": "small", "stakes": "low", "lane": "SMALL"})
        lib.save_ticket(tpath, doc)
        before = lib.load_ticket(tpath)

        res = self.acs("lane", "deescalate", "--ticket", ticket, "--size", "small",
                       "--stakes", "low", "--clarify-ref", "C-99")
        self.assertEqual(res.returncode, 2)
        self.assertEqual(res.stdout.strip(), "", "a refusal that wrote nothing prints nothing")
        self.assertIn("does not resolve", res.stderr)
        self.assertNotIn("LOWERED", res.stderr)
        self.assertEqual(lib.load_ticket(tpath), before)

    def test_a_marker_with_a_real_session_is_never_blanked(self):
        """Guarded at the root now, so a caller that forgets record_marker=False
        cannot cost the next run its attribution."""
        ctx = lib.build_context(self.repo)
        path = lib.session_marker_path(self.ws, "acme-shop", ctx["checkout_id"])
        os.makedirs(os.path.dirname(path), exist_ok=True)
        lib.write_json(path, {"session_id": "REAL", "transcript_path": "/x/t.jsonl"})
        lib.record_session_marker(ctx, {"cwd": self.repo})          # no session_id
        self.assertEqual(lib.read_json(path)["session_id"], "REAL")

    def test_a_fresh_marker_still_records_absent_fields_as_null(self):
        """The guard must not have broken the invariant it sits next to: a
        genuinely absent field is written as null, never guessed."""
        ctx = lib.build_context(self.repo)
        path = lib.session_marker_path(self.ws, "acme-shop", ctx["checkout_id"])
        if os.path.exists(path):
            os.unlink(path)
        lib.record_session_marker(ctx, {"cwd": self.repo})
        self.assertIsNone(lib.read_json(path)["session_id"])

    def test_doctor_and_setup_agree_on_what_is_missing(self):
        """One predicate: doctor reuses missing_tools over pre-probed rows
        rather than re-implementing its kind filter."""
        out = self.ok_json(self.acs("doctor"))
        self.assertEqual(out["missing"], lib.missing_tools(rows=out["toolchain"]))
        self.assertEqual(out["missing_required"],
                         lib.missing_tools(kinds=("required",), rows=out["toolchain"]))


class TestSharedEnvelopeProbe(AcsCliCase):
    """MAR-520 gave the envelope one probe order in claude_code_adapter; the
    gate path and the session marker were still reading `cwd` directly, so a
    payload carrying workspace.current_dir resolved a DIFFERENT checkout for
    gating than for measurement."""

    def test_the_gate_path_honours_workspace_current_dir(self):
        payload = {"workspace": {"current_dir": self.repo},
                   "tool_input": {"skill": "create-prd"}}   # no top-level cwd
        self.assertEqual(lib.run_pre_payload("create-prd", payload, record_marker=False), 0)

    def test_the_marker_records_the_probed_cwd_but_never_invents_one(self):
        ctx = lib.build_context(self.repo)
        path = lib.session_marker_path(self.ws, "acme-shop", ctx["checkout_id"])
        for existing in (path,):
            if os.path.exists(existing):
                os.unlink(existing)
        lib.record_session_marker(ctx, {"session_id": "S1",
                                        "workspace": {"current_dir": self.repo}})
        self.assertEqual(lib.read_json(path)["cwd"], self.repo)

        os.unlink(path)
        lib.record_session_marker(ctx, {"session_id": "S2"})
        self.assertIsNone(lib.read_json(path)["cwd"],
                          "an envelope with no cwd must persist null, not the process cwd")


if __name__ == "__main__":
    unittest.main()
