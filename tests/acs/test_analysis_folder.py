"""ADR-0133: an analysis is a FOLDER -- README.md plus one file per bounded
context -- checked, published and read as one.

- `acs_lib.analysis_folder.check_folder`: names (kebab-case `.md`, no
  `index.md`, no subfolder), README front matter + ordered headings + a
  contexts table whose links all resolve and list every context file, each
  context file's front matter (`context` = its stem) and ordered headings.
- publish copies every reviewed file byte-for-byte, records each file's
  sha256, removes context files the new analysis no longer has -- inside the
  analysis folder ONLY -- and record-publication verifies every file.
- `artifacts show` keeps `artifacts["analysis.md"]` (the folder's README) and
  adds `analysis_files`; a legacy single analysis.md is still read; `docs
  where --doc analysis.md` names the folder; `design list` groups a feature's
  living analysis folder, README first; the commit plan groups the folder as
  one documents group.

Run:  python3 -m unittest tests.acs.test_analysis_folder -v
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_analysis_loop import (CONTEXT, CONTEXT_NAME, DRAFT, FEATURE,  # noqa: E402
                                AnalysisLoopCase, TicketlessAnalysisCase)

from acs_lib import analysis_folder as F  # noqa: E402
from acs_lib import analysis_loop as L  # noqa: E402
from acs_lib import commit_plan, design_docs, doc_sets  # noqa: E402

TID = "SHOP-1"

#: A second bounded context, and the README that lists both.
REFUNDS = CONTEXT.replace("context: bulk-import", "context: payment-refunds") \
    .replace("# Bulk import", "# Payment refunds")
TWO_ROWS = ("| Bulk import | [bulk-import.md](bulk-import.md) | the import pipeline |\n"
            "| Payment refunds | [payment-refunds.md](./payment-refunds.md) | refunds |\n")
ONE_ROW = "| Bulk import | [bulk-import.md](bulk-import.md) | the import pipeline |\n"


def readme(tid=TID, rows=ONE_ROW):
    return DRAFT.format(tid=tid).replace(ONE_ROW, rows)


class FolderCase(unittest.TestCase):
    """A scratch analysis folder."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-analysis-folder-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.folder = os.path.join(self.tmp, "analysis")
        self.put("README.md", readme())
        self.put(CONTEXT_NAME, CONTEXT)

    def put(self, name, text, folder=None):
        path = os.path.join(folder or self.folder, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def rules(self, ticket=TID, phase=None):
        return [(f["file"], f["text"].split("] ")[0].split("[")[-1])
                for f in F.check_folder(self.folder, ticket, phase)]


class TestFolderChecks(FolderCase):

    def test_a_well_formed_folder_has_no_findings(self):
        self.assertEqual(F.check_folder(self.folder, TID), [])
        self.put("README.md", readme(rows=TWO_ROWS))
        self.put("payment-refunds.md", REFUNDS)
        self.assertEqual(F.check_folder(self.folder, TID), [])

    def test_every_finding_blocks_from_the_checks_slice(self):
        os.unlink(os.path.join(self.folder, "README.md"))
        finding = F.check_folder(self.folder, TID)[0]
        self.assertEqual((finding["slice"], finding["severity"], finding["dimension"],
                          finding["file"]),
                         ("draft-checks", "blocking", "structure", "analysis/README.md"))
        self.assertIn("[missing-readme]", finding["text"])

    def test_a_missing_folder_is_one_finding(self):
        shutil.rmtree(self.folder)
        self.assertEqual(self.rules(), [("analysis", "missing-folder")])

    def test_index_md_is_refused(self):
        self.put("index.md", CONTEXT)
        self.assertIn(("analysis/index.md", "index-file"), self.rules())
        os.rename(os.path.join(self.folder, "README.md"), os.path.join(self.folder, "x"))
        rules = self.rules()
        self.assertIn(("analysis/README.md", "missing-readme"), rules)

    def test_names_must_be_kebab_case_md_in_one_flat_folder(self):
        for name in ("Order_Checkout.md", "orderCheckout.md", "notes.txt", "readme.md",
                     "-lead.md", "a--b.md"):
            self.put(name, CONTEXT)
        os.makedirs(os.path.join(self.folder, "extra"))
        rules = self.rules()
        for name in ("Order_Checkout.md", "orderCheckout.md", "notes.txt", "readme.md",
                     "-lead.md", "a--b.md"):
            self.assertIn(("analysis/%s" % name, "bad-name"), rules, name)
        self.assertIn(("analysis/extra", "unexpected-entry"), rules)

    def test_a_broken_table_link_is_refused(self):
        self.put("README.md", readme(rows=TWO_ROWS))
        rules = self.rules()
        self.assertIn(("analysis/README.md", "broken-link"), rules)
        finding = [f for f in F.check_folder(self.folder, TID) if "broken-link" in f["text"]][0]
        self.assertIn("payment-refunds.md", finding["text"])
        self.assertTrue(finding["text"].startswith("line 1"), finding["text"])

    def test_a_link_leaving_the_folder_or_naming_the_readme_is_refused(self):
        for target in ("../plan.md", "docs/other.md", "https://example.com/a.md",
                       "README.md"):
            with self.subTest(target=target):
                self.put("README.md", readme(rows=ONE_ROW + "| x | [x](%s) | y |\n" % target))
                self.assertIn(("analysis/README.md", "bad-link"), self.rules())

    def test_an_anchor_on_a_context_link_is_fine(self):
        self.put("README.md", readme(rows="| B | [b](bulk-import.md#risks) | p |\n"))
        self.assertEqual(self.rules(), [])

    def test_every_context_file_is_listed(self):
        self.put("payment-refunds.md", REFUNDS)
        self.assertEqual(self.rules(), [("analysis/README.md", "unlisted-context")])

    def test_the_contexts_section_needs_a_table_with_linked_rows(self):
        self.put("README.md", readme(rows=ONE_ROW + "| Orphan | none | - |\n"))
        self.assertEqual(self.rules(), [("analysis/README.md", "unlinked-row")])
        text = readme().replace("| Context | File | Purpose |\n| --- | --- | --- |\n" + ONE_ROW,
                                "See [bulk-import.md](bulk-import.md).\n")
        self.put("README.md", text)
        self.assertEqual(self.rules(), [("analysis/README.md", "no-contexts-table")])
        self.put("README.md", readme(rows=""))
        rules = self.rules()
        self.assertIn(("analysis/README.md", "no-contexts"), rules)
        self.assertIn(("analysis/README.md", "unlisted-context"), rules)

    def test_at_least_one_context_file(self):
        os.unlink(os.path.join(self.folder, CONTEXT_NAME))
        rules = self.rules()
        self.assertIn(("analysis", "no-context-files"), rules)
        self.assertIn(("analysis/README.md", "broken-link"), rules)

    def test_readme_headings_are_required_in_order(self):
        text = readme()
        swapped = text.replace("## Refined acceptance criteria", "## TMP") \
            .replace("## Scope and summary", "## Refined acceptance criteria") \
            .replace("## TMP", "## Scope and summary")
        self.put("README.md", swapped)
        self.assertIn(("analysis/README.md", "section-order"), self.rules())
        self.put("README.md", text.replace("## Questions and assumptions\n", ""))
        self.assertIn(("analysis/README.md", "missing-section"), self.rules())

    def test_readme_front_matter_is_the_full_spec(self):
        self.put("README.md", readme().replace("ready_for_planning: true\n", "", 1))
        self.assertEqual(self.rules(), [("analysis/README.md", "missing-key")])
        self.put("README.md", readme(tid="SHOP-9"))
        self.assertEqual(self.rules(), [("analysis/README.md", "ticket-mismatch")])
        rules = self.rules(ticket=None, phase="discovery")
        self.assertIn(("analysis/README.md", "missing-key"), rules)

    def test_api_surface_is_no_longer_part_of_the_spec(self):
        """ADR-0134: whether an interface changes no longer decides a step,
        so the analysis states no `api_surface`."""
        for spec in (F.FRONT_MATTER_SPEC, F.FEATURE_FRONT_MATTER_SPEC):
            self.assertNotIn("api_surface", spec)
        self.assertNotIn("api_surface", readme())
        self.assertEqual(F.check_folder(self.folder, TID), [])

    def test_an_analysis_published_with_api_surface_still_validates(self):
        """An analysis published before ADR-0134 carries `api_surface:` --
        an unknown front-matter key, ignored, so it keeps validating."""
        legacy = readme().replace("ready_for_planning: true\n",
                                  "ready_for_planning: true\napi_surface: true\n")
        self.assertIn("api_surface: true", legacy)
        self.put("README.md", legacy)
        self.assertEqual(F.check_folder(self.folder, TID), [])

    def test_an_analysis_published_with_a_design_recommendation_still_validates(self):
        """ADR-0139: the analysis says nothing about design. One published
        before it carries `needs_design_recommendation:` -- an unknown key,
        ignored, so it keeps validating."""
        for spec in (F.FRONT_MATTER_SPEC, F.FEATURE_FRONT_MATTER_SPEC):
            self.assertNotIn("needs_design_recommendation", spec)
        self.assertNotIn("needs_design_recommendation", readme())
        legacy = readme().replace("ready_for_planning: true\n",
                                  "ready_for_planning: true\n"
                                  "needs_design_recommendation: true\n")
        self.put("README.md", legacy)
        self.assertEqual(F.check_folder(self.folder, TID), [])

    def test_context_headings_are_required_in_order(self):
        self.put(CONTEXT_NAME, CONTEXT.replace("## Risks\nNone.\n\n", ""))
        self.assertEqual(self.rules(), [("analysis/bulk-import.md", "missing-section")])
        self.put(CONTEXT_NAME, CONTEXT.replace("## API notes", "## TMP")
                 .replace("## Impact map", "## API notes").replace("## TMP", "## Impact map"))
        self.assertIn(("analysis/bulk-import.md", "section-order"), self.rules())

    def test_context_front_matter_names_its_own_file(self):
        self.put(CONTEXT_NAME, CONTEXT.replace("context: bulk-import", "context: imports"))
        self.assertEqual(self.rules(), [("analysis/bulk-import.md", "context-mismatch")])
        self.put(CONTEXT_NAME, CONTEXT.replace("---\ncontext: bulk-import\n---\n\n", ""))
        self.assertEqual(self.rules(), [("analysis/bulk-import.md", "front-matter-missing")])

    def test_a_discovery_context_carries_the_feature_and_version_keys(self):
        keys = "feature: bulk-import\nstatus: proposed\nversion: 1\ntickets: []"
        self.put("README.md", readme().replace("ticket: %s" % TID, keys))
        rules = self.rules(ticket=None, phase="discovery")
        self.assertEqual(rules, [("analysis/bulk-import.md", "missing-key")] * 4)
        self.put(CONTEXT_NAME, CONTEXT.replace("context: bulk-import",
                                               "context: bulk-import\n" + keys))
        self.assertEqual(self.rules(ticket=None, phase="discovery"), [])
        self.put(CONTEXT_NAME, CONTEXT.replace(
            "context: bulk-import", "context: bulk-import\n" + keys.replace(
                "feature: bulk-import", "feature: other")))
        self.assertEqual(self.rules(ticket=None, phase="discovery"),
                         [("analysis/bulk-import.md", "feature-mismatch")])

    def test_an_undecodable_file_is_a_finding_not_a_crash(self):
        with open(os.path.join(self.folder, CONTEXT_NAME), "wb") as fh:
            fh.write(b"\xff\xfe\x00bad")
        self.assertIn(("analysis/bulk-import.md", "unreadable"), self.rules())
        with open(os.path.join(self.folder, "README.md"), "wb") as fh:
            fh.write(b"\xff\xfe\x00bad")
        self.assertIn(("analysis/README.md", "unreadable"), self.rules())


class TestFolderMechanics(FolderCase):

    def test_files_lists_readme_first_then_contexts(self):
        self.put("payment-refunds.md", REFUNDS)
        self.put("index.md", "x")
        self.put("notes.txt", "x")
        self.assertEqual(F.files(self.folder), ["README.md", CONTEXT_NAME, "payment-refunds.md"])
        self.assertEqual(F.files(os.path.join(self.tmp, "nope")), [])

    def test_file_list_and_legacy_sibling(self):
        entry = os.path.join(self.folder, "README.md")
        self.assertEqual(F.file_list(entry), [entry, os.path.join(self.folder, CONTEXT_NAME)])
        legacy = os.path.join(self.tmp, "analysis.md")
        self.assertEqual(F.legacy_sibling(entry), legacy)
        self.assertEqual(F.file_list(legacy), [legacy])
        self.assertEqual(F.file_list(None), [])
        self.assertIsNone(F.entry_folder(legacy))
        self.assertIsNone(F.legacy_sibling(legacy))
        self.assertEqual(F.existing(entry), entry)
        os.unlink(entry)
        self.assertIsNone(F.existing(entry))
        self.put("analysis.md", "# legacy\n", folder=self.tmp)
        self.assertEqual(F.existing(entry), legacy)

    def test_the_digest_covers_every_file_and_its_name(self):
        first, shas, total = F.digest(self.folder)
        self.assertEqual(sorted(shas), ["README.md", CONTEXT_NAME])
        self.assertEqual(total, len(readme().encode()) + len(CONTEXT.encode()))
        os.rename(os.path.join(self.folder, CONTEXT_NAME),
                  os.path.join(self.folder, "imports.md"))
        self.assertNotEqual(F.digest(self.folder)[0], first, "a rename is a change")
        self.put("notes.txt", "x")
        self.assertIn("notes.txt", F.digest(self.folder)[1])

    def test_copy_removes_stale_context_files_only_inside_the_folder(self):
        target_parent = os.path.join(self.tmp, "docs", "SHOP-1")
        target = os.path.join(target_parent, "analysis")
        self.put("stale-context.md", "# old\n", folder=target)
        self.put("diagram.png", "png", folder=target)
        self.put("keep/inner.md", "# nested\n", folder=target)
        outside = [self.put("plan.md", "# plan\n", folder=target_parent),
                   self.put("analysis.md", "# legacy\n", folder=target_parent),
                   self.put("stale-context.md", "# sibling\n", folder=target_parent)]
        written, removed = F.copy_folder(self.folder, target)
        self.assertEqual(removed, ["stale-context.md"])
        self.assertEqual(sorted(written), ["README.md", CONTEXT_NAME])
        self.assertEqual(sorted(os.listdir(target)),
                         ["README.md", CONTEXT_NAME, "diagram.png", "keep"])
        self.assertTrue(os.path.isfile(os.path.join(target, "keep", "inner.md")))
        for path in outside:
            self.assertTrue(os.path.isfile(path), "never deletes outside the folder: %s" % path)
        self.assertEqual(F.verify(target, written), [])

    def test_copy_refuses_a_target_that_is_not_an_analysis_folder(self):
        for target in (os.path.join(self.tmp, "docs"), self.tmp):
            with self.assertRaises(ValueError):
                F.copy_folder(self.folder, target)
        real = os.path.join(self.tmp, "elsewhere")
        os.makedirs(real)
        self.put("victim.md", "# keep me\n", folder=real)
        link_parent = os.path.join(self.tmp, "linked")
        os.makedirs(link_parent)
        os.symlink(real, os.path.join(link_parent, "analysis"))
        with self.assertRaises(ValueError):
            F.copy_folder(self.folder, os.path.join(link_parent, "analysis"))
        self.assertTrue(os.path.isfile(os.path.join(real, "victim.md")))
        self.put("analysis", "a file", folder=os.path.join(self.tmp, "f"))
        with self.assertRaises(ValueError):
            F.copy_folder(self.folder, os.path.join(self.tmp, "f", "analysis"))

    def test_verify_names_a_changed_missing_or_unreviewed_file(self):
        target = os.path.join(self.tmp, "out", "analysis")
        written, _removed = F.copy_folder(self.folder, target)
        self.put("new-context.md", "# new\n", folder=target)
        with open(os.path.join(target, "README.md"), "a") as fh:
            fh.write("edit\n")
        os.unlink(os.path.join(target, CONTEXT_NAME))
        problems = " | ".join(F.verify(target, written))
        self.assertIn("README.md is not the reviewed bytes", problems)
        self.assertIn("%s is missing" % CONTEXT_NAME, problems)
        self.assertIn("new-context.md was not part of the reviewed analysis", problems)
        shutil.rmtree(target)
        self.assertIn("is missing", F.verify(target, written)[0])

    def test_seed_copies_once(self):
        target = os.path.join(self.tmp, "iter-2", "analysis")
        self.assertTrue(F.seed(self.folder, target))
        self.assertEqual(sorted(os.listdir(target)), ["README.md", CONTEXT_NAME])
        self.assertFalse(F.seed(self.folder, target))
        self.assertFalse(F.seed(os.path.join(self.tmp, "nope"), os.path.join(self.tmp, "x")))

    def test_the_draft_specs_follow_the_run(self):
        self.assertEqual(F.front_matter_spec(TID), F.FRONT_MATTER_SPEC)
        self.assertIn("version: int", F.front_matter_spec(None, "discovery"))
        self.assertNotIn("version", F.front_matter_spec(None, "development"))
        self.assertEqual(F.context_front_matter_spec(), "context: str")
        self.assertIn("feature: str", F.context_front_matter_spec("discovery"))


class TestDocSetsAndDesignList(FolderCase):

    def test_the_folder_is_one_doc_set(self):
        for path in ("docs/product/features/export/analysis/README.md",
                     "docs/product/features/export/analysis/order-export.md",
                     "docs/product/features/export/analysis.md"):
            self.assertEqual(doc_sets.doc_set(path),
                             ("prd/features/export", "feature export"), path)
        self.assertEqual(doc_sets.doc_set("docs/development/export/SHOP-1/analysis/README.md"),
                         ("development/export/SHOP-1", "SHOP-1 docs"))
        self.assertNotEqual(doc_sets.doc_set("docs/product/features/export/notes.md")[0],
                            "prd/features/export")
        self.assertNotEqual(doc_sets.doc_set(
            "docs/product/features/export/analysis/deep/x.md")[0], "prd/features/export")

    def test_design_list_groups_a_living_analysis_readme_first(self):
        root = self.tmp
        keys = "status: proposed\nversion: 2\ntickets: []\nfeature: export\n"
        base = os.path.join(root, "docs", "product", "features", "export")
        self.put("README.md", "---\n%s---\n\n# A\n" % keys, folder=os.path.join(base, "analysis"))
        for name in ("order-export.md", "audit-trail.md"):
            self.put(name, "---\ncontext: %s\n%s---\n\n# C\n" % (name[:-3], keys),
                     folder=os.path.join(base, "analysis"))
        self.put("index.txt", "not listed", folder=os.path.join(base, "analysis"))
        out = design_docs.list_documents(root)
        groups = [g for g in out["groups"] if g["key"] == "prd/features/export"]
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["feature"], "export")
        rel = "docs/product/features/export/analysis/"
        self.assertEqual([d["path"] for d in groups[0]["docs"]],
                         [rel + "README.md", rel + "audit-trail.md", rel + "order-export.md"])
        self.assertTrue(all(d["status"] == "proposed" and not d["problems"]
                            for d in groups[0]["docs"]))


