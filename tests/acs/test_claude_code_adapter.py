"""Behavior tests for claude_code_adapter.py -- the single module encoding
what acs assumes about Claude Code's undocumented interfaces (MAR-520).

Three things are under test here:

1. Every accessor is TOTAL. A malformed, absent, or wrong-typed value yields
   None (or the documented default), never an exception -- measurement code
   must not have to validate Claude Code's output at each call site.
2. The degradation switch logs its reason and returns it, and never raises
   even when the log destination is unusable.
3. `claude_version` is cached, bounded, and degrades to None -- it runs on
   every measurement tick, so a missing or slow `claude` binary can never
   cost the caller anything.

Plus a structural guard (`TestInterfaceLiteralsLiveInTheAdapter`) that fails
if any of the five interfaces' distinctive field names reappear in another
plugin module -- the enforceable half of this ticket's "all five interface
assumptions live in one adapter module".
"""

import ast
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

TESTS_ACS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS_ACS)

import acs_case  # noqa: E402
import claude_code_adapter as cc  # noqa: E402

PLUGIN_SCRIPTS = os.path.join(
    os.path.dirname(os.path.dirname(TESTS_ACS)), "plugins", "acs", "hooks", "scripts")


class TestHookEnvelope(unittest.TestCase):
    """Interface 1: the JSON a hook receives on stdin."""

    ENVELOPE = {"session_id": "s-1", "transcript_path": "/t/s-1.jsonl",
                "cwd": "/repo", "hook_event_name": "PreToolUse",
                "tool_input": {"skill": "acs:code"}}

    def test_reads_each_field(self):
        self.assertEqual(cc.hook_session_id(self.ENVELOPE), "s-1")
        self.assertEqual(cc.hook_transcript_path(self.ENVELOPE), "/t/s-1.jsonl")
        self.assertEqual(cc.hook_event_name(self.ENVELOPE), "PreToolUse")
        self.assertEqual(cc.hook_tool_input(self.ENVELOPE), {"skill": "acs:code"})

    def test_absent_fields_are_none_never_constructed(self):
        for accessor in (cc.hook_session_id, cc.hook_transcript_path, cc.hook_event_name):
            self.assertIsNone(accessor({}))
        self.assertEqual(cc.hook_tool_input({}), {})

    def test_wrong_typed_fields_are_none(self):
        bad = {"session_id": 7, "transcript_path": "", "hook_event_name": [],
               "tool_input": "not-an-object"}
        self.assertIsNone(cc.hook_session_id(bad))
        self.assertIsNone(cc.hook_transcript_path(bad))
        self.assertIsNone(cc.hook_event_name(bad))
        self.assertEqual(cc.hook_tool_input(bad), {})

    def test_a_non_dict_payload_never_raises(self):
        for payload in ([], "x", None, 3):
            self.assertIsNone(cc.hook_session_id(payload))
            self.assertEqual(cc.hook_tool_input(payload), {})


class TestPayloadCwd(unittest.TestCase):
    """The cwd probe order shared by hook envelopes and statusLine payloads."""

    def test_workspace_current_dir_wins(self):
        payload = {"workspace": {"current_dir": "/ws"}, "cwd": "/other"}
        self.assertEqual(cc.payload_cwd(payload), "/ws")

    def test_falls_back_to_top_level_cwd(self):
        self.assertEqual(cc.payload_cwd({"cwd": "/other"}), "/other")

    def test_falls_back_to_the_default_then_the_process_cwd(self):
        self.assertEqual(cc.payload_cwd({}, default="/fallback"), "/fallback")
        self.assertEqual(cc.payload_cwd({}), os.getcwd())
        self.assertEqual(cc.payload_cwd([]), os.getcwd())

    def test_empty_string_is_not_a_directory(self):
        self.assertEqual(cc.payload_cwd({"workspace": {"current_dir": ""}, "cwd": "/c"}), "/c")


