"""ADR-0145: the roadmap document, its derived delivery status and its floor.

`acs_lib.roadmap` parses the milestones and the Release versions table and
derives each milestone's status from the tickets it tracks; `acs.py roadmap
status` reports and writes it; `roadmap_check.py` holds the document to its
shape and to the PRD hub's Features index.

Run:  python3 -m unittest tests.acs.test_roadmap -v
"""

import contextlib
import io
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
import roadmap_check  # noqa: E402
from acs_lib import roadmap  # noqa: E402

ROADMAP = """---
status: proposed
version: 1
tickets: []
---

# Roadmap — shop

## Milestones

### M1 Wishlist — v0.1.0

- Status: planned
- Features: [Wishlist](features/wishlist/prd.md)
- Epics: SHOP-1
- Target: 2027-03-31

Shoppers can keep products for later.

### M2 Checkout — v0.2.0

- Status: planned
- Features: [Checkout](features/checkout/prd.md)
- Epics: none yet

Card checkout.

## Release versions

| Version | Milestone | Epics | Status |
|---|---|---|---|
| v0.1.0 | M1 Wishlist | SHOP-1 | planned |
| v0.2.0 | M2 Checkout | — | planned |
"""


class ParseAndDeriveTest(unittest.TestCase):

    def test_parse(self):
        parsed = roadmap.parse(ROADMAP)
        self.assertEqual([(m["name"], m["version"], m["status"]) for m in parsed["milestones"]],
                         [("M1 Wishlist", "0.1.0", "planned"), ("M2 Checkout", "0.2.0", "planned")])
        m1 = parsed["milestones"][0]
        self.assertEqual((m1["features"], m1["epics"], m1["target"]),
                         (["wishlist"], ["SHOP-1"], "2027-03-31"))
        self.assertEqual([(r["version"], r["milestone"], r["status"]) for r in parsed["versions"]],
                         [("0.1.0", "M1 Wishlist", "planned"), ("0.2.0", "M2 Checkout", "planned")])
        self.assertTrue(all(h["versioned"] for h in parsed["headings"]))

    def test_status_follows_the_tracked_tickets(self):
        index = {"SHOP-1": {"status": "done"}, "SHOP-2": {"status": "open", "features": ["wishlist"]}}
        self.assertEqual(roadmap.status_of([], index), "planned")
        self.assertEqual(roadmap.status_of(["SHOP-2"], index), "planned")
        self.assertEqual(roadmap.status_of(["SHOP-1", "SHOP-2"], index), "in progress")
        self.assertEqual(roadmap.status_of(["SHOP-1", "SHOP-2"], index, merged={"SHOP-2"}),
                         "delivered")
        self.assertEqual(roadmap.status_of(["SHOP-9"], {}), "planned")

    def test_a_feature_ticket_is_tracked_with_the_epics(self):
        m1 = roadmap.parse(ROADMAP)["milestones"][0]
        index = {"SHOP-3": {"status": "in_review", "features": ["wishlist"]},
                 "SHOP-4": {"status": "done", "features": ["checkout"]}}
        self.assertEqual(roadmap.tracked(m1, index), ["SHOP-1", "SHOP-3"])

    def test_derive_and_render_touch_only_the_status(self):
        index = {"SHOP-1": {"status": "done"}, "SHOP-5": {"status": "in_progress",
                                                          "features": ["checkout"]}}
        derived = roadmap.derive(ROADMAP, index)
        self.assertEqual([(d["status"], d["was"]) for d in derived],
                         [("delivered", "planned"), ("in progress", "planned")])
        out = roadmap.render(ROADMAP, derived)
        self.assertIn("- Status: delivered", out)
        self.assertIn("| v0.1.0 | M1 Wishlist | SHOP-1 | delivered |", out)
        self.assertIn("| v0.2.0 | M2 Checkout | — | in progress |", out)
        self.assertEqual(out.replace("delivered", "planned").replace("in progress", "planned"),
                         ROADMAP)

    def test_render_adds_a_missing_status_line(self):
        text = ROADMAP.replace("- Status: planned\n- Features: [Checkout]", "- Features: [Checkout]")
        out = roadmap.render(text, roadmap.derive(text, {}))
        self.assertEqual(roadmap.parse(out)["milestones"][1]["status"], "planned")

    def test_merged_ids_read_the_branch(self):
        root = tempfile.mkdtemp(prefix="roadmap-git-")
        self.addCleanup(shutil.rmtree, root, True)
        subprocess.run(["git", "init", "-q", "-b", "main", root], check=True)
        for msg in ("SHOP-1 Wishlist API (#3)", "chore: tidy", "SHOP-7 fix"):
            subprocess.run(["git", "-C", root, "-c", "user.email=a@b", "-c", "user.name=n",
                            "commit", "-q", "--allow-empty", "-m", msg], check=True)
        self.assertEqual(roadmap.merged_ids(root, "main", "SHOP"), {"SHOP-1", "SHOP-7"})
        self.assertEqual(roadmap.merged_ids(root, "nope", "SHOP"), set())
        self.assertEqual(roadmap.merged_ids(None, "main", "SHOP"), set())

    def test_roadmap_path(self):
        self.assertEqual(roadmap.roadmap_path("/r/docs/product/prd.md"),
                         "/r/docs/product/roadmap.md")
        self.assertIsNone(roadmap.roadmap_path(None))


