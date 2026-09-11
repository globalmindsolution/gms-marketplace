"""Brief section 4: the human-facing ticket documents move from the workspace
partition to the repo docs tree, `<settings.artifacts.tickets_path>/<ID>/`.

What is pinned here is the contract every caller of load_ticket/save_ticket
now relies on:

  * ticket.md is today's ticket.json as YAML front matter (every field but
    `status`) over a markdown body -- and it round-trips through the strict
    YAML subset acs_lib.yamlsubset reads, field for field;
  * `status` is DERIVED from the ledger and the archive (derive_status), not
    stored, and it agrees with the flips the hooks used to write;
  * load_ticket reads ticket.md when the ticket's docs folder holds one, else
    ticket.json (so every fixture that writes ticket.json keeps working), else
    the file the ticket.json.moved pointer names;
  * save_ticket writes ticket.md only when the docs tree is ACTIVE for this
    checkout and the ticket lives there (or has no ticket.json yet); a ticket
    that still has a ticket.json keeps it until `acs.py artifacts migrate`
    moves it -- one home per ticket, nothing goes stale;
  * migrate is idempotent, honours --dry-run, leaves the archive alone, and
    leaves a pointer behind;
  * the executor file-map guard treats the docs tree as a control input.

Run:  python3 -m unittest tests.acs.test_artifacts -v
"""

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import AcsWorkspaceCase, SCRIPTS, pushd  # noqa: E402
from test_file_map_guard import FileMapGuardCase  # noqa: E402

sys.path.insert(0, SCRIPTS)
import acs_lib as lib  # noqa: E402
from acs_lib import artifacts  # noqa: E402

TICKET = "SHOP-1"
REPO_ID = "acme-shop"


