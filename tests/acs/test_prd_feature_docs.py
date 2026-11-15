"""ADR-0142: the PRD is a hub (`prd.md`) plus one PRD per feature
(`features/<slug>/prd.md`). The deterministic floor for that layout --
`prd_feature_check.py` -- the doc-set grouping, the lister, and the answer
anchors that may land in a feature's own document.

Run:  python3 -m unittest tests.acs.test_prd_feature_docs -v
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

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
sys.path.insert(0, SCRIPTS)

import prd_conformance_check  # noqa: E402
import prd_feature_check  # noqa: E402
from acs_lib import design_docs, doc_sets  # noqa: E402

HUB = """# Shop PRD

## Vision

Win.

## Goals & success metrics

- G1: retention up 10% by GA
- G2: p95 checkout under 2 s by GA

## Features (prioritized)

### Must have

- [Wishlist](features/wishlist/prd.md) — save products (supports G1)
- [Checkout](features/checkout/prd.md) — pay (supports G1, G2)

### Won't have

- Gift cards — out of this release (supports G1)
"""


def feature(goals="G1", requirements="- **R1** — save a product\n- **R2** — remove it", extra=""):
    return """# Feature

## Summary

Does a thing.

## Goals served

%s

## Requirements

%s

## Acceptance criteria

Given a user, when saving, then it is listed.

## Dependencies

None.

## Out of scope