class FloorTest(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="roadmap-floor-")
        self.addCleanup(shutil.rmtree, self.root, True)
        write_prd(self.root, features=("wishlist", "checkout"))
        self.prd = os.path.join(self.root, "docs", "product", "prd.md")
        self.path = os.path.join(self.root, "docs", "product", "roadmap.md")
        self.write(ROADMAP)

    def write(self, text):
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def rules(self, text=None):
        if text is not None:
            self.write(text)
        return sorted(f.rule for f in roadmap_check.check_roadmap(self.path, self.prd)[0])

    def test_a_conforming_roadmap_is_clean(self):
        self.assertEqual(self.rules(), [])

    def test_version_mapping(self):
        self.assertEqual(self.rules(ROADMAP.replace("### M2 Checkout — v0.2.0", "### M2 Checkout")),
                         ["milestone-unversioned", "must-unscheduled", "version-orphan"])
        self.assertEqual(self.rules(ROADMAP.replace("| v0.2.0 | M2 Checkout", "| v0.2.0 | M3")),
                         ["version-unmapped"])
        self.assertEqual(self.rules(ROADMAP.replace("v0.2.0", "v0.1.0")),
                         ["version-duplicate", "version-duplicate", "version-unmapped"])

    def test_features_must_resolve_and_musts_be_scheduled(self):
        text = ROADMAP.replace("features/checkout/prd.md", "features/loyalty/prd.md")
        self.assertEqual(self.rules(text), ["feature-unknown", "must-unscheduled"])

    def test_a_wont_have_is_not_scheduled(self):
        with open(self.prd, "a", encoding="utf-8") as fh:
            fh.write("\n### Won't have\n\n- [Gifts](features/gifts/prd.md)\n")
        os.makedirs(os.path.join(self.root, "docs", "product", "features", "gifts"))
        with open(os.path.join(self.root, "docs", "product", "features", "gifts", "prd.md"),
                  "w") as fh:
            fh.write("# Gifts\n")
        text = ROADMAP.replace("- Features: [Checkout](features/checkout/prd.md)",
                               "- Features: [Checkout](features/checkout/prd.md), "
                               "[Gifts](features/gifts/prd.md)")
        self.assertEqual(self.rules(text), ["wont-scheduled"])

    def test_status_must_be_valid_and_agree(self):
        self.assertEqual(self.rules(ROADMAP.replace("- Status: planned\n- Features: [Wish",
                                                    "- Status: soon\n- Features: [Wish")),
                         ["status-invalid"])
        self.assertEqual(self.rules(ROADMAP.replace("| SHOP-1 | planned |", "| SHOP-1 | delivered |")),
                         ["status-mismatch"])

    def run_main(self, *args):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = roadmap_check.main(["x"] + list(args))
        return code, err.getvalue()

    def test_cli_with_the_notes(self):
        plan = os.path.join(self.root, "notes.md")
        with open(plan, "w") as fh:
            fh.write('## Roadmap milestones\n\n- Milestone: "M1 Wishlist — v0.1.0"\n'
                     '- Milestone: "M2 Checkout — v0.2.0"\n\n## Answer fidelity\n\n'
                     '- C-1 — roadmap.md — "Shoppers can keep products for later."\n')
        clar = os.path.join(self.root, "clar.json")
        with open(clar, "w") as fh:
            json.dump({"clarifications": [{"id": "C-1", "status": "answered"}]}, fh)
        base = ["--roadmap", self.path, "--prd", self.prd]
        self.assertEqual(self.run_main(*base)[0], 0)
        self.assertEqual(self.run_main(*base, "--plan", plan, "--mode", "create",
                                       "--clarifications", clar)[0], 0)
        with open(plan, "a") as fh:
            fh.write('- Milestone: "M9 Ghost — v9.0.0"\n')
        code, err = self.run_main(*base, "--plan", plan, "--mode", "create")
        self.assertEqual(code, 0)  # the extra line sits under Answer fidelity, not milestones
        with open(plan, "w") as fh:
            fh.write('## Roadmap milestones\n\n- Milestone: "M9 Ghost — v9.0.0"\n')
        code, err = self.run_main(*base, "--plan", plan, "--mode", "create")
        self.assertEqual(code, 1)
        self.assertIn("roadmap-milestone-not-found", err)

    def test_cli_usage_and_unreadable(self):
        self.assertEqual(self.run_main()[0], 2)
        self.assertEqual(self.run_main("--roadmap")[0], 2)
        self.assertEqual(self.run_main("--nope", "x")[0], 2)
        self.assertEqual(self.run_main("--roadmap", self.path, "--prd", self.prd,
                                       "--plan", "p.md", "--mode", "weird")[0], 2)
        self.assertEqual(self.run_main("--roadmap", "/no/such.md", "--prd", self.prd)[0], 2)


