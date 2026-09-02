"""The gate dispatcher must fail closed.

Claude Code treats any exit code other than 2 as "not blocked", so a gate that
raises, hangs, or dies has to end as an explicit exit 2 (MAR-514). The gate now
runs in-process under a bounded alarm rather than in a subprocess whose failure
took its exit code with it.

Patching note. `acs_case.load_module` pops "acs_lib" from sys.modules before
loading a script, so a freshly loaded `dispatch` holds its OWN acs_lib object
with its own GATES dict. Patching the GATES imported at the top of this file
therefore patches a dictionary the dispatcher never reads, and the gate under
test never runs -- which is exactly how the first version of these tests passed
while asserting nothing. Always patch `dispatch.acs_lib.GATES`, and assert on
the distinguishing stderr rather than on the exit code alone, since the real
gate_code also exits 2 (for a completely unrelated reason).
"""

import io
import json
import os
import sys
import time
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

    def _dispatch_with_gate(self, gate, alias, timeout=None):
        """Load dispatch and install `gate` on the acs_lib object IT holds."""
        dispatch = load_module("dispatch.py", alias)
        self.assertIsNot(dispatch.acs_lib.GATES, lib.GATES,
                         "load_module's re-import behaviour changed; re-check this helper")
        original = dispatch.acs_lib.GATES["code"]
        dispatch.acs_lib.GATES["code"] = gate
        self.addCleanup(dispatch.acs_lib.GATES.__setitem__, "code", original)
        if timeout is not None:
            self.addCleanup(setattr, dispatch, "GATE_TIMEOUT_SECONDS",
                            dispatch.GATE_TIMEOUT_SECONDS)
            dispatch.GATE_TIMEOUT_SECONDS = timeout
        return dispatch

    def _run(self, dispatch, skill="code"):
        """run_gate with stderr captured, so the REASON can be asserted."""
        buffer = io.StringIO()
        real_stderr = sys.stderr
        sys.stderr = buffer
        try:
            code = dispatch.run_gate(skill, {"cwd": self.repo})
        finally:
            sys.stderr = real_stderr
        return code, buffer.getvalue()

    def test_gate_that_raises_exits_2(self):
        """An unexpected exception inside a gate blocks rather than passing."""
        def boom(_ctx, _payload):
            raise RuntimeError("gate is broken")

        dispatch = self._dispatch_with_gate(boom, "dispatch_raise_test")
        code, stderr = self._run(dispatch)
        self.assertEqual(code, 2, stderr)
        self.assertIn("gate is broken", stderr)

    def test_gate_that_hangs_exits_2(self):
        """The bound is the point: without it the hook's own timeout kills the
        process with no exit code of 2, which reads as 'not blocked'."""
        def hang(_ctx, _payload):
            time.sleep(30)

        dispatch = self._dispatch_with_gate(hang, "dispatch_hang_test", timeout=1)
        started = time.time()
        code, stderr = self._run(dispatch)
        self.assertEqual(code, 2, stderr)
        self.assertIn("timed out", stderr)
        self.assertLess(time.time() - started, 10, "the bound did not fire")

    def test_a_hang_inside_a_git_call_still_blocks(self):
        """The regression that made the bound useless in practice.

        TimeoutError subclasses OSError, and acs_lib._git does
        `except (OSError, subprocess.TimeoutExpired): return None`. A
        TimeoutError-based alarm raised while the gate sat in a git call was
        swallowed there -- the gate then ran on unbounded, on silently-wrong
        git data, and returned 0. Only a BaseException survives that handler.
        """
        def hang_inside_git(ctx, _payload):
            try:
                time.sleep(30)
            except OSError:
                return  # _git's handler shape: swallow and carry on

        dispatch = self._dispatch_with_gate(hang_inside_git, "dispatch_git_hang_test",
                                            timeout=1)
        started = time.time()
        code, stderr = self._run(dispatch)
        self.assertEqual(code, 2, stderr)
        self.assertLess(time.time() - started, 10,
                        "the alarm was swallowed by the gate's own OSError handler")

    def test_a_gate_that_calls_sys_exit_still_blocks(self):
        """SystemExit is not an Exception, so `except Exception` misses it and
        the frame returns an exit code that is not 2."""
        def early_exit(_ctx, _payload):
            sys.exit(0)

        dispatch = self._dispatch_with_gate(early_exit, "dispatch_sysexit_test")
        code, stderr = self._run(dispatch)
        self.assertEqual(code, 2, stderr)

    def test_a_gate_interrupted_by_ctrl_c_still_blocks(self):
        def interrupted(_ctx, _payload):
            raise KeyboardInterrupt()

        dispatch = self._dispatch_with_gate(interrupted, "dispatch_sigint_test")
        code, stderr = self._run(dispatch)
        self.assertEqual(code, 2, stderr)

    def test_the_timeout_is_not_an_ordinary_exception(self):
        """A structural guard. If the bound is ever raised as TimeoutError (or
        anything under Exception) again, every broad handler on the gate path
        silently absorbs it and the tests above stop testing the bound.
        """
        dispatch = load_module("dispatch.py", "dispatch_type_test")
        self.assertTrue(issubclass(dispatch.GateTimeout, BaseException))
        self.assertFalse(issubclass(dispatch.GateTimeout, Exception))


class AllocateOnlyWhenAbsentTest(AcsWorkspaceCase):
    """--allocate must not mint a second ticket for work that already has one
    (MAR-509), and must not let one product-level leg adopt another's ticket."""

    def _ids(self):
        index = lib.read_json(lib.index_path(self.ws, lib.build_context(self.repo)["repo_id"]))
        return sorted((index or {}).get("tickets", {}))

    def test_fresh_run_allocates(self):
        result = self.run_script("skill-start.py", "--skill", "create-ticket",
                                 "--allocate", "--args", "add a wishlist API")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self._ids()), 1)

    def test_resume_with_the_id_in_args_reuses_the_partition(self):
        first = self.run_script("skill-start.py", "--skill", "create-ticket",
                                "--allocate", "--args", "add a wishlist API")
        self.assertEqual(first.returncode, 0, first.stderr)
        ticket_id = json.loads(first.stdout)["ticket_id"]
        lib.release_lock(lib.ticket_dir(self.ws, lib.build_context(self.repo)["repo_id"], ticket_id))

        again = self.run_script("skill-start.py", "--skill", "create-ticket",
                                "--allocate", "--args", ticket_id)
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(json.loads(again.stdout)["ticket_id"], ticket_id)
        self.assertEqual(self._ids(), [ticket_id])

    def test_a_second_product_leg_still_gets_its_own_ticket(self):
        """Two doc-bootstrap legs run concurrently with no id in their args;
        neither may adopt the other's ticket through the session pointer."""
        first = self.run_script("skill-start.py", "--skill", "create-quality", "--allocate")
        self.assertEqual(first.returncode, 0, first.stderr)
        second = self.run_script("skill-start.py", "--skill", "create-operations", "--allocate")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertNotEqual(json.loads(first.stdout)["ticket_id"],
                            json.loads(second.stdout)["ticket_id"])
        self.assertEqual(len(self._ids()), 2)


if __name__ == "__main__":
    unittest.main()
