"""MAR-528: the subagent and stop lifecycle events are bound, not remembered.

acs bound two hook events (PreToolUse on `Skill`, SessionEnd). Everything else
the pipeline needs at a lifecycle boundary — snapshot the subagent's XML,
validate it, finish the run before stopping, flush context before a compaction —
was an instruction in a SKILL.md. An instruction a model must remember is not an
enforcement point; it is a request.

These tests drive the hooks the way Claude Code does: a JSON payload on stdin
to `dispatch.py <mode>`, and its exit code. Every hook is also exercised with a
payload that resolves NO acs partition — the headless / not-our-repo case, which
is most sessions, and where a bookkeeping hook that raises would break a session
over nothing.
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
HOOKS_JSON = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "hooks.json")
sys.path.insert(0, SCRIPTS)

import acs_lib as lib  # noqa: E402

sys.path.insert(0, os.path.join(REPO_ROOT, "tests", "acs"))
from acs_case import AcsWorkspaceCase  # noqa: E402


def result_xml(skill="code", phase="execute", ticket="SHOP-1", iteration=None,
               status="completed"):
    attrs = 'skill="%s" phase="%s" ticket-id="%s"' % (skill, phase, ticket)
    if iteration is not None:
        attrs += ' iteration="%s"' % iteration
    return '<result %s status="%s"><outputs><file>a.py</file></outputs></result>' % (attrs, status)


class ParseAgentTypeTest(unittest.TestCase):

    def test_hyphenated_skill_names_survive(self):
        """Splitting from the LEFT would make `acs:create-pr-executor` a skill
        called "create" — a bug that only appears on the hyphenated half of the
        skill list, which is most of it."""
        for agent_type, expected in (
                ("acs:code-executor", ("code", "executor")),
                ("acs:create-pr-planner", ("create-pr", "planner")),
                ("acs:docs-sync-verifier", ("docs-sync", "verifier")),
                ("acs:standardize-project-executor", ("standardize-project", "executor"))):
            with self.subTest(agent_type=agent_type):
                self.assertEqual(lib.parse_agent_type(agent_type), expected)

    def test_anything_that_is_not_an_acs_triad_agent_is_not_ours(self):
        for agent_type in ("Explore", "general-purpose", "other:code-executor",
                           "acs:code-reviewer", "acs:nosuchskill-executor",
                           "acs:code", "", None, 7):
            with self.subTest(agent_type=agent_type):
                self.assertEqual(lib.parse_agent_type(agent_type), (None, None))

    def test_every_role_maps_to_the_phase_its_artifact_is_filed_under(self):
        self.assertEqual(lib.ROLE_PHASES,
                         {"planner": "plan", "executor": "execute", "verifier": "verify"})


class ExtractMessageTest(unittest.TestCase):

    def test_finds_the_element_inside_surrounding_prose(self):
        text = "Here is my result:\n\n%s\n\nDone." % result_xml()
        self.assertEqual(lib.extract_message(text), result_xml())

    def test_finds_the_element_inside_a_code_fence(self):
        text = "```xml\n%s\n```" % result_xml()
        self.assertEqual(lib.extract_message(text), result_xml())

    def test_takes_the_last_element_when_an_earlier_one_is_quoted(self):
        """A subagent often restates the task or an earlier attempt before its
        own answer; the one it is RETURNING is the last."""
        text = "Earlier I sent %s but corrected it to %s" % (
            result_xml(status="failed"), result_xml(status="completed"))
        self.assertIn('status="completed"', lib.extract_message(text))

    def test_a_handoff_counts_as_a_returned_message(self):
        handoff = '<handoff skill="code" ticket-id="SHOP-1" status="needs_input"><summary>x</summary></handoff>'
        self.assertEqual(lib.extract_message("blah %s" % handoff), handoff)

    def test_absent_or_non_string_input_is_none(self):
        for text in ("no xml here", "", None, 7, "<task skill='code'/>"):
            with self.subTest(text=text):
                self.assertIsNone(lib.extract_message(text))


class LifecycleCase(AcsWorkspaceCase):
    """Shared fixture: a ticket with an in_progress run, plus payload builders."""

    def setUp(self):
        super().setUp()
        self.ticket = self.new_ticket("Ship the thing", "task")
        self.tdir_path = self.tdir(self.ticket)

    def payload(self, **over):
        doc = {"session_id": "sess-1", "cwd": self.repo,
               "transcript_path": os.path.join(self.tmp, "t.jsonl")}
        doc.update(over)
        return doc

    def hook(self, mode, payload, env=None):
        return subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "dispatch.py"), mode],
            input=json.dumps(payload), capture_output=True, text=True,
            cwd=self.repo, env=env)

    def start_run(self, skill="code"):
        """Register an in_progress run AND the session pointer.

        A subagent only ever runs while a skill is in flight, and the pointer
        skill-start.py writes is what makes this checkout's ticket resolvable
        from a hook payload — so this is the realistic precondition for every
        lifecycle hook, not just the ones that read the run."""
        out = self.start(skill, self.ticket)
        self.assertEqual(out.returncode, 0, out.stderr)
        return skill

    def finish_run(self, skill="code", status="completed"):
        out = self.post(skill, self.ticket, {"status": status})
        self.assertEqual(out.returncode, 0, out.stderr)

    def write_result(self, skill, **doc):
        path = os.path.join(self.tdir_path, "phases", skill, "result.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh)
        return path


class SubagentStartTest(LifecycleCase):

    def setUp(self):
        super().setUp()
        self.start_run("code")

    def test_records_the_running_agent_in_the_partition(self):
        out = self.hook("subagent-start", self.payload(
            agent_id="a-1", agent_type="acs:code-executor"))
        self.assertEqual(out.returncode, 0, out.stderr)
        entry = lib.read_agent(self.tdir_path, "a-1")
        self.assertEqual(entry["skill"], "code")
        self.assertEqual(entry["role"], "executor")
        self.assertEqual(entry["phase"], "execute")
        self.assertEqual(entry["session_id"], "sess-1")
        self.assertEqual(entry["stop_attempts"], 0)

    def test_records_parallel_executors_separately(self):
        """A fan-out runs several executors of the SAME type at once, so the
        record is keyed by agent_id, not agent_type."""
        for agent_id in ("a-1", "a-2"):
            self.hook("subagent-start", self.payload(
                agent_id=agent_id, agent_type="acs:code-executor"))
        doc = lib.read_json(lib.active_agents_path(self.tdir_path))
        self.assertEqual(sorted(doc["agents"]), ["a-1", "a-2"])

    def test_another_plugins_agent_is_not_recorded(self):
        out = self.hook("subagent-start", self.payload(
            agent_id="a-1", agent_type="Explore"))
        self.assertEqual(out.returncode, 0)
        self.assertFalse(os.path.exists(lib.active_agents_path(self.tdir_path)))

    def test_a_claude_code_without_agent_fields_is_a_no_op(self):
        out = self.hook("subagent-start", self.payload())
        self.assertEqual(out.returncode, 0)
        self.assertFalse(os.path.exists(lib.active_agents_path(self.tdir_path)))


class SubagentStopTest(LifecycleCase):

    def setUp(self):
        super().setUp()
        self.start_run("code")

    def _snapshot(self, skill="code", iteration="1", phase="execute"):
        return lib.phase_artifact_path(self.tdir_path, skill, iteration, phase)

    def test_writes_the_snapshot_the_coordinator_used_to_write(self):
        message = result_xml(ticket=self.ticket, iteration="3")
        out = self.hook("subagent-stop", self.payload(
            agent_id="a-1", agent_type="acs:code-executor",
            last_assistant_message="Here you go:\n%s" % message))
        self.assertEqual(out.returncode, 0, out.stderr)
        path = self._snapshot(iteration="3")
        self.assertTrue(os.path.exists(path), path)
        with open(path, encoding="utf-8") as fh:
            self.assertEqual(fh.read().strip(), message)

    def test_the_path_comes_from_the_message_not_from_a_guess(self):
        """skill/phase/iteration are attributes of the message
        (acs-messages.xsd), so nothing about the snapshot has to be
        remembered — including which iteration is running."""
        self.hook("subagent-stop", self.payload(
            agent_id="a-1", agent_type="acs:code-planner",
            last_assistant_message=result_xml(ticket=self.ticket, phase="plan", iteration="7")))
        self.assertTrue(os.path.exists(self._snapshot(iteration="7", phase="plan")))

    def test_an_absent_iteration_defaults_to_one_as_the_schema_says(self):
        self.hook("subagent-stop", self.payload(
            agent_id="a-1", agent_type="acs:code-executor",
            last_assistant_message=result_xml(ticket=self.ticket)))
        self.assertTrue(os.path.exists(self._snapshot(iteration="1")))

    def test_an_omitted_iteration_that_would_clobber_an_earlier_one_is_called_out(self):
        """The schema reads an absent `iteration` as 1, so a message that omits
        it on iteration 3 CLAIMS to be iteration 1. The message is what is
        wrong; the hook cannot see a counter, so it says so."""
        first = result_xml(ticket=self.ticket)
        self.hook("subagent-stop", self.payload(
            agent_id="a-1", agent_type="acs:code-executor", last_assistant_message=first))
        second = first.replace("a.py", "b.py")
        out = self.hook("subagent-stop", self.payload(
            agent_id="a-2", agent_type="acs:code-executor", last_assistant_message=second))
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("omitted `iteration`", out.stderr)

    def test_an_echoed_iteration_never_warns(self):
        for n in ("1", "2"):
            out = self.hook("subagent-stop", self.payload(
                agent_id="a-%s" % n, agent_type="acs:code-executor",
                last_assistant_message=result_xml(ticket=self.ticket, iteration=n)))
            self.assertNotIn("omitted", out.stderr)

    def test_clears_the_active_agent_record(self):
        self.hook("subagent-start", self.payload(agent_id="a-1", agent_type="acs:code-executor"))
        self.hook("subagent-stop", self.payload(
            agent_id="a-1", agent_type="acs:code-executor",
            last_assistant_message=result_xml(ticket=self.ticket)))
        self.assertIsNone(lib.read_agent(self.tdir_path, "a-1"))

    def test_an_invalid_message_sends_the_subagent_back_with_the_errors(self):
        out = self.hook("subagent-stop", self.payload(
            agent_id="a-1", agent_type="acs:code-executor",
            last_assistant_message='<result skill="code" phase="execute" '
                                   'ticket-id="%s" status="ok"/>' % self.ticket))
        self.assertEqual(out.returncode, 2)
        self.assertIn("acs-messages.xsd", out.stderr)
        self.assertIn("status='ok'", out.stderr)
        self.assertFalse(os.path.exists(self._snapshot()))

    def test_a_message_with_no_xml_at_all_sends_it_back(self):
        out = self.hook("subagent-stop", self.payload(
            agent_id="a-1", agent_type="acs:code-executor",
            last_assistant_message="I finished the work."))
        self.assertEqual(out.returncode, 2)
        self.assertIn("no <result> or <handoff>", out.stderr)

    def test_it_stops_refusing_after_the_block_limit(self):
        """A hook that can refuse forever is a hung session. The skill contract
        already says a still-invalid message fails the run rather than looping,
        so after BLOCK_LIMIT attempts this lets the subagent stop and says the
        coordinator has to record the failure."""
        payload = self.payload(agent_id="a-1", agent_type="acs:code-executor",
                               last_assistant_message="still nothing")
        codes = [self.hook("subagent-stop", payload).returncode for _ in range(4)]
        self.assertEqual(codes[0], 2)
        self.assertEqual(codes[1:], [0, 0, 0])
        self.assertEqual(lib.BLOCK_LIMIT, 2)

    def test_the_cap_holds_without_a_subagent_start_record(self):
        """The cap is the only thing between a malformed message and an
        unbounded refuse-retry loop, so it must not depend on SubagentStart
        having fired — an older Claude Code, or a restart mid-subagent, would
        otherwise leave the hook refusing forever."""
        self.assertIsNone(lib.read_agent(self.tdir_path, "never-started"))
        payload = self.payload(agent_id="never-started", agent_type="acs:code-executor",
                               last_assistant_message="no xml at all")
        codes = [self.hook("subagent-stop", payload).returncode for _ in range(3)]
        self.assertEqual(codes, [2, 0, 0])

    def test_the_give_up_message_names_the_validation_errors(self):
        """The coordinator has to record the failure, so the third refusal has
        to hand it the reason rather than just giving up quietly."""
        bad = ('<result skill="code" phase="execute" ticket-id="%s" status="ok"/>' % self.ticket)
        payload = self.payload(agent_id="a-1", agent_type="acs:code-executor",
                               last_assistant_message=bad)
        for _ in range(lib.BLOCK_LIMIT):
            self.hook("subagent-stop", payload)
        out = self.hook("subagent-stop", payload)
        self.assertEqual(out.returncode, 0)
        self.assertIn("still invalid after", out.stderr)
        self.assertIn("status='ok'", out.stderr)

    def test_a_message_that_is_not_parseable_xml_writes_nothing(self):
        """extract_message found something element-shaped, but it does not
        parse. Nothing is filed rather than a broken artifact."""
        out = self.hook("subagent-stop", self.payload(
            agent_id="a-1", agent_type="acs:code-executor",
            last_assistant_message='<result skill="code"><unclosed></result>',
            ))
        self.assertEqual(out.returncode, 2)  # the validator rejects it first
        self.assertFalse(os.path.exists(self._snapshot()))

    def test_a_handoff_validates_but_writes_no_phase_artifact(self):
        """A handoff is the run's outcome, not a phase artifact; the run ledger
        carries it."""
        handoff = ('<handoff skill="code" ticket-id="%s" status="needs_input">'
                   '<summary>blocked on a decision</summary></handoff>' % self.ticket)
        out = self.hook("subagent-stop", self.payload(
            agent_id="a-1", agent_type="acs:code-executor", last_assistant_message=handoff))
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertFalse(os.path.isdir(os.path.join(self.tdir_path, "phases", "code")))

    def test_another_plugins_agent_is_never_blocked(self):
        out = self.hook("subagent-stop", self.payload(
            agent_id="a-1", agent_type="Explore", last_assistant_message="whatever"))
        self.assertEqual(out.returncode, 0)


class StopTest(LifecycleCase):

    def test_refuses_to_end_a_turn_that_abandoned_a_run(self):
        self.start_run("code")
        out = self.hook("stop", self.payload())
        self.assertEqual(out.returncode, 2)
        self.assertIn("in_progress", out.stderr)
        self.assertIn(self.ticket, out.stderr)
        self.assertIn("acs.py\" finish", out.stderr)
        self.assertIn("handoff.py", out.stderr)

    def test_a_written_result_document_is_enough_to_stop(self):
        """The post hook's own absence is what the next gate reports; this hook
        is about the document, not about who ran which script."""
        self.start_run("code")
        self.write_result("code", status="completed")
        self.assertEqual(self.hook("stop", self.payload()).returncode, 0)

    def test_an_in_progress_result_document_does_not_count(self):
        self.start_run("code")
        self.write_result("code", status="in_progress")
        self.assertEqual(self.hook("stop", self.payload()).returncode, 2)

    def test_no_run_in_progress_is_nothing_to_do(self):
        self.start_run("code")
        self.finish_run("code")
        self.assertEqual(self.hook("stop", self.payload()).returncode, 0)

    def test_it_stops_refusing_after_the_block_limit(self):
        self.start_run("code")
        codes = [self.hook("stop", self.payload()).returncode for _ in range(4)]
        self.assertEqual(codes, [2, 2, 0, 0])

    def test_the_give_up_message_says_the_safety_net_will_finalize_it(self):
        self.start_run("code")
        for _ in range(lib.BLOCK_LIMIT):
            self.hook("stop", self.payload())
        out = self.hook("stop", self.payload())
        self.assertEqual(out.returncode, 0)
        self.assertIn("SessionEnd will finalize it as `interrupted`", out.stderr)

    def test_finishing_the_run_clears_the_block_counter(self):
        """Otherwise a long session that legitimately blocked twice would be
        unable to block on the NEXT abandoned run."""
        self.start_run("code")
        self.hook("stop", self.payload())
        self.post("code", self.ticket, {"status": "completed"})
        self.assertEqual(self.hook("stop", self.payload()).returncode, 0)
        blocks = lib.read_json(os.path.join(
            lib.sessions_dir(self.ws, "acme-shop"),
            "%s-stop-blocks.json" % lib.checkout_id(self.repo)))
        self.assertEqual(blocks, {})


class PreCompactTest(LifecycleCase):

    def _context(self):
        path = os.path.join(self.tdir_path, lib.HANDOFF_CONTEXT_FILENAME)
        with open(path, encoding="utf-8") as fh:
            return fh.read()

    def test_writes_the_ledger_not_a_summary_of_the_window(self):
        self.start_run("code")
        out = self.hook("pre-compact", self.payload())
        self.assertEqual(out.returncode, 0, out.stderr)
        body = self._context()
        self.assertIn("# Handoff context — %s" % self.ticket, body)
        self.assertIn("Ship the thing", body)
        self.assertIn("`/acs:code` run started", body)
        self.assertIn("not written yet", body)
        self.assertIn("acs.py finish --ticket %s --skill code" % self.ticket, body)

    def test_says_so_when_the_result_document_already_exists(self):
        self.start_run("code")
        self.write_result("code", status="completed")
        self.hook("pre-compact", self.payload())
        self.assertIn("written (status `completed`)", self._context())

    def test_carries_the_findings_the_run_is_working_through(self):
        self.start_run("code")
        state = lib.load_state(self.tdir_path, "code", self.ticket)
        state["findings"] = [{"severity": "blocking", "dimension": "tests",
                              "detail": "coverage 71% below the 90% target"}]
        lib.write_json(lib.state_path(self.tdir_path, "code"), state)
        self.hook("pre-compact", self.payload())
        body = self._context()
        self.assertIn("### Findings carried into this run", body)
        self.assertIn("coverage 71% below the 90% target", body)

    def test_names_the_parent_epic_when_the_ticket_has_one(self):
        self.start_run("code")
        ticket = lib.load_ticket(self.tdir_path)
        ticket["parent"] = "SHOP-99"
        lib.save_ticket(self.tdir_path, ticket)
        self.hook("pre-compact", self.payload())
        self.assertIn("parent epic: `SHOP-99`", self._context())

    def test_says_so_when_no_pipeline_step_has_run_yet(self):
        self.start_run("code")
        os.remove(os.path.join(self.tdir_path, "pipeline-state.json"))
        self.hook("pre-compact", self.payload())
        self.assertIn("no pipeline steps recorded yet", self._context())

    def test_records_open_clarifications(self):
        self.start_run("code")
        lib.write_json(os.path.join(self.tdir_path, "clarifications.json"),
                       {"clarifications": [
                           {"id": "C-1", "status": "open", "question": "which database?"},
                           {"id": "C-2", "status": "answered", "question": "answered one"}]})
        self.hook("pre-compact", self.payload())
        body = self._context()
        self.assertIn("which database?", body)
        self.assertNotIn("answered one", body)

    def test_with_no_run_in_flight_it_still_records_where_the_pipeline_is(self):
        self.start_run("code")
        self.finish_run("code")
        out = self.hook("pre-compact", self.payload())
        self.assertEqual(out.returncode, 0, out.stderr)
        body = self._context()
        self.assertIn("no run is in progress", body)
        self.assertIn("## Pipeline", body)

    def test_a_render_failure_never_truncates_an_existing_context_file(self):
        """`open(..., "w")` truncates, so rendering INSIDE the with-block would
        replace a good handoff-context.md with an empty one the moment the
        renderer raised — at exactly the moment there is nothing left to
        rebuild it from."""
        self.start_run("code")
        lib.write_handoff_context(self.tdir_path, self.ticket, "code")
        good = self._context()
        self.assertTrue(good.strip())
        with mock.patch.object(lib.lifecycle, "render_handoff_context",
                               side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                lib.write_handoff_context(self.tdir_path, self.ticket, "code")
        self.assertEqual(self._context(), good)

    def test_it_is_rewritten_each_time_not_appended(self):
        self.start_run("code")
        self.hook("pre-compact", self.payload())
        first = self._context()
        self.hook("pre-compact", self.payload())
        self.assertEqual(self._context().count("# Handoff context"), 1)
        self.assertNotEqual(first, "")


class HeadlessAndFailOpenTest(unittest.TestCase):
    """Most sessions are not working an acs ticket. For those, every lifecycle
    hook must be indistinguishable from absent."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def _hook(self, mode, payload, cwd=None):
        return subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "dispatch.py"), mode],
            input=json.dumps(payload), capture_output=True, text=True, cwd=cwd or self.tmp)

    MODES = ("subagent-start", "subagent-stop", "stop", "pre-compact")

    def test_an_empty_payload_is_a_no_op_everywhere(self):
        for mode in self.MODES:
            with self.subTest(mode=mode):
                out = self._hook(mode, {})
                self.assertEqual(out.returncode, 0, out.stderr)

    def test_a_directory_that_is_not_a_git_repo_is_a_no_op(self):
        for mode in self.MODES:
            with self.subTest(mode=mode):
                out = self._hook(mode, {"cwd": self.tmp, "agent_id": "a-1",
                                        "agent_type": "acs:code-executor",
                                        "last_assistant_message": "nothing"})
                self.assertEqual(out.returncode, 0, out.stderr)

    def test_malformed_stdin_is_a_no_op(self):
        for mode in self.MODES:
            with self.subTest(mode=mode):
                out = subprocess.run(
                    [sys.executable, os.path.join(SCRIPTS, "dispatch.py"), mode],
                    input="not json", capture_output=True, text=True, cwd=self.tmp)
                self.assertEqual(out.returncode, 0, out.stderr)

    def test_a_raising_hook_body_becomes_exit_zero_with_a_note(self):
        """The gate fails CLOSED because letting a skill run unchecked is the
        harm. These do bookkeeping: a bug here must not end a session."""
        dispatch = __import__("importlib").import_module("importlib.util")
        spec = dispatch.spec_from_file_location("dispatch_under_test",
                                                os.path.join(SCRIPTS, "dispatch.py"))
        module = dispatch.module_from_spec(spec)
        spec.loader.exec_module(module)
        with mock.patch.object(module.acs_lib, "pre_compact", side_effect=RuntimeError("boom")):
            with mock.patch("sys.stderr"):
                self.assertEqual(module.run_lifecycle("pre-compact", {}), 0)

    def test_the_gate_mode_still_fails_closed(self):
        """The two policies are opposite on purpose; a change that unified them
        would silently let a blocked skill run."""
        out = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "dispatch.py"), "pre"],
            input=json.dumps({"cwd": self.tmp, "tool_name": "Skill",
                              "tool_input": {"skill": "acs:code", "args": "SHOP-1"}}),
            capture_output=True, text=True, cwd=self.tmp)
        self.assertEqual(out.returncode, 2)


