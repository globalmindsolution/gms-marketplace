"""Requirements from any container (ADR-0128): `acs_lib.requirements`,
`acs_lib.doc_layout`, `acs_lib.run_docs` and their CLI.

A ticket id, documents (in the repo, or attached from outside it) and a prompt
are only CONTAINERS of a run's requirements, and one invocation may mix them.
Pinned here, against real temp repos and workspaces:

  * parsing -- mixed, quoted, `~`, a quoted path with spaces, absolute paths,
    a missing path read as prompt text, an unknown ticket refused;
  * the run's subject stays ONE primary (ticket > document > prompt), with the
    whole list kept as `subject.sources` for a mixed invocation;
  * materialise -- sources.json, the copy and digest of an outside document,
    requirements.md (AC-n numbering, inlined markdown, cited binaries),
    idempotent, regenerated when a later invocation adds sources;
  * refine -- with and without a ticket (the ticket is patched too);
  * the PRD / architecture / Development directories and the phase folders a
    run's documents are filed in, with the legacy docs/tickets read fallback;
  * the plumbing: the pre-hook and `step start` both materialise, the start
    context carries `requirements`, `run next --args`, `requirements
    show|add|refine`, `artifacts show --run`, the ticketless clarify ledger,
    and a design skill's run over a prompt.

Run:  python3 -m unittest tests.acs.test_requirements -v
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import AcsWorkspaceCase, lib, pushd  # noqa: E402

from acs_lib import doc_layout, requirements as R, run_docs  # noqa: E402

REPO_ID = "acme-shop"
SPEC_MD = "# Spec\n\n## Export\nBulk export as CSV.\n"


class RequirementsCase(AcsWorkspaceCase):

    def setUp(self):
        super().setUp()
        self.home = tempfile.mkdtemp(prefix="acs-home-")
        self.addCleanup(shutil.rmtree, self.home, True)

    def ctx(self):
        with pushd(self.repo):
            return lib.build_context(self.repo)

    def write(self, path, text, root=None):
        full = path if os.path.isabs(path) else os.path.join(root or self.repo, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(text)
        return full

    def read(self, path):
        with open(path, encoding="utf-8") as fh:
            return fh.read()

    def env(self):
        return dict(os.environ, HOME=self.home)

    def acs(self, *argv, stdin=None, code=0):
        out = self.run_script("acs.py", *argv, stdin=stdin, env=self.env())
        self.assertEqual(out.returncode, code, out.stdout + out.stderr)
        return json.loads(out.stdout) if code == 0 and out.stdout.strip() else out

    def ticket(self, title="Wishlist", ttype="story", features="wishlist", criteria=None):
        extra = ("--features", features) if features else ()
        tid = self.new_ticket(title, ttype, *extra)
        if criteria:
            self.acs("ticket", "save", "--ticket", tid, "--from", "-",
                     stdin=json.dumps({"acceptance_criteria": criteria}))
        return tid

    def new_run(self, subject, run_id=None):
        wf_path = lib.default_workflow_path()
        wf = lib.validate_workflow_file(wf_path)
        run_id, rdir, _doc = lib.create_run(lib.repo_dir(self.ws, REPO_ID), subject, wf,
                                            wf_path, run_id=run_id)
        return rdir


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

class TestParseSources(RequirementsCase):

    def parse(self, text):
        with mock.patch.dict(os.environ, {"HOME": self.home}):
            return R.parse_sources(text, self.ctx())

    def test_a_mixed_invocation_keeps_every_container_in_order(self):
        self.write("docs/spec.md", SPEC_MD)
        sources = self.parse('SHOP-12 docs/spec.md "also bulk export"')
        self.assertEqual([s["kind"] for s in sources], ["ticket", "document", "prompt"])
        self.assertEqual(sources[0], {"kind": "ticket", "ticket_id": "SHOP-12"})
        self.assertEqual(sources[1]["path"], "docs/spec.md")
        self.assertTrue(sources[1]["inside_repo"])
        self.assertEqual(sources[1]["sha256"], R.sha256_file(sources[1]["abs"]))
        self.assertEqual(sources[2], {"kind": "prompt", "text": "also bulk export"})

    def test_unquoted_prompt_words_join_into_one_prompt(self):
        sources = self.parse("SHOP-3 make the export faster please")
        self.assertEqual(sources[1], {"kind": "prompt", "text": "make the export faster please"})

    def test_a_tilde_path_outside_the_repo_is_a_document(self):
        self.write(os.path.join(self.home, "Downloads", "spec.pdf"), "%PDF-1.4\n")
        sources = self.parse("~/Downloads/spec.pdf")
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["path"], "~/Downloads/spec.pdf")
        self.assertFalse(sources[0]["inside_repo"])
        self.assertEqual(sources[0]["abs"], os.path.join(self.home, "Downloads", "spec.pdf"))

    def test_a_quoted_path_with_spaces_is_one_document(self):
        self.write("my docs/spec v2.md", SPEC_MD)
        sources = self.parse('"my docs/spec v2.md" and more')
        self.assertEqual(sources[0]["path"], "my docs/spec v2.md")
        self.assertEqual(sources[1]["text"], "and more")

    def test_an_absolute_path_inside_the_repo_is_stored_repo_relative(self):
        full = self.write("docs/rfc.md", SPEC_MD)
        sources = self.parse(full)
        self.assertEqual(sources[0]["path"], "docs/rfc.md")
        self.assertTrue(sources[0]["inside_repo"])

    def test_a_path_that_does_not_exist_is_prompt_text(self):
        sources = self.parse("docs/nope.md fix the timeout")
        self.assertEqual(sources, [{"kind": "prompt", "text": "docs/nope.md fix the timeout"}])

    def test_a_pure_prompt_is_kept_verbatim_quotes_and_all(self):
        self.assertEqual(self.parse('fix the "login" timeout'),
                         [{"kind": "prompt", "text": 'fix the "login" timeout'}])
        self.assertEqual(self.parse("don't break the export"),
                         [{"kind": "prompt", "text": "don't break the export"}])

    def test_an_unbalanced_quote_falls_back_to_whitespace_splitting(self):
        sources = self.parse("SHOP-4 don't break it")
        self.assertEqual(sources, [{"kind": "ticket", "ticket_id": "SHOP-4"},
                                   {"kind": "prompt", "text": "don't break it"}])

    def test_repeated_tickets_and_documents_are_recorded_once(self):
        self.write("a.md", "a\n")
        sources = self.parse("SHOP-1 a.md SHOP-1 a.md")
        self.assertEqual([s["kind"] for s in sources], ["ticket", "document"])

    def test_a_skills_own_options_are_never_requirements(self):
        self.write("plan.md", "# plan\n")
        self.assertEqual(self.parse("--base origin/main SHOP-2 --plan plan.md --fan-out"),
                         [{"kind": "ticket", "ticket_id": "SHOP-2"}])
        self.assertEqual(self.parse("--suite smoke check the export"),
                         [{"kind": "prompt", "text": "check the export"}])
        self.assertEqual(self.parse("--draft=yes"), [])
        self.assertEqual(R.subject_from_text("--base origin/main", self.ctx()),
                         {"kind": "prompt", "text": "--base origin/main"},
                         "an options-only invocation still opens a run")

    def test_another_prefix_is_not_a_ticket(self):
        self.assertEqual(self.parse("MAR-1"), [{"kind": "prompt", "text": "MAR-1"}])

    def test_nothing_parses_to_nothing(self):
        self.assertEqual(self.parse("   "), [])
        self.assertIsNone(R.primary_subject([]))

    def test_an_unknown_ticket_is_refused(self):
        with self.assertRaises(lib.GateError) as caught:
            R.check_tickets(self.ctx(), self.parse("SHOP-99 also x"), "code")
        self.assertIn("no ticket SHOP-99", str(caught.exception))
        self.assertIn("/acs:create-ticket", str(caught.exception))


class TestPrimarySubject(RequirementsCase):

    def test_ticket_beats_document_beats_prompt(self):
        doc = {"kind": "document", "path": "a.md", "abs": "/x/a.md", "sha256": "f",
               "inside_repo": True}
        prompt = {"kind": "prompt", "text": "p"}
        ticket = {"kind": "ticket", "ticket_id": "SHOP-1"}
        self.assertEqual(R.primary_subject([prompt, doc, ticket])["kind"], "ticket")
        self.assertEqual(R.primary_subject([prompt, doc]),
                         {"kind": "document", "path": "a.md", "sha256": "f",
                          "sources": [prompt, doc]})
        self.assertEqual(R.primary_subject([prompt]), {"kind": "prompt", "text": "p"})

    def test_a_single_source_subject_carries_no_list(self):
        subject = R.primary_subject([{"kind": "ticket", "ticket_id": "SHOP-1"}])
        self.assertEqual(subject, {"kind": "ticket", "ticket_id": "SHOP-1"})
        self.assertEqual(R.sources_of(subject), [{"kind": "ticket", "ticket_id": "SHOP-1"}])
        self.assertEqual(R.sources_of({"kind": "document", "path": "a.md", "sha256": "f"}),
                         [{"kind": "document", "path": "a.md", "sha256": "f"}])
        self.assertEqual(R.sources_of({"kind": "branch", "branch": "x"}), [])

    def test_the_gate_delegates_to_it(self):
        self.write("docs/spec.md", SPEC_MD)
        subject = lib.subject_from_payload(
            self.ctx(), {"tool_input": {"args": "SHOP-7 docs/spec.md also X"}})
        self.assertEqual(subject["ticket_id"], "SHOP-7")
        self.assertEqual([s["kind"] for s in subject["sources"]],
                         ["ticket", "document", "prompt"])
        self.assertIsNone(lib.subject_from_payload(self.ctx(), {"tool_input": {}}))

    def test_a_mixed_subject_validates_against_the_run_schema(self):
        from acs_lib.schemasubset import schema_errors
        self.write("docs/spec.md", SPEC_MD)
        subject = R.subject_from_text("SHOP-7 docs/spec.md also X", self.ctx())
        doc = lib.run_machine.empty_run("SHOP-7", "ship", 3, subject)
        self.assertEqual(schema_errors(lib.load_schema("run.schema.json"), doc), [])
        doc["driver"] = "ship"
        self.assertEqual(schema_errors(lib.load_schema("run.schema.json"), doc), [])


# ---------------------------------------------------------------------------
# materialise / add_sources
# ---------------------------------------------------------------------------

class TestMaterialise(RequirementsCase):

    def test_an_outside_document_is_copied_and_hashed_an_inside_one_is_not(self):
        outside = self.write(os.path.join(self.home, "spec.pdf"), "%PDF-1.4 binary\n")
        self.write("docs/notes.md", SPEC_MD)
        tid = self.ticket(criteria=["user can add", "user can remove"])
        with mock.patch.dict(os.environ, {"HOME": self.home}):
            sources = R.parse_sources("%s ~/spec.pdf docs/notes.md also bulk export" % tid,
                                      self.ctx())
        rdir = self.new_run(R.primary_subject(sources))
        result = R.materialise(rdir, self.ctx())
        recorded = R.load_sources(rdir)
        self.assertEqual([e["kind"] for e in recorded],
                         ["ticket", "document", "document", "prompt"])
        pdf = recorded[1]
        self.assertEqual(pdf["copy"], os.path.join(rdir, "subject", "2-spec.pdf"))
        self.assertEqual(self.read(pdf["copy"]), self.read(outside))
        self.assertEqual(pdf["sha256"], R.sha256_file(outside))
        self.assertIsNone(recorded[2]["copy"], "a repo document is not copied")
        self.assertEqual(result["path"], os.path.join(rdir, "requirements.md"))
        text = self.read(result["path"])
        self.assertIn("## Ticket %s" % tid, text)
        self.assertIn("- **AC-1** user can add", text)
        self.assertIn("- **AC-2** user can remove", text)
        self.assertIn("- features: wishlist", text)
        self.assertIn("## Prompt", text)
        self.assertIn("also bulk export", text)
        self.assertIn("### docs/notes.md", text)
        self.assertIn("Bulk export as CSV.", text, "markdown is inlined")
        self.assertIn("Read the run copy `%s`" % pdf["copy"], text, "a PDF is cited")
        self.assertNotIn("## Refined", text)
        self.assertTrue(text.startswith("---\nrun_id: "))

    def test_acceptance_criteria_are_numbered_across_tickets_in_order(self):
        a = self.ticket("A", criteria=["a1", "a2"])
        b = self.ticket("B", criteria=["b1"])
        rdir = self.new_run(R.subject_from_text("%s %s" % (a, b), self.ctx()))
        R.materialise(rdir, self.ctx())
        text = self.read(R.requirements_path(rdir))
        self.assertLess(text.index("**AC-2** a2"), text.index("**AC-3** b1"))
        summary = R.summary(rdir, self.ctx())
        self.assertEqual([(c["id"], c["text"], c["source"]) for c in
                          summary["acceptance_criteria"]],
                         [("AC-1", "a1", a), ("AC-2", "a2", a), ("AC-3", "b1", b)])

    def test_materialise_is_idempotent(self):
        rdir = self.new_run({"kind": "prompt", "text": "speed up imports"})
        R.materialise(rdir, self.ctx())
        paths = (R.requirements_path(rdir), R.sources_path(rdir))
        before = [(self.read(p), os.stat(p).st_mtime_ns) for p in paths]
        again = R.materialise(rdir, self.ctx())
        self.assertEqual(again["added"], [])
        self.assertEqual([(self.read(p), os.stat(p).st_mtime_ns) for p in paths], before)

    def test_a_later_invocation_appends_and_regenerates_never_replaces(self):
        rdir = self.new_run({"kind": "prompt", "text": "speed up imports"})
        R.materialise(rdir, self.ctx())
        self.write("docs/extra.md", "Extra rule.\n")
        R.add_sources(rdir, self.ctx(), "docs/extra.md and keep the order")
        R.add_sources(rdir, self.ctx(), "docs/extra.md")  # repeated: a no-op
        recorded = R.load_sources(rdir)
        self.assertEqual([(e["kind"], e["ref"]) for e in recorded],
                         [("prompt", "speed up imports"), ("document", "docs/extra.md"),
                          ("prompt", "and keep the order")])
        text = self.read(R.requirements_path(rdir))
        self.assertIn("speed up imports", text)
        self.assertIn("Extra rule.", text)
        with self.assertRaises(lib.GateError):
            R.add_sources(rdir, self.ctx(), "SHOP-404")

    def test_an_edited_repo_document_keeps_one_entry_with_its_new_digest(self):
        self.write("docs/spec.md", "v1\n")
        rdir = self.new_run(R.subject_from_text("docs/spec.md", self.ctx()))
        R.materialise(rdir, self.ctx())
        self.write("docs/spec.md", "v2 changed\n")
        R.add_sources(rdir, self.ctx(), "docs/spec.md")
        recorded = R.load_sources(rdir)
        self.assertEqual(len(recorded), 1)
        self.assertEqual(recorded[0]["sha256"],
                         R.sha256_file(os.path.join(self.repo, "docs", "spec.md")))
        self.assertIn("updated_at", recorded[0])

    def test_a_vanished_document_is_reported_not_fatal(self):
        self.write("docs/gone.md", "x\n")
        rdir = self.new_run(R.subject_from_text("docs/gone.md", self.ctx()))
        R.materialise(rdir, self.ctx())
        os.unlink(os.path.join(self.repo, "docs", "gone.md"))
        R.add_sources(rdir, self.ctx(), "one more line")
        self.assertIn("_Not found any more", self.read(R.requirements_path(rdir)))

    def test_a_document_with_backtick_fences_is_fenced_safely(self):
        self.write("docs/code.md", "```py\nx = 1\n```\n")
        rdir = self.new_run(R.subject_from_text("docs/code.md", self.ctx()))
        R.materialise(rdir, self.ctx())
        self.assertIn("````text\n```py", self.read(R.requirements_path(rdir)))


# ---------------------------------------------------------------------------
# refine
# ---------------------------------------------------------------------------

class TestRefine(RequirementsCase):

    def test_without_a_ticket_it_records_and_renders_the_refined_section(self):
        rdir = self.new_run({"kind": "prompt", "text": "bulk export"})
        report = R.refine(rdir, self.ctx(), {
            "acceptance_criteria": ["exports CSV", "exports JSON"], "needs_design": True,
            "features": ["export"], "feature": "export", "phase": "discovery"})
        self.assertIsNone(report["ticket_patched"])
        text = self.read(R.requirements_path(rdir))
        self.assertIn("## Refined", text)
        self.assertIn("- **AC-2** exports JSON", text)
        self.assertIn("- needs_design: true", text)
        summary = R.summary(rdir, self.ctx())
        self.assertEqual([c["source"] for c in summary["acceptance_criteria"]],
                         ["refined", "refined"])
        self.assertEqual((summary["feature"], summary["features"], summary["needs_design"],
                          summary["phase"], summary["refined"]),
                         ("export", ["export"], True, "discovery", True))
        R.refine(rdir, self.ctx(), {"needs_design": False})
        self.assertEqual(R.load_refined(rdir)["acceptance_criteria"],
                         ["exports CSV", "exports JSON"], "a refine is a patch")
        self.assertIs(R.recorded_needs_design(rdir), False)

    def test_with_a_ticket_it_patches_the_ticket_too(self):
        tid = self.ticket(features=None, criteria=["old"])
        rdir = self.new_run({"kind": "ticket", "ticket_id": tid}, run_id=tid)
        report = R.refine(rdir, self.ctx(), {"acceptance_criteria": ["new 1", "new 2"],
                                            "needs_design": True, "feature": "wishlist"})
        self.assertEqual(report["ticket_patched"], tid)
        self.assertEqual(report["ticket_fields"],
                         ["acceptance_criteria", "features", "needs_design"])
        ticket = lib.load_ticket(self.tdir(tid))
        self.assertEqual(ticket["acceptance_criteria"], ["new 1", "new 2"])
        self.assertTrue(ticket["needs_design"])
        self.assertEqual(ticket["features"], ["wishlist"])
        index = lib.read_json(lib.index_path(self.ws, REPO_ID))["tickets"][tid]
        self.assertEqual(index["features"], ["wishlist"])

    def test_a_later_refine_of_one_key_keeps_the_others(self):
        rdir = self.new_run({"kind": "prompt", "text": "x"})
        R.refine(rdir, self.ctx(), {"acceptance_criteria": ["a"], "needs_design": True,
                                    "feature": "export"})
        R.refine(rdir, self.ctx(), {"features": ["export", "billing"]})
        refined = R.load_refined(rdir)
        self.assertEqual((refined["acceptance_criteria"], refined["needs_design"],
                          refined["feature"], refined["features"]),
                         (["a"], True, "export", ["export", "billing"]))

    def test_bad_input_is_refused(self):
        rdir = self.new_run({"kind": "prompt", "text": "x"})
        for data in ({"ticket": "SHOP-1"}, {"acceptance_criteria": "one"},
                     {"acceptance_criteria": [""]}, {"needs_design": "yes"},
                     {"features": ["Not A Slug"]}, {"feature": "x y"},
                     {"phase": "design"}, ["not", "an", "object"]):
            with self.subTest(data=data), self.assertRaises(lib.GateError):
                R.refine(rdir, self.ctx(), data)
        self.assertFalse(os.path.exists(R.refined_path(rdir)))


# ---------------------------------------------------------------------------
# The phase folders
# ---------------------------------------------------------------------------

class TestDocLayout(RequirementsCase):

    def test_the_defaults(self):
        self.assertEqual(doc_layout.prd_dir(self.repo), "docs/product")
        self.assertEqual(doc_layout.architecture_dir(self.repo), "docs/architecture")
        self.assertEqual(doc_layout.development_dir(self.repo), "docs/development")
        self.assertEqual(R.prd_dir(None), "docs/product")

    def test_a_prd_found_in_the_tree_is_used(self):
        self.write("product-docs/prd.md", "# PRD\n")
        self.write("product-docs/old/prd.md", "# older\n")
        self.assertEqual(doc_layout.prd_dir(self.repo), "product-docs")

    def test_claude_md_naming_the_prd_wins_over_a_search(self):
        self.write("a/prd.md", "# PRD\n")
        self.write("spec/product/prd.md", "# PRD\n")
        self.write("CLAUDE.md", "The PRD is ./spec/product/prd.md.\n")
        self.assertEqual(doc_layout.prd_dir(self.repo), "spec/product")

    def test_a_hidden_or_vendored_prd_is_ignored(self):
        self.write(".cache/prd.md", "x\n")
        self.write("node_modules/pkg/prd.md", "x\n")
        self.assertEqual(doc_layout.prd_dir(self.repo), "docs/product")

    def test_settings_name_the_folders(self):
        settings = {"docs": {"prd_dir": "p/", "architecture_dir": "a",
                             "development_dir": "d/dev"}}
        self.assertEqual(doc_layout.prd_dir(self.repo, settings), "p")
        self.assertEqual(doc_layout.architecture_dir(self.repo, settings), "a")
        self.assertEqual(doc_layout.development_dir(self.repo, settings), "d/dev")

    def test_the_architecture_folder_is_where_hld_tech_stack_lives(self):
        self.write("design/arch/hld/tech-stack.md", "# stack\n")
        self.assertEqual(doc_layout.architecture_dir(self.repo), "design/arch")

    def test_feature_and_run_paths(self):
        join = os.path.join
        self.assertEqual(doc_layout.feature_dir(self.repo, "export"),
                         join(self.repo, "docs", "product", "features", "export"))
        self.assertIsNone(doc_layout.feature_dir(self.repo, None))
        self.assertEqual(doc_layout.document_target(self.repo, "plan.md", "export", "SHOP-1"),
                         join(self.repo, "docs", "development", "export", "SHOP-1", "plan.md"))
        self.assertEqual(
            doc_layout.document_target(self.repo, "api-contract.md", "export", "r-1"),
            join(self.repo, "docs", "architecture", "lld", "export", "r-1", "api-contract.md"))
        self.assertEqual(
            doc_layout.document_target(self.repo, "analysis.md", "export", "r-1", "discovery"),
            join(self.repo, "docs", "product", "features", "export", "analysis.md"))
        self.assertIsNone(doc_layout.document_target(self.repo, "plan.md", None, "r-1"))
        self.assertIsNone(doc_layout.document_target(self.repo, "ticket.md", "export", "r"))
        self.assertEqual(
            doc_layout.document_candidates(self.repo, "plan.md", "export", "SHOP-1",
                                           ticket_id="SHOP-1")[1],
            join(self.repo, "docs", "tickets", "SHOP-1", "plan.md"))


class TestDocsSettings(RequirementsCase):
    """The optional `docs` folders are first-class settings: declared in the
    schema with no default, validated at every gate, discovered when absent."""

    def schema(self):
        from acs_case import REPO_ROOT
        with open(os.path.join(REPO_ROOT, "plugins", "acs", "schemas",
                               "settings.schema.json"), encoding="utf-8") as fh:
            return json.load(fh)

    def test_the_schema_declares_exactly_the_keys_the_code_reads_and_no_default(self):
        from acs_lib import settings as settings_mod
        docs = self.schema()["properties"]["docs"]
        self.assertEqual(tuple(docs["properties"]), settings_mod.DOCS_KEYS)
        self.assertIs(docs["additionalProperties"], False)
        self.assertNotIn("default", docs)
        for key, spec in docs["properties"].items():
            with self.subTest(key=key):
                self.assertEqual(spec["type"], "string")
                self.assertNotIn("default", spec)
        self.assertNotIn("docs", lib.DEFAULT_SETTINGS)

    def test_the_schema_pattern_and_the_validator_agree(self):
        import re
        from acs_lib.settings import docs_path_problem
        pattern = self.schema()["properties"]["docs"]["properties"]["prd_dir"]["pattern"]
        for value in ("docs/product", "spec", "a/b/c/", "/abs/path", "../up", "a/../b",
                      "a/..", "..", "a..b/c"):
            with self.subTest(value=value):
                self.assertEqual(bool(re.search(pattern, value)),
                                 docs_path_problem(value) is None)

    def test_a_bad_value_is_refused(self):
        for docs in ({"prd_dir": "/etc"}, {"development_dir": "../elsewhere"},
                     {"architecture_dir": 3}, {"architecture_dir": " "},
                     {"plans_dir": "x"}, ["docs"]):
            with self.subTest(docs=docs), self.assertRaises(lib.GateError):
                lib.validate_settings({"ticket_prefix": "SHOP", "docs": docs}, self.repo)
        lib.validate_settings({"ticket_prefix": "SHOP",
                               "docs": {"development_dir": "engineering/changes"}}, self.repo)

    def test_a_bad_value_stops_a_step_and_is_never_obeyed(self):
        self.write_settings({"ticket_prefix": "SHOP", "docs": {"development_dir": "../out"}})
        out = self.acs("step", "start", "--step", "analyze-requirements", "--args", "x",
                       code=2)
        self.assertIn("docs.development_dir", out.stderr)
        self.assertEqual(doc_layout.development_dir(
            self.repo, {"docs": {"development_dir": "../out"}}), "docs/development")

    def test_a_configured_folder_is_used_and_absence_means_discovery(self):
        self.write("handbook/prd.md", "# PRD\n")
        self.write_settings({"ticket_prefix": "SHOP",
                             "docs": {"development_dir": "engineering/changes"}})
        self.acs("run", "new", "--prompt", "bulk export")
        self.acs("requirements", "refine", "--from", "-",
                 stdin=json.dumps({"feature": "export"}))
        out = self.acs("artifacts", "show")
        self.assertEqual((out["development_dir"], out["prd_dir"]),
                         ("engineering/changes", "handbook"))
        self.assertTrue(out["paths"]["plan.md"].startswith(
            os.path.join(self.repo, "engineering", "changes", "export")))


class TestRunDocs(RequirementsCase):

    def test_a_ticket_run_files_by_the_tickets_feature_and_reads_legacy_first(self):
        tid = self.ticket()
        rdir = self.new_run({"kind": "ticket", "ticket_id": tid}, run_id=tid)
        legacy = self.write("docs/tickets/%s/plan.md" % tid, "# old plan\n")
        layout = run_docs.run_layout(self.ctx(), rdir)
        dev = os.path.join(self.repo, "docs", "development", "wishlist", tid)
        self.assertEqual((layout["feature"], layout["phase"], layout["key"]),
                         ("wishlist", "development", tid))
        self.assertEqual(layout["paths"]["plan.md"], os.path.join(dev, "plan.md"))
        self.assertEqual(layout["paths"]["analysis.md"], os.path.join(dev, "analysis.md"))
        self.assertEqual(layout["paths"]["design.md"], os.path.join(
            self.repo, "docs", "architecture", "lld", "wishlist", tid, "design.md"))
        self.assertEqual(layout["artifacts"]["plan.md"], legacy, "legacy read fallback")
        fresh = self.write(os.path.join(dev, "plan.md"), "# new plan\n")
        self.assertEqual(run_docs.document_path(self.ctx(), "plan.md", rdir), (fresh, fresh))

    def test_a_standalone_prompt_run_files_its_analysis_as_the_features(self):
        rdir = self.new_run({"kind": "prompt", "text": "bulk export"})
        layout = run_docs.run_layout(self.ctx(), rdir)
        self.assertIsNone(layout["feature"])
        self.assertTrue(all(v is None for v in layout["paths"].values()))
        R.refine(rdir, self.ctx(), {"feature": "export"})
        living = self.write("docs/product/features/export/analysis.md", "# a\n")
        layout = run_docs.run_layout(self.ctx(), rdir)
        self.assertEqual(layout["phase"], "discovery")
        self.assertEqual(layout["paths"]["analysis.md"], living)
        self.assertEqual(layout["feature_analysis"], living)
        run_id = os.path.basename(rdir)
        self.assertEqual(layout["paths"]["plan.md"], os.path.join(
            self.repo, "docs", "development", "export", run_id, "plan.md"))

    def test_a_shipped_prompt_run_is_a_development_run(self):
        rdir = self.new_run({"kind": "prompt", "text": "bulk export"})
        doc = lib.load_run(rdir)
        doc["driver"] = "ship"
        lib.save_run(rdir, doc)
        R.refine(rdir, self.ctx(), {"feature": "export"})
        self.assertEqual(run_docs.run_layout(self.ctx(), rdir)["phase"], "development")
        R.refine(rdir, self.ctx(), {"phase": "discovery"})
        self.assertEqual(run_docs.run_layout(self.ctx(), rdir)["phase"], "discovery")

    def test_a_ticket_with_no_run_is_described_from_the_ticket(self):
        tid = self.ticket()
        out = run_docs.describe(self.ctx(), ticket_id=tid)
        self.assertIsNone(out["run_id"])
        self.assertEqual(out["feature"], "wishlist")
        self.assertEqual(out["source"], "ticket.json")
        with self.assertRaises(lib.GateError):
            run_docs.describe(self.ctx(), ticket_id="SHOP-404")


# ---------------------------------------------------------------------------
# The plumbing, through the real CLIs
# ---------------------------------------------------------------------------

class TestPlumbing(RequirementsCase):

    def test_the_pre_hook_records_the_mixed_invocations_requirements(self):
        tid = self.ticket(criteria=["works"])
        self.write("docs/spec.md", SPEC_MD)
        out = self.pre("analyze-requirements", '%s docs/spec.md "also bulk export"' % tid)
        self.assertEqual(out.returncode, 0, out.stderr)
        rdir = self.rdir(tid)
        subject = lib.load_run(rdir)["subject"]
        self.assertEqual(subject["ticket_id"], tid)
        self.assertEqual([s["kind"] for s in subject["sources"]],
                         ["ticket", "document", "prompt"])
        text = self.read(R.requirements_path(rdir))
        self.assertIn("**AC-1** works", text)
        self.assertIn("Bulk export as CSV.", text)

    def test_the_pre_hook_refuses_an_unknown_ticket_among_the_sources(self):
        tid = self.ticket()
        out = self.pre("analyze-requirements", "%s SHOP-404" % tid)
        self.assertEqual(out.returncode, 2)
        self.assertIn("no ticket SHOP-404", out.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.rdir(tid), "run.json")))

    def test_step_start_materialises_and_its_context_carries_requirements(self):
        outside = self.write(os.path.join(self.home, "brief.md"), "Brief.\n")
        out = self.acs("step", "start", "--step", "analyze-requirements",
                       "--args", "~/brief.md speed up the import")
        req = out["requirements"]
        self.assertEqual(sorted(req), ["acceptance_criteria", "feature", "feature_analysis",
                                       "features", "needs_design", "path", "phase",
                                       "refined", "sources"])
        self.assertEqual(out["subject"]["kind"], "document")
        self.assertEqual([s["kind"] for s in req["sources"]], ["document", "prompt"])
        self.assertEqual(self.read(req["sources"][0]["copy"]), self.read(outside))
        self.assertEqual((req["phase"], req["feature"], req["needs_design"]),
                         ("discovery", None, None))
        self.assertNotIn("design", out)
        self.assertTrue(os.path.isfile(req["path"]))

    def test_a_ticket_runs_context_carries_both_its_ticket_and_requirements(self):
        tid = self.ticket(criteria=["a"])
        out = self.acs("step", "start", "--step", "analyze-requirements", "--args", tid)
        self.assertEqual(out["ticket"]["id"], tid)
        self.assertEqual(out["requirements"]["acceptance_criteria"],
                         [{"id": "AC-1", "text": "a", "source": tid}])
        self.assertEqual(out["requirements"]["phase"], "development")
        self.assertEqual(out["design"], {"required": False, "dir": None, "source": None})

    def test_step_start_adds_a_later_invocations_sources_to_the_current_run(self):
        first = self.acs("step", "start", "--step", "analyze-requirements",
                         "--args", "speed up the import")
        rdir = first["partition"]
        self.acs("step", "finish", "--step", "analyze-requirements", "--status",
                 "interrupted", "--stop-reason", "session_end")
        self.acs("step", "start", "--step", "analyze-requirements",
                 "--args", "and keep the order")
        self.assertEqual([e["ref"] for e in R.load_sources(rdir)],
                         ["speed up the import", "and keep the order"])
        out = self.acs("step", "start", "--step", "create-impl-plan", "--args", "SHOP-77",
                       code=2)
        self.assertIn("no ticket SHOP-77", out.stderr)

    def test_a_refined_needs_design_reaches_a_ticketless_runs_context(self):
        first = self.acs("step", "start", "--step", "analyze-requirements",
                         "--args", "split the service")
        self.acs("requirements", "refine", "--from", "-",
                 stdin=json.dumps({"needs_design": True}))
        self.acs("step", "finish", "--step", "analyze-requirements", "--status",
                 "interrupted", "--stop-reason", "session_end")
        again = self.acs("step", "start", "--step", "analyze-requirements")
        self.assertEqual(again["run_id"], first["run_id"])
        self.assertEqual(again["design"],
                         {"required": True, "dir": None, "source": "requirements"})

    def test_a_refined_needs_design_is_the_tickets_design_requirement(self):
        tid = self.ticket()
        rdir = self.ensure_run(tid)
        ctx = self.ctx()
        tdir = self.tdir(tid)
        ticket = lib.load_ticket(tdir)
        self.assertEqual(lib.design_requirement(ctx, tdir, ticket, rdir), (False, None, None))
        R.refine(rdir, ctx, {"needs_design": True})
        self.assertEqual(lib.design_requirement(ctx, tdir, lib.load_ticket(tdir), rdir),
                         (True, tdir, "requirements"))
        lib.write_json(R.refined_path(rdir), {"needs_design": False})
        self.assertEqual(lib.design_requirement(ctx, tdir, lib.load_ticket(tdir), rdir),
                         (False, None, None), "the refined value wins over the flag")

    def test_run_next_takes_a_raw_invocation_and_marks_the_run_shipped(self):
        tid = self.ticket(criteria=["a"])
        self.write("docs/spec.md", SPEC_MD)
        out = self.acs("run", "next", "--args", "%s docs/spec.md also export" % tid)
        self.assertEqual((out["run_id"], out["next"]), (tid, "analyze-requirements"))
        self.assertEqual(out["args"], "%s docs/spec.md also export" % tid)
        doc = lib.load_run(self.rdir(tid))
        self.assertEqual(doc["driver"], "ship")
        self.assertEqual(len(R.load_sources(self.rdir(tid))), 3)
        bare = self.acs("run", "next")
        self.assertEqual((bare["run_id"], bare["args"]), (tid, tid))
        prompt = self.acs("run", "next", "--prompt", "cap the page size")
        self.assertEqual(prompt["args"], "cap the page size")
        refused = self.acs("run", "next", "--args", "SHOP-404 x", code=2)
        self.assertIn("no ticket SHOP-404", refused.stderr)

    def test_run_new_takes_a_document_and_args(self):
        self.write("docs/rfc.md", SPEC_MD)
        out = self.acs("run", "new", "--document", "docs/rfc.md")
        self.assertEqual(out["subject"]["path"], "docs/rfc.md")
        self.assertTrue(os.path.isfile(R.requirements_path(out["path"])))
        missing = self.acs("run", "new", "--document", "docs/none.md", code=2)
        self.assertIn("cannot read docs/none.md", missing.stderr)
        self.acs("run", "new", code=2)

    def test_requirements_show_add_and_refine(self):
        self.acs("run", "new", "--prompt", "bulk export")
        shown = self.acs("requirements", "show")
        self.assertEqual([e["ref"] for e in shown["sources"]], ["bulk export"])
        added = self.acs("requirements", "add", "--args", "also JSON")
        self.assertEqual(added["added"], [{"kind": "prompt", "ref": "also JSON"}])
        self.acs("requirements", "add", code=2)
        self.acs("requirements", "add", "--args", "SHOP-404", code=2)
        refined = self.acs("requirements", "refine", "--from", "-",
                           stdin=json.dumps({"feature": "export",
                                             "acceptance_criteria": ["CSV"]}))
        self.assertEqual(refined["feature"], "export")
        self.assertIsNone(refined["ticket_patched"])
        self.acs("requirements", "refine", "--from", "-", stdin='{"bogus": 1}', code=2)
        self.acs("requirements", "show", "--run", "nope", code=2)

    def test_requirements_show_materialises_an_older_run_on_first_read(self):
        rdir = self.new_run({"kind": "prompt", "text": "older run"})
        shown = self.acs("requirements", "show", "--run", os.path.basename(rdir))
        self.assertTrue(os.path.isfile(shown["path"]))

    def test_artifacts_show_resolves_by_run_without_a_ticket(self):
        self.acs("run", "new", "--prompt", "bulk export")
        out = self.acs("artifacts", "show")
        self.assertIsNone(out["ticket_id"])
        self.assertNotIn("ticket", out)
        self.assertIsNone(out["paths"]["plan.md"])
        self.acs("requirements", "refine", "--from", "-",
                 stdin=json.dumps({"feature": "export"}))
        out = self.acs("artifacts", "show", "--run", out["run_id"])
        self.assertEqual(out["paths"]["plan.md"], os.path.join(
            self.repo, "docs", "development", "export", out["run_id"], "plan.md"))
        self.assertEqual((out["prd_dir"], out["architecture_dir"], out["development_dir"]),
                         ("docs/product", "docs/architecture", "docs/development"))

    def test_artifacts_show_with_no_run_and_no_ticket_says_so(self):
        out = self.acs("artifacts", "show", code=2)
        self.assertIn("pass --run", out.stderr)

    def test_artifacts_show_by_ticket_uses_its_latest_run(self):
        tid = self.ticket()
        self.ensure_run(tid)
        lib.save_pointer(lib.repo_dir(self.ws, REPO_ID), lib.checkout_id(self.repo),
                         run_id=None)
        out = self.acs("artifacts", "show", "--ticket", tid)
        self.assertEqual((out["run_id"], out["feature"]), (tid, "wishlist"))

    def test_the_ticketless_clarify_ledger_is_the_runs(self):
        run = self.acs("run", "new", "--prompt", "bulk export")
        out = self.run_script("clarify.py", "add", "--skill", "analyze-requirements",
                              "--question", "CSV only?", "--run", run["run_id"])
        self.assertEqual(out.returncode, 0, out.stderr)
        ledger = os.path.join(run["path"], "clarifications.json")
        self.assertEqual(lib.read_json(ledger)["clarifications"][0]["question"], "CSV only?")
        out = self.run_script("clarify.py", "answer", "--id", "C-1", "--answer", "yes")
        self.assertEqual(out.returncode, 0, out.stderr)
        listed = json.loads(self.run_script("clarify.py", "list").stdout)
        self.assertEqual((listed["run_id"], listed["count"], listed["ledger"]),
                         (run["run_id"], 1, ledger))
        self.assertIsNone(listed["ticket_id"])
        bad = self.run_script("clarify.py", "list", "--run", "nope")
        self.assertEqual(bad.returncode, 2)
        self.assertIn("no run 'nope'", bad.stderr)

    def test_a_ticket_runs_clarify_ledger_is_still_the_tickets(self):
        tid = self.ticket()
        self.ensure_run(tid)
        out = self.run_script("clarify.py", "add", "--skill", "code", "--question", "Q?",
                              "--run", tid)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertTrue(os.path.isfile(os.path.join(self.tdir(tid), "clarifications.json")))
        self.assertFalse(os.path.isfile(os.path.join(self.rdir(tid), "clarifications.json")))

    def test_a_design_skill_on_a_prompt_opens_a_run_and_its_post_hook_concludes_it(self):
        out = self.acs("step", "start", "--step", "create-data-design",
                       "--args", "orders and their line items")
        self.assertFalse(out["in_workflow"])
        self.assertEqual(out["subject"], {"kind": "prompt",
                                          "text": "orders and their line items"})
        self.assertTrue(os.path.isfile(out["requirements"]["path"]))
        result = {"skill": "create-data-design", "run_id": out["run_id"],
                  "status": "completed"}
        vocabulary = lib.outcome_vocabulary("create-data-design")
        if vocabulary:
            result["outcome"] = vocabulary[0]
        post = self.run_script("post-create-data-design.py", "--run", out["run_id"],
                               stdin=json.dumps(result))
        self.assertEqual(post.returncode, 0, post.stderr)
        doc = lib.load_run(out["partition"])
        self.assertEqual((doc["status"], doc.get("concluded_by")),
                         ("completed", "create-data-design"))

    def test_no_writer_touches_the_legacy_docs_tree(self):
        os.makedirs(os.path.join(self.repo, "docs", "tickets"))
        tid = self.ticket(criteria=["a"])
        self.acs("step", "start", "--step", "analyze-requirements", "--args", tid)
        self.acs("requirements", "refine", "--from", "-",
                 stdin=json.dumps({"acceptance_criteria": ["b"], "feature": "wishlist"}))
        self.assertEqual(os.listdir(os.path.join(self.repo, "docs", "tickets")), [])


from test_file_map_guard import FileMapGuardCase  # noqa: E402


class TestRunDocsAreAGuardControlInput(FileMapGuardCase):
    """An executor may not rewrite the plan it is checked against: the run's
    Development and Design folders are denied even when declared, as
    docs/tickets/<ID>/ was."""

    def test_the_runs_phase_folders_are_denied_even_when_declared(self):
        with pushd(self.repo):
            R.refine(self.rdir_path, lib.build_context(self.repo), {"feature": "ship-it"})
        self.declare("docs/")
        self.spawn_writer()
        for target in ("docs/development/ship-it/%s/plan.md" % self.ticket,
                       os.path.join(self.repo, "docs", "architecture", "lld", "ship-it",
                                    self.ticket, "design.md")):
            with self.subTest(target=target):
                out = self.write_attempt(target)
                self.assertEqual(out.returncode, 2, out.stderr)
                self.assertIn("this run's documents", out.stderr)
        self.assertEqual(self.write_attempt("docs/development/other.md").returncode, 0)
        living = self.write_attempt("docs/product/features/ship-it/analysis.md")
        self.assertEqual(living.returncode, 2, living.stderr)
        self.assertIn("living analysis", living.stderr)


class TestCommitPlanDocSets(unittest.TestCase):

    def test_a_changes_documents_group_by_feature_and_id(self):
        from acs_lib import commit_plan
        self.assertEqual(commit_plan.doc_set("docs/development/export/SHOP-1/plan.md"),
                         ("development/export/SHOP-1", "SHOP-1 docs"))
        self.assertEqual(commit_plan.doc_set("docs/development/export/notes.md")[0],
                         "development/export")
        self.assertEqual(commit_plan.doc_set("docs/architecture/lld/export/SHOP-1/design.md"),
                         ("lld/export/SHOP-1", "SHOP-1 design records"))
        self.assertEqual(commit_plan.doc_set("docs/architecture/lld/export/data/erd.md")[0],
                         "lld/export", "the living LLD stays the feature's group")
        self.assertEqual(commit_plan.doc_set("docs/product/features/export/analysis.md"),
                         ("prd/features/export", "feature export analysis"))
        self.assertEqual(commit_plan.doc_set("docs/product/prd.md")[0], "prd")


if __name__ == "__main__":
    unittest.main()
