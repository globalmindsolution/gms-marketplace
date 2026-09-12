"""Every file-map guard denial leaves a durable event (MAR-578).

The guard already refused the write; what it never did was record that it had.
`runs[-1].guard_events` on the executor's `<skill>-state.json` is that record —
appended on every deny, never on a fail-open branch, and never able to change
the verdict it describes: a failed append is one extra stderr note, not a
second opinion.
"""

import contextlib
import io
import json
import os
import re
import sys
import unittest
from unittest import mock

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
SCHEMA_PATH = os.path.join(REPO_ROOT, "plugins", "acs", "schemas", "skill-state.schema.json")
INTERNALS = os.path.join(REPO_ROOT, "plugins", "acs", "docs", "INTERNALS.md")
WORKSPACE_DOC = os.path.join(REPO_ROOT, "docs", "requirements", "functional",
                             "workspace-and-state.md")
CODE_SKILL = os.path.join(REPO_ROOT, "plugins", "acs", "skills", "code", "SKILL.md")
sys.path.insert(0, SCRIPTS)

import acs_lib as lib  # noqa: E402

sys.path.insert(0, os.path.join(REPO_ROOT, "tests", "acs"))
from acs_case import AcsWorkspaceCase  # noqa: E402
from test_file_map_guard import FileMapGuardCase  # noqa: E402

#: The exact field set every recorded event carries.
EVENT_FIELDS = {"ts", "skill", "iteration", "tool", "target", "reason", "declared_count"}

#: `now_iso()`'s shape, asserted rather than assumed.
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

#: The one line a failed append is allowed to add to stderr.
NOTE_PREFIX = "acs: file-map guard denial not recorded"


class _Boom(BaseException):
    """A BaseException the recorder must NOT catch — dispatch.GateTimeout is one."""


class RecordGuardEventTest(unittest.TestCase):
    """The writer itself: same read-modify-write as record_escalation_event,
    with the one deliberate difference — no run entry is not an exception."""

    def setUp(self):
        import shutil
        import tempfile
        self.tdir_path = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.tdir_path, True)

    def _seed_run(self):
        lib.write_json(lib.state_path(self.tdir_path, "code"), {
            "skill": "code", "ticket_id": "SHOP-1", "states": {}, "findings": [],
            "errors": [], "runs": [{"started_at": lib.now_iso(), "status": "in_progress"}]})

    def _events(self):
        state = lib.read_json(lib.state_path(self.tdir_path, "code")) or {}
        return (state.get("runs") or [{}])[-1].get("guard_events")

    def test_the_event_lands_on_the_last_run_entry(self):
        self._seed_run()
        self.assertIs(lib.record_guard_event(self.tdir_path, "code", {"reason": "outside_map"}),
                      True)
        self.assertEqual(self._events(), [{"reason": "outside_map"}])

    def test_a_second_event_appends_rather_than_replaces(self):
        self._seed_run()
        lib.record_guard_event(self.tdir_path, "code", {"reason": "outside_map"})
        lib.record_guard_event(self.tdir_path, "code", {"reason": "control_input"})
        self.assertEqual([e["reason"] for e in self._events()],
                         ["outside_map", "control_input"])

    def test_no_run_entry_returns_false_and_never_raises(self):
        """record_escalation_event raises here. This sibling runs inside a deny
        path, where an exception would be the caller's problem to catch."""
        self.assertIs(lib.record_guard_event(self.tdir_path, "code", {"reason": "outside_map"}),
                      False)
        self.assertIsNone(self._events())
        with self.assertRaises(ValueError):
            lib.record_escalation_event(self.tdir_path, "code", {"reason": "x"})


class RecordedTargetTest(unittest.TestCase):
    """How a denied path is written down, for the shapes a hook payload can
    carry: under the checkout, outside it, and one no relpath can express."""

    def test_a_path_under_the_checkout_is_repo_relative(self):
        self.assertEqual(
            lib.filemap._recorded_target("/repo/src/a.py", {"checkout_root": "/repo"}),
            "src/a.py")

    def test_a_path_outside_the_checkout_is_recorded_as_given(self):
        self.assertEqual(
            lib.filemap._recorded_target("/elsewhere/a.py", {"checkout_root": "/repo"}),
            "/elsewhere/a.py")

    def test_a_path_no_relpath_can_express_is_recorded_as_given(self):
        """Windows drives, and anything else relpath refuses: the event still
        names the target rather than losing it."""
        with mock.patch.object(lib.filemap.os.path, "relpath",
                               side_effect=ValueError("different drives")):
            self.assertEqual(
                lib.filemap._recorded_target("/elsewhere/a.py", {"checkout_root": "/repo"}),
                "/elsewhere/a.py")

    def test_with_no_checkout_root_there_is_nothing_to_relativize_against(self):
        self.assertEqual(lib.filemap._recorded_target("/tmp/a.py", {}), "/tmp/a.py")


