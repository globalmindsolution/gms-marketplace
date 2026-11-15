"""--allocate mints a ticket only when the run is not resuming one.

MAR-509. /acs:ship re-invokes an interrupted create-ticket with the ticket id
as its args; allocating again there minted a second ticket for the same work.

Reuse is deliberately narrow, and the narrowness is the safety property: an
--allocate run adopting the wrong partition writes one flow's state into
another's ticket. Three ways that can happen, one test each below --
the session pointer, free text that merely CITES a live id, and a
product-level skill picking up a ticket it never owned (since ADR-0127 a
product skill may not --allocate at all).

Run:  python3 -m unittest tests.acs.test_allocate_only_when_absent -v
"""

import json
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import acs_lib as lib  # noqa: E402
from acs_case import AcsWorkspaceCase  # noqa: E402


class AllocateOnlyWhenAbsentTest(AcsWorkspaceCase):
    """--allocate must not mint a second ticket for work that already has one
    (MAR-509), and must not let one product-level leg adopt another's ticket."""

    def _release(self, ticket_id):
        """The lock is the RUN's (§4.5), and `acs step start --allocate` takes
        it over the run it just minted. A second start from the same checkout
        is a no-op re-acquire, but a fixture standing in for a LATER session
        has to put it down the way SessionEnd would."""
        lib.release_lock(self.rdir(ticket_id))

    def _ids(self):
        index = lib.read_json(lib.index_path(self.ws, lib.build_context(self.repo)["repo_id"]))
        return sorted((index or {}).get("tickets", {}))

    def test_fresh_run_allocates(self):
        result = self.run_script("acs.py", "step", "start", "--step", "create-ticket",
                                 "--allocate", "--args", "add a wishlist API")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self._ids()), 1)

    def test_resume_with_the_id_in_args_reuses_the_partition(self):
        first = self.run_script("acs.py", "step", "start", "--step", "create-ticket",
                                "--allocate", "--args", "add a wishlist API")
        self.assertEqual(first.returncode, 0, first.stderr)
        ticket_id = json.loads(first.stdout)["ticket_id"]
        self._release(ticket_id)

        again = self.run_script("acs.py", "step", "start", "--step", "create-ticket",
                                "--allocate", "--args", ticket_id)
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(json.loads(again.stdout)["ticket_id"], ticket_id)
        self.assertEqual(self._ids(), [ticket_id])

    def test_a_product_skill_can_no_longer_allocate(self):
        """ADR-0127: create-prd and create-architecture mint no delivery
        ticket -- they run ticketless, and /acs:create-pr commits their documents."""
        for step in ("create-prd", "create-architecture"):
            with self.subTest(step=step):
                out = self.run_script("acs.py", "step", "start", "--step", step, "--allocate")
                self.assertEqual(out.returncode, 2, out.stdout)
                self.assertIn("ADR-0127", out.stderr)
        self.assertEqual(self._ids(), [])

    def test_free_text_that_only_cites_a_live_id_still_mints_a_new_one(self):
        """create-ticket is invoked with the user's prompt verbatim as --args
        (create-ticket/SKILL.md; ship/SKILL.md). ticket_id_from_text is a
        re.search, so a prompt that mentions an existing ticket would resolve
        to it -- and only when that ticket is live, i.e. exactly when adopting
        it overwrites active work."""
        first = self.run_script("acs.py", "step", "start", "--step", "create-ticket",
                                "--allocate", "--args", "add a wishlist API")
        self.assertEqual(first.returncode, 0, first.stderr)
        existing = json.loads(first.stdout)["ticket_id"]
        self._release(existing)

        second = self.run_script(
            "acs.py", "step", "start", "--step", "create-ticket", "--allocate",
            "--args", "follow-up to %s: also handle the archived case" % existing)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertNotEqual(json.loads(second.stdout)["ticket_id"], existing,
                            "a prompt citing a ticket adopted that ticket's partition")
        self.assertEqual(len(self._ids()), 2)

    def test_a_product_skill_never_adopts_a_ticket_from_args(self):
        """A product skill handed a live ticket id is refused --allocate rather
        than adopting a ticket it never owned."""
        first = self.run_script("acs.py", "step", "start", "--step", "create-ticket",
                                "--allocate", "--args", "add a wishlist API")
        self.assertEqual(first.returncode, 0, first.stderr)
        delivery = json.loads(first.stdout)["ticket_id"]
        self._release(delivery)

        leg = self.run_script("acs.py", "step", "start", "--step", "create-architecture",
                              "--allocate", "--args", delivery)
        self.assertEqual(leg.returncode, 2, leg.stdout)
        self.assertEqual(self._ids(), [delivery])

    def test_seed_next_on_a_resuming_run_is_refused(self):
        """MAR-402's --seed-next repairs the counter for a newly minted id. A
        resume mints nothing, so combining the two would silently ignore the
        seed -- refuse instead of swallowing it."""
        first = self.run_script("acs.py", "step", "start", "--step", "create-ticket",
                                "--allocate", "--args", "add a wishlist API")
        self.assertEqual(first.returncode, 0, first.stderr)
        ticket_id = json.loads(first.stdout)["ticket_id"]
        self._release(ticket_id)

        again = self.run_script("acs.py", "step", "start", "--step", "create-ticket",
                                "--allocate", "--ticket", ticket_id, "--seed-next", "42")
        self.assertEqual(again.returncode, 2, again.stdout)
        self.assertIn("--seed-next", again.stderr)
        self.assertIn(ticket_id, again.stderr)

    def test_an_explicit_ticket_flag_still_resumes(self):
        """The narrowing is on --args only: --ticket is unambiguous by
        construction and stays the supported resume path."""
        first = self.run_script("acs.py", "step", "start", "--step", "create-ticket",
                                "--allocate")
        self.assertEqual(first.returncode, 0, first.stderr)
        minted = json.loads(first.stdout)["ticket_id"]
        self._release(minted)

        again = self.run_script("acs.py", "step", "start", "--step", "create-ticket",
                                "--allocate", "--ticket", minted)
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(json.loads(again.stdout)["ticket_id"], minted)
        self.assertEqual(self._ids(), [minted])


if __name__ == "__main__":
    unittest.main()