class TestPublishFolder(AnalysisLoopCase):
    """The CLI round trip with two bounded contexts and a re-publish that
    drops one."""

    TWO = {CONTEXT_NAME: CONTEXT, "payment-refunds.md": REFUNDS}

    def docs(self, *parts):
        return os.path.join(self.repo, "docs", "development", FEATURE, self.tid, *parts)

    def to_publish_two(self):
        self.to_draft()
        self.do_draft(1, text=readme(self.tid, TWO_ROWS), contexts=self.TWO)
        self.assertEqual(self.cli("record-draft")["next"]["draft_checks"], [])
        self.do_review(1)
        self.assertTrue(self.cli("record-review")["passed"])

    def test_two_contexts_publish_and_verify_every_file(self):
        self.to_publish_two()
        draft = self.loop()["draft"]
        self.assertEqual(sorted(draft["files"]), ["README.md", CONTEXT_NAME,
                                                  "payment-refunds.md"])
        self.assertEqual(draft["dir"], L.draft_dir(self.r, 1))
        pub = self.cli("publish")["publication"]
        self.assertEqual(pub["dir"], self.docs("analysis"))
        self.assertEqual(pub["file_shas"], draft["files"])
        self.assertEqual((pub["removed"], pub["superseded"], pub["iteration"]), ([], None, 1))
        prefix = "docs/development/%s/%s/analysis/" % (FEATURE, self.tid)
        self.assertEqual(pub["files"], [prefix + n for n in
                                        ("README.md", CONTEXT_NAME, "payment-refunds.md")])
        self.assertEqual(self.cli("record-publication")["next"]["action"], "completed")
        out = self.run_script("acs.py", "artifacts", "show", "--run", self.tid)
        self.assertEqual(out.returncode, 0, out.stderr)
        shown = json.loads(out.stdout)
        self.assertEqual(shown["artifacts"]["analysis.md"], self.docs("analysis", "README.md"))
        self.assertEqual(shown["analysis_files"], [self.docs("analysis", n) for n in
                                                   ("README.md", CONTEXT_NAME,
                                                    "payment-refunds.md")])
        self.assertEqual(shown["analysis_dir"], self.docs("analysis"))
        where = self.run_script("acs.py", "docs", "where", "--doc", "analysis.md",
                                "--run", self.tid)
        self.assertEqual(where.returncode, 0, where.stderr)
        info = json.loads(where.stdout)
        self.assertEqual(info["path"], prefix.rstrip("/"))
        self.assertEqual(info["entry_path"], prefix + "README.md")

    def test_a_republish_removes_the_dropped_context_inside_the_folder_only(self):
        """A revision that drops a context removes its file from the analysis
        folder -- and nothing beside it."""
        stale = self.docs("analysis", "old-context.md")
        self.write(stale, "# from an earlier analysis\n")
        self.write(self.docs("analysis", "diagram.svg"), "<svg/>")
        legacy = self.write_and_path(self.docs("analysis.md"), "# single-file analysis\n")
        plan = self.write_and_path(self.docs("plan.md"), "# plan\n")
        self.to_publish_two()
        pub = self.cli("publish")["publication"]
        prefix = "docs/development/%s/%s/" % (FEATURE, self.tid)
        self.assertEqual(pub["removed"], [prefix + "analysis/old-context.md"])
        self.assertEqual(pub["superseded"], legacy)
        self.assertFalse(os.path.exists(stale))
        for kept in (legacy, plan, self.docs("analysis", "diagram.svg")):
            self.assertTrue(os.path.isfile(kept), kept)
        self.assertEqual(self.cli("record-publication")["next"]["action"], "completed")
        records = commit_plan.Records(self.repo, self.tid)
        records.read_run(self.r)
        self.assertEqual(records.claims[prefix + "analysis/old-context.md"],
                         ("ticket-docs", None), "the deletion commits with the documents")

    def write_and_path(self, path, text):
        self.write(path, text)
        return path

    def test_record_publication_refuses_an_unreviewed_context(self):
        self.to_publish_two()
        self.cli("publish")
        self.write(self.docs("analysis", "sneaky.md"), "# added after review\n")
        nxt = self.cli("record-publication")["next"]
        self.assertEqual(nxt["action"], "blocked")
        self.assertIn("sneaky.md was not part of the reviewed analysis", nxt["reason"])
        os.unlink(self.docs("analysis", "sneaky.md"))
        os.unlink(self.docs("analysis", "payment-refunds.md"))
        self.assertIn("payment-refunds.md is missing",
                      self.cli("record-publication")["next"]["reason"])

    def test_record_publication_refuses_a_stale_record(self):
        self.to_publish_two()
        self.cli("publish")
        loop = self.loop()
        loop["publication"]["sha256"] = "0" * 64
        L.save_loop(self.r, loop)
        self.assertIn("not the reviewed analysis",
                      self.cli("record-publication")["next"]["reason"])

    def test_publish_refuses_a_context_added_after_review(self):
        self.to_publish_two()
        self.write(os.path.join(L.draft_dir(self.r, 1), "late.md"), CONTEXT)
        out = self.run_script("acs.py", "analysis", "publish", "--run", self.tid)
        self.assertEqual(out.returncode, 2)
        self.assertIn("not the files the review passed", out.stderr)
        self.assertFalse(os.path.exists(self.docs("analysis")))

    def test_publish_refuses_without_a_draft_readme(self):
        self.to_publish_two()
        os.unlink(L.draft_readme(self.r, 1))
        out = self.run_script("acs.py", "analysis", "publish", "--run", self.tid)
        self.assertEqual(out.returncode, 2)
        self.assertIn("no draft folder with a README.md", out.stderr)