class GuardEventsCase(FileMapGuardCase):
    """The real guard, driven through dispatch.py exactly as the hook does."""

    def entry(self, skill="code"):
        state = lib.read_json(lib.state_path(self.tdir_path, skill)) or {}
        runs = state.get("runs") or []
        return runs[-1] if runs else {}

    def events(self, skill="code"):
        return self.entry(skill).get("guard_events")

    def payload(self, path, tool="Write"):
        key = lib.WRITE_TOOL_PATH_KEYS[tool]
        return {"cwd": self.repo, "tool_name": tool, "tool_input": {key: path}}


class RecordedDenialTest(GuardEventsCase):

    def test_an_out_of_map_write_records_one_complete_event(self):
        self.declare("src/a.py", "tests/test_a.py")
        self.spawn_executor()
        self.assertEqual(self.write_attempt("src/somewhere_else.py").returncode, 2)

        events = self.events()
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(set(event), EVENT_FIELDS)
        self.assertRegex(event["ts"], TS_RE)
        self.assertEqual(event["skill"], "code")
        self.assertEqual(event["iteration"], "1")
        self.assertEqual(event["tool"], "Write")
        self.assertEqual(event["target"], "src/somewhere_else.py")
        self.assertEqual(event["reason"], "outside_map")
        self.assertEqual(event["declared_count"], 2,
                         "declared_count is the union the guard actually enforced")

    def test_every_write_tool_records_the_tool_that_was_denied(self):
        self.declare("src/a.py")
        self.spawn_executor()
        for tool in lib.WRITE_TOOL_PATH_KEYS:
            with self.subTest(tool=tool):
                self.assertEqual(self.write_attempt("src/nope.py", tool=tool).returncode, 2)
                self.assertEqual(self.events()[-1]["tool"], tool)

    def test_an_absolute_target_records_repo_relative(self):
        self.declare("src/a.py")
        self.spawn_executor()
        self.assertEqual(
            self.write_attempt(os.path.join(self.repo, "src", "elsewhere.py")).returncode, 2)
        self.assertEqual(self.events()[-1]["target"], "src/elsewhere.py")

    def test_a_target_outside_the_checkout_records_as_given(self):
        """A control input lives in the WORKSPACE, not the checkout: there is no
        repo-relative form of it, so the path is recorded as it was written."""
        self.declare("src/a.py")
        self.spawn_executor()
        record = lib.agent_record_path(self.tdir_path, "a-1")
        out = self.hook("file-map", {"cwd": self.repo, "tool_name": "Write",
                                     "tool_input": {"file_path": record}})
        self.assertEqual(out.returncode, 2, out.stderr)
        event = self.events()[-1]
        self.assertEqual(event["target"], record)
        self.assertEqual(event["reason"], "control_input")
        self.assertEqual(event["declared_count"], 0)

    def test_an_unreadable_payload_records_the_reason_with_no_target(self):
        """Nothing nameable was written, so `target` is null rather than an
        empty string a real path could be confused with."""
        self.declare("src/a.py")
        self.spawn_executor()
        out = self.hook("file-map", {"cwd": self.repo, "tool_name": "Write",
                                     "tool_input": "file_path=evil.py"})
        self.assertEqual(out.returncode, 2, out.stderr)
        event = self.events()[-1]
        self.assertEqual(set(event), EVENT_FIELDS)
        self.assertEqual(event["reason"], "unreadable_payload")
        self.assertIsNone(event["target"])
        self.assertEqual(event["declared_count"], 0)
        self.assertEqual(event["tool"], "Write")

    def test_two_denials_append_in_order_to_the_same_run_entry(self):
        self.declare("src/a.py")
        self.spawn_executor()
        self.write_attempt("src/one.py")
        self.write_attempt("src/two.py")
        state = lib.read_json(lib.state_path(self.tdir_path, "code"))
        self.assertEqual(len(state["runs"]), 1, "no second run entry is created")
        self.assertEqual([e["target"] for e in self.events()], ["src/one.py", "src/two.py"])

    def test_the_iteration_in_force_is_the_one_recorded(self):
        self.declare("src/a.py", iteration=1)
        self.declare("src/b.py", iteration=2)
        self.spawn_executor()
        self.assertEqual(self.write_attempt("src/a.py").returncode, 2)
        self.assertEqual(self.events()[-1]["iteration"], "2")


