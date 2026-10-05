"""Share or keep local, and confirm where documents go (ADR-0132):
`acs_lib.doc_share`, `doc_layout.resolve_dir`, `acs.py docs where|decide`, and
what the decision changes in `artifacts show`, `analysis publish` and the
commit plan.

Pinned here, against real temp repos and workspaces:

  * the resolution source of each phase folder: setting | discovered | default;
  * the where matrix: (setting | discovered | default) x (share true | false |
    undecided) for a run document, and the living documents (always shared,
    asked location only);
  * `docs decide`: the user scope writes `.acs/settings.local.json` (created,
    minimal, kept out of git), the team scope and `--location` merge into
    `.acs/settings.json` touching no other key, bad input writes nothing, a
    more specific answer that overrides the one just saved is warned about;
  * `artifacts show`: `paths` honours the decision (undecided -> null plus
    `needs`), `artifacts` reads a local document;
  * `analysis publish` refuses an undecided write naming `acs.py docs decide`,
    and a LOCAL decision publishes into the run folder, recorded `local`;
  * the commit plan never lists a local document, in groups or left out.

Run:  python3 -m unittest tests.acs.test_doc_share -v
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import AcsWorkspaceCase, lib, pushd  # noqa: E402
from test_analysis_loop import AnalysisLoopCase, TicketlessAnalysisCase  # noqa: E402

from acs_lib import doc_layout, doc_share, requirements as R, run_docs  # noqa: E402
from acs_lib import settings as settings_mod  # noqa: E402

REPO_ID = "acme-shop"
BASE = {"ticket_prefix": "SHOP", "tests": {"coverage": 90}}


class DocShareCase(AcsWorkspaceCase):

    def setUp(self):
        super().setUp()
        self.home = tempfile.mkdtemp(prefix="acs-home-")
        self.addCleanup(shutil.rmtree, self.home, True)

    def env(self):
        return dict(os.environ, HOME=self.home)

    def acs(self, *argv, code=0):
        out = self.run_script("acs.py", *argv, env=self.env())
        self.assertEqual(out.returncode, code, out.stdout + out.stderr)
        return json.loads(out.stdout) if code == 0 else out

    def ctx(self):
        with pushd(self.repo):
            return lib.build_context(self.repo)

    def settings(self, **docs):
        self.write_settings(dict(BASE, docs=docs) if docs else dict(BASE))

    def mkdir(self, rel):
        os.makedirs(os.path.join(self.repo, *rel.split("/")), exist_ok=True)

    def write(self, rel, text="x\n"):
        path = rel if os.path.isabs(rel) else os.path.join(self.repo, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def raw(self, rel):
        with open(os.path.join(self.repo, *rel.split("/")), encoding="utf-8") as fh:
            return fh.read()

    def new_run(self, feature="export", run_id=None):
        wf_path = lib.default_workflow_path()
        wf = lib.validate_workflow_file(wf_path)
        _run_id, rdir, _doc = lib.create_run(lib.repo_dir(self.ws, REPO_ID),
                                             {"kind": "prompt", "text": "bulk export"}, wf,
                                             wf_path, run_id=run_id)
        doc = lib.load_run(rdir)
        doc["driver"] = "ship"  # delivered: a Development run
        lib.save_run(rdir, doc)
        if feature:
            R.refine(rdir, self.ctx(), {"feature": feature})
        return rdir

    def ignored(self, rel):
        return subprocess.run(["git", "-C", self.repo, "check-ignore", "-q", rel]).returncode == 0


# ---------------------------------------------------------------------------
# How a phase folder was resolved
# ---------------------------------------------------------------------------

class TestResolutionSource(DocShareCase):

    def test_nothing_on_disk_is_only_the_default(self):
        self.assertEqual(doc_layout.resolve_dirs(self.repo, {}), {
            "prd": {"path": "docs/product", "source": "default"},
            "architecture": {"path": "docs/architecture", "source": "default"},
            "development": {"path": "docs/development", "source": "default"}})

    def test_an_existing_folder_is_discovered(self):
        self.write("handbook/prd.md")
        self.write("design/hld/tech-stack.md")
        self.mkdir("docs/development")
        self.assertEqual(doc_layout.resolve_dirs(self.repo, {}), {
            "prd": {"path": "handbook", "source": "discovered"},
            "architecture": {"path": "design", "source": "discovered"},
            "development": {"path": "docs/development", "source": "discovered"}})

    def test_an_existing_default_folder_without_its_marker_is_discovered(self):
        self.mkdir("docs/product")
        self.mkdir("docs/architecture")
        self.assertEqual(doc_layout.resolve_dir(self.repo, "prd", {})["source"], "discovered")
        self.assertEqual(doc_layout.resolve_dir(self.repo, "architecture", {})["source"],
                         "discovered")

    def test_a_setting_is_the_users_answer_even_before_the_folder_exists(self):
        settings = {"docs": {"prd_dir": "p/", "architecture_dir": "a",
                             "development_dir": "d/dev"}}
        self.assertEqual(doc_layout.resolve_dirs(self.repo, settings), {
            "prd": {"path": "p", "source": "setting"},
            "architecture": {"path": "a", "source": "setting"},
            "development": {"path": "d/dev", "source": "setting"}})

    def test_no_checkout_and_an_unknown_kind(self):
        self.assertEqual(doc_layout.resolve_dir(None, "prd"),
                         {"path": "docs/product", "source": "default"})
        with self.assertRaises(ValueError):
            doc_layout.resolve_dir(self.repo, "tickets", {})

    def test_document_kinds(self):
        self.assertEqual(doc_layout.document_kind("analysis.md", "discovery"), "prd")
        self.assertEqual(doc_layout.document_kind("analysis.md"), "development")
        self.assertEqual(doc_layout.document_kind("design.md"), "architecture")
        self.assertEqual(doc_layout.document_kind("test-cases.md"), "development")
        self.assertIsNone(doc_layout.document_kind("ticket.md"))


# ---------------------------------------------------------------------------
# The share setting
# ---------------------------------------------------------------------------

class TestShareSetting(DocShareCase):

    def test_validated_as_a_boolean(self):
        for value in ("yes", 1, None, []):
            with self.subTest(value=value), self.assertRaises(lib.GateError):
                lib.validate_settings(dict(BASE, docs={"share_run_documents": value}),
                                      self.repo)
        for value in (True, False):
            lib.validate_settings(dict(BASE, docs={"share_run_documents": value}), self.repo)

    def test_absent_is_undecided(self):
        self.assertIsNone(settings_mod.share_run_documents({}))
        self.assertIsNone(settings_mod.share_run_documents({"docs": {"prd_dir": "p"}}))
        self.assertIs(settings_mod.share_run_documents(
            {"docs": {"share_run_documents": False}}), False)

    def test_an_invalid_value_stops_a_step(self):
        self.settings(share_run_documents="no")
        out = self.acs("docs", "where", "--doc", "plan.md", code=2)
        self.assertIn("docs.share_run_documents", out.stderr)


# ---------------------------------------------------------------------------
# where: the matrix
# ---------------------------------------------------------------------------

class TestWhereMatrix(DocShareCase):

    LOCATIONS = ("setting", "discovered", "default")
    SHARES = (True, False, None)

    def arrange(self, location, share):
        docs = {}
        if location == "setting":
            docs["development_dir"] = "engineering/changes"
        elif location == "discovered":
            self.mkdir("docs/development")
        if share is not None:
            docs["share_run_documents"] = share
        self.settings(**docs)

    def test_the_matrix_for_a_run_document(self):
        for location in self.LOCATIONS:
            for share in self.SHARES:
                with self.subTest(location=location, share=share):
                    self.setUp()
                    self.arrange(location, share)
                    rdir = self.new_run()
                    run_id = os.path.basename(rdir)
                    info = doc_share.where(self.ctx(), "plan.md", rdir)
                    folder = "engineering/changes" if location == "setting" \
                        else "docs/development"
                    expected_needs = (["share"] if share is None else []) + \
                        (["location"] if location == "default" and share is not False else [])
                    self.assertEqual(info["needs"], expected_needs)
                    self.assertEqual(info["share"], share)
                    self.assertEqual((info["location_kind"], info["location"],
                                      info["location_source"], info["proposed_path"]),
                                     ("development", folder, location, folder))
                    shared = "%s/export/%s/plan.md" % (folder, run_id)
                    self.assertEqual(info["shared_path"], shared)
                    self.assertEqual(info["local_path"], "steps/create-impl-plan/local/plan.md")
                    if expected_needs:
                        self.assertIsNone(info["path"])
                        self.assertIsNone(info["abs_path"])
                    elif share:
                        self.assertEqual(info["path"], shared)
                        self.assertEqual(info["abs_path"],
                                         os.path.join(self.repo, *shared.split("/")))
                    else:
                        self.assertEqual(info["path"], "steps/create-impl-plan/local/plan.md")
                        self.assertEqual(info["abs_path"], os.path.join(
                            rdir, "steps", "create-impl-plan", "local", "plan.md"))
                    self.assertEqual(info["kind"], "run")
                    self.assertEqual(info["decide"], "acs.py docs decide")

    def test_each_document_is_kept_in_its_own_steps_folder(self):
        self.settings(share_run_documents=False)
        rdir = self.new_run()
        for name, skill in (("analysis.md", "analyze-requirements"),
                            ("plan.md", "create-impl-plan"),
                            ("test-cases.md", "create-test-docs"),
                            ("design.md", "create-design"),
                            ("api-contract.md", "create-api-contract")):
            with self.subTest(name=name):
                info = doc_share.where(self.ctx(), name, rdir)
                self.assertEqual(info["path"], "steps/%s/local/%s" % (skill, name))

    def test_a_design_document_asks_for_the_architecture_folder(self):
        self.settings(share_run_documents=True)
        rdir = self.new_run()
        info = doc_share.where(self.ctx(), "design.md", rdir)
        self.assertEqual((info["location_kind"], info["needs"], info["proposed_path"]),
                         ("architecture", ["location"], "docs/architecture"))
        self.write("docs/architecture/hld/tech-stack.md")
        info = doc_share.where(self.ctx(), "api-contract.md", rdir)
        self.assertEqual(info["needs"], [])
        self.assertEqual(info["path"], "docs/architecture/lld/export/%s/api-contract.md"
                         % os.path.basename(rdir))

    def test_a_local_document_needs_no_feature_and_a_shared_one_has_no_path_without(self):
        self.settings(share_run_documents=False)
        rdir = self.new_run(feature=None)
        self.assertEqual(doc_share.where(self.ctx(), "plan.md", rdir)["path"],
                         "steps/create-impl-plan/local/plan.md")
        self.settings(share_run_documents=True, development_dir="docs/development")
        info = doc_share.where(self.ctx(), "plan.md", rdir)
        self.assertEqual((info["needs"], info["path"], info["feature"]), ([], None, None))

    def test_without_a_run_a_local_document_has_no_path(self):
        self.settings(share_run_documents=False)
        info = doc_share.where(self.ctx(), "plan.md")
        self.assertEqual((info["needs"], info["path"], info["local_path"]), ([], None, None))

    def test_the_living_documents_are_always_shared_and_ask_location_only(self):
        self.settings()
        for doc, kind, default in (("living:prd", "prd", "docs/product"),
                                   ("living:architecture", "architecture",
                                    "docs/architecture")):
            with self.subTest(doc=doc):
                info = doc_share.where(self.ctx(), doc)
                self.assertEqual((info["kind"], info["share"], info["share_scope"]),
                                 ("living", True, "living"))
                self.assertEqual((info["location_kind"], info["needs"], info["path"],
                                  info["proposed_path"]), (kind, ["location"], None, default))
        self.write("spec/prd.md")
        self.settings(architecture_dir="arch")
        prd = doc_share.where(self.ctx(), "living:prd")
        self.assertEqual((prd["needs"], prd["path"], prd["location_source"]),
                         ([], "spec", "discovered"))
        arch = doc_share.where(self.ctx(), "living:architecture")
        self.assertEqual((arch["needs"], arch["path"], arch["location_source"]),
                         ([], "arch", "setting"))

    def test_a_discovery_analysis_is_the_features_living_one(self):
        self.settings(share_run_documents=False)
        rdir = self.new_run()
        R.refine(rdir, self.ctx(), {"phase": "discovery"})
        info = doc_share.where(self.ctx(), "analysis.md", rdir)
        self.assertEqual((info["kind"], info["share"], info["location_kind"], info["needs"]),
                         ("living", True, "prd", ["location"]),
                         "a saved 'keep local' never applies to a living document")
        self.mkdir("docs/product")
        info = doc_share.where(self.ctx(), "analysis.md", rdir)
        self.assertEqual(info["path"], "docs/product/features/export/analysis.md")

    def test_an_unknown_document_is_refused(self):
        with self.assertRaises(lib.GateError):
            doc_share.where(self.ctx(), "ticket.md")
        out = self.acs("docs", "where", "--doc", "notes.md", code=2)
        self.assertIn("invalid choice", out.stderr)

    def test_the_scope_of_the_saved_answer_is_reported(self):
        self.settings(share_run_documents=True)
        info = doc_share.where(self.ctx(), "plan.md")
        self.assertEqual((info["share"], info["share_scope"]), (True, "team"))
        self.assertEqual(info["share_file"], os.path.join(self.repo, ".acs", "settings.json"))
        self.write(".acs/settings.local.json",
                   json.dumps({"docs": {"share_run_documents": False}}))
        info = doc_share.where(self.ctx(), "plan.md")
        self.assertEqual((info["share"], info["share_scope"]), (False, "user"),
                         "this machine's answer takes precedence")
        self.assertEqual(doc_share.describe_choice(info), "kept local (user default)")

    def test_describe_choice(self):
        self.assertEqual(doc_share.describe_choice({"needs": ["share"]}),
                         "undecided (needs share)")
        self.assertEqual(doc_share.describe_choice(
            {"needs": [], "share": True, "path": "docs/development/x/R/plan.md"}),
            "shared to docs/development/x/R/plan.md")
        self.assertEqual(doc_share.describe_choice(
            {"needs": [], "share": False, "share_scope": "team"}), "kept local (team default)")

    def test_require_decided_names_the_command_and_both_questions(self):
        self.settings()
        info = doc_share.where(self.ctx(), "plan.md")
        with self.assertRaises(lib.GateError) as caught:
            doc_share.require_decided(info, verb="publish")
        message = str(caught.exception)
        for part in ("refusing to publish plan.md", "acs.py docs decide",
                     "--share yes|no --scope user|team", "--location development=",
                     "docs/development"):
            self.assertIn(part, message)
        self.settings(share_run_documents=False)
        decided = doc_share.where(self.ctx(), "plan.md")
        self.assertIs(doc_share.require_decided(decided), decided)

    def test_where_cli_uses_the_current_run_or_none(self):
        self.settings(share_run_documents=False)
        out = self.acs("docs", "where", "--doc", "plan.md")
        self.assertTrue(out["ok"])
        self.assertIsNone(out["run_id"])
        run = self.acs("run", "new", "--prompt", "bulk export")
        out = self.acs("docs", "where", "--doc", "plan.md")
        self.assertEqual((out["run_id"], out["path"]),
                         (run["run_id"], "steps/create-impl-plan/local/plan.md"))
        out = self.acs("docs", "where", "--doc", "test-cases.md", "--run", run["run_id"])
        self.assertEqual(out["path"], "steps/create-test-docs/local/test-cases.md")
        self.acs("docs", "where", "--doc", "plan.md", "--run", "nope", code=2)


# ---------------------------------------------------------------------------
# decide: what is written, where, and nothing else
# ---------------------------------------------------------------------------

class TestDecide(DocShareCase):

    def team(self):
        return json.loads(self.raw(".acs/settings.json"))

    def test_the_user_scope_creates_a_minimal_local_file_kept_out_of_git(self):
        before = self.raw(".acs/settings.json")
        self.assertFalse(self.ignored(".acs/settings.local.json"))
        out = self.acs("docs", "decide", "--share", "no", "--scope", "user", "--doc", "plan.md")
        local = os.path.join(self.repo, ".acs", "settings.local.json")
        self.assertEqual(json.loads(self.raw(".acs/settings.local.json")),
                         {"docs": {"share_run_documents": False}})
        self.assertEqual(self.raw(".acs/settings.local.json"),
                         '{\n  "docs": {\n    "share_run_documents": false\n  }\n}\n')
        self.assertEqual(self.raw(".acs/settings.json"), before, "the team file is untouched")
        self.assertTrue(self.ignored(".acs/settings.local.json"))
        self.assertIn(".acs/settings.local.json", self.raw(".git/info/exclude"))
        self.assertNotIn(".acs/settings.local.json",
                         subprocess.run(["git", "-C", self.repo, "status", "--porcelain"],
                                        capture_output=True, text=True).stdout)
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".gitignore")),
                         "the repo's own .gitignore is not acs's to change here")
        self.assertEqual(out["written"], [{"scope": "user", "file": local, "changed": True,
                                           "keys": ["docs.share_run_documents"],
                                           "ignored_via": ".git/info/exclude"}])
        self.assertEqual((out["doc"], out["share"], out["share_scope"], out["needs"]),
                         ("plan.md", False, "user", []))
        again = self.acs("docs", "decide", "--share", "no", "--scope", "user")
        self.assertEqual((again["written"][0]["changed"], again["written"][0]["ignored_via"]),
                         (False, "already ignored"))
        self.assertEqual(self.raw(".git/info/exclude").count(".acs/settings.local.json"), 1)

    def test_an_existing_ignore_rule_is_respected(self):
        self.write(".gitignore", ".acs/settings.local.json\n")
        out = self.acs("docs", "decide", "--share", "yes", "--scope", "user")
        self.assertEqual(out["written"][0]["ignored_via"], "already ignored")
        self.assertNotIn("settings.local.json", self.raw(".git/info/exclude"))

    def test_the_team_scope_merges_into_settings_json_touching_nothing_else(self):
        self.write_settings(dict(BASE, docs={"prd_dir": "handbook"}, extra={"keep": [1, 2]}))
        out = self.acs("docs", "decide", "--share", "yes", "--scope", "team")
        self.assertEqual(self.team(), dict(BASE, docs={"prd_dir": "handbook",
                                                       "share_run_documents": True},
                                           extra={"keep": [1, 2]}))
        self.assertTrue(self.raw(".acs/settings.json").startswith('{\n  "ticket_prefix"'))
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".acs", "settings.local.json")))
        self.assertNotIn("ignored_via", out["written"][0])
        self.assertEqual(set(out["documents"]), set(doc_share.DOC_CHOICES))
        self.assertEqual(out["documents"]["plan.md"]["share_scope"], "team")

    def test_a_missing_team_file_is_created(self):
        os.unlink(os.path.join(self.repo, ".acs", "settings.json"))
        self.acs("docs", "decide", "--location", "development=engineering/changes/")
        self.assertEqual(self.team(), {"docs": {"development_dir": "engineering/changes"}})

    def test_location_answers_are_team_settings_and_change_the_source(self):
        self.acs("run", "new", "--prompt", "bulk export")
        out = self.acs("docs", "decide", "--location", "development=eng/dev",
                       "--location", "architecture_dir=design", "--share", "yes",
                       "--scope", "team", "--doc", "design.md")
        self.assertEqual(self.team()["docs"], {"development_dir": "eng/dev",
                                               "architecture_dir": "design",
                                               "share_run_documents": True})
        self.assertEqual(len(out["written"]), 1, "one file, one merge")
        self.assertEqual(out["written"][0]["keys"], [
            "docs.architecture_dir", "docs.development_dir", "docs.share_run_documents"])
        self.assertEqual((out["location"], out["location_source"], out["needs"]),
                         ("design", "setting", []))
        self.assertIsNone(out["path"], "no feature yet to file a shared design under")

    def test_keep_local_is_saved_without_a_location(self):
        out = self.acs("docs", "decide", "--share", "no", "--scope", "team", "--doc",
                       "analysis.md")
        self.assertEqual(self.team()["docs"], {"share_run_documents": False})
        self.assertEqual((out["needs"], out["share"]), ([], False))
        self.assertFalse(os.path.exists(os.path.join(self.repo, "docs")))

    def test_bad_input_writes_nothing(self):
        before = self.raw(".acs/settings.json")
        for argv, needle in ((("--share", "yes"), "go together"),
                             (("--scope", "team"), "go together"),
                             ((), "nothing to record"),
                             (("--location", "tickets=docs/t"), "KIND=PATH"),
                             (("--location", "development"), "KIND=PATH"),
                             (("--location", "development=/abs"), "repo-relative"),
                             (("--location", "prd=../up"), "no '..'"),
                             (("--location", "prd= "), "non-empty"),
                             (("--share", "no", "--scope", "user", "--doc", "x.md"),
                              "unknown document")):
            with self.subTest(argv=argv):
                out = self.acs("docs", "decide", *argv, code=2)
                self.assertIn(needle, out.stderr)
        self.assertEqual(self.raw(".acs/settings.json"), before)
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".acs", "settings.local.json")))

    def test_an_unreadable_settings_file_is_never_overwritten(self):
        self.write(".acs/settings.local.json", "{not json")
        out = self.acs("docs", "decide", "--share", "no", "--scope", "user", code=2)
        self.assertIn("not readable JSON", out.stderr)
        self.assertEqual(self.raw(".acs/settings.local.json"), "{not json")

    def test_an_answer_overridden_by_a_more_specific_file_is_warned_about(self):
        self.acs("docs", "decide", "--share", "no", "--scope", "user")
        out = self.acs("docs", "decide", "--share", "yes", "--scope", "team",
                       "--doc", "plan.md")
        self.assertEqual(len(out["warnings"]), 1)
        self.assertIn("settings.local.json", out["warnings"][0])
        self.assertEqual((out["share"], out["share_scope"]), (False, "user"))
        self.assertTrue(self.team()["docs"]["share_run_documents"])


class TestRunScopeAndOverview(DocShareCase):
    """When the user cannot be asked (headless), a skill keeps the documents
    local for THIS run only and saves nothing: `--scope run`."""

    def test_a_run_choice_needs_a_run_and_saves_nothing(self):
        before = self.raw(".acs/settings.json")
        out = self.acs("docs", "decide", "--share", "no", "--scope", "run", code=2)
        self.assertIn("--scope run", out.stderr)
        run = self.acs("run", "new", "--prompt", "bulk export")
        out = self.acs("docs", "decide", "--share", "no", "--scope", "run", "--doc", "plan.md")
        choice = os.path.join(run["path"], "docs-choice.json")
        self.assertEqual(out["written"], [{"scope": "run", "changed": True, "file": choice,
                                           "keys": ["share_run_documents"]}])
        self.assertEqual((out["share"], out["share_scope"], out["share_file"], out["needs"],
                          out["path"]),
                         (False, "run", choice, [], "steps/create-impl-plan/local/plan.md"))
        self.assertEqual(self.raw(".acs/settings.json"), before)
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".acs", "settings.local.json")))
        self.assertEqual(doc_share.describe_choice(out), "kept local (this run only)")
        other = self.acs("run", "new", "--prompt", "another change")
        out = self.acs("docs", "where", "--doc", "plan.md", "--run", other["run_id"])
        self.assertEqual((out["share"], out["needs"]), (None, ["share", "location"]),
                         "another run is not covered by it")

    def test_a_run_choice_takes_precedence_and_publish_honours_it(self):
        self.settings(share_run_documents=True)
        rdir = self.new_run()
        doc_share.record_run_choice(rdir, False)
        info = doc_share.where(self.ctx(), "analysis.md", rdir)
        self.assertEqual((info["share"], info["share_scope"]), (False, "run"))
        self.assertEqual(run_docs.run_layout(self.ctx(), rdir)["paths"]["analysis.md"],
                         doc_share.local_path(rdir, "analysis.md"))
        with self.assertRaises(lib.GateError):
            doc_share.record_run_choice(None, False)

    def test_where_without_a_doc_is_the_setup_view(self):
        self.write("handbook/prd.md")
        self.acs("docs", "decide", "--share", "no", "--scope", "user")
        out = self.acs("docs", "where")
        self.assertEqual((out["ok"], out["share"], out["share_scope"], out["run_id"]),
                         (True, False, "user", None))
        self.assertEqual(out["kinds"], {
            "prd": {"path": "handbook", "source": "discovered"},
            "architecture": {"path": "docs/architecture", "source": "default"},
            "development": {"path": "docs/development", "source": "default"}})
        self.assertEqual(set(out["documents"]), set(doc_share.DOC_CHOICES))
        self.assertEqual(out["documents"]["living:architecture"]["needs"], ["location"])
        self.assertEqual(out["documents"]["plan.md"]["needs"], [])

    def test_the_team_file_is_team_even_when_home_is_the_repo(self):
        self.settings(share_run_documents=False)
        env = dict(os.environ, HOME=self.repo)
        out = self.run_script("acs.py", "docs", "where", "--doc", "plan.md", env=env)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout)["share_scope"], "team")
        home = os.path.join(self.home, ".acs", "settings.json")
        self.write(home, json.dumps({"docs": {"share_run_documents": True}}))
        with pushd(self.repo):
            from unittest import mock
            with mock.patch.dict(os.environ, {"HOME": self.home}):
                self.assertEqual(doc_share.share_source(self.repo)[1:], ("team",
                                 os.path.join(self.repo, ".acs", "settings.json")))
                os.unlink(os.path.join(self.repo, ".acs", "settings.json"))
                self.assertEqual(doc_share.share_source(self.repo), (True, "user", home))


# ---------------------------------------------------------------------------
# artifacts show
# ---------------------------------------------------------------------------

class TestArtifactsShow(DocShareCase):

    def test_undecided_paths_are_null_with_needs(self):
        self.settings()
        rdir = self.new_run()
        layout = run_docs.run_layout(self.ctx(), rdir)
        self.assertTrue(all(v is None for v in layout["paths"].values()))
        self.assertEqual(layout["needs"]["plan.md"], ["share", "location"])
        self.assertIsNone(layout["share"])
        self.assertEqual(layout["locations"]["development"],
                         {"path": "docs/development", "source": "default"})
        self.assertEqual(layout["shared_paths"]["plan.md"], os.path.join(
            self.repo, "docs", "development", "export", os.path.basename(rdir), "plan.md"))

    def test_local_paths_point_into_the_run_and_a_local_doc_is_read(self):
        self.settings(share_run_documents=False)
        run = self.acs("run", "new", "--prompt", "bulk export")
        rdir = run["path"]
        out = self.acs("artifacts", "show")
        local = os.path.join(rdir, "steps", "create-impl-plan", "local", "plan.md")
        self.assertEqual(out["paths"]["plan.md"], local)
        self.assertEqual(out["needs"]["plan.md"], [])
        self.assertIs(out["share"], False)
        self.assertIsNone(out["artifacts"]["plan.md"])
        self.write(local, "# plan\n")
        out = self.acs("artifacts", "show")
        self.assertEqual(out["artifacts"]["plan.md"], local)
        self.assertFalse(os.path.exists(os.path.join(self.repo, "docs")))

    def test_a_local_doc_is_still_read_after_the_choice_flips_to_shared(self):
        self.settings(share_run_documents=False)
        rdir = self.new_run()
        local = self.write(os.path.join(rdir, "steps", "create-test-docs", "local",
                                        "test-cases.md"), "# cases\n")
        self.settings(share_run_documents=True, development_dir="docs/development")
        layout = run_docs.run_layout(self.ctx(), rdir)
        self.assertEqual(layout["paths"]["test-cases.md"],
                         layout["shared_paths"]["test-cases.md"])
        self.assertEqual(layout["artifacts"]["test-cases.md"], local)
        shared = self.write(layout["shared_paths"]["test-cases.md"], "# shared\n")
        self.assertEqual(run_docs.run_layout(self.ctx(), rdir)["artifacts"]["test-cases.md"],
                         shared, "the decided side is read first")

    def test_shared_paths_are_the_phase_folders(self):
        self.settings(share_run_documents=True)
        self.mkdir("docs/development")
        rdir = self.new_run()
        layout = run_docs.run_layout(self.ctx(), rdir)
        self.assertEqual(layout["paths"]["plan.md"], layout["shared_paths"]["plan.md"])
        self.assertIsNone(layout["paths"]["design.md"], "the architecture folder is undecided")
        self.assertEqual(layout["needs"]["design.md"], ["location"])


# ---------------------------------------------------------------------------
# analysis publish, and the commit plan
# ---------------------------------------------------------------------------

class PublishCase(AnalysisLoopCase):
    DOCS = None  # undecided

    def decide_shared(self):
        settings = dict(BASE)
        if self.DOCS is not None:
            settings["docs"] = dict(self.DOCS)
        self.write_settings(settings)

    def git(self, *args):
        return subprocess.run(["git", "-C", self.repo] + list(args), capture_output=True,
                              text=True, check=True).stdout


class TestPublishUndecided(PublishCase):

    def refused(self, verb):
        out = self.run_script("acs.py", "analysis", verb, "--run", self.tid)
        self.assertEqual(out.returncode, 2, out.stdout + out.stderr)
        return out.stderr

    def test_an_undecided_publish_is_refused_naming_docs_decide(self):
        self.to_publish()
        self.assertIn("acs.py docs decide", self.refused("publish"))

    def test_nothing_is_written_to_the_repo_and_the_loop_stays_at_publish(self):
        self.to_publish()
        stderr = self.refused("publish")
        self.assertIn("share run documents in the repo or keep them local", stderr)
        self.assertIn("development folder", stderr)
        self.assertFalse(os.path.exists(os.path.join(self.repo, "docs")))
        self.assertIsNone(self.loop().get("publication"))
        self.assertEqual(self.next()["action"], "publish")

    def test_a_shared_choice_with_an_unconfirmed_folder_is_still_refused(self):
        self.to_publish()
        self.write_settings(dict(BASE, docs={"share_run_documents": True}))
        stderr = self.refused("publish")
        self.assertIn("development folder, which does not exist yet", stderr)
        self.assertNotIn("share run documents", stderr)
        out = self.run_script("acs.py", "docs", "decide", "--location",
                              "development=docs/development")
        self.assertEqual(out.returncode, 0, out.stderr)
        pub = self.cli("publish")["publication"]
        self.assertFalse(pub["local"])
        self.assertTrue(pub["path"].startswith(os.path.join(self.repo, "docs", "development")))


class TestPublishLocal(PublishCase):
    DOCS = {"share_run_documents": False}

    def test_a_local_publish_targets_the_run_folder_and_records_it(self):
        self.to_publish()
        pub = self.cli("publish")["publication"]
        target = os.path.join(self.r, "steps", "analyze-requirements", "local", "analysis.md")
        self.assertEqual(pub["path"], target)
        self.assertEqual((pub["local"], pub["files"], pub["docs_dir"], pub["share_scope"]),
                         (True, [], None, "team"))
        self.assertEqual(pub["destination"], "kept local (team default)")
        with open(target, "rb") as a, open(os.path.join(self.r, "steps", "analyze-requirements",
                                                        "analysis.md"), "rb") as b:
            self.assertEqual(a.read(), b.read())
        self.assertFalse(os.path.exists(os.path.join(self.repo, "docs")),
                         "no docs folder is created for a local document")
        self.assertEqual(self.cli("record-publication")["next"]["action"], "completed")
        layout = run_docs.run_layout(self.ctx(), self.r)
        self.assertEqual(layout["artifacts"]["analysis.md"], target)

    def ctx(self):
        with pushd(self.repo):
            return lib.build_context(self.repo)

    def test_the_commit_plan_never_lists_a_local_document(self):
        self.to_publish()
        self.cli("publish")
        from acs_lib import commit_plan
        records = commit_plan.Records(self.repo, self.tid)
        records.read_run(self.r)
        self.assertFalse([p for p in records.claims if "analysis.md" in p], records.claims)
        # Even when nothing ignores acs's workspace, its files are never a commit's.
        exclude = os.path.join(self.repo, ".git", "info", "exclude")
        with open(exclude, encoding="utf-8") as fh:
            kept = [line for line in fh if "state-machine" not in line]
        with open(exclude, "w", encoding="utf-8") as fh:
            fh.writelines(kept)
        os.unlink(os.path.join(self.ws, ".gitignore"))  # the workspace's own `*`
        self.assertIn(".acs/state-machine/", self.git("status", "--porcelain", "-uall"))
        with open(os.path.join(self.repo, "src.py"), "w") as fh:
            fh.write("x = 1\n")
        out = self.run_script("acs.py", "pr", "plan-commits", "--run", self.tid)
        self.assertEqual(out.returncode, 0, out.stderr)
        plan = json.loads(out.stdout)
        listed = [p for g in plan["groups"] for p in g["paths"]] + plan["left_out"] + \
            plan["excluded"]
        self.assertIn("src.py", listed)
        self.assertFalse([p for p in listed if p.startswith(".acs/state-machine")], listed)

    def test_records_skip_a_local_publication_and_the_workspace(self):
        from acs_lib import commit_plan
        records = commit_plan.Records(self.repo, None)
        records.claim(".acs/state-machine/acme-shop/runs/R/steps/x/local/plan.md", "other")
        records.claim(os.path.join(self.repo, ".acs", "state-machine", "a.md"), "other")
        records.claim("docs/development/f/R/plan.md", "ticket-docs")
        self.assertEqual(list(records.claims), ["docs/development/f/R/plan.md"])


class TestPublishLocalWithoutAFeature(TicketlessAnalysisCase):
    """A Development run over a prompt with no PRD feature yet: shared, publish
    is refused for want of a feature; kept local, it needs none. (A standalone
    run's analysis is the feature's LIVING one -- always shared.)"""

    def decide_shared(self):
        self.write_settings(dict(BASE, docs={"share_run_documents": False}))

    def test_a_local_analysis_needs_no_feature(self):
        self.cli("plan", "--mode", "development")
        self.do_survey()
        self.cli("record-survey")
        self.do_synthesis()
        self.cli("record-synthesis")
        self.cli("record-clarify")
        self.do_draft(1)
        self.cli("record-draft")
        self.do_review(1)
        self.assertTrue(self.cli("record-review")["passed"])
        pub = self.cli("publish")["publication"]
        self.assertEqual(pub["path"], os.path.join(self.r, "steps", "analyze-requirements",
                                                   "local", "analysis.md"))
        self.assertTrue(os.path.isfile(pub["path"]))
        self.assertTrue(pub["local"])

    def test_a_standalone_runs_living_analysis_ignores_keep_local(self):
        self.to_publish()
        out = self.run_script("acs.py", "analysis", "publish", "--run", self.tid)
        self.assertEqual(out.returncode, 2, out.stdout + out.stderr)
        self.assertIn("the prd folder, which does not exist yet", out.stderr)


if __name__ == "__main__":
    unittest.main()
