"""`acs step start --ticket <id>` resolves the subject it was given.

Two defects, one cause: the run-keyed rewrite (ADR-0097) routed every `acs
run` / `acs step` verb through THIS CHECKOUT'S CURRENT RUN, read from
`sessions/<checkout-id>/pointer.json`. That default is right -- nobody should
have to type a run id (§4.9) -- but it became the ONLY resolution, so a caller
who had named the subject explicitly was still refused when the pointer was
empty:

    acs step start: no current run for this checkout, and no --run given.

which is false: they said `--ticket SHOP-1`. It is also exactly the case the
standalone rule exists for -- "every skill must work independently with a
ticket id, a prompt or a document as input" (§3.11) -- since a fresh checkout
invoking `/acs:code SHOP-1` by hand has never pointed anywhere.

The deterministic suite did not catch it because `tests/acs/acs_case.py`'s
`start()` calls `ensure_run()` first, creating the run the way a pre-hook
would. The behavioural eval, which drives the real CLI with no such
shortcut, did. These tests take the eval's path: no run is created for them.

The second half is the guard that comes with it. A `<PREFIX>-<n>` token is a
REFERENCE, unlike a prompt or a document, which carry their own content -- so
a run minted over a reference to nothing has a subject that cannot be read,
and the failure surfaces several steps later at whichever step first needs
`ticket.json`. Both the CLI and the PreToolUse gate now refuse it up front,
naming the skill that makes one.

Run: python3 -m unittest tests.acs.test_step_start_names_its_subject -v
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import acs_case  # noqa: E402
from acs_case import lib  # noqa: E402


class StepStartResolvesAnExplicitTicketTest(acs_case.AcsWorkspaceCase):
    """`--ticket` names the subject, on a checkout with no pointer at all."""

    def _runs_root(self):
        return os.path.join(lib.repo_dir(self.ws, "acme-shop"), "runs")

    def _clear_pointer(self):
        """A checkout that has never run anything. `new-ticket.py` may leave a
        pointer behind; removing it is what makes this the FIRST invocation."""
        repo = lib.repo_dir(self.ws, "acme-shop")
        path = lib.pointer_path(self.ws, "acme-shop", lib.checkout_id(self.repo))
        if os.path.isfile(path):
            os.remove(path)
        return repo

    def test_it_creates_the_run_for_the_named_ticket(self):
        tid = self.new_ticket("Add a /health endpoint", "task")
        self._clear_pointer()
        out = self.run_script("acs.py", "step", "start", "--step", "code",
                              "--ticket", tid)
        self.assertEqual(out.returncode, 0, out.stderr)
        doc = json.loads(out.stdout)
        self.assertEqual(doc["run_id"], tid,
                         "the run id for a ticket subject IS the ticket id")
        self.assertTrue(os.path.isfile(lib.run_path(self.rdir(tid))))

    def test_the_step_is_in_progress_afterwards(self):
        tid = self.new_ticket("Add a /health endpoint", "task")
        self._clear_pointer()
        self.run_script("acs.py", "step", "start", "--step", "code", "--ticket", tid)
        state = lib.read_json(lib.step_state_path(self.rdir(tid), "code"))
        self.assertEqual(state["invocations"][-1]["status"], "in_progress")

    def test_the_checkout_pointer_follows_the_named_subject(self):
        """Naming a subject explicitly MOVES this checkout to it -- otherwise
        the next verb, which defaults to the pointer, would act on whatever
        the checkout last touched instead."""
        tid = self.new_ticket("Add a /health endpoint", "task")
        self._clear_pointer()
        self.run_script("acs.py", "step", "start", "--step", "code", "--ticket", tid)
        with open(lib.pointer_path(self.ws, "acme-shop",
                                   lib.checkout_id(self.repo))) as fh:
            self.assertEqual(json.load(fh)["run_id"], tid)

    def test_it_is_idempotent_across_two_invocations(self):
        """A resumed session runs the same command again; it must find its own
        run rather than mint a second one."""
        tid = self.new_ticket("Add a /health endpoint", "task")
        self._clear_pointer()
        first = self.run_script("acs.py", "step", "start", "--step", "code",
                                "--ticket", tid)
        self.assertEqual(first.returncode, 0, first.stderr)
        second = self.run_script("acs.py", "step", "start", "--step", "code",
                                 "--ticket", tid)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(os.listdir(self._runs_root()), [tid])

    def test_an_unknown_ticket_is_refused_not_given_a_run(self):
        """A reference to nothing is refused where the message can still name
        the skill that makes one -- never minted into a run whose subject
        cannot be read."""
        self._clear_pointer()
        out = self.run_script("acs.py", "step", "start", "--step", "code",
                              "--ticket", "SHOP-404")
        self.assertEqual(out.returncode, 2, out.stdout)
        self.assertIn("SHOP-404", out.stderr)
        self.assertNotIn("Traceback", out.stderr)
        self.assertFalse(os.path.isdir(self.rdir("SHOP-404")))

    def test_an_empty_checkout_with_no_ticket_still_says_so(self):
        """The pointer-default message stays for the case it was written for:
        no subject named, nothing to fall back on."""
        self._clear_pointer()
        out = self.run_script("acs.py", "step", "start", "--step", "code")
        self.assertEqual(out.returncode, 2, out.stdout)
        self.assertIn("no current run", out.stderr)


class GateRefusesATicketSubjectThatDoesNotExistTest(acs_case.AcsWorkspaceCase):
    """The same guard on the PreToolUse path, which is where a real
    `/acs:code SHOP-404` arrives."""

    def test_the_gate_names_create_ticket(self):
        out = self.pre("code", "SHOP-404")
        self.assertEqual(out.returncode, 2, out.stdout)
        self.assertIn("create-ticket", out.stderr)
        self.assertFalse(os.path.isdir(self.rdir("SHOP-404")))

    def test_a_prompt_subject_is_untouched_by_the_guard(self):
        """Only a ticket id is a reference. A prompt carries its own content,
        so a run over one is self-describing and must still be created."""
        out = self.pre("code", "fix the login timeout on slow networks")
        self.assertEqual(out.returncode, 0, out.stderr)
        runs = os.path.join(lib.repo_dir(self.ws, "acme-shop"), "runs")
        self.assertTrue(os.path.isdir(runs) and os.listdir(runs))


if __name__ == "__main__":
    unittest.main()