class FailOpenSilenceTest(GuardEventsCase):
    """AC-2: a write the guard waves through leaves no trace at all."""

    def test_no_fail_open_branch_records_anything(self):
        report = os.path.join(self.tdir_path, "phases", "code", "iter-1-execute.json")
        cases = {
            "not a write tool": {"cwd": self.repo, "tool_name": "Read",
                                 "tool_input": {"file_path": "anything.py"}},
            "no path in tool_input": {"cwd": self.repo, "tool_name": "Write",
                                      "tool_input": {}},
            "the executor's own phase artifact": {"cwd": self.repo, "tool_name": "Write",
                                                  "tool_input": {"file_path": report}},
        }
        self.declare("src/a.py")
        self.spawn_executor()
        for label, payload in cases.items():
            with self.subTest(case=label):
                self.assertEqual(self.hook("file-map", payload).returncode, 0)
                self.assertIsNone(self.events(), "%s must record nothing" % label)

        # in the map
        self.assertEqual(self.write_attempt("src/a.py").returncode, 0)
        self.assertIsNone(self.events())

    def test_no_map_declared_records_nothing(self):
        self.spawn_executor()
        self.assertEqual(self.write_attempt("anything.py").returncode, 0)
        self.assertIsNone(self.events())

    def test_no_executor_running_records_nothing(self):
        self.declare("src/a.py")
        self.assertEqual(self.write_attempt("anything.py").returncode, 0)
        self.assertIsNone(self.events())

    def test_outside_an_acs_partition_records_nothing(self):
        import shutil
        import subprocess
        import tempfile
        tmp = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, tmp, True)
        out = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "dispatch.py"), "file-map"],
            input=json.dumps({"cwd": tmp, "tool_name": "Write",
                              "tool_input": {"file_path": "x.py"}}),
            capture_output=True, text=True, cwd=tmp)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIsNone(self.events())


class VerdictInvarianceTest(GuardEventsCase):
    """AC-3: recording is a side effect of the deny, never a condition of it."""

    def _clear_runs(self):
        path = lib.state_path(self.tdir_path, "code")
        state = lib.read_json(path)
        state["runs"] = []
        lib.write_json(path, state)

    def test_with_no_run_entry_the_deny_is_unchanged_and_says_so_once(self):
        self.declare("src/a.py")
        self.spawn_executor()
        self._clear_runs()
        out = self.write_attempt("src/somewhere_else.py")
        self.assertEqual(out.returncode, 2)
        self.assertIn("is outside this task's file map.", out.stderr)
        notes = [line for line in out.stderr.splitlines() if line.startswith(NOTE_PREFIX)]
        self.assertEqual(len(notes), 1, out.stderr)
        self.assertEqual(lib.read_json(lib.state_path(self.tdir_path, "code"))["runs"], [])

    def test_a_writer_that_raises_leaves_the_verdict_and_notes_once(self):
        self.declare("src/a.py")
        self.spawn_executor()
        stderr = io.StringIO()
        with mock.patch.object(lib.state, "write_json", side_effect=OSError("read-only")):
            with contextlib.redirect_stderr(stderr):
                self.assertEqual(lib.file_map_guard(self.payload("src/nope.py")), 2)
        notes = [line for line in stderr.getvalue().splitlines()
                 if line.startswith(NOTE_PREFIX)]
        self.assertEqual(len(notes), 1, stderr.getvalue())
        self.assertIn("is outside this task's file map.", stderr.getvalue())

    def test_the_append_is_one_write_with_no_lock_and_no_retry(self):
        self.declare("src/a.py")
        self.spawn_executor()
        before = sorted(self._partition_files())
        with mock.patch.object(lib.state, "write_json",
                               wraps=lib.state.write_json) as writer:
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(lib.file_map_guard(self.payload("src/nope.py")), 2)
        self.assertEqual(writer.call_count, 1, "no retries on a deny path")
        self.assertEqual(sorted(self._partition_files()), before,
                         "the recorder acquires no lock and writes no sidecar")

    def test_a_base_exception_still_reaches_the_dispatcher(self):
        """dispatch.GateTimeout is a BaseException precisely so no broad handler
        can absorb it; a recorder that caught it would unbound the guard."""
        self.declare("src/a.py")
        self.spawn_executor()
        with mock.patch.object(lib.state, "write_json", side_effect=_Boom("timeout")):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(_Boom):
                    lib.file_map_guard(self.payload("src/nope.py"))

    def _partition_files(self):
        out = []
        for root, _dirs, names in os.walk(self.tdir_path):
            out += [os.path.join(root, name) for name in names]
        return out


