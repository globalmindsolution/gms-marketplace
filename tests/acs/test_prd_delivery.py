"""ADR-0146: a feature PRD's `implemented` status is derived from its tickets.

`acs_lib.prd_delivery` reads which tickets name each requirement `<slug>/R<n>`
and whether they are done; `acs.py prd status` reports it; `acs.py design
list` carries it beside each feature PRD; `acs.py design status --set
implemented` refuses a feature PRD its tickets do not bear out.

Run:  python3 -m unittest tests.acs.test_prd_delivery -v
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import AcsWorkspaceCase, SCRIPTS, lib, write_prd  # noqa: E402

sys.path.insert(0, SCRIPTS)
from acs_lib import prd_delivery  # noqa: E402

FEATURE = "docs/product/features/wishlist/prd.md"


class DeriveTest(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="acs-delivery-")
        self.addCleanup(shutil.rmtree, self.root, True)
        write_prd(self.root, features=("wishlist", "checkout"))

    def derive(self, index, merged=(), feature="wishlist"):
        return prd_delivery.derive_feature(self.root, feature, index, set(merged))

    def test_the_features_are_the_feature_prds(self):
        self.assertEqual(prd_delivery.feature_slugs(self.root), ["checkout", "wishlist"])
        self.assertEqual(prd_delivery.feature_of(self.root, FEATURE), "wishlist")
        self.assertIsNone(prd_delivery.feature_of(self.root, "docs/product/prd.md"))

    def test_no_ticket_is_uncovered(self):
        found = self.derive({})
        self.assertEqual(found["delivery"], "uncovered")
        self.assertEqual([r["state"] for r in found["requirements"]], ["uncovered"] * 2)

    def test_every_requirement_done_is_implemented(self):
        index = {"S-1": {"status": "done", "requirements": ["wishlist/R1"]},
                 "S-2": {"status": "open", "requirements": ["wishlist/R2"]}}
        self.assertEqual(self.derive(index)["delivery"], "in progress")
        self.assertEqual(self.derive(index, merged=["S-2"])["delivery"], "implemented")

    def test_an_open_ticket_on_a_delivered_requirement_reopens_it(self):
        index = {"S-1": {"status": "done", "requirements": ["wishlist/R1", "wishlist/R2"]},
                 "B-1": {"status": "open", "requirements": ["wishlist/R2"]}}
        found = self.derive(index)
        self.assertEqual(found["delivery"], "in progress")
        self.assertEqual(found["requirements"][1],
                         {"id": "wishlist/R2", "state": "in progress",
                          "tickets": {"B-1": "open", "S-1": "done"}})

    def test_planned_and_partly_uncovered(self):
        self.assertEqual(prd_delivery.feature_state(["planned", "planned"]), "planned")
        self.assertEqual(prd_delivery.feature_state(["planned", "uncovered"]), "uncovered")
        self.assertEqual(prd_delivery.feature_state([]), "uncovered")

    def test_agreement_with_the_document_status(self):
        done = {"S-1": {"status": "done", "requirements": ["wishlist/R1", "wishlist/R2"]}}
        path = os.path.join(self.root, FEATURE)
        with open(path, encoding="utf-8") as fh:
            body = fh.read()
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("---\nstatus: approved\nversion: 1\n---\n" + body)
        self.assertEqual(self.derive(done)["agreement"], "ready")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("---\nstatus: implemented\nversion: 1\n---\n" + body)
        self.assertEqual(self.derive({})["agreement"], "drift")
        self.assertEqual(self.derive(done)["agreement"], "consistent")

    def test_other_features_tickets_do_not_count(self):
        index = {"S-1": {"status": "done", "requirements": ["checkout/R1", "checkout/R2"],
                         "features": ["checkout"]}}
        self.assertEqual(self.derive(index)["delivery"], "uncovered")
        self.assertEqual(self.derive(index, feature="checkout")["delivery"], "implemented")


class CliTest(AcsWorkspaceCase):

    def setUp(self):
        super().setUp()
        self.write_prd(features=("wishlist",))
        out = self.run_script("acs.py", "design", "init", "--status", "approved",
                              "docs/product/prd.md", FEATURE)
        self.assertEqual(out.returncode, 0, out.stderr)

    def story(self, *requirements, status=None):
        tid = self.new_ticket("Wishlist", "story", "--features", "wishlist",
                              "--requirements", ",".join(requirements))
        if status:
            ticket = lib.load_ticket(self.tdir(tid))
            lib.update_index(self.ws, "acme-shop", dict(ticket, status=status))
        return tid

    def prd_status(self, *args):
        out = self.run_script("acs.py", "prd", "status", "--no-git", *args)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def implement(self, *extra):
        return self.run_script("acs.py", "design", "status", "--set", "implemented",
                               *extra, FEATURE)

    def test_status_reports_ready_once_every_requirement_is_done(self):
        self.story("wishlist/R1", "wishlist/R2", status="in_progress")
        doc = self.prd_status()
        self.assertEqual(doc["features"][0]["delivery"], "in progress")
        self.assertEqual(doc["ready"], [])
        self.story("wishlist/R1", "wishlist/R2", status="done")
        tid = sorted(lib.read_json(lib.index_path(self.ws, "acme-shop"))["tickets"])[0]
        ticket = lib.load_ticket(self.tdir(tid))
        lib.update_index(self.ws, "acme-shop", dict(ticket, status="done"))
        self.assertEqual(self.prd_status("--feature", "wishlist")["ready"], ["wishlist"])

    def test_status_refuses_without_a_prd_or_feature(self):
        out = self.run_script("acs.py", "prd", "status", "--feature", "nope")
        self.assertEqual(out.returncode, 2)
        self.assertIn("no PRD of its own", out.stderr)
        shutil.rmtree(os.path.join(self.repo, "docs"))
        out = self.run_script("acs.py", "prd", "status")
        self.assertEqual(out.returncode, 2)
        self.assertIn("/acs:create-prd", out.stderr)

    def test_design_list_carries_the_delivery(self):
        self.story("wishlist/R1", status="done")
        out = self.run_script("acs.py", "design", "list", "--phase", "discovery")
        self.assertEqual(out.returncode, 0, out.stderr)
        docs = [d for g in json.loads(out.stdout)["groups"] for d in g["docs"]]
        feature = [d for d in docs if d["path"] == FEATURE][0]
        self.assertEqual(feature["delivery"], {"state": "in progress",
                                               "agreement": "consistent",
                                               "open": ["wishlist/R2"]})
        hub = [d for d in docs if d["path"] == "docs/product/prd.md"][0]
        self.assertNotIn("delivery", hub)

    def test_implemented_is_refused_until_delivered(self):
        self.story("wishlist/R1", status="done")
        out = self.implement()
        self.assertEqual(out.returncode, 2)
        self.assertIn("wishlist/R2 uncovered", out.stderr)
        self.assertIn("ADR-0146", out.stderr)
        self.story("wishlist/R2", status="done")
        out = self.implement()
        self.assertEqual(out.returncode, 0, out.stderr)

    def test_an_override_needs_a_reason(self):
        out = self.implement("--override-delivery")
        self.assertEqual(out.returncode, 2)
        self.assertIn("needs --reason", out.stderr)
        out = self.implement("--override-delivery", "--reason", "shipped before acs")
        self.assertEqual(out.returncode, 0, out.stderr)
        with open(os.path.join(self.repo, FEATURE), encoding="utf-8") as fh:
            self.assertIn('status_reason: "shipped before acs"', fh.read())

    def test_other_moves_and_documents_are_not_gated(self):
        out = self.run_script("acs.py", "design", "status", "--set", "proposed", FEATURE)
        self.assertEqual(out.returncode, 0, out.stderr)

    def test_merged_on_the_default_branch_counts(self):
        tid = self.story("wishlist/R1", "wishlist/R2")
        subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "%s Wishlist" % tid],
                       cwd=self.repo, check=True, capture_output=True)
        out = self.run_script("acs.py", "prd", "status")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout)["features"][0]["delivery"], "implemented")


if __name__ == "__main__":
    unittest.main()
