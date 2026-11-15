"""ADR-0135: /acs:create-design is renamed /acs:create-tech-design, and its
document design.md is renamed tech-design.md -- the hand-off design the team
reviews before implementation, approved through /acs:set-doc-status.

Pinned here, at the hook-library layer:

  * the per-run document is `tech-design.md`, filed in the Design phase folder
    `<architecture_dir>/lld/<f>/<key>/` (doc_layout, doc_share, run_docs,
    artifacts), with the old `design.md` a READ fallback everywhere a reader
    resolves it -- the phase folder, the old local step folder
    `steps/create-design/local/`, the legacy docs/tickets/<ID>/ folder and
    the partition -- and never a write target;
  * the run artifact key stays `design` (`tech-design` is an alias): it names
    `steps/create-tech-design/tech-design.md`, falling back to
    `steps/create-design/design.md` for a run recorded before the rename;
  * `acs.py settings migrate` renames a `models.create-design` block to
    `models.create-tech-design` (and its `design-reviewer` to `reviewer`),
    and a settings file that still carries it is named as legacy;
  * `acs.py design list` shows a run's `tech-design.md` -- only that file of
    a per-run folder -- in its feature's LLD group, labelled with its key;
  * the registries: SKILL_LAYER, LOCAL_STEPS, the scaffold's roles, the
    clarification ledger's skill enum, the hook scripts.

Run:  python3 -m unittest tests.acs.test_tech_design_core -v
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import AcsWorkspaceCase, lib, pushd  # noqa: E402,F401
from test_doc_share import DocShareCase  # noqa: E402
from test_design_doc_status import TreeCase, block  # noqa: E402

from acs_lib import (artifacts, commit_plan, design_docs, doc_layout, doc_share,  # noqa: E402
                     migrate_settings, models, run as run_machine, run_docs, skills)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")


# ---------------------------------------------------------------------------
# Where the document lives
# ---------------------------------------------------------------------------

class DocLayoutTest(unittest.TestCase):

    def test_tech_design_is_the_design_side_document_and_design_md_is_not(self):
        self.assertIn("tech-design.md", doc_layout.DOCUMENT_NAMES)
        self.assertNotIn("design.md", doc_layout.DOCUMENT_NAMES)
        self.assertEqual(doc_layout.document_kind("tech-design.md"), "architecture")

    def test_the_legacy_name_resolves_to_the_new_one(self):
        self.assertEqual(doc_layout.canonical_document("design.md"), "tech-design.md")
        self.assertEqual(doc_layout.canonical_document("plan.md"), "plan.md")
        self.assertEqual(doc_layout.legacy_names("tech-design.md"), ("design.md",))
        self.assertEqual(doc_layout.legacy_names("plan.md"), ())
        self.assertEqual(doc_layout.document_kind("design.md"), "architecture")

    def test_a_new_write_goes_to_tech_design_md_in_the_design_folder(self):
        root = "/repo"
        want = os.path.join(root, "docs", "architecture", "lld", "wishlist", "SHOP-7",
                            "tech-design.md")
        settings = {"docs": {"architecture_dir": "docs/architecture"}}
        for name in ("tech-design.md", "design.md"):
            with self.subTest(name=name):
                self.assertEqual(doc_layout.document_target(
                    root, name, "wishlist", "SHOP-7", settings=settings), want)

    def test_readers_fall_back_to_design_md_beside_it_and_in_the_ticket_folder(self):
        root = "/repo"
        settings = {"docs": {"architecture_dir": "docs/architecture"}}
        folder = os.path.join(root, "docs", "architecture", "lld", "wishlist", "SHOP-7")
        legacy = os.path.join(root, "docs", "tickets", "SHOP-7")
        self.assertEqual(doc_layout.document_candidates(
            root, "tech-design.md", "wishlist", "SHOP-7", ticket_id="SHOP-7",
            settings=settings), [
            os.path.join(folder, "tech-design.md"), os.path.join(folder, "design.md"),
            os.path.join(legacy, "tech-design.md"), os.path.join(legacy, "design.md")])


class DocShareTest(unittest.TestCase):

    def test_kept_local_in_its_own_step_folder(self):
        self.assertEqual(doc_share.LOCAL_STEPS["tech-design.md"], "create-tech-design")
        self.assertNotIn("design.md", doc_share.LOCAL_STEPS)
        self.assertEqual(doc_share.local_path("/r", "tech-design.md"), os.path.join(
            "/r", "steps", "create-tech-design", "local", "tech-design.md"))

    def test_the_legacy_local_copy_is_where_create_design_kept_it(self):
        self.assertEqual(doc_share.legacy_local_paths("/r", "tech-design.md"), [
            os.path.join("/r", "steps", "create-design", "local", "design.md")])
        self.assertEqual(doc_share.legacy_local_paths("/r", "plan.md"), [])
        self.assertEqual(doc_share.legacy_local_paths(None, "tech-design.md"), [])

    def test_design_md_is_still_accepted_as_a_document_choice(self):
        self.assertIn("tech-design.md", doc_share.DOC_CHOICES)
        self.assertIn("design.md", doc_share.DOC_ALIASES)


class RunDocsTest(DocShareCase):
    """`artifacts show`: the write target is tech-design.md; a reader finds a
    design.md written before the rename wherever it was kept."""

    def setUp(self):
        super().setUp()
        self.write("docs/architecture/hld/tech-stack.md")

    def design_folder(self, rdir):
        return os.path.join(self.repo, "docs", "architecture", "lld", "export",
                            os.path.basename(rdir))

    def test_the_shared_target_is_tech_design_md(self):
        self.settings(share_run_documents=True)
        rdir = self.new_run()
        layout = run_docs.run_layout(self.ctx(), rdir)
        self.assertEqual(layout["paths"]["tech-design.md"],
                         os.path.join(self.design_folder(rdir), "tech-design.md"))
        self.assertNotIn("design.md", layout["paths"])
        self.assertIsNone(layout["artifacts"]["tech-design.md"])

    def test_a_shared_legacy_design_md_is_read_until_tech_design_md_exists(self):
        self.settings(share_run_documents=True)
        rdir = self.new_run()
        old = self.write(os.path.join(self.design_folder(rdir), "design.md"))
        self.assertEqual(run_docs.document_path(self.ctx(), "tech-design.md", rdir),
                         (old, os.path.join(self.design_folder(rdir), "tech-design.md")))
        new = self.write(os.path.join(self.design_folder(rdir), "tech-design.md"))
        self.assertEqual(run_docs.document_path(self.ctx(), "tech-design.md", rdir)[0], new)

    def test_a_local_legacy_design_md_is_read_from_the_old_step_folder(self):
        self.settings(share_run_documents=False)
        rdir = self.new_run()
        old = self.write(os.path.join(rdir, "steps", "create-design", "local", "design.md"))
        layout = run_docs.run_layout(self.ctx(), rdir)
        self.assertEqual(layout["artifacts"]["tech-design.md"], old)
        self.assertEqual(layout["paths"]["tech-design.md"], os.path.join(
            rdir, "steps", "create-tech-design", "local", "tech-design.md"))

    def test_where_answers_for_the_legacy_name_with_the_new_document(self):
        self.settings(share_run_documents=True)
        rdir = self.new_run()
        info = doc_share.where(self.ctx(), "design.md", rdir)
        self.assertEqual(info["doc"], "tech-design.md")
        self.assertEqual(info["path"], "docs/architecture/lld/export/%s/tech-design.md"
                         % os.path.basename(rdir))

    def test_docs_where_accepts_the_legacy_name(self):
        self.settings(share_run_documents=True)
        self.acs("run", "new", "--prompt", "bulk export")
        out = self.acs("docs", "where", "--doc", "design.md")
        self.assertEqual(out["doc"], "tech-design.md")


class RunArtifactTest(unittest.TestCase):

    def setUp(self):
        import tempfile
        import shutil
        self.rdir = tempfile.mkdtemp(prefix="acs-run-")
        self.addCleanup(shutil.rmtree, self.rdir, True)

    def put(self, *parts):
        path = os.path.join(self.rdir, *parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write("x\n")
        return path

    def test_the_design_artifact_is_the_tech_design(self):
        want = os.path.join(self.rdir, "steps", "create-tech-design", "tech-design.md")
        self.assertEqual(run_machine.ARTIFACT_FILES["design"],
                         ("create-tech-design", "tech-design.md"))
        self.assertEqual(run_machine.artifact_path(self.rdir, "design"), want)
        self.assertEqual(run_machine.artifact_path(self.rdir, "tech-design"), want)

    def test_a_run_recorded_before_the_rename_is_read_from_its_old_step(self):
        old = self.put("steps", "create-design", "design.md")
        self.assertEqual(run_machine.artifact_path(self.rdir, "design"), old)
        self.assertEqual(run_machine.artifact_path(self.rdir, "tech-design"), old)
        new = self.put("steps", "create-tech-design", "tech-design.md")
        self.assertEqual(run_machine.artifact_path(self.rdir, "design"), new)


class TicketArtifactTest(unittest.TestCase):

    def setUp(self):
        import tempfile
        import shutil
        self.root = tempfile.mkdtemp(prefix="acs-art-")
        self.addCleanup(shutil.rmtree, self.root, True)
        self.tdir = os.path.join(self.root, "ws", "SHOP-2")
        os.makedirs(self.tdir)

    def test_tech_design_is_a_ticket_document_and_design_md_its_fallback(self):
        self.assertIn("tech-design.md", artifacts.ARTIFACT_NAMES)
        self.assertIn("design.md", artifacts.ARTIFACT_NAMES, "kept: the legacy name")
        legacy = os.path.join(self.root, "docs", "tickets", "SHOP-2")
        os.makedirs(legacy)
        old = os.path.join(legacy, "design.md")
        with open(old, "w") as fh:
            fh.write("# old\n")
        self.assertEqual(artifacts.artifact_path(self.root, self.tdir, "SHOP-2",
                                                 "tech-design.md"), old)
        part = os.path.join(self.tdir, "tech-design.md")
        with open(part, "w") as fh:
            fh.write("# new\n")
        self.assertEqual(artifacts.artifact_path(self.root, self.tdir, "SHOP-2",
                                                 "tech-design.md"), part)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class MigrateSettingsTest(unittest.TestCase):

    OLD = {"models": {"create-design": {
        "designer": {"model": "opus", "effort": "high"},
        "design-reviewer": {"model": "sonnet", "effort": "medium"}}}}

    def test_the_block_is_renamed_and_so_is_its_judge(self):
        new, notes = migrate_settings.migrate(self.OLD)
        self.assertEqual(new["models"], {"create-tech-design": {
            "designer": {"model": "opus", "effort": "high"},
            "reviewer": {"model": "sonnet", "effort": "medium"}}})
        self.assertIn("models.create-design -> models.create-tech-design (ADR-0135)", notes)
        self.assertIn("models.create-tech-design.design-reviewer -> "
                      "models.create-tech-design.reviewer (ADR-0135)", notes)
        self.assertEqual(self.OLD["models"]["create-design"]["design-reviewer"]["model"],
                         "sonnet", "the input is not mutated")
        models.validate_models(new["models"])

    def test_an_existing_new_block_wins_entry_by_entry(self):
        data = {"models": {
            "create-design": {"designer": {"model": "opus"},
                              "design-reviewer": {"model": "sonnet"}},
            "create-tech-design": {"reviewer": {"model": "haiku"}}}}
        new, _notes = migrate_settings.migrate(data)
        self.assertEqual(new["models"], {"create-tech-design": {
            "designer": {"model": "opus"}, "reviewer": {"model": "haiku"}}})

    def test_a_current_file_is_left_alone(self):
        data = {"models": {"create-tech-design": {"reviewer": {"model": "opus"}}}}
        self.assertEqual(migrate_settings.migrate(data), (data, []))

    def test_the_old_block_is_named_as_legacy(self):
        problems = migrate_settings.legacy_problems(self.OLD)
        self.assertEqual(len(problems), 1)
        self.assertIn("models.create-design is now models.create-tech-design", problems[0])
        self.assertEqual(migrate_settings.legacy_problems(
            {"models": {"create-tech-design": {}}}), [])


class MigrateSettingsCliTest(AcsWorkspaceCase):

    def test_the_cli_rewrites_the_file(self):
        path = os.path.join(self.repo, ".acs", "settings.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            json.dump(dict(MigrateSettingsTest.OLD, ticket_prefix="SHOP"), fh)
        out = self.run_script("acs.py", "settings", "migrate", "--write")
        self.assertEqual(out.returncode, 0, out.stderr)
        with open(path) as fh:
            written = json.load(fh)
        self.assertEqual(sorted(written["models"]), ["create-tech-design"])
        self.assertEqual(sorted(written["models"]["create-tech-design"]),
                         ["designer", "reviewer"])
        self.assertEqual(written["ticket_prefix"], "SHOP")


class ModelsTest(unittest.TestCase):

    def test_the_scaffold_names_the_renamed_skill_and_roles(self):
        inv = models.inventory()
        self.assertEqual(inv["create-tech-design"], ["designer", "reviewer"])
        self.assertNotIn("create-design", inv)

    def test_design_reviewer_is_no_role_any_more(self):
        self.assertNotIn("design-reviewer", skills.ROLE_KINDS)
        self.assertNotIn("design-reviewer", models.covered_roles())

    def test_the_settings_schema_and_this_repos_settings_name_it(self):
        with open(os.path.join(PLUGIN, "schemas", "settings.schema.json")) as fh:
            schema = json.load(fh)
        props = schema["properties"]["models"]["properties"]
        self.assertIn("create-tech-design", props)
        self.assertNotIn("create-design", props)
        with open(os.path.join(REPO_ROOT, ".acs", "settings.json")) as fh:
            ours = json.load(fh)
        if "models" in ours:
            self.assertNotIn("create-design", ours["models"])
            models.validate_models(ours["models"])


# ---------------------------------------------------------------------------
# `acs.py design list`
# ---------------------------------------------------------------------------

class DesignListTest(TreeCase):

    def listing(self, **kw):
        return design_docs.list_documents(self.root, **kw)

    def seed_feature(self):
        self.put("docs/architecture/lld/wishlist/data/erd.md", block(feature="wishlist"))
        self.put("docs/architecture/lld/wishlist/SHOP-7/tech-design.md",
                 block(feature="wishlist"))
        self.put("docs/architecture/lld/wishlist/SHOP-7/api-contract.md",
                 block(feature="wishlist"))                 # a per-run record: not listed
        self.put("docs/architecture/lld/wishlist/SHOP-6/design.md",
                 block(feature="wishlist"))                 # legacy: not listed

    def test_a_tech_design_is_listed_in_its_features_lld_group(self):
        self.seed_feature()
        groups = self.listing()["groups"]
        self.assertEqual([(g["phase"], g["key"], g["label"]) for g in groups],
                         [("design", "lld/wishlist", "LLD wishlist")])
        docs = groups[0]["docs"]
        self.assertEqual([d["path"] for d in docs], [
            "docs/architecture/lld/wishlist/SHOP-7/tech-design.md",
            "docs/architecture/lld/wishlist/data/erd.md"])
        tech = docs[0]
        self.assertEqual((tech["key"], tech["label"]), ("SHOP-7", "SHOP-7 tech design"))
        self.assertEqual((tech["status"], tech["allowed"]), ("proposed", ["approved",
                                                                          "deprecated"]))
        self.assertNotIn("key", docs[1], "a living document carries no run key")

    def test_a_tech_design_alone_makes_its_features_group(self):
        self.put("docs/architecture/lld/export/run-20261005-1/tech-design.md",
                 block(feature="export"))
        groups = self.listing(feature="export")["groups"]
        self.assertEqual([(g["key"], g["feature"]) for g in groups], [("lld/export", "export")])
        self.assertEqual(groups[0]["docs"][0]["key"], "run-20261005-1")

    def test_feature_and_phase_filters_keep_it(self):
        self.seed_feature()
        self.assertEqual(self.listing(phase="discovery")["groups"], [])
        self.assertEqual(self.listing(feature="export")["groups"], [])
        self.assertEqual(len(self.listing(phase="design", feature="wishlist")["groups"][0]
                             ["docs"]), 2)


# ---------------------------------------------------------------------------
# Registries
# ---------------------------------------------------------------------------

class RegistryTest(unittest.TestCase):

    def test_hook_scripts_carry_the_new_name(self):
        for kind in ("pre", "post"):
            with self.subTest(kind=kind):
                path = os.path.join(SCRIPTS, "%s-create-tech-design.py" % kind)
                with open(path, encoding="utf-8") as fh:
                    body = fh.read()
                self.assertIn('run_%s("create-tech-design")' % kind, body)
                self.assertNotIn("create-design", body)
                self.assertFalse(os.path.exists(
                    os.path.join(SCRIPTS, "%s-create-design.py" % kind)))

    def test_its_paths_commit_with_the_design_docs(self):
        self.assertEqual(commit_plan.SKILL_LAYER["create-tech-design"], "design")
        self.assertIn("tech_design_path", commit_plan.STATE_PATH_KEYS)
        self.assertIn("design_path", commit_plan.STATE_PATH_KEYS)

    def test_the_subject_gate_is_keyed_by_the_new_name(self):
        self.assertIs(lib.SUBJECT_GATES["create-tech-design"], lib.gate_create_tech_design)
        self.assertNotIn("create-design", lib.SUBJECT_GATES)
        self.assertFalse(hasattr(lib, "gate_create_design"))

    def test_the_clarification_ledger_accepts_the_new_name(self):
        with open(os.path.join(PLUGIN, "schemas", "clarifications.schema.json")) as fh:
            schema = json.load(fh)
        enum = json.dumps(schema)
        self.assertIn('"create-tech-design"', enum)
        self.assertIn('"create-design"', enum, "historical: an older ledger still validates")


if __name__ == "__main__":
    unittest.main()