class GuardEventsCliTest(GuardEventsCase):
    """AC-4: denials are readable without knowing the state-file layout."""

    def acs(self, *args):
        return self.run_script("acs.py", *args)

    def test_it_prints_the_events_a_real_deny_recorded(self):
        self.declare("src/a.py")
        self.spawn_executor()
        self.assertEqual(self.write_attempt("src/somewhere_else.py").returncode, 2)
        out = self.acs("guard", "events", "--ticket", self.ticket)
        self.assertEqual(out.returncode, 0, out.stderr)
        body = json.loads(out.stdout)
        self.assertIs(body["ok"], True)
        self.assertEqual(body["ticket_id"], self.ticket)
        self.assertEqual(body["skill"], "code")
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["events"][0]["reason"], "outside_map")

    def test_a_run_with_no_denial_prints_an_empty_array(self):
        out = self.acs("guard", "events", "--ticket", self.ticket)
        self.assertEqual(out.returncode, 0, out.stderr)
        body = json.loads(out.stdout)
        self.assertEqual(body["events"], [])
        self.assertEqual(body["count"], 0)

    def test_the_skill_defaults_to_code(self):
        out = self.acs("guard", "events")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout)["skill"], "code")

    def test_an_unknown_ticket_is_a_refusal(self):
        out = self.acs("guard", "events", "--ticket", "SHOP-999")
        self.assertEqual(out.returncode, 2)
        self.assertIn("acs guard events:", out.stderr)

    def test_a_skill_that_never_ran_names_the_missing_state_file(self):
        out = self.acs("guard", "events", "--ticket", self.ticket, "--skill", "docs-sync")
        self.assertEqual(out.returncode, 2)
        self.assertIn("acs guard events:", out.stderr)
        self.assertIn("docs-sync-state.json", out.stderr)

    def test_the_guard_group_is_registered_as_a_group_of_its_own(self):
        """Asserting the word "guard" in `--help` proves nothing: the untouched
        tree already prints "the axis guard" and "the write guard enforces".
        Assert what only this group can emit -- its own help line, a `--help`
        that names its subcommand, and the usage a subcommand-less group owes
        (the shape at tests/acs/test_acs_cli.py:521-527)."""
        top = self.acs("--help")
        self.assertEqual(top.returncode, 0)
        self.assertIn("what the executor file-map guard denied", top.stdout)

        group = self.acs("guard", "--help")
        self.assertEqual(group.returncode, 0, group.stderr)
        self.assertIn("events", group.stdout)

        bare = self.acs("guard")
        self.assertEqual(bare.returncode, 2)
        self.assertIn("usage", bare.stderr.lower())
        self.assertEqual(bare.stdout, "")


class DerivedGuardDenialsCase(AcsWorkspaceCase):

    def setUp(self):
        super().setUp()
        self.ticket = self.new_ticket("Bulk import", "task")
        self.tdir_path = self.tdir(self.ticket)

    def seed_run(self, events=None, skill="code"):
        path = lib.state_path(self.tdir_path, skill)
        state = lib.read_json(path)
        if not isinstance(state, dict) or not state.get("runs"):
            state = lib.empty_state(skill, self.ticket)
            state["runs"] = [{"started_at": lib.now_iso(), "ended_at": None,
                              "tokens": {"input": 0, "output": 0}, "cost_usd": 0.0,
                              "status": "in_progress", "stop_reason": None}]
        if events is not None:
            state["runs"][-1]["guard_events"] = [
                {"ts": lib.now_iso(), "skill": skill, "iteration": "1", "tool": "Write",
                 "target": "src/%d.py" % n, "reason": "outside_map", "declared_count": 2}
                for n in range(events)]
        lib.write_json(path, state)


class GuardDenialsDerivationTest(DerivedGuardDenialsCase):
    """The unit arms of the derivation itself (post-code.py is coverage-omitted)."""

    def test_no_state_file_is_zero_rather_than_an_error(self):
        self.assertEqual(lib.guard_denials(self.tdir_path, "code"), 0)

    def test_a_run_entry_with_no_events_is_zero(self):
        self.seed_run()
        self.assertEqual(lib.guard_denials(self.tdir_path, "code"), 0)

    def test_the_count_is_the_length_of_the_list(self):
        self.seed_run(events=3)
        self.assertEqual(lib.guard_denials(self.tdir_path, "code"), 3)