class StatusCliTest(AcsWorkspaceCase):

    def setUp(self):
        super().setUp()
        self.write_prd(features=("wishlist", "checkout"))
        self.path = os.path.join(self.repo, "docs", "product", "roadmap.md")
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write(ROADMAP)

    def status(self, *args):
        return self.run_script("acs.py", "roadmap", "status", "--no-git", *args)

    def test_reports_and_writes_the_derived_status(self):
        tid = self.new_ticket("Wishlist API", "story", "--features", "wishlist")
        ticket = lib.load_ticket(self.tdir(tid))
        lib.update_index(self.ws, "acme-shop", dict(ticket, status="in_progress"))
        out = self.status()
        self.assertEqual(out.returncode, 0, out.stderr)
        doc = json.loads(out.stdout)
        self.assertEqual([m["status"] for m in doc["milestones"]], ["in progress", "planned"])
        self.assertTrue(doc["changed"])
        self.assertFalse(doc["written"])
        with open(self.path) as fh:
            self.assertEqual(fh.read(), ROADMAP)
        written = json.loads(self.status("--write").stdout)
        self.assertTrue(written["written"])
        with open(self.path) as fh:
            self.assertIn("| v0.1.0 | M1 Wishlist | SHOP-1 | in progress |", fh.read())

    def test_no_roadmap_is_a_refusal(self):
        os.unlink(self.path)
        out = self.status()
        self.assertEqual(out.returncode, 2)
        self.assertIn("/acs:manage-roadmap", out.stderr)

    def test_reads_the_default_branch(self):
        out = self.run_script("acs.py", "roadmap", "status", "--roadmap", "docs/product/roadmap.md")
        self.assertEqual(out.returncode, 0, out.stderr)


if __name__ == "__main__":
    unittest.main()
