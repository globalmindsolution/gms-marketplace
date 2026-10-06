"""ADR-0137: `states.implemented` is derived, never asserted.

/acs:docs-sync flips each living LLD document whose gap notes mark it
`implemented-candidate` from `approved` to `implemented`
(`acs.py design status <doc>... --set implemented --by acs --reason ...`) and
lists the flipped paths in its result's `states.implemented`. The list is a
claim about documents on disk, so the post-hook reads each one's version front
matter and keeps only those that really say `status: implemented`. A path the
coordinator listed but did not flip is dropped and the disagreement recorded,
the same way `verifier_passed` and `tests` are treated (MAR-523).

Run:  python3 -m unittest tests.acs.test_docs_sync_implemented_states -v
"""

import json
import os
import sys
import tempfile
import shutil
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
sys.path.insert(0, SCRIPTS)

import acs_lib as lib  # noqa: E402
from acs_lib import design_docs as D  # noqa: E402

sys.path.insert(0, os.path.join(REPO_ROOT, "tests", "acs"))
from acs_case import AcsWorkspaceCase  # noqa: E402

DATA = "docs/architecture/lld/wishlist/data/logical-erd.md"
API = "docs/architecture/lld/wishlist/api/http.md"
FLOWS = "docs/architecture/lld/wishlist/flows/add-item.md"


def put(root, rel, status=None, body="# Doc\n"):
    """A design document at `root/rel`; `status=None` writes no front matter."""
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        if status is not None:
            fh.write("---\nstatus: %s\nversion: 2\ntickets: [\"SHOP-1\"]\n"
                     "feature: wishlist\n---\n" % status)
        fh.write(body)
    return path


class DeriveImplementedTest(unittest.TestCase):
    """The derivation itself: what the front matter says, not what was listed."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="acs-implemented-")
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_keeps_only_documents_whose_front_matter_reads_implemented(self):
        put(self.root, DATA, "implemented")
        put(self.root, API, "approved")
        put(self.root, FLOWS, None)
        kept, why = lib.derive_implemented([DATA, API, FLOWS, "docs/gone.md"], self.root)
        self.assertEqual(kept, [DATA])
        self.assertIn("1 of 4", why)
        for dropped in (API, FLOWS, "docs/gone.md"):
            self.assertIn(dropped, why)
        self.assertIn("approved", why)
        self.assertIn("no such file", why)

    def test_an_absolute_path_is_read_where_it_points_and_kept_as_written(self):
        path = put(self.root, DATA, "implemented")
        kept, _why = lib.derive_implemented([path], self.root)
        self.assertEqual(kept, [path])

    def test_a_duplicate_is_listed_once(self):
        put(self.root, DATA, "implemented")
        kept, _why = lib.derive_implemented([DATA, DATA], self.root)
        self.assertEqual(kept, [DATA])

    def test_front_matter_that_does_not_parse_is_dropped_not_fatal(self):
        put(self.root, DATA, None, body="---\nstatus: [unclosed\n---\n# Doc\n")
        kept, why = lib.derive_implemented([DATA], self.root)
        self.assertEqual(kept, [])
        self.assertIn(DATA, why)

    def test_a_non_list_claim_derives_an_empty_list(self):
        kept, why = lib.derive_implemented(DATA, self.root)
        self.assertEqual(kept, [])
        self.assertIn("not a list", why)

    def test_an_entry_that_is_not_a_path_is_dropped_and_named(self):
        put(self.root, DATA, "implemented")
        kept, why = lib.derive_implemented([None, "", DATA], self.root)
        self.assertEqual(kept, [DATA])
        self.assertIn("None (not a path)", why)

    def test_an_empty_list_is_agreed_with(self):
        kept, why = lib.derive_implemented([], self.root)
        self.assertEqual(kept, [])
        self.assertIn("0 of 0", why)

    def test_the_key_is_one_the_kernel_derives(self):
        self.assertIn("implemented", lib.DERIVED_KEYS)
        self.assertEqual(lib.IMPLEMENTED_SKILLS, ("docs-sync",))


class DeriveStatesWiringTest(unittest.TestCase):
    """derive_states only touches `implemented` for docs-sync, only when the
    result claims it, and leaves the claim alone when it cannot read the tree."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="acs-implemented-")
        self.addCleanup(shutil.rmtree, self.root, True)
        self.rdir = os.path.join(self.root, "run")
        os.makedirs(self.rdir)
        put(self.root, DATA, "implemented")
        put(self.root, API, "approved")

    def derive(self, skill, states, root):
        return lib.derive_states(self.rdir, skill, {"states": states}, root=root)

    def test_docs_sync_derives_the_flipped_documents(self):
        derived, notes = self.derive("docs-sync", {"implemented": [DATA, API]}, self.root)
        self.assertEqual(derived["implemented"], [DATA])
        self.assertIn(API, notes["implemented"])

    def test_no_claim_derives_no_key(self):
        derived, notes = self.derive("docs-sync", {"files": [DATA]}, self.root)
        self.assertNotIn("implemented", derived)
        self.assertNotIn("implemented", notes)

    def test_another_skill_s_key_of_that_name_is_not_touched(self):
        derived, notes = self.derive("code", {"implemented": [API]}, self.root)
        self.assertNotIn("implemented", derived)
        self.assertNotIn("implemented", notes)

    def test_without_a_checkout_root_the_claim_is_left_and_says_so(self):
        derived, notes = self.derive("docs-sync", {"implemented": [API]}, None)
        self.assertNotIn("implemented", derived)
        self.assertIn("no checkout", notes["implemented"])


