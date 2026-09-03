"""--allocate mints a ticket only when the run is not resuming one.

MAR-509. /acs:ship re-invokes an interrupted create-ticket with the ticket id
as its args; allocating again there minted a second ticket for the same work.

Reuse is deliberately narrow, and the narrowness is the safety property: an
--allocate run adopting the wrong partition writes one flow's state into
another's ticket. Three ways that can happen, one test each below --
the session pointer (a doc-bootstrap fan-out runs two legs at once, neither
passing an id), free text that merely CITES a live id, and a product-level
skill picking up a delivery ticket it never owned.

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



    def test_free_text_that_only_cites_a_live_id_still_mints_a_new_one(self):
        """create-ticket is invoked with the user's prompt verbatim as --args
        (create-ticket/SKILL.md; ship/SKILL.md). ticket_id_from_text is a
        re.search, so a prompt that mentions an existing ticket would resolve
        to it -- and only when that ticket is live, i.e. exactly when adopting
        it overwrites active work."""
        first = self.run_script("skill-start.py", "--skill", "create-ticket",
                                "--allocate", "--args", "add a wishlist API")
        self.assertEqual(first.returncode, 0, first.stderr)
        existing = json.loads(first.stdout)["ticket_id"]
        lib.release_lock(lib.ticket_dir(self.ws, lib.build_context(self.repo)["repo_id"], existing))

        second = self.run_script(
            "skill-start.py", "--skill", "create-ticket", "--allocate",
            "--args", "follow-up to %s: also handle the archived case" % existing)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertNotEqual(json.loads(second.stdout)["ticket_id"], existing,
                            "a prompt citing a ticket adopted that ticket's partition")
        self.assertEqual(len(self._ids()), 2)

    def test_a_product_leg_never_derives_its_ticket_from_args(self):
        """The six product-level skills each route resume through a separate
        --ticket call with no --allocate, so args-derived reuse buys them
        nothing -- and would let a delivery ticket be adopted by a flow that
        never owned it."""
        first = self.run_script("skill-start.py", "--skill", "create-ticket",
                                "--allocate", "--args", "add a wishlist API")
        self.assertEqual(first.returncode, 0, first.stderr)
        delivery = json.loads(first.stdout)["ticket_id"]
        lib.release_lock(lib.ticket_dir(self.ws, lib.build_context(self.repo)["repo_id"], delivery))

        leg = self.run_script("skill-start.py", "--skill", "create-quality",
                              "--allocate", "--args", delivery)
        self.assertEqual(leg.returncode, 0, leg.stderr)
        self.assertNotEqual(json.loads(leg.stdout)["ticket_id"], delivery,
                            "a product-level leg adopted a delivery ticket")

    def test_an_explicit_ticket_flag_still_resumes_for_any_skill(self):
        """The narrowing is on --args only: --ticket is unambiguous by
        construction and stays the supported resume path everywhere."""
        first = self.run_script("skill-start.py", "--skill", "create-quality", "--allocate")
        self.assertEqual(first.returncode, 0, first.stderr)
        leg = json.loads(first.stdout)["ticket_id"]
        lib.release_lock(lib.ticket_dir(self.ws, lib.build_context(self.repo)["repo_id"], leg))

        again = self.run_script("skill-start.py", "--skill", "create-quality",
                                "--allocate", "--ticket", leg)
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(json.loads(again.stdout)["ticket_id"], leg)
        self.assertEqual(self._ids(), [leg])


if __name__ == "__main__":
    unittest.main()