Sharing.
%s""" % (goals, requirements, extra)


class FeatureCheckCase(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="prd-features-")
        self.addCleanup(shutil.rmtree, self.root, True)
        self.write("prd.md", HUB)
        self.write("features/wishlist/prd.md", feature("G1"))
        self.write("features/checkout/prd.md", feature("G1, G2"))

    def write(self, rel, text):
        path = os.path.join(self.root, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def rules(self):
        findings, _manifest = prd_feature_check.check_features(os.path.join(self.root, "prd.md"))
        return sorted(f.rule for f in findings)


class FeatureCheckTest(FeatureCheckCase):

    def test_a_conforming_set_is_clean_and_listed(self):
        findings, manifest = prd_feature_check.check_features(os.path.join(self.root, "prd.md"))
        self.assertEqual(findings, [])
        self.assertEqual([m["feature"] for m in manifest], ["checkout", "wishlist"])

    def test_a_wont_have_feature_needs_no_document(self):
        self.assertEqual(self.rules(), [])

    def test_a_committed_feature_without_a_link_is_a_finding(self):
        self.write("prd.md", HUB.replace("- [Checkout](features/checkout/prd.md) — pay",
                                         "- Checkout — pay"))
        self.assertEqual(self.rules(), ["feature-doc-unindexed", "feature-link-missing"])

    def test_a_link_to_a_missing_document_is_a_finding(self):
        os.unlink(os.path.join(self.root, "features", "checkout", "prd.md"))
        self.assertEqual(self.rules(), ["feature-doc-missing"])

    def test_a_document_no_bullet_links_is_a_finding(self):
        self.write("features/orphan/prd.md", feature("G1"))
        self.assertEqual(self.rules(), ["feature-doc-unindexed"])

    def test_goals_served_must_equal_the_hubs_bullet(self):
        self.write("features/checkout/prd.md", feature("G1"))
        self.assertEqual(self.rules(), ["feature-goals-mismatch"])

    def test_an_unknown_goal_is_a_finding(self):
        self.write("features/wishlist/prd.md", feature("G1, G9"))
        self.assertEqual(self.rules(), ["feature-goal-unknown", "feature-goals-mismatch"])

    def test_requirements_need_ids_each_once(self):
        self.write("features/wishlist/prd.md", feature(requirements="- save a product"))
        self.assertEqual(self.rules(), ["feature-requirement-ids"])
        self.write("features/wishlist/prd.md",
                   feature(requirements="- **R1** — a\n- **R1** — b"))
        self.assertEqual(self.rules(), ["feature-requirement-ids"])

    def test_a_missing_section_is_structure_lints_finding(self):
        text = feature().replace("## Dependencies\n\nNone.\n\n", "")
        self.write("features/wishlist/prd.md", text)
        self.assertEqual(self.rules(), ["missing-section"])

    def test_a_front_matter_block_does_not_hide_the_sections(self):
        front = "---\nstatus: proposed\nversion: 1\ntickets: []\n---\n\n"
        self.write("features/wishlist/prd.md", front + feature("G1"))
        self.assertEqual(self.rules(), [])

    def test_a_hub_with_no_goal_ids_skips_the_unknown_goal_rule(self):
        self.write("prd.md", HUB.replace("G1:", "Retention:").replace("G2:", "Latency:"))
        self.assertEqual(self.rules(), [])


class FeatureCheckCliTest(FeatureCheckCase):

    def run_cli(self, *args):
        return subprocess.run([sys.executable, os.path.join(SCRIPTS, "prd_feature_check.py")]
                              + list(args), capture_output=True, text=True)

    def test_clean_exits_zero_with_a_manifest(self):
        done = self.run_cli("--prd", os.path.join(self.root, "prd.md"))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual([json.loads(l)["family"] for l in done.stdout.splitlines()],
                         ["feature-docs", "feature-docs"])

    def test_findings_exit_one_on_stderr(self):
        os.unlink(os.path.join(self.root, "features", "checkout", "prd.md"))
        done = self.run_cli("--prd", os.path.join(self.root, "prd.md"))
        self.assertEqual(done.returncode, 1)
        self.assertIn("[feature-doc-missing]", done.stderr)

    def test_usage_and_unreadable_exit_two(self):
        self.assertEqual(self.run_cli().returncode, 2)
        self.assertEqual(self.run_cli("--prd").returncode, 2)
        self.assertEqual(self.run_cli("--nope", "x").returncode, 2)
        self.assertEqual(self.run_cli("--prd", os.path.join(self.root, "gone.md")).returncode, 2)

    def test_the_feature_sections_are_overridable(self):
        done = self.run_cli("--prd", os.path.join(self.root, "prd.md"),
                            "--feature-sections", "Summary; Rollout")
        self.assertEqual(done.returncode, 1)
        self.assertIn("'Rollout'", done.stderr)

    def test_main_is_importable(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = prd_feature_check.main(["x", "--prd", os.path.join(self.root, "prd.md")])
        self.assertEqual(code, 0)


class AnswerAnchorTest(FeatureCheckCase):
    """An answer may anchor in a feature's own PRD (`features/<slug>/prd.md`)."""

    def check(self, target, anchor):
        plan = "## Answer fidelity\n\n- C-1 — %s — \"%s\"\n" % (target, anchor)
        clar = [{"id": "C-1", "status": "answered"}]
        texts = prd_conformance_check.feature_texts(os.path.join(self.root, "prd.md"))
        findings, manifest = prd_conformance_check.check_answer_fidelity(
            plan, clar, HUB, "# Roadmap\n", "plan.md", texts)
        return [f.rule for f in findings], manifest

    def test_feature_texts_reads_each_feature_prd(self):
        texts = prd_conformance_check.feature_texts(os.path.join(self.root, "prd.md"))
        self.assertEqual(sorted(texts), ["features/checkout/prd.md", "features/wishlist/prd.md"])

    def test_no_features_folder_is_no_texts(self):
        self.assertEqual(prd_conformance_check.feature_texts(
            os.path.join(self.root, "features", "wishlist", "prd.md")), {})

    def test_an_anchor_in_a_feature_prd_resolves(self):
        rules, manifest = self.check("features/wishlist/prd.md", "save a product")
        self.assertEqual(rules, [])
        self.assertEqual(manifest[0]["target"], "features/wishlist/prd.md")

    def test_an_anchor_absent_from_the_named_feature_prd_is_a_finding(self):
        self.assertEqual(self.check("features/wishlist/prd.md", "not written")[0],
                         ["answer-anchor-not-found"])

    def test_an_unknown_target_is_still_refused(self):
        self.assertEqual(self.check("features/ghost/prd.md", "x")[0],
                         ["answer-anchor-file-unknown"])


