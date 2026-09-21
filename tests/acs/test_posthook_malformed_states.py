"""A malformed `states.pr` finalizes the step instead of stranding it (MAR-586).

`states` is typed as a bare object in schemas/result.schema.json, so
`step.validate_result` ADMITS `states.pr` as a string or a list: such a value
reaches the post hook through the sanctioned write path, and `save_state` has
already persisted the invocation by the time the hook reads it. `run_post` read
`((result.get("states") or {}).get("pr") or {}).get("number")`, which handles
None but not a non-dict -- so the AttributeError escaped the `except
GuardTimeout` arm, skipped `release_lock`, and left the next gate refusing a run
that had in fact finished, after a partial write.

The PRE side refuses the same value (the `_pr_recorded_for` brake in gates.py)
and is right to: exit 2 blocks BEFORE any work is done. A post hook is the other
side of the pipeline -- it runs after the work, and the run entry it finalises
is the audit trail -- so here the value degrades to "no number recorded" with
the reason on stderr, which is how metrics.py's roll-up and this hook's own
derivation block already treat a result document they cannot use. Nothing is
swallowed: the pre-side brake still refuses the mis-shaped value at the next
gate, so the operator is still made to correct it.
"""

import json
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "src", "acs", "hooks", "scripts")
sys.path.insert(0, SCRIPTS)

import acs_lib as lib  # noqa: E402

sys.path.insert(0, os.path.join(REPO_ROOT, "tests", "acs"))
from acs_case import AcsWorkspaceCase  # noqa: E402


class MalformedPrReferenceCase(AcsWorkspaceCase):

    def setUp(self):
        super().setUp()
        self.ticket = self.new_ticket("Bulk import", "task")
        self.rdir_path = self.ensure_run(self.ticket)

    def post_pr(self, pr):
        """Finalize create-pr with whatever `states.pr` the coordinator wrote."""
        out = self.start("create-pr", self.ticket)
        self.assertEqual(out.returncode, 0, out.stderr)
        return self.post("create-pr", self.ticket,
                         {"status": "completed", "states": {"pr": pr}})

    def metrics(self):
        return lib.read_json(lib.metrics_path(self.ws, "acme-shop")) or {}


class MalformedPrReferenceTest(MalformedPrReferenceCase):

    def test_a_string_pr_reference_does_not_crash_the_hook(self):
        """The defect: a string is admitted by validate_result, so it arrives
        here, and `.get("number")` on it raised out of the hook."""
        out = self.post_pr("https://github.com/acme/shop/pull/7")
        self.assertNotIn("Traceback", out.stderr)
        self.assertNotIn("AttributeError", out.stderr)
        self.assertEqual(out.returncode, 0, out.stderr)

    def test_a_list_pr_reference_does_not_crash_the_hook(self):
        out = self.post_pr([{"number": 7}])
        self.assertNotIn("Traceback", out.stderr)
        self.assertNotIn("AttributeError", out.stderr)
        self.assertEqual(out.returncode, 0, out.stderr)

    def test_the_mis_shaped_value_is_reported_not_swallowed(self):
        """Degrading quietly would hide the only signal the operator gets on
        this side; the stderr line names the key and what it actually is."""
        out = self.post_pr("https://github.com/acme/shop/pull/7")
        self.assertIn("states.pr", out.stderr)
        self.assertIn("str", out.stderr)

    def test_the_step_is_finalized_rather_than_left_in_progress(self):
        """This one held even with the defect, and that IS the argument for
        degrading here: the invocation is already durable when the read
        happens, so refusing at this point could only abandon a step the hook
        had finished writing."""
        self.post_pr("https://github.com/acme/shop/pull/7")
        state = lib.load_state(self.rdir_path, "create-pr", self.ticket)
        self.assertEqual(lib.last_invocation(state).get("status"), "completed")

    def test_the_lock_is_released_so_the_next_gate_is_not_refused(self):
        """The AttributeError escaped the GuardTimeout arm, so release_lock was
        never reached and every later gate refused with "crashed or still
        running elsewhere"."""
        self.post_pr("https://github.com/acme/shop/pull/7")
        self.assertFalse(os.path.exists(lib.lock_path(self.rdir_path)))

    def test_no_pr_number_is_recorded_for_a_reference_that_carries_none(self):
        self.post_pr("https://github.com/acme/shop/pull/7")
        self.assertEqual(self.metrics().get("prs", {}).get("created_pr_numbers"), [])

    def test_a_well_formed_reference_still_records_its_number(self):
        """The guard must not cost the working path its number."""
        self.post_pr({"number": 7, "url": "https://github.com/acme/shop/pull/7"})
        self.assertEqual(self.metrics().get("prs", {}).get("created_pr_numbers"), [7])

    def test_an_absent_pr_reference_is_still_silent(self):
        """None was already handled; the guard must not start warning about it."""
        out = self.start("create-pr", self.ticket)
        self.assertEqual(out.returncode, 0, out.stderr)
        out = self.post("create-pr", self.ticket, {"status": "completed"})
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertNotIn("states.pr", out.stderr)


if __name__ == "__main__":
    unittest.main()