class PostHookGuardDenialsTest(DerivedGuardDenialsCase):
    """AC-5: the number reaches the result contract through the post hook."""

    def setUp(self):
        super().setUp()
        self.assertEqual(self.start("code", self.ticket).returncode, 0)

    def _states(self):
        return lib.load_state(self.tdir_path, "code", self.ticket)["states"]

    def _entry(self):
        return lib.last_run(lib.load_state(self.tdir_path, "code", self.ticket))

    def test_the_count_is_derived_from_the_state_file(self):
        self.seed_run(events=2)
        out = self.post("code", self.ticket, {"status": "completed"})
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(self._states()["review"]["guard_denials"], 2)

    def test_a_coordinator_supplied_count_is_overridden_and_recorded(self):
        self.seed_run(events=2)
        out = self.post("code", self.ticket,
                        {"status": "completed", "states": {"review": {"guard_denials": 0}}})
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(self._states()["review"]["guard_denials"], 2)
        overrode = self._entry()["derived_states"]["overrode"]
        self.assertEqual([row["key"] for row in overrode], ["review"])
        self.assertEqual(overrode[0]["supplied"], {"guard_denials": 0})
        self.assertEqual(overrode[0]["derived"], {"guard_denials": 2})
        self.assertIn("guard denial",
                      self._entry()["derived_states"]["provenance"]["review"])

    def test_no_denial_leaves_the_key_absent_rather_than_zero(self):
        self.seed_run(events=0)
        self.seed_verdict(self.ticket, iteration=1)
        out = self.post("code", self.ticket,
                        {"status": "completed", "states": {"review": {"findings_open": 3}}})
        self.assertEqual(out.returncode, 0, out.stderr)
        review = self._states()["review"]
        self.assertNotIn("guard_denials", review)
        self.assertEqual(review["iterations"], 1)
        self.assertEqual(review["findings_open"], 3,
                         "a key this module does not own must survive")

    def test_it_derives_with_no_verify_artifact_at_all(self):
        self.seed_run(events=1)
        out = self.post("code", self.ticket, {"status": "completed"})
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(self._states()["review"], {"guard_denials": 1})


class SchemaTest(unittest.TestCase):
    """AC-7: the shape is declared, and nothing valid today becomes invalid."""

    def setUp(self):
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            self.schema = json.load(fh)
        self.entry = (self.schema["properties"]["runs"]["items"])

    def test_guard_events_is_declared_on_the_run_entry(self):
        events = self.entry["properties"]["guard_events"]
        self.assertEqual(events["type"], "array")
        item = events["items"]
        self.assertEqual(set(item["properties"]), EVENT_FIELDS)
        self.assertEqual(sorted(item["properties"]["reason"]["enum"]),
                         ["control_input", "outside_map", "unreadable_payload"])

    def test_it_is_not_required_on_a_run_entry(self):
        self.assertNotIn("guard_events", self.entry.get("required", []))
        self.assertIs(self.entry.get("additionalProperties"), True)

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed")
    def test_legacy_and_recorded_entries_both_validate(self):
        legacy = {"started_at": "2026-01-01T00:00:00Z", "ended_at": None,
                  "status": "completed", "tokens": {"input": 1, "output": 2},
                  "cost_usd": 0.0}
        event = {"ts": "2026-09-10T13:41:07Z", "skill": "code", "iteration": "1",
                 "tool": "Write", "target": "src/a.py", "reason": "outside_map",
                 "declared_count": 2}

        def state(entry):
            return {"skill": "code", "ticket_id": "SHOP-1", "states": {},
                    "findings": [], "errors": [], "runs": [entry]}

        jsonschema.validate(state(legacy), self.schema)
        recorded = dict(legacy, guard_events=[event])
        jsonschema.validate(state(recorded), self.schema)
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(
                state(dict(legacy, guard_events=[dict(event, reason="because")])),
                self.schema)


class ProseTest(unittest.TestCase):
    """AC-7: the audit trail is documented where its neighbours are."""

    def _body(self, path):
        with open(path, encoding="utf-8") as fh:
            return " ".join(fh.read().split())

    def test_internals_documents_the_trail_and_its_two_rules(self):
        body = self._body(INTERNALS)
        for token in ("guard_events", "outside_map", "control_input", "unreadable_payload",
                      "record_escalation_event"):
            self.assertIn(token, body)
        self.assertIn("never on a fail-open branch", body)
        self.assertIn("never changes the verdict", body)

    def test_internals_lists_the_derived_key(self):
        self.assertIn("review.guard_denials", self._body(INTERNALS))

    def test_the_requirements_doc_names_the_guard_audit_trail(self):
        body = self._body(WORKSPACE_DOC)
        self.assertIn("runs[-1].guard_events", body)

    def test_the_code_skill_names_guard_denials_as_derived(self):
        self.assertIn("guard_denials", self._body(CODE_SKILL))


if __name__ == "__main__":
    unittest.main()