def read_text(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def full_ticket(ticket_id=TICKET):
    """A ticket document exercising every field new_ticket_doc writes, with
    values chosen to trip a careless emitter: quotes, a hash, a colon, a
    multi-line acceptance criterion, a nested mapping and a list."""
    doc = lib.new_ticket_doc(
        ticket_id, 'Widget "alpha": the #1 feature', "story",
        description="Add the widget.\n\nSecond paragraph with `code`, a # hash and a: colon.",
        acceptance_criteria=["Widget lists items", "Widget handles an empty list:\nshows a hint"],
        priority="high", parent="SHOP-9", children=[], external={"provider": "jira", "key": "PROJ-1"},
        assignee="jane", story_points=3, needs_design=False, docs_only=False,
        size="small", stakes="high", due_date="2026-12-01")
    doc["status"] = "in_progress"
    return doc


class ArtifactsCase(AcsWorkspaceCase):
    """The shared fixture plus the docs-tree helpers."""

    def docs_root(self):
        return os.path.join(self.repo, "docs", "tickets")

    def activate(self):
        """The docs tree is active once its root exists (migrate creates it)."""
        os.makedirs(self.docs_root(), exist_ok=True)

    def partition(self, ticket_id=TICKET, ttype="task", **fields):
        """A workspace partition with a ticket.json, the way every existing
        fixture builds one -- no docs folder."""
        tdir = self.tdir(ticket_id)
        os.makedirs(tdir, exist_ok=True)
        doc = lib.new_ticket_doc(ticket_id, "Widget %s" % ticket_id, ttype)
        doc.update(fields)
        lib.write_json(os.path.join(tdir, "ticket.json"), doc)
        return tdir

    def md_path(self, ticket_id=TICKET):
        return os.path.join(self.docs_root(), ticket_id, "ticket.md")

    def write_md(self, ticket, ticket_id=TICKET):
        path = self.md_path(ticket_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(artifacts.render_ticket_md(ticket))
        return path

    def index(self, *entries):
        data = {"tickets": {}}
        for ticket_id, status in entries:
            data["tickets"][ticket_id] = {"id": ticket_id, "status": status}
        lib.write_json(lib.index_path(self.ws, REPO_ID), data)


# ---------------------------------------------------------------------------
# ticket_docs_dir / artifact_path
# ---------------------------------------------------------------------------

class TestTicketDocsDir(unittest.TestCase):

    def test_default_path_is_docs_tickets_under_the_checkout(self):
        self.assertEqual(artifacts.ticket_docs_dir({}, "/repo", "SHOP-1"),
                         os.path.join("/repo", "docs", "tickets", "SHOP-1"))
        self.assertEqual(artifacts.ticket_docs_dir(lib.DEFAULT_SETTINGS, "/repo", "SHOP-1"),
                         os.path.join("/repo", "docs", "tickets", "SHOP-1"))

    def test_a_configured_path_is_honoured(self):
        settings = {"artifacts": {"tickets_path": "work/tickets"}}
        self.assertEqual(artifacts.ticket_docs_dir(settings, "/repo", "SHOP-2"),
                         os.path.join("/repo", "work", "tickets", "SHOP-2"))

    def test_null_opts_out_and_a_missing_checkout_resolves_nothing(self):
        self.assertIsNone(artifacts.ticket_docs_dir({"artifacts": {"tickets_path": None}}, "/repo", "SHOP-1"))
        self.assertIsNone(artifacts.ticket_docs_dir({}, None, "SHOP-1"))
        self.assertIsNone(artifacts.ticket_docs_root({"artifacts": {"tickets_path": None}}, "/repo"))


class TestArtifactPath(ArtifactsCase):

    def test_docs_folder_wins_then_partition_then_legacy(self):
        tdir = self.partition()
        settings = lib.DEFAULT_SETTINGS
        docs_plan = os.path.join(self.docs_root(), TICKET, "plan.md")
        legacy_plan = os.path.join(tdir, "phases", "code", "plan.md")
        # Nothing exists: the answer is where a writer should put it (docs tree).
        self.assertEqual(artifacts.artifact_path(settings, self.repo, tdir, TICKET, "plan.md"), docs_plan)
        os.makedirs(os.path.dirname(legacy_plan))
        with open(legacy_plan, "w") as fh:
            fh.write("# plan\n")
        self.assertEqual(artifacts.artifact_path(settings, self.repo, tdir, TICKET, "plan.md"), legacy_plan)
        with open(os.path.join(tdir, "plan.md"), "w") as fh:
            fh.write("# plan\n")
        self.assertEqual(artifacts.artifact_path(settings, self.repo, tdir, TICKET, "plan.md"),
                         os.path.join(tdir, "plan.md"))
        os.makedirs(os.path.dirname(docs_plan))
        with open(docs_plan, "w") as fh:
            fh.write("# plan\n")
        self.assertEqual(artifacts.artifact_path(settings, self.repo, tdir, TICKET, "plan.md"), docs_plan)

    def test_opted_out_resolves_to_the_partition(self):
        tdir = self.partition()
        settings = {"artifacts": {"tickets_path": None}}
        for name in ("design.md", "analysis.md", "api-contract.md", "test-cases.md"):
            with self.subTest(name=name):
                self.assertEqual(artifacts.artifact_path(settings, self.repo, tdir, TICKET, name),
                                 os.path.join(tdir, name))


# ---------------------------------------------------------------------------
# render_ticket_md / parse_ticket_md
# ---------------------------------------------------------------------------

class TestRenderParse(unittest.TestCase):

    def test_every_field_round_trips_and_status_is_not_stored(self):
        doc = full_ticket()
        text = artifacts.render_ticket_md(doc)
        parsed = artifacts.parse_ticket_md(text)
        self.assertNotIn("status", parsed)
        for key, value in doc.items():
            if key == "status":
                continue
            with self.subTest(field=key):
                self.assertEqual(parsed.get(key), value)
        self.assertEqual(sorted(parsed), sorted(k for k in doc if k != "status"))

    def test_front_matter_stays_inside_the_yaml_subset(self):
        text = artifacts.render_ticket_md(full_ticket())
        front, body = lib.split_front_matter(text)
        self.assertEqual(front["title"], 'Widget "alpha": the #1 feature')
        self.assertEqual(front["external"], {"provider": "jira", "key": "PROJ-1"})
        self.assertIn("## Description", body)
        self.assertIn("## Acceptance criteria", body)
        self.assertIn("## Clarifications", body)
        self.assertIn("2. Widget handles an empty list:\n   shows a hint", body)

    def test_scalar_lookalikes_stay_strings_and_nested_values_survive(self):
        doc = lib.new_ticket_doc("SHOP-3", "42", "task")
        doc.update({"assignee": "true", "due_date": "null", "labels": ["a", "b: c", "3"],
                    "meta": {"k": [1, 2], "flag": True, "none": None, "nested": {"deep": "x"}},
                    "rows": [{"n": 1, "tags": ["x"]}, {"n": 2}], "empty": []})
        parsed = artifacts.parse_ticket_md(artifacts.render_ticket_md(doc))
        for key in ("title", "assignee", "due_date", "labels", "meta", "rows", "empty"):
            with self.subTest(field=key):
                self.assertEqual(parsed[key], doc[key])

    def test_empty_body_fields_round_trip_as_empty(self):
        doc = lib.new_ticket_doc("SHOP-4", "Bare", "task")
        parsed = artifacts.parse_ticket_md(artifacts.render_ticket_md(doc))
        self.assertEqual(parsed["description"], "")
        self.assertEqual(parsed["acceptance_criteria"], [])

    def test_clarifications_are_a_read_only_mirror(self):
        entries = [{"id": "C-1", "status": "answered", "source": "user",
                    "question": "Which widget?", "answer": "The blue one"},
                   {"id": "C-2", "status": "open", "question": "How many?"}]
        text = artifacts.render_ticket_md(full_ticket(), entries)
        self.assertIn("C-1", text)
        self.assertIn("The blue one", text)
        self.assertIn("C-2", text)
        self.assertNotIn("clarifications", artifacts.parse_ticket_md(text))
        self.assertIn("None recorded", artifacts.render_ticket_md(full_ticket(), []))

    def test_a_file_without_front_matter_is_refused(self):
        with self.assertRaises(lib.YamlSubsetError):
            artifacts.parse_ticket_md("# just a heading\n")

    def test_a_key_outside_the_subset_is_refused_at_render(self):
        doc = lib.new_ticket_doc("SHOP-5", "Bad", "task")
        doc["bad key"] = 1
        with self.assertRaises(ValueError):
            artifacts.render_ticket_md(doc)


# ---------------------------------------------------------------------------
# derive_status
# ---------------------------------------------------------------------------

class TestDeriveStatus(ArtifactsCase):

    def step(self, step_id, status, ticket_id=TICKET):
        lib.update_pipeline(self.tdir(ticket_id), ticket_id, step_id, status)

    def test_table(self):
        cases = [
            ("no ledger", [], "open"),
            ("create-ticket alone", [("create-ticket", "completed")], "open"),
            ("a skip alone", [("create-ticket", "completed"), ("create-api-contract", "skipped")], "open"),
            ("design started", [("create-design", "in_progress")], "in_progress"),
            ("code in progress", [("create-ticket", "completed"), ("code", "in_progress")], "in_progress"),
            ("code completed", [("code", "completed")], "in_progress"),
            ("pr opened", [("code", "completed"), ("create-pr", "completed")], "in_review"),
            ("pr failed", [("code", "completed"), ("create-pr", "failed")], "in_progress"),
            ("merged", [("create-pr", "completed"), ("merge-pr", "completed")], "done"),
        ]
        for label, steps, expected in cases:
            with self.subTest(case=label):
                shutil.rmtree(self.tdir(TICKET), ignore_errors=True)
                self.partition()
                for step_id, status in steps:
                    self.step(step_id, status)
                self.assertEqual(artifacts.derive_status(self.tdir(TICKET)), expected)

    def test_a_delivery_ticket_is_in_review_once_its_run_recorded_a_pr(self):
        tdir = self.partition()
        self.step("create-prd", "completed")
        self.assertEqual(artifacts.derive_status(tdir), "in_progress")
        lib.append_in_progress_run(tdir, "create-prd", TICKET)
        lib.finalize_run(tdir, "create-prd", TICKET,
                         {"status": "completed", "states": {"pr": {"number": 7}}})
        self.assertEqual(artifacts.derive_status(tdir), "in_review")

    def test_an_archived_partition_is_done_whatever_the_ledger_says(self):
        tdir = self.partition()
        self.step("code", "in_progress")
        dest = os.path.join(lib.archive_dir(self.ws, REPO_ID), TICKET)
        os.makedirs(os.path.dirname(dest))
        shutil.move(tdir, dest)
        self.assertEqual(artifacts.derive_status(dest), "done")

    def test_an_epic_follows_its_children(self):
        epic = "SHOP-9"
        tdir = self.partition(epic, ttype="epic", children=["SHOP-1", "SHOP-2"])
        self.step("create-design", "completed", ticket_id=epic)
        self.index(("SHOP-1", "open"), ("SHOP-2", "open"))
        # A designed epic whose children have not started is in progress
        # (the design ran), never done.
        self.assertEqual(artifacts.derive_status(tdir), "in_progress")
        self.index(("SHOP-1", "in_progress"), ("SHOP-2", "open"))
        self.assertEqual(artifacts.derive_status(tdir), "in_progress")
        self.index(("SHOP-1", "done"), ("SHOP-2", "done"))
        self.assertEqual(artifacts.derive_status(tdir), "done")
        # The same answer when the caller passes the front matter instead of
        # letting derive_status read it from the index.
        self.assertEqual(artifacts.derive_status(tdir, {"type": "epic", "children": ["SHOP-1", "SHOP-2"]}),
                         "done")

    def test_an_epic_with_open_children_and_no_design_run_is_open(self):
        epic = "SHOP-9"
        tdir = self.partition(epic, ttype="epic", children=["SHOP-1"])
        self.index(("SHOP-1", "open"))
        self.assertEqual(artifacts.derive_status(tdir), "open")


# ---------------------------------------------------------------------------
# load_ticket / save_ticket routing -- both paths
# ---------------------------------------------------------------------------

class TestLoadSaveRouting(ArtifactsCase):

    def test_a_ticket_json_partition_loads_unchanged(self):
        """Every fixture that writes ticket.json keeps working: the fallback."""
        tdir = self.partition(status="in_review", description="d", acceptance_criteria=["a"])
        with pushd(self.repo):
            ticket = lib.load_ticket(tdir)
        self.assertEqual(ticket, lib.read_json(os.path.join(tdir, "ticket.json")))
        self.assertEqual(ticket["status"], "in_review")

    def test_without_the_tree_root_save_writes_ticket_json(self):
        tdir = self.tdir(TICKET)
        os.makedirs(tdir)
        with pushd(self.repo):
            lib.save_ticket(tdir, lib.new_ticket_doc(TICKET, "Widget", "task"))
        self.assertIn("ticket.json", os.listdir(tdir))
        self.assertNotIn("docs", os.listdir(self.repo))

    def test_an_active_tree_takes_a_new_ticket(self):
        self.activate()
        tdir = self.tdir(TICKET)
        os.makedirs(tdir)
        doc = full_ticket()
        with pushd(self.repo):
            lib.save_ticket(tdir, doc)
            loaded = lib.load_ticket(tdir)
        self.assertTrue(os.path.isfile(self.md_path()))
        self.assertNotIn("ticket.json", os.listdir(tdir))
        self.assertEqual(loaded["status"], "open")
        for key in ("id", "title", "description", "acceptance_criteria", "external", "lane"):
            with self.subTest(field=key):
                self.assertEqual(loaded[key], doc[key])

    def test_an_unmigrated_ticket_keeps_its_ticket_json_in_an_active_tree(self):
        """One home per ticket: until migrate moves it, ticket.json stays the
        file that is written, so nothing goes stale behind a reader."""
        self.activate()
        tdir = self.partition()
        with pushd(self.repo):
            ticket = lib.load_ticket(tdir)
            ticket["priority"] = "critical"
            lib.save_ticket(tdir, ticket)
            self.assertEqual(lib.load_ticket(tdir)["priority"], "critical")
        self.assertEqual(lib.read_json(os.path.join(tdir, "ticket.json"))["priority"], "critical")
        self.assertNotIn(TICKET, os.listdir(self.docs_root()))

    def test_a_migrated_ticket_is_read_and_written_as_ticket_md(self):
        self.activate()
        tdir = self.tdir(TICKET)
        os.makedirs(tdir)
        self.write_md(full_ticket())
        with pushd(self.repo):
            ticket = lib.load_ticket(tdir)
            self.assertEqual(ticket["status"], "open")
            ticket["status"] = "open"  # what a caller would flip; never stored
            ticket["title"] = "Renamed"
            lib.save_ticket(tdir, ticket)
            lib.update_pipeline(tdir, TICKET, "code", "in_progress")
            reloaded = lib.load_ticket(tdir)
        self.assertEqual(reloaded["title"], "Renamed")
        self.assertEqual(reloaded["status"], "in_progress")
        self.assertNotIn("ticket.json", os.listdir(tdir))
        self.assertNotIn("status:", read_text(self.md_path()))

    def test_a_partition_outside_this_checkouts_workspace_falls_back(self):
        """The safety property: an in-process caller whose cwd is some other
        checkout never writes into that checkout's docs tree."""
        self.activate()
        elsewhere = tempfile.mkdtemp(prefix="acs-elsewhere-")
        self.addCleanup(shutil.rmtree, elsewhere, True)
        tdir = os.path.join(elsewhere, "other-repo", TICKET)
        os.makedirs(tdir)
        with pushd(self.repo):
            lib.save_ticket(tdir, lib.new_ticket_doc(TICKET, "Widget", "task"))
            self.assertEqual(lib.load_ticket(tdir)["title"], "Widget")
        self.assertIn("ticket.json", os.listdir(tdir))
        self.assertEqual(os.listdir(self.docs_root()), [])

    def test_opted_out_never_touches_the_tree(self):
        self.write_settings({"ticket_prefix": "SHOP", "artifacts": {"tickets_path": None}})
        self.activate()
        tdir = self.tdir(TICKET)
        os.makedirs(tdir)
        with pushd(self.repo):
            lib.save_ticket(tdir, lib.new_ticket_doc(TICKET, "Widget", "task"))
        self.assertIn("ticket.json", os.listdir(tdir))
        self.assertEqual(os.listdir(self.docs_root()), [])

    def test_a_corrupt_ticket_md_reads_as_absent_with_a_warning(self):
        self.activate()
        tdir = self.tdir(TICKET)
        os.makedirs(tdir)
        path = self.md_path()
        os.makedirs(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("---\nid: SHOP-1\nid: SHOP-1\n---\n")
        err = io.StringIO()
        with pushd(self.repo), contextlib.redirect_stderr(err):
            self.assertIsNone(lib.load_ticket(tdir))
        self.assertIn("ticket.md", err.getvalue())
        self.assertIn("duplicate key", err.getvalue())

    def test_the_pointer_finds_the_ticket_when_the_checkout_cannot_be_resolved(self):
        self.activate()
        tdir = self.tdir(TICKET)
        os.makedirs(tdir)
        path = self.write_md(full_ticket())
        lib.write_json(os.path.join(tdir, artifacts.MOVED_POINTER_FILENAME), {"moved_to": path})
        with pushd(self.tmp):  # not a git checkout
            ticket = lib.load_ticket(tdir)
        self.assertEqual(ticket["id"], TICKET)
        self.assertEqual(ticket["status"], "open")

    def test_the_hook_scripts_create_and_flip_tickets_in_the_tree(self):
        """End to end through the real CLIs: new-ticket.py writes ticket.md,
        skill-start flips the derived status, ticket show reads it back."""
        self.activate()
        ticket = self.new_ticket("Ship the thing", "task")
        tdir = self.tdir(ticket)
        self.assertTrue(os.path.isfile(self.md_path(ticket)))
        self.assertNotIn("ticket.json", os.listdir(tdir))
        out = self.run_script("acs.py", "ticket", "show", "--ticket", ticket)
        self.assertEqual(out.returncode, 0, out.stderr)
        shown = json.loads(out.stdout)["ticket"]
        self.assertEqual((shown["id"], shown["title"], shown["status"]), (ticket, "Ship the thing", "open"))
        out = self.start("code", ticket)
        self.assertEqual(out.returncode, 0, out.stderr)
        out = self.run_script("acs.py", "ticket", "show", "--ticket", ticket)
        self.assertEqual(json.loads(out.stdout)["ticket"]["status"], "in_progress")
        index = lib.read_json(lib.index_path(self.ws, REPO_ID))["tickets"][ticket]
        self.assertEqual(index["status"], "in_progress")


# ---------------------------------------------------------------------------
# migrate
# ---------------------------------------------------------------------------

class TestMigrate(ArtifactsCase):

    def setUp(self):
        super().setUp()
        self.a = self.partition("SHOP-1", description="A", acceptance_criteria=["one"])
        self.b = self.partition("SHOP-2", needs_design=True)
        with open(os.path.join(self.b, "design.md"), "w") as fh:
            fh.write("# Design B\n")
        os.makedirs(os.path.join(self.a, "phases", "code"))
        with open(os.path.join(self.a, "phases", "code", "plan.md"), "w") as fh:
            fh.write("# Plan A\n")
        lib.write_json(os.path.join(self.a, "clarifications.json"), {"ticket_id": "SHOP-1", "clarifications": [
            {"id": "C-1", "status": "answered", "source": "user", "question": "Q?", "answer": "A."}]})
        archived = os.path.join(lib.archive_dir(self.ws, REPO_ID), "SHOP-0")
        os.makedirs(archived)
        lib.write_json(os.path.join(archived, "ticket.json"), lib.new_ticket_doc("SHOP-0", "Old", "task"))
        self.archived = archived

    def migrate(self, dry_run=False):
        return artifacts.migrate(self.ws, REPO_ID, lib.DEFAULT_SETTINGS, self.repo, dry_run=dry_run)

    def test_dry_run_lists_the_moves_and_writes_nothing(self):
        report = self.migrate(dry_run=True)
        self.assertTrue(report["dry_run"])
        self.assertEqual(report["migrated"], ["SHOP-1", "SHOP-2"])
        kinds = {(a["ticket"], a["action"], a["file"]) for a in report["actions"]}
        self.assertIn(("SHOP-1", "render", "ticket.md"), kinds)
        self.assertIn(("SHOP-1", "copy", "plan.md"), kinds)
        self.assertIn(("SHOP-2", "copy", "design.md"), kinds)
        self.assertNotIn("docs", os.listdir(self.repo))
        self.assertIn("ticket.json", os.listdir(self.a))

    def test_the_move_renders_copies_points_and_leaves_the_archive_alone(self):
        report = self.migrate()
        self.assertEqual(report["migrated"], ["SHOP-1", "SHOP-2"])
        self.assertEqual(report["docs_root"], self.docs_root())
        md = self.md_path("SHOP-1")
        text = read_text(md)
        self.assertIn("## Description\n\nA\n", text)
        self.assertIn("1. one", text)
        self.assertIn("C-1", text)
        self.assertEqual(read_text(os.path.join(self.docs_root(), "SHOP-1", "plan.md")), "# Plan A\n")
        self.assertEqual(read_text(os.path.join(self.docs_root(), "SHOP-2", "design.md")), "# Design B\n")
        self.assertNotIn("ticket.json", os.listdir(self.a))
        pointer = lib.read_json(os.path.join(self.a, artifacts.MOVED_POINTER_FILENAME))
        self.assertEqual(pointer["moved_to"], md)
        self.assertEqual(pointer["relative"], os.path.join("docs", "tickets", "SHOP-1", "ticket.md"))
        self.assertIn("ticket.json", os.listdir(self.archived))
        self.assertNotIn("SHOP-0", os.listdir(self.docs_root()))
        with pushd(self.repo):
            self.assertEqual(lib.load_ticket(self.a)["description"], "A")

    def test_migrate_is_idempotent(self):
        self.migrate()
        before = read_text(self.md_path("SHOP-1"))
        pointer = lib.read_json(os.path.join(self.a, artifacts.MOVED_POINTER_FILENAME))
        report = self.migrate()
        self.assertEqual(report["migrated"], [])
        self.assertEqual(report["already"], ["SHOP-1", "SHOP-2"])
        self.assertEqual(read_text(self.md_path("SHOP-1")), before)
        self.assertEqual(lib.read_json(os.path.join(self.a, artifacts.MOVED_POINTER_FILENAME)), pointer)

    def test_a_ticket_md_already_in_the_tree_is_kept_over_a_stale_ticket_json(self):
        newer = lib.new_ticket_doc("SHOP-1", "Newer title", "task")
        self.write_md(newer, "SHOP-1")
        report = self.migrate()
        self.assertIn(("SHOP-1", "keep", "ticket.md"),
                      {(a["ticket"], a["action"], a["file"]) for a in report["actions"]})
        self.assertIn("Newer title", read_text(self.md_path("SHOP-1")))
        self.assertNotIn("ticket.json", os.listdir(self.a))

    def test_a_locked_partition_refuses_the_whole_migration(self):
        lib.write_json(lib.lock_path(self.b), {"checkout_id": "x", "created_at": lib.now_iso()})
        with self.assertRaises(lib.GateError) as ctx:
            self.migrate()
        self.assertIn("SHOP-2", str(ctx.exception))
        self.assertIn("ticket.json", os.listdir(self.a))

    def test_opted_out_refuses(self):
        with self.assertRaises(lib.GateError):
            artifacts.migrate(self.ws, REPO_ID, {"artifacts": {"tickets_path": None}}, self.repo)

    def test_the_cli_wraps_migrate_and_show(self):
        out = self.run_script("acs.py", "artifacts", "migrate", "--dry-run")
        self.assertEqual(out.returncode, 0, out.stderr)
        body = json.loads(out.stdout)
        self.assertTrue(body["ok"])
        self.assertTrue(body["dry_run"])
        self.assertEqual(body["migrated"], ["SHOP-1", "SHOP-2"])

        out = self.run_script("acs.py", "artifacts", "migrate")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout)["migrated"], ["SHOP-1", "SHOP-2"])

        out = self.run_script("acs.py", "artifacts", "show", "--ticket", "SHOP-2")
        self.assertEqual(out.returncode, 0, out.stderr)
        shown = json.loads(out.stdout)
        self.assertTrue(shown["ok"])
        self.assertEqual(shown["source"], "ticket.md")
        self.assertEqual(shown["source_path"], self.md_path("SHOP-2"))
        self.assertEqual(shown["docs_dir"], os.path.join(self.docs_root(), "SHOP-2"))
        self.assertTrue(shown["active"])
        self.assertEqual(shown["status"], "open")
        self.assertEqual(shown["artifacts"]["design.md"], os.path.join(self.docs_root(), "SHOP-2", "design.md"))
        self.assertIsNone(shown["artifacts"]["plan.md"])
        self.assertEqual(shown["ticket"]["id"], "SHOP-2")

        out = self.run_script("acs.py", "artifacts", "show", "--ticket", "SHOP-77")
        self.assertEqual(out.returncode, 2)
        self.assertIn("acs artifacts show:", out.stderr)

    def test_show_on_an_unmigrated_ticket_names_ticket_json(self):
        out = self.run_script("acs.py", "artifacts", "show", "--ticket", "SHOP-1")
        self.assertEqual(out.returncode, 0, out.stderr)
        shown = json.loads(out.stdout)
        self.assertEqual(shown["source"], "ticket.json")
        self.assertFalse(shown["active"])
        self.assertEqual(shown["artifacts"]["plan.md"], os.path.join(self.a, "phases", "code", "plan.md"))


# ---------------------------------------------------------------------------
# The file-map guard: the docs tree is a control input
# ---------------------------------------------------------------------------

class TestGuardControlInput(FileMapGuardCase):

    def test_the_ticket_docs_tree_is_denied_even_when_declared(self):
        self.declare("docs/", "src/a.py")
        self.spawn_executor()
        for target in ("docs/tickets/%s/plan.md" % self.ticket,
                       "docs/tickets/OTHER-9/design.md",
                       os.path.join(self.repo, "docs", "tickets", self.ticket, "ticket.md")):
            with self.subTest(target=target):
                out = self.write_attempt(target)
                self.assertEqual(out.returncode, 2, out.stderr)
                self.assertIn("control input", out.stderr)
                self.assertIn("needs_input", out.stderr)
        self.assertEqual(self.write_attempt("docs/other.md").returncode, 0)

    def test_opting_out_of_the_tree_lifts_the_denial(self):
        self.write_settings({"ticket_prefix": "SHOP", "test_coverage_percent": 90,
                             "artifacts": {"tickets_path": None}})
        self.declare("docs/")
        self.spawn_executor()
        self.assertEqual(self.write_attempt("docs/tickets/%s/plan.md" % self.ticket).returncode, 0)


if __name__ == "__main__":
    unittest.main()