class TestDraftFolderLoop(AnalysisLoopCase):

    def test_the_draft_action_names_the_folder_and_its_shape(self):
        self.to_draft()
        action = self.next()
        self.assertEqual(action["draft"], L.draft_dir(self.r, 1))
        self.assertTrue(action["draft"].endswith(os.path.join("iter-1", "analysis")))
        self.assertEqual(action["readme"], L.draft_readme(self.r, 1))
        self.assertIsNone(action["previous_draft"])
        self.assertEqual(action["shape"]["readme_sections"], list(F.README_SECTIONS))
        self.assertEqual(action["shape"]["context_sections"], list(F.CONTEXT_SECTIONS))

    def test_a_folder_without_a_readme_blocks_the_record(self):
        self.to_draft()
        self.do_draft(1)
        os.unlink(L.draft_readme(self.r, 1))
        nxt = self.cli("record-draft")["next"]
        self.assertEqual((nxt["action"], nxt["kind"]), ("blocked", "machinery"))
        self.assertIn("iter-1/analysis/README.md", nxt["reason"])

    def test_structure_refusals_fail_the_iteration(self):
        self.to_draft()
        self.do_draft(1, text=readme(self.tid, TWO_ROWS),
                      contexts={CONTEXT_NAME: CONTEXT, "index.md": CONTEXT,
                                "Bad_Name.md": CONTEXT})
        review = self.cli("record-draft")["next"]
        texts = " ".join(f["text"] for f in review["draft_checks"])
        for rule in ("[index-file]", "[bad-name]", "[broken-link]"):
            self.assertIn(rule, texts)
        self.do_review(1)
        out = self.cli("record-review")
        self.assertFalse(out["passed"])
        self.assertTrue(all(f["slice"] == "draft-checks" for f in out["blocking"]))

    def test_a_failed_iteration_seeds_the_next_draft_folder(self):
        self.to_draft()
        self.do_draft(1, text=readme(self.tid, TWO_ROWS), contexts=self.two())
        self.cli("record-draft")
        self.do_review(1, findings={"surface": [self.finding("refunds is out of scope")]})
        self.assertFalse(self.cli("record-review")["passed"])
        action = self.next()
        self.assertEqual((action["action"], action["iteration"]), ("draft", 2))
        self.assertEqual(action["previous_draft"], L.draft_dir(self.r, 1))
        self.assertEqual(sorted(os.listdir(L.draft_dir(self.r, 2))),
                         sorted(os.listdir(L.draft_dir(self.r, 1))))
        # The revision drops a context: delete it from the seeded folder.
        os.unlink(os.path.join(L.draft_dir(self.r, 2), "payment-refunds.md"))
        self.snapshot("analyst", 2)
        self.write(L.draft_readme(self.r, 2), readme(self.tid))
        self.write(L.iter_path(self.r, 2, "analyst.json"), "{}")
        self.write(L.iter_path(self.r, 2, "authoring.md"), "## Findings addressed\n-\n")
        self.assertEqual(self.cli("record-draft")["next"]["draft_checks"], [])
        review = self.next()
        self.assertEqual(review["draft_files"], [os.path.join(L.draft_dir(self.r, 2), n)
                                                 for n in ("README.md", CONTEXT_NAME)])
        self.do_review(2)
        self.assertTrue(self.cli("record-review")["passed"])
        self.assertEqual(self.next()["draft"], L.draft_dir(self.r, 2))
        pub = self.cli("publish")["publication"]
        self.assertEqual((pub["iteration"], sorted(pub["file_shas"])),
                         (2, ["README.md", CONTEXT_NAME]))

    def two(self):
        return {CONTEXT_NAME: CONTEXT, "payment-refunds.md": REFUNDS}