class HooksJsonTest(unittest.TestCase):
    """The registration itself — a hook body nothing calls is prose again."""

    @classmethod
    def setUpClass(cls):
        with open(HOOKS_JSON, encoding="utf-8") as fh:
            cls.doc = json.load(fh)

    def test_every_lifecycle_event_is_registered(self):
        self.assertEqual(
            list(self.doc["hooks"]),
            ["PreToolUse", "SubagentStart", "SubagentStop", "Stop", "PreCompact", "SessionEnd"])

    def test_the_subagent_events_are_anchored_on_the_plugin_scope(self):
        """Unanchored, these would fire for every subagent in the session —
        Explore, Plan, another plugin's agents — and try to snapshot their
        output as an acs phase artifact."""
        for event in ("SubagentStart", "SubagentStop"):
            with self.subTest(event=event):
                self.assertEqual(self.doc["hooks"][event][0]["matcher"], "^acs:")

    def test_stop_and_precompact_take_no_matcher(self):
        for event in ("Stop", "PreCompact"):
            with self.subTest(event=event):
                self.assertNotIn("matcher", self.doc["hooks"][event][0])

    def test_each_registration_reaches_the_dispatcher_mode_that_implements_it(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "dispatch_modes", os.path.join(SCRIPTS, "dispatch.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for event, mode in (("SubagentStart", "subagent-start"),
                            ("SubagentStop", "subagent-stop"),
                            ("Stop", "stop"), ("PreCompact", "pre-compact")):
            with self.subTest(event=event):
                command = self.doc["hooks"][event][0]["hooks"][0]["command"]
                self.assertTrue(command.endswith('dispatch.py" %s' % mode), command)
                self.assertIn(mode, module.LIFECYCLE_MODES)
                self.assertTrue(hasattr(lib, module.LIFECYCLE_MODES[mode]))

    def test_every_hook_has_a_timeout(self):
        for event, entries in self.doc["hooks"].items():
            for entry in entries:
                for hook in entry["hooks"]:
                    with self.subTest(event=event):
                        self.assertIsInstance(hook.get("timeout"), int)


if __name__ == "__main__":
    unittest.main()
