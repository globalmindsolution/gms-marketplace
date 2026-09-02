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
