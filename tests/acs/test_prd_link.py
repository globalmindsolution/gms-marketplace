"""ADR-0144: tickets are made from the PRD and link it.

`acs_lib.prd_link` judges a proposed link (features, `<slug>/R<n>`
requirements) against the repo's PRD; /acs:create-ticket and
/acs:breakdown-ticket refuse a repo with no PRD; `new-ticket.py
--require-prd-link`, `acs.py ticket link-check` and `acs.py ticket save` hold
the link to what the PRD says.

Run:  python3 -m unittest tests.acs.test_prd_link -v
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import AcsWorkspaceCase, lib, write_prd  # noqa: E402

prd_link = lib.prd_link


class ParseTest(unittest.TestCase):

    def test_ids_are_parsed_in_order_once(self):
        self.assertEqual(prd_link.parse_requirements("a/R1, b-c/R12, a/R1"),
                         ["a/R1", "b-c/R12"])
        self.assertEqual(prd_link.parse_requirements(""), [])
        self.assertEqual(prd_link.parse_requirements(None), [])

    def test_a_malformed_id_is_refused(self):
        for bad in ("R1", "a/r1", "A/R1", "a/R", "a/R1/x", "a R1"):
            with self.subTest(bad=bad), self.assertRaises(lib.GateError):
                prd_link.parse_requirements(bad)


class CheckLinkTest(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="prd-link-")
        self.addCleanup(shutil.rmtree, self.root, True)
        write_prd(self.root, features=("wishlist", "checkout"))

    def check(self, ttype, features, requirements=()):
        return prd_link.check_link(self.root, ttype, features, requirements)

    def test_a_sound_link_has_no_problems(self):
        self.assertEqual(self.check("story", ["wishlist"], ["wishlist/R1"]), [])
        for ttype in ("epic", "task", "bug"):
            self.assertEqual(self.check(ttype, ["wishlist", "checkout"]), [], ttype)

    def test_no_prd_is_the_one_problem(self):
        shutil.rmtree(os.path.join(self.root, "docs"))
        self.assertEqual(self.check("story", ["wishlist"], ["wishlist/R1"]), [prd_link.NO_PRD])
        self.assertIsNone(prd_link.prd_path(self.root))
        with self.assertRaises(lib.GateError):
            prd_link.require_prd(self.root)
        self.assertIsNone(prd_link.prd_path(None))

    def test_every_type_links_a_feature(self):
        for ttype in ("epic", "story", "task", "bug"):
            self.assertTrue(any("at least one PRD feature" in p for p in self.check(ttype, [])),
                            ttype)

    def test_a_story_names_a_requirement(self):
        problems = self.check("story", ["wishlist"])
        self.assertEqual(len(problems), 1)
        self.assertIn("wishlist/R1", problems[0])

    def test_a_feature_without_its_own_prd(self):
        problems = self.check("task", ["loyalty"])
        self.assertEqual(len(problems), 1)
        self.assertIn("'loyalty' has no PRD of its own", problems[0])

    def test_a_deprecated_feature_takes_no_new_ticket(self):
        path = os.path.join(self.root, "docs", "product", "features", "checkout", "prd.md")
        with open(path, encoding="utf-8") as fh:
            body = fh.read()
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("---\nstatus: deprecated\nversion: 2\ntickets: []\n---\n\n" + body)
        self.assertEqual(self.check("task", ["checkout"]),
                         ["feature 'checkout' is deprecated; a new ticket cannot link it"])

    def test_a_requirement_must_be_real_and_of_a_linked_feature(self):
        problems = self.check("story", ["wishlist"], ["wishlist/R9", "checkout/R1", "bad"])
        self.assertEqual(len(problems), 3)
        self.assertIn("wishlist/R9 is not in wishlist's PRD (it declares: R1, R2)", problems[0])
        self.assertIn("names feature 'checkout', which the ticket does not link", problems[1])
        self.assertIn("'bad' is not", problems[2])

    def test_requirements_are_read_from_their_section_only(self):
        text = ("# F\n\n## Summary\n\n- **R7** — not a requirement here\n\n"
                "## Requirements\n\n- **R1** — one\n* **R2** — two\n\n## Out of scope\n\n- **R3** x\n")
        self.assertEqual(prd_link.feature_requirements(text), ["R1", "R2"])

    def test_ensure_link_raises_every_problem(self):
        with self.assertRaises(lib.GateError) as caught:
            prd_link.ensure_link(self.root, "story", [])
        self.assertIn("not sound", str(caught.exception))
        prd_link.ensure_link(self.root, "story", ["wishlist"], ["wishlist/R2"])


class CliTest(AcsWorkspaceCase):

    def setUp(self):
        super().setUp()
        self.write_prd()

    def link_check(self, *args):
        return self.run_script("acs.py", "ticket", "link-check", *args)

    def test_link_check_reports_ok(self):
        out = self.link_check("--type", "story", "--features", "wishlist",
                              "--requirements", "wishlist/R1")
        self.assertEqual(out.returncode, 0, out.stderr)
        doc = json.loads(out.stdout)
        self.assertEqual((doc["ok"], doc["problems"]), (True, []))

    def test_link_check_lists_problems_and_exits_one(self):
        out = self.link_check("--type", "story", "--features", "wishlist")
        self.assertEqual(out.returncode, 1)
        self.assertFalse(json.loads(out.stdout)["ok"])
        self.assertEqual(self.link_check("--type", "story", "--requirements", "x").returncode, 2)

    def test_new_ticket_with_require_prd_link(self):
        refused = self.run_script("new-ticket.py", "--title", "Save", "--type", "story",
                                  "--features", "wishlist", "--require-prd-link")
        self.assertEqual(refused.returncode, 2)
        self.assertIn("No ticket id was minted", refused.stderr)
        minted = self.run_script("new-ticket.py", "--title", "Save", "--type", "story",
                                 "--features", "wishlist", "--requirements", "wishlist/R1",
                                 "--require-prd-link")
        self.assertEqual(minted.returncode, 0, minted.stderr)
        doc = json.loads(minted.stdout)
        self.assertEqual(doc["requirements"], ["wishlist/R1"])
        ticket = lib.load_ticket(self.tdir(doc["ticket_id"]))
        self.assertEqual(ticket["requirements"], ["wishlist/R1"])
        index = lib.read_json(lib.index_path(self.ws, "acme-shop"))
        self.assertEqual(index["tickets"][doc["ticket_id"]]["requirements"], ["wishlist/R1"])

    def test_a_given_requirement_is_always_checked(self):
        out = self.run_script("new-ticket.py", "--title", "Save", "--type", "task",
                              "--features", "wishlist", "--requirements", "wishlist/R9")
        self.assertEqual(out.returncode, 2)
        self.assertIn("wishlist/R9", out.stderr)
        bad = self.run_script("new-ticket.py", "--title", "Save", "--type", "task",
                              "--requirements", "R9")
        self.assertEqual(bad.returncode, 2)

    def test_without_the_flag_a_regression_bug_needs_no_link(self):
        out = self.run_script("new-ticket.py", "--title", "Suite red", "--type", "bug")
        self.assertEqual(out.returncode, 0, out.stderr)

    def test_ticket_save_holds_a_requirements_patch_to_the_prd(self):
        tid = self.new_ticket("Save", "task", "--features", "wishlist")
        bad = self.run_script("acs.py", "ticket", "save", "--ticket", tid, "--from", "-",
                              stdin=json.dumps({"requirements": ["wishlist/R9"]}))
        self.assertEqual(bad.returncode, 2)
        self.assertIn("wishlist/R9", bad.stderr)
        good = self.run_script("acs.py", "ticket", "save", "--ticket", tid, "--from", "-",
                               stdin=json.dumps({"requirements": ["wishlist/R2"]}))
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertEqual(lib.load_ticket(self.tdir(tid))["requirements"], ["wishlist/R2"])


class CreateTicketPostHookTest(AcsWorkspaceCase):
    """A completed create-ticket run whose ticket does not link the PRD is refused."""

    def run_create_ticket(self, patch):
        self.write_prd()
        start = self.run_script("acs.py", "step", "start", "--step", "create-ticket",
                                "--allocate", "--type", "task", "--title", "(draft)")
        self.assertEqual(start.returncode, 0, start.stderr)
        tid = json.loads(start.stdout)["ticket_id"]
        saved = self.run_script("acs.py", "ticket", "save", "--ticket", tid, "--from", "-",
                                stdin=json.dumps(patch))
        self.assertEqual(saved.returncode, 0, saved.stderr)
        return tid, self.post("create-ticket", tid, {
            "status": "completed", "summary": "story created",
            "states": {"ticket_id": tid, "type": patch.get("type", "task"), "children": [],
                       "prd_trace": {"feature": "wishlist", "divergence": None}}})

    def test_an_unlinked_story_is_refused(self):
        _tid, post = self.run_create_ticket({"type": "story", "title": "Save"})
        self.assertEqual(post.returncode, 1)
        self.assertIn("does not link the PRD", post.stderr)

    def test_a_linked_story_completes(self):
        _tid, post = self.run_create_ticket({"type": "story", "title": "Save",
                                             "features": ["wishlist"],
                                             "requirements": ["wishlist/R1"]})
        self.assertEqual(post.returncode, 0, post.stderr)


class CreateTicketGateTest(AcsWorkspaceCase):

    def test_no_prd_refuses_create_ticket(self):
        out = self.pre("create-ticket", "Add a wishlist")
        self.assertEqual(out.returncode, 2)
        self.assertIn("/acs:create-prd", out.stderr)

    def test_a_prd_lets_it_start(self):
        self.write_prd()
        out = self.pre("create-ticket", "Add a wishlist")
        self.assertEqual(out.returncode, 0, out.stderr)


if __name__ == "__main__":
    unittest.main()