class TestTranscriptRecords(unittest.TestCase):
    """Interface 2: the transcript JSONL record shape."""

    RECORD = {"timestamp": "2026-09-03T10:00:00Z",
              "message": {"model": "claude-opus-5",
                          "usage": {"input_tokens": 10, "output_tokens": 2},
                          "content": "SECRET PROMPT TEXT"}}

    def test_reads_timestamp_usage_and_model(self):
        self.assertEqual(cc.record_timestamp(self.RECORD), "2026-09-03T10:00:00Z")
        self.assertEqual(cc.record_usage(self.RECORD), {"input_tokens": 10, "output_tokens": 2})
        self.assertEqual(cc.record_model(self.RECORD), "claude-opus-5")

    def test_usage_is_the_only_door_into_message(self):
        """Privacy boundary: no accessor here returns message.content."""
        returned = [cc.record_usage(self.RECORD), cc.record_model(self.RECORD),
                    cc.record_timestamp(self.RECORD)]
        self.assertNotIn("SECRET PROMPT TEXT", json.dumps(returned))

    def test_missing_or_malformed_pieces_are_none(self):
        self.assertIsNone(cc.record_usage({}))
        self.assertIsNone(cc.record_usage({"message": "not-an-object"}))
        self.assertIsNone(cc.record_usage({"message": {"usage": []}}))
        self.assertIsNone(cc.record_model({"message": {}}))
        self.assertIsNone(cc.record_timestamp({"timestamp": 12345}))
        self.assertIsNone(cc.record_usage([]))

    def test_the_four_token_classes_pair_positionally_with_acs_buckets(self):
        self.assertEqual(len(cc.USAGE_FIELDS), 4)
        self.assertEqual(len(cc.BUCKET_KEYS), 4)
        self.assertEqual(cc.USAGE_FIELDS[0], "input_tokens")
        self.assertEqual(cc.BUCKET_KEYS[0], "input")


class TestAttribution(unittest.TestCase):
    """Interface 3: attributionSkill / attributionAgent."""

    def test_reads_both_attribution_fields(self):
        self.assertEqual(cc.record_attribution_skill({"attributionSkill": "acs:code"}), "acs:code")
        self.assertEqual(
            cc.record_attribution_agent({"attributionAgent": "acs:code-verifier"}),
            "acs:code-verifier")

    def test_absent_or_empty_attribution_is_none(self):
        self.assertIsNone(cc.record_attribution_skill({}))
        self.assertIsNone(cc.record_attribution_skill({"attributionSkill": ""}))
        self.assertIsNone(cc.record_attribution_agent({"attributionAgent": 5}))

    def test_strip_skill_prefix(self):
        self.assertEqual(cc.strip_skill_prefix("acs:code"), "code")
        self.assertEqual(cc.strip_skill_prefix("code"), "code")
        self.assertIsNone(cc.strip_skill_prefix(""))
        self.assertIsNone(cc.strip_skill_prefix(None))

    def test_agent_role_maps_each_observed_suffix(self):
        self.assertEqual(cc.agent_role("acs:code-planner"), "planner")
        self.assertEqual(cc.agent_role("acs:code-executor"), "executor")
        self.assertEqual(cc.agent_role("acs:docs-sync-verifier"), "verifier")

    def test_an_unmatched_agent_is_attributed_not_dropped(self):
        self.assertEqual(cc.agent_role("Explore"), "other")
        self.assertEqual(cc.agent_role("Explore", default="something-else"), "something-else")

    def test_an_absent_agent_is_none(self):
        self.assertIsNone(cc.agent_role(None))
        self.assertIsNone(cc.agent_role(""))
        self.assertIsNone(cc.agent_role(42))


class TestSubagentLayout(unittest.TestCase):
    """Interface 4: where a session's subagent transcripts live."""

    def test_session_id_comes_from_the_transcripts_own_basename(self):
        self.assertEqual(cc.session_id_from_transcript("/p/abc-123.jsonl"), "abc-123")

    def test_subagents_dir_is_sibling_session_dir(self):
        self.assertEqual(cc.subagents_dir("/p/abc-123.jsonl"),
                         os.path.join("/p", "abc-123", "subagents"))

    def test_absent_transcript_path_yields_none_not_a_constructed_slug(self):
        self.assertIsNone(cc.session_id_from_transcript(None))
        self.assertIsNone(cc.session_id_from_transcript(""))
        self.assertIsNone(cc.subagents_dir(None))
        self.assertIsNone(cc.subagents_dir("/p/"))

    def test_only_jsonl_transcripts_match_the_privacy_boundary(self):
        self.assertTrue(cc.is_transcript_file("a.jsonl"))
        self.assertFalse(cc.is_transcript_file("a.meta.json"))
        self.assertFalse(cc.is_transcript_file("a.json"))
        self.assertFalse(cc.is_transcript_file(None))


