"""The gate dispatcher must fail closed.

Claude Code treats any exit code other than 2 as "not blocked", so a gate that
raises, hangs, or dies has to end as an explicit exit 2 (MAR-514). The gate now
runs in-process under a bounded alarm rather than in a subprocess whose failure
took its exit code with it.
"""

import json
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import acs_lib as lib  # noqa: E402
from acs_case import AcsWorkspaceCase, load_module  # noqa: E402


class DispatchFailClosedTest(AcsWorkspaceCase):
    def _payload(self, skill="code", args_text=""):
        return json.dumps({
            "cwd": self.repo, "tool_name": "Skill",
            "tool_input": {"skill": "acs:" + skill, "args": args_text},
        })

    def test_unhooked_skill_passes_through(self):
        result = self.run_script("dispatch.py", "pre", stdin=self._payload("ship"))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_foreign_plugin_skill_passes_through(self):
        payload = json.dumps({"cwd": self.repo, "tool_input": {"skill": "other:thing"}})
        result = self.run_script("dispatch.py", "pre", stdin=payload)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_blocked_gate_exits_2(self):
        """A real gate failure (no ticket) still blocks."""
        result = self.run_script("dispatch.py", "pre", stdin=self._payload("code"))
        self.assertEqual(result.returncode, 2, result.stdout)

    def test_gate_that_raises_exits_2(self):
        """An unexpected exception inside a gate blocks rather than passing."""
        dispatch = load_module("dispatch.py", "dispatch_under_test")

        def boom(_ctx, _payload):
            raise RuntimeError("gate is broken")

        original = lib.GATES["code"]
        lib.GATES["code"] = boom
        self.addCleanup(lambda: lib.GATES.__setitem__("code", original))
        self.assertEqual(dispatch.run_gate("code", {"cwd": self.repo}), 2)

    def test_gate_that_hangs_exits_2(self):
        """The bound is the point: without it the hook's own timeout kills the
        process with no exit code of 2, which reads as 'not blocked'."""
        dispatch = load_module("dispatch.py", "dispatch_hang_test")

        def hang(_ctx, _payload):
            import time
            time.sleep(30)

        original = lib.GATES["code"]
        original_timeout = dispatch.GATE_TIMEOUT_SECONDS
        lib.GATES["code"] = hang
        dispatch.GATE_TIMEOUT_SECONDS = 1
        self.addCleanup(lambda: lib.GATES.__setitem__("code", original))
        self.addCleanup(setattr, dispatch, "GATE_TIMEOUT_SECONDS", original_timeout)
        self.assertEqual(dispatch.run_gate("code", {"cwd": self.repo}), 2)


if __name__ == "__main__":
    unittest.main()