class PostDocsSyncTest(AcsWorkspaceCase):
    """End to end through post-docs-sync.py, the hook the coordinator runs."""

    def setUp(self):
        super().setUp()
        self.ticket = self.new_ticket("Wishlist", "task")
        self.rdir_path = self.ensure_run(self.ticket)
        self.assertEqual(self.start("docs-sync", self.ticket).returncode, 0)

    def state(self):
        return lib.load_step_state(self.rdir_path, "docs-sync", self.ticket)

    def flip(self, *rels):
        out = self.run_script("acs.py", "design", "status", "--set", "implemented",
                              "--by", "acs", "--reason", "%s: the code matches" % self.ticket,
                              *rels)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def test_the_documented_flip_command_moves_every_candidate_at_once(self):
        """The coordinator's one call: approved -> implemented with who and why."""
        put(self.repo, DATA, "approved")
        put(self.repo, FLOWS, "approved")
        self.flip(DATA, FLOWS)
        for rel in (DATA, FLOWS):
            front, _body = D.read(os.path.join(self.repo, rel))
            self.assertEqual(front["status"], "implemented")
            self.assertEqual(front["status_by"], "acs")
            self.assertEqual(front["status_reason"], "%s: the code matches" % self.ticket)
            self.assertTrue(front["status_at"])

    def test_a_proposed_document_cannot_be_flipped_and_nothing_moves(self):
        """proposed -> implemented is not a legal move, and the batch is atomic:
        a candidate list carrying one is refused whole."""
        put(self.repo, DATA, "approved")
        put(self.repo, API, "proposed")
        out = self.run_script("acs.py", "design", "status", "--set", "implemented",
                              "--by", "acs", DATA, API)
        self.assertEqual(out.returncode, 2, out.stdout)
        self.assertEqual(D.read(os.path.join(self.repo, DATA))[0]["status"], "approved")

    def test_listed_but_not_flipped_is_dropped_and_recorded(self):
        put(self.repo, DATA, "approved")
        put(self.repo, API, "approved")
        self.flip(DATA)
        out = self.post("docs-sync", self.ticket, {
            "status": "completed",
            "states": {"files": [DATA], "implemented": [DATA, API]}})
        self.assertEqual(out.returncode, 0, out.stderr)
        state = self.state()
        self.assertEqual(state["states"]["implemented"], [DATA])
        self.assertEqual(state["states"]["files"], [DATA])
        entry = lib.last_invocation(state)
        self.assertEqual(entry["derived_states"]["overrode"],
                         [{"key": "implemented", "supplied": [DATA, API], "derived": [DATA]}])
        self.assertIn("states.implemented was", out.stderr)

    def test_an_honest_list_is_kept_without_a_disagreement(self):
        put(self.repo, DATA, "approved")
        self.flip(DATA)
        out = self.post("docs-sync", self.ticket, {
            "status": "completed", "states": {"implemented": [DATA]}})
        self.assertEqual(out.returncode, 0, out.stderr)
        state = self.state()
        self.assertEqual(state["states"]["implemented"], [DATA])
        self.assertEqual(lib.last_invocation(state)["derived_states"]["overrode"], [])

    def test_a_run_that_flipped_nothing_carries_no_key(self):
        out = self.post("docs-sync", self.ticket, {"status": "completed",
                                                   "states": {"files": []}})
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertNotIn("implemented", self.state()["states"])


class PostHookDocstringTest(unittest.TestCase):
    def test_post_docs_sync_names_the_derived_implemented_key(self):
        with open(os.path.join(SCRIPTS, "post-docs-sync.py"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("states.implemented", text)
        self.assertIn("status: implemented", text)


if __name__ == "__main__":
    unittest.main()