class TestStatusPayload(unittest.TestCase):
    """Interface 5: statusLine payload keys and the cost probe order."""

    def test_model_display_name_with_default(self):
        self.assertEqual(cc.status_model_display_name({"model": {"display_name": "Opus"}}), "Opus")
        self.assertEqual(cc.status_model_display_name({}), "Claude")
        self.assertEqual(cc.status_model_display_name([]), "Claude")
        self.assertEqual(cc.status_model_display_name({"model": {}}, default="X"), "X")

    def test_probe_source_labels_match_the_recorded_src_values(self):
        self.assertEqual(cc.probe_source("cost", "total_cost_usd"), "cost.total_cost_usd")
        self.assertEqual(cc.probe_source(None, "total_cost_usd"), "total_cost_usd")

    def test_duration_probe_order_mirrors_the_cost_one(self):
        self.assertEqual(len(cc.COST_PROBE_ORDER), len(cc.DURATION_PROBE_ORDER))
        self.assertEqual([container for container, _ in cc.COST_PROBE_ORDER],
                         [container for container, _ in cc.DURATION_PROBE_ORDER])


class TestDegradationSwitch(unittest.TestCase):
    """The one switch: it returns the reason and logs it, and never raises."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-degrade-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.log = os.path.join(self.tmp, "nested", "degradations.jsonl")

    def test_returns_the_reason_it_was_given(self):
        with mock.patch.dict(os.environ, {cc.DEGRADATION_LOG_ENV: self.log}):
            self.assertEqual(cc.unavailable("cap_exceeded"), "cap_exceeded")

    def test_logs_the_reason_creating_the_destination(self):
        with mock.patch.dict(os.environ, {cc.DEGRADATION_LOG_ENV: self.log}):
            cc.unavailable("no_tokens_in_window", detail="run 3", source="usage_reader")
        with open(self.log) as fh:
            entry = json.loads(fh.readline())
        self.assertEqual(entry["reason"], "no_tokens_in_window")
        self.assertEqual(entry["detail"], "run 3")
        self.assertEqual(entry["source"], "usage_reader")

    def test_rotates_past_the_cap(self):
        with mock.patch.dict(os.environ, {cc.DEGRADATION_LOG_ENV: self.log}):
            os.makedirs(os.path.dirname(self.log))
            with open(self.log, "w") as fh:
                fh.write("x" * (cc.MAX_DEGRADATION_LOG_BYTES + 1))
            cc.unavailable("cap_exceeded")
        self.assertTrue(os.path.exists(self.log + ".1"))
        with open(self.log) as fh:
            self.assertEqual(json.loads(fh.readline())["reason"], "cap_exceeded")

    def test_an_unusable_log_destination_never_costs_the_caller_its_reason(self):
        unwritable = os.path.join(self.tmp, "a-file")
        with open(unwritable, "w") as fh:
            fh.write("")
        with mock.patch.dict(os.environ,
                             {cc.DEGRADATION_LOG_ENV: os.path.join(unwritable, "nope.jsonl")}):
            self.assertEqual(cc.unavailable("unreadable_transcript"), "unreadable_transcript")

    def test_quiet_on_stderr_unless_debugging(self):
        env = {k: v for k, v in os.environ.items()
               if k not in (cc.DEGRADATION_LOG_ENV, cc.DEBUG_ENV)}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(cc.sys, "stderr") as stderr:
            cc.unavailable("empty_window")
        stderr.write.assert_not_called()

    def test_the_unavailable_constant_is_what_callers_write(self):
        self.assertEqual(cc.UNAVAILABLE, "unavailable")


class TestClaudeVersion(unittest.TestCase):
    """`claude --version` alongside samples: cached, bounded, degrades to None."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-version-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.cache = os.path.join(self.tmp, "sessions", "ck-claude-version.json")
        cc._VERSION_MEMO.clear()
        self.addCleanup(cc._VERSION_MEMO.clear)

    def test_probes_once_and_caches_to_disk(self):
        with mock.patch.object(cc, "_probe_claude_version", return_value="2.1.0") as probe:
            self.assertEqual(cc.claude_version(self.cache), "2.1.0")
            self.assertEqual(cc.claude_version(self.cache), "2.1.0")
        self.assertEqual(probe.call_count, 1)
        with open(self.cache) as fh:
            self.assertEqual(json.load(fh)["version"], "2.1.0")

    def test_reprobes_once_the_ttl_has_passed(self):
        with mock.patch.object(cc, "_probe_claude_version", return_value="2.1.0"):
            cc.claude_version(self.cache)
        with mock.patch.object(cc, "_probe_claude_version", return_value="2.2.0") as probe:
            self.assertEqual(cc.claude_version(self.cache, ttl_seconds=-1), "2.2.0")
        self.assertEqual(probe.call_count, 1)

    def test_a_missing_claude_binary_degrades_to_none(self):
        with mock.patch.object(cc.subprocess, "run", side_effect=OSError("no claude")):
            self.assertIsNone(cc.claude_version(self.cache))

    def test_a_nonzero_exit_degrades_to_none(self):
        proc = mock.Mock(returncode=1, stdout=b"")
        with mock.patch.object(cc.subprocess, "run", return_value=proc):
            self.assertIsNone(cc.claude_version(self.cache))

    def test_the_version_string_is_stripped(self):
        proc = mock.Mock(returncode=0, stdout=b"  2.1.0 (Claude Code)\n")
        with mock.patch.object(cc.subprocess, "run", return_value=proc):
            self.assertEqual(cc.claude_version(self.cache), "2.1.0 (Claude Code)")

    def test_without_a_cache_path_the_process_memo_still_bounds_the_probe(self):
        with mock.patch.object(cc, "_probe_claude_version", return_value="2.1.0") as probe:
            cc.claude_version()
            cc.claude_version()
        self.assertEqual(probe.call_count, 1)


