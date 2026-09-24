"""Behavior tests for claude_code_adapter.py -- the single module encoding
what acs assumes about Claude Code's undocumented interfaces (MAR-520).

Under test: every accessor is TOTAL. A malformed, absent, or wrong-typed value
yields None (or the documented default), never an exception -- a hook must not
have to validate Claude Code's output at each call site.

Plus a structural guard (`TestInterfaceLiteralsLiveInTheAdapter`) that fails
if the envelope's distinctive field names reappear in another plugin module --
the enforceable half of "every interface assumption lives in one adapter
module". (The transcript, attribution, subagent-layout and statusLine
interfaces went with the usage measurement and status line that read them --
ADR-0103, ADR-0104.)
"""

import ast
import os
import sys
import unittest

TESTS_ACS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS_ACS)

import acs_case  # noqa: E402,F401  (puts the plugin scripts on sys.path)
import claude_code_adapter as cc  # noqa: E402

PLUGIN_SCRIPTS = os.path.join(
    os.path.dirname(os.path.dirname(TESTS_ACS)), "plugins", "acs", "hooks", "scripts")


class TestHookEnvelope(unittest.TestCase):
    """Interface 1: the JSON a hook receives on stdin."""

    ENVELOPE = {"session_id": "s-1", "cwd": "/repo", "agent_id": "a-1",
                "agent_type": "acs:code-executor",
                "last_assistant_message": "<result/>"}

    def test_reads_each_field(self):
        self.assertEqual(cc.hook_session_id(self.ENVELOPE), "s-1")
        self.assertEqual(cc.hook_agent_id(self.ENVELOPE), "a-1")
        self.assertEqual(cc.hook_agent_type(self.ENVELOPE), "acs:code-executor")
        self.assertEqual(cc.hook_last_assistant_message(self.ENVELOPE), "<result/>")

    def test_absent_fields_are_none_never_constructed(self):
        for accessor in (cc.hook_session_id, cc.hook_agent_id, cc.hook_agent_type,
                         cc.hook_last_assistant_message):
            self.assertIsNone(accessor({}))

    def test_wrong_typed_fields_are_none(self):
        bad = {"session_id": 7, "agent_id": "", "agent_type": [],
               "last_assistant_message": {}}
        for accessor in (cc.hook_session_id, cc.hook_agent_id, cc.hook_agent_type,
                         cc.hook_last_assistant_message):
            self.assertIsNone(accessor(bad))

    def test_a_non_dict_payload_never_raises(self):
        for payload in ([], "x", None, 3):
            self.assertIsNone(cc.hook_session_id(payload))
            self.assertIsNone(cc.hook_agent_id(payload))


class TestPayloadCwd(unittest.TestCase):
    """The cwd probe order every payload shape shares."""

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


class TestInterfaceLiteralsLiveInTheAdapter(unittest.TestCase):
    """The enforceable half of "every interface assumption lives in one
    adapter module": these field names are Claude Code's, not acs's, so a
    second spelling of one anywhere else in the plugin is the drift this
    ticket removed. Docstrings and comments are exempt -- prose may name a
    field; executable code may not re-derive it."""

    ADAPTER_ONLY = ("current_dir", "last_assistant_message")

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

    def _plugin_modules(self):
        """Every plugin module under the scripts dir, RECURSIVELY.

        acs_lib became a package in MAR-522. A non-recursive listdir would skip
        its eight modules entirely -- the guard would keep passing while the
        literals it exists to catch moved into acs_lib/step.py."""
        found = []
        for root, _dirs, files in os.walk(PLUGIN_SCRIPTS):
            if "__pycache__" in root:
                continue
            for name in sorted(files):
                if name.endswith(".py") and name != "claude_code_adapter.py":
                    found.append(os.path.join(root, name))
        return sorted(found)

    def test_the_walk_reaches_inside_the_acs_lib_package(self):
        """Grounding check: without it, the guard below could pass vacuously."""
        scanned = self._plugin_modules()
        # `state.py` was split into one module per machine (§4.7); `run.py` is
        # the one that carries the RUN machine, and it is the module a literal
        # would most plausibly drift into.
        self.assertTrue(any(os.path.join("acs_lib", "run.py") in p for p in scanned),
                        "the module walk must reach acs_lib's package modules")
        self.assertGreater(len(scanned), 30)

    def test_no_other_plugin_module_spells_these_out(self):
        offenders = []
        for path in self._plugin_modules():
            name = os.path.relpath(path, PLUGIN_SCRIPTS)
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


if __name__ == "__main__":
    unittest.main()