class FeatureNotesTest(FeatureCheckCase):
    """A feature author's notes disposition its own answers (`--feature-notes`)."""

    def run_check(self, plan, *notes):
        files = []
        for i, text in enumerate([plan] + list(notes)):
            files.append(self.write("n%d.md" % i, text))
        clar = self.write("clar.json", json.dumps(
            {"clarifications": [{"id": "C-1", "status": "answered"}]}))
        self.write("roadmap.md", "Milestones come later.\n")
        args = ["--plan", files[0], "--mode", "greenfield", "--repo-root", self.root,
                "--clarifications", clar, "--prd", os.path.join(self.root, "prd.md"),
                "--roadmap", os.path.join(self.root, "roadmap.md")]
        for path in files[1:]:
            args += ["--feature-notes", path]
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = prd_conformance_check.main(["x"] + args)
        return code, err.getvalue()

    PLAN = "## Answer fidelity\n\n- C-1 — features/wishlist/prd.md — \"to be completed\"\n"

    def test_the_plans_placeholder_is_overridden_by_the_feature_notes(self):
        notes = "## Answer fidelity\n\n- C-1 — features/wishlist/prd.md — \"save a product\"\n"
        self.assertEqual(self.run_check(self.PLAN, notes)[0], 0)

    def test_without_the_notes_the_placeholder_anchor_is_not_found(self):
        code, err = self.run_check(self.PLAN)
        self.assertEqual(code, 1)
        self.assertIn("answer-anchor-not-found", err)

    def test_an_unreadable_notes_file_is_a_usage_error(self):
        self.run_check(self.PLAN, "x")
        os.unlink(os.path.join(self.root, "n1.md"))
        out = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(out):
            code = prd_conformance_check.main(
                ["x", "--plan", os.path.join(self.root, "n0.md"), "--mode", "greenfield",
                 "--repo-root", self.root, "--clarifications", os.path.join(self.root, "clar.json"),
                 "--prd", os.path.join(self.root, "prd.md"),
                 "--roadmap", os.path.join(self.root, "roadmap.md"),
                 "--feature-notes", os.path.join(self.root, "n1.md")])
        self.assertEqual(code, 2)


class DocSetTest(unittest.TestCase):

    def test_a_feature_prd_joins_its_features_group(self):
        for path in ("docs/product/features/export/prd.md",
                     "docs/product/features/export/analysis/README.md"):
            self.assertEqual(doc_sets.doc_set(path), ("prd/features/export", "feature export"))
        self.assertEqual(doc_sets.doc_set("docs/product/prd.md"), ("prd", "PRD"))

    def test_the_lister_shows_the_hub_the_roadmap_and_each_feature_prd(self):
        root = tempfile.mkdtemp(prefix="prd-list-")
        self.addCleanup(shutil.rmtree, root, True)
        front = "---\nstatus: proposed\nversion: 1\ntickets: []\n---\n\n"
        for rel in ("prd.md", "roadmap.md", "features/export/prd.md",
                    "features/export/analysis/README.md"):
            path = os.path.join(root, "docs", "product", *rel.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(front + "# Doc\n")
        groups = design_docs.list_documents(root)["groups"]
        by_key = {g["key"]: [d["path"] for d in g["docs"]] for g in groups}
        self.assertEqual(by_key["prd"], ["docs/product/prd.md", "docs/product/roadmap.md"])
        self.assertEqual(by_key["prd/features/export"], [
            "docs/product/features/export/analysis/README.md",
            "docs/product/features/export/prd.md"])
        only = design_docs.list_documents(root, feature="export")["groups"]
        self.assertEqual([g["key"] for g in only], ["prd/features/export"])


if __name__ == "__main__":
    unittest.main()