class TestInterfaceLiteralsLiveInTheAdapter(unittest.TestCase):
    """The enforceable half of "all five interface assumptions live in one
    adapter module": these field names are Claude Code's, not acs's, so a
    second spelling of one anywhere else in the plugin is the drift this
    ticket removed. Docstrings and comments are exempt -- prose may name a
    field; executable code may not re-derive it."""

    ADAPTER_ONLY = ("attributionSkill", "attributionAgent",
                    "input_tokens", "output_tokens",
                    "cache_creation_input_tokens", "cache_read_input_tokens",
                    "display_name", "current_dir")

    def _code_strings(self, path):
        """Every string constant in `path` that is not a docstring."""
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                body = getattr(node, "body", None)
                if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                        and isinstance(body[0].value.value, str):
                    docstrings.add(id(body[0].value))
        found = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and id(node) not in docstrings:
                found.append(node.value)
        return found

    def test_no_other_plugin_module_spells_these_out(self):
        offenders = []
        for name in sorted(os.listdir(PLUGIN_SCRIPTS)):
            if not name.endswith(".py") or name == "claude_code_adapter.py":
                continue
            path = os.path.join(PLUGIN_SCRIPTS, name)
            strings = self._code_strings(path)
            for literal in self.ADAPTER_ONLY:
                if any(literal == value for value in strings):
                    offenders.append("%s: %r" % (name, literal))
        self.assertEqual(offenders, [], "Claude Code interface literals outside "
                         "claude_code_adapter.py -- route them through an accessor "
                         "there instead:\n  " + "\n  ".join(offenders))

    def test_the_adapter_itself_does_define_them(self):
        strings = self._code_strings(os.path.join(PLUGIN_SCRIPTS, "claude_code_adapter.py"))
        for literal in self.ADAPTER_ONLY:
            self.assertIn(literal, strings, "%s must be defined in the adapter" % literal)


class TestCostSampleCarriesTheVersion(acs_case.AcsWorkspaceCase):
    """The sample record grows a `claude_version` field, so a shape change
    can be dated against the build that produced the sample."""

    def test_record_cost_sample_writes_the_version(self):
        import cost_sampler
        with mock.patch.object(cc, "_probe_claude_version", return_value="2.1.0"):
            cc._VERSION_MEMO.clear()
            with acs_case.pushd(self.repo):
                cost_sampler.record_cost_sample({"cost": {"total_cost_usd": 1.5},
                                                 "cwd": self.repo})
        ctx = acs_case.lib.build_context(self.repo)
        path = cost_sampler.cost_samples_path(ctx["workspace"], ctx["repo_id"], ctx["checkout_id"])
        with open(path) as fh:
            sample = json.loads(fh.readline())
        self.assertEqual(sample["claude_version"], "2.1.0")
        self.assertEqual(sample["total_cost_usd"], 1.5)


if __name__ == "__main__":
    unittest.main()