class TestLivingAnalysisFolder(TicketlessAnalysisCase):

    def test_a_discovery_analysis_publishes_the_features_living_folder(self):
        legacy = os.path.join(self.repo, "docs", "product", "features", FEATURE,
                              "analysis.md")
        self.write(legacy, "# the single-file analysis of before ADR-0133\n")
        self.to_publish()
        self.refine({"feature": FEATURE})
        pub = self.cli("publish")["publication"]
        folder = os.path.join(os.path.dirname(legacy), "analysis")
        self.assertEqual((pub["dir"], pub["superseded"]), (folder, legacy))
        self.assertTrue(os.path.isfile(legacy), "publish never deletes outside the folder")
        self.assertEqual(self.cli("record-publication")["next"]["action"], "completed")
        shown = json.loads(self.run_script("acs.py", "artifacts", "show", "--run",
                                           self.tid).stdout)
        self.assertEqual(shown["feature_analysis"], os.path.join(folder, "README.md"))
        self.assertEqual(shown["feature_analysis_files"],
                         [os.path.join(folder, n) for n in ("README.md", CONTEXT_NAME)])
        listed = design_docs.list_documents(self.repo, feature=FEATURE)["groups"]
        self.assertEqual([g["key"] for g in listed], ["prd/features/%s" % FEATURE])
        rel = "docs/product/features/%s/" % FEATURE
        self.assertEqual([d["path"] for d in listed[0]["docs"]],
                         [rel + "analysis.md", rel + "analysis/README.md",
                          rel + "analysis/" + CONTEXT_NAME])


class TestLegacyTicketDocs(AnalysisLoopCase):

    def test_a_legacy_docs_tickets_analysis_is_still_read(self):
        legacy = os.path.join(self.repo, "docs", "tickets", self.tid, "analysis.md")
        self.write(legacy, "# legacy\n")
        out = self.run_script("acs.py", "artifacts", "show", "--run", self.tid)
        self.assertEqual(out.returncode, 0, out.stderr)
        shown = json.loads(out.stdout)
        self.assertEqual(shown["artifacts"]["analysis.md"], legacy)
        self.assertEqual(shown["analysis_files"], [legacy])
        self.assertIsNone(shown["analysis_dir"])
        dev = os.path.join(self.repo, "docs", "development", FEATURE, self.tid)
        self.assertEqual(shown["analysis_target_dir"], os.path.join(dev, "analysis"))
        single = os.path.join(dev, "analysis.md")
        self.write(single, "# development single file\n")
        shown = json.loads(self.run_script("acs.py", "artifacts", "show", "--run",
                                           self.tid).stdout)
        self.assertEqual(shown["artifacts"]["analysis.md"], single,
                         "the run's own single file wins over docs/tickets")


if __name__ == "__main__":
    unittest.main()
