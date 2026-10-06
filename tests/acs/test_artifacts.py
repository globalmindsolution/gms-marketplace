"""The ticket document and the legacy docs tree, `docs/tickets/<ID>/`.

ADR-0090 moved the human-facing ticket documents into the repo docs tree;
ADR-0128 takes the TICKET back out: a ticket lives only in the workspace and
the tracker, and a run's documents are filed by phase (acs_lib.doc_layout,
tests/acs/test_requirements.py). What is pinned here:

  * ticket.md (the legacy rendering) is ticket.json as YAML front matter
    (every field but `status`) over a markdown body -- and it still
    round-trips through the strict YAML subset, field for field, because an
    existing docs/tickets/<ID>/ticket.md must stay readable;
  * `status` is DERIVED from the ledger and the archive (derive_status);
  * load_ticket reads the partition's ticket.json first, else the legacy
    ticket.md, else the file the ticket.json.moved pointer names;
  * save_ticket ALWAYS writes the partition's ticket.json -- never the docs
    tree, not for a new ticket and not for a migrated one;
  * `artifacts migrate` is retired: it reports so and writes nothing;
  * the executor file-map guard still treats the legacy tree as a control
    input.

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
from acs_case import AcsWorkspaceCase, REPO_ROOT, SCRIPTS, pushd  # noqa: E402
from test_file_map_guard import FileMapGuardCase  # noqa: E402

sys.path.insert(0, SCRIPTS)
import acs_lib as lib  # noqa: E402
from acs_lib import artifacts  # noqa: E402

TICKET = "SHOP-1"
REPO_ID = "acme-shop"
#: The description templates /acs:create-ticket builds every ticket body from.
TEMPLATES_DIR = os.path.join(REPO_ROOT, "plugins", "acs", "templates")
DESCRIPTION_TEMPLATES = ("task-default", "story-default", "epic-default", "bug-default")


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
        due_date="2026-12-01")
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

    def test_the_path_is_docs_tickets_under_the_checkout(self):
        self.assertEqual(artifacts.TICKETS_PATH, "docs/tickets")
        self.assertEqual(artifacts.ticket_docs_dir("/repo", "SHOP-1"),
                         os.path.join("/repo", "docs", "tickets", "SHOP-1"))

    def test_a_missing_checkout_resolves_nothing(self):
        self.assertIsNone(artifacts.ticket_docs_dir(None, "SHOP-1"))
        self.assertIsNone(artifacts.ticket_docs_root(None))


class TestArtifactPath(ArtifactsCase):

    def test_docs_folder_wins_then_partition_then_legacy(self):
        tdir = self.partition()
        docs_plan = os.path.join(self.docs_root(), TICKET, "plan.md")
        legacy_plan = os.path.join(tdir, "phases", "code", "plan.md")
        # Nothing exists: the partition -- never a path in the docs tree
        # (ADR-0128: nothing writes docs/tickets/ any more).
        self.assertEqual(artifacts.artifact_path(self.repo, tdir, TICKET, "plan.md"),
                         os.path.join(tdir, "plan.md"))
        os.makedirs(os.path.dirname(legacy_plan))
        with open(legacy_plan, "w") as fh:
            fh.write("# plan\n")
        self.assertEqual(artifacts.artifact_path(self.repo, tdir, TICKET, "plan.md"), legacy_plan)
        with open(os.path.join(tdir, "plan.md"), "w") as fh:
            fh.write("# plan\n")
        self.assertEqual(artifacts.artifact_path(self.repo, tdir, TICKET, "plan.md"),
                         os.path.join(tdir, "plan.md"))
        os.makedirs(os.path.dirname(docs_plan))
        with open(docs_plan, "w") as fh:
            fh.write("# plan\n")
        self.assertEqual(artifacts.artifact_path(self.repo, tdir, TICKET, "plan.md"), docs_plan)


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

    def test_a_shipped_description_template_round_trips_byte_for_byte(self):
        """The regression that made this a blocking defect: every shipped
        description template is `## `-headed (task-default even opens with
        `## Description`), and /acs:create-ticket builds every ticket's body
        from one of them. A forward section scan cut the description at its
        first heading, so the FIRST load-save round trip after `artifacts
        migrate` silently deleted most of a committed document."""
        for name in DESCRIPTION_TEMPLATES:
            with self.subTest(template=name):
                body = read_text(os.path.join(TEMPLATES_DIR, "%s.md" % name)).strip("\n")
                self.assertIn("\n## ", "\n" + body, "template no longer h2-headed")
                doc = full_ticket()
                doc["description"] = body
                parsed = artifacts.parse_ticket_md(artifacts.render_ticket_md(doc))
                self.assertEqual(parsed["description"], body)
                self.assertEqual(parsed["acceptance_criteria"], doc["acceptance_criteria"])

    def test_a_description_carrying_the_other_section_headings_round_trips(self):
        """story-default's body contains `## Acceptance criteria` and
        task-default's contains `## Description`: the boundaries are the LAST
        occurrences, not the first."""
        doc = full_ticket()
        doc["description"] = ("## Description\n\nintro\n\n## Acceptance criteria\n\n- [ ] drafted\n"
                             "\n## Clarifications\n\nnone yet\n\n## Notes\n\nacs-ticket: SHOP-1")
        parsed = artifacts.parse_ticket_md(artifacts.render_ticket_md(doc))
        self.assertEqual(parsed["description"], doc["description"])
        self.assertEqual(parsed["acceptance_criteria"], doc["acceptance_criteria"])

    def test_the_round_trip_is_stable_under_repeated_saves(self):
        """Re-rendering a parsed ticket is a fixed point -- the loss the old
        parser took compounded: each save wrote back less than the last."""
        doc = full_ticket()
        doc["description"] = read_text(os.path.join(TEMPLATES_DIR, "task-default.md")).strip("\n")
        first = artifacts.render_ticket_md(doc)
        parsed = artifacts.parse_ticket_md(first)
        parsed["status"] = "in_progress"  # what a caller flips; never stored
        self.assertEqual(artifacts.render_ticket_md(parsed), first)

    def test_a_clarification_cannot_forge_a_section_heading(self):
        """The mirror is the last section and is scanned for from the end, so
        a recorded question/answer is folded onto one line."""
        entries = [{"id": "C-1", "status": "answered", "source": "user",
                    "question": "Which widget?\n## Acceptance criteria\n1. forged",
                    "answer": "The blue one\n## Clarifications"}]
        doc = full_ticket()
        text = artifacts.render_ticket_md(doc, entries)
        parsed = artifacts.parse_ticket_md(text)
        self.assertEqual(parsed["acceptance_criteria"], doc["acceptance_criteria"])
        self.assertEqual(parsed["description"], doc["description"])
        self.assertIn("- **C-1** (answered, user): Which widget? ## Acceptance criteria 1. forged", text)

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

    def rdir(self, ticket_id=TICKET):
        """The RUN over this ticket. A ticket is a run SUBJECT, not the
        partition a run writes into (§4.2): the ledger lives under
        `<repo>/runs/<run-id>/`, and a ticket-subject run's id is the ticket
        id."""
        return lib.run_dir(lib.repo_dir(self.ws, REPO_ID), ticket_id)

    def step(self, step_id, status, ticket_id=TICKET):
        """A ticket's status is derived from its RUN's ledger now, so seeding
        a step means writing run.json's `steps` entry."""
        rdir = self.rdir(ticket_id)
        os.makedirs(rdir, exist_ok=True)
        doc = lib.read_json(os.path.join(rdir, "run.json"))
        if not isinstance(doc, dict):
            doc = {"run_id": ticket_id, "workflow": "ship", "workflow_version": 3,
                   "subject": {"kind": "ticket", "ticket_id": ticket_id},
                   "status": "in_progress", "steps": {}}
        doc.setdefault("steps", {})[step_id] = {"status": status}
        lib.write_json(os.path.join(rdir, "run.json"), doc)

    def test_table(self):
        cases = [
            ("no ledger", [], "open"),
            ("create-ticket alone", [("create-ticket", "completed")], "open"),
            # ADR-0138: breaking a ticket down mints its children; it starts no work.
            ("breakdown-ticket alone", [("create-ticket", "completed"),
                                        ("breakdown-ticket", "completed")], "open"),
            ("a skip alone", [("create-ticket", "completed"), ("create-test-docs", "skipped")], "open"),
            ("design started", [("create-tech-design", "in_progress")], "in_progress"),
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

    def test_a_legacy_delivery_ticket_is_in_review_once_its_run_recorded_a_pr(self):
        """Minted before ADR-0127, when create-prd opened its own PR."""
        tdir = self.partition()
        self.step("create-prd", "completed")
        self.assertEqual(artifacts.derive_status(tdir), "in_progress")
        rdir = self.rdir()
        lib.append_invocation(rdir, "create-prd", TICKET)
        lib.finalize_invocation(rdir, "create-prd", TICKET,
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
        self.step("create-tech-design", "completed", ticket_id=epic)
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

    def test_the_docs_tree_never_takes_a_new_ticket(self):
        """ADR-0128: a ticket lives in the workspace; an existing docs tree is
        read, never written."""
        self.activate()
        tdir = self.tdir(TICKET)
        os.makedirs(tdir)
        doc = full_ticket()
        with pushd(self.repo):
            lib.save_ticket(tdir, doc)
            loaded = lib.load_ticket(tdir)
        self.assertFalse(os.path.exists(self.md_path()))
        self.assertIn("ticket.json", os.listdir(tdir))
        self.assertEqual(os.listdir(self.docs_root()), [])
        self.assertEqual(loaded["status"], "in_progress")
        for key in ("id", "title", "description", "acceptance_criteria",
                    "external", "needs_design", "due_date"):
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

    def test_a_migrated_ticket_reads_its_ticket_md_and_saves_to_the_partition(self):
        """A ticket migrated into the tree under ADR-0090 still READS from its
        ticket.md; the first save writes ticket.json into the partition, which
        wins from then on, and the tracked ticket.md is left byte for byte."""
        self.activate()
        tdir = self.tdir(TICKET)
        os.makedirs(tdir)
        md = self.write_md(full_ticket())
        before = read_text(md)
        with pushd(self.repo):
            ticket = lib.load_ticket(tdir)
            self.assertEqual(ticket["status"], "open")
            self.assertEqual(artifacts.ticket_source(tdir)[0], "ticket.md")
            ticket["title"] = "Renamed"
            lib.save_ticket(tdir, ticket)
            self.assertEqual(artifacts.ticket_source(tdir)[0], "ticket.json")
            # The derived status comes from the RUN's ledger, never from a
            # field in the document: a status written into ticket.md would be
            # a second answer nothing keeps in step with the run.
            rdir = lib.run_dir(lib.repo_dir(self.ws, REPO_ID), TICKET)
            os.makedirs(rdir, exist_ok=True)
            lib.write_json(os.path.join(rdir, "run.json"), {
                "run_id": TICKET, "workflow": "ship", "workflow_version": 3,
                "subject": {"kind": "ticket", "ticket_id": TICKET},
                "status": "in_progress",
                "steps": {"code": {"status": "in_progress"}}})
            reloaded = lib.load_ticket(tdir)
        self.assertEqual(reloaded["title"], "Renamed")
        self.assertIn("ticket.json", os.listdir(tdir))
        self.assertEqual(read_text(md), before)

    def test_a_templated_description_survives_a_real_save_load_save(self):
        """The defect's reachable path: after migrate, ticket.md is the file
        every hooked run loads, mutates and saves. A ticket whose description
        is a shipped template body must come back whole, twice."""
        self.activate()
        tdir = self.tdir(TICKET)
        os.makedirs(tdir)
        doc = full_ticket()
        doc["description"] = read_text(os.path.join(TEMPLATES_DIR, "task-default.md")).strip("\n")
        with pushd(self.repo):
            lib.save_ticket(tdir, doc)
            loaded = lib.load_ticket(tdir)
            self.assertEqual(loaded["description"], doc["description"])
            loaded["priority"] = "critical"
            lib.save_ticket(tdir, loaded)
            again = lib.load_ticket(tdir)
        self.assertEqual(again["description"], doc["description"])
        self.assertEqual(again["acceptance_criteria"], doc["acceptance_criteria"])
        self.assertEqual(again["priority"], "critical")

    def test_a_save_never_rewrites_a_legacy_ticket_md(self):
        """The legacy ticket.md is a TRACKED file: no save -- a status flip or
        a real change -- dirties it again."""
        self.activate()
        tdir = self.tdir(TICKET)
        os.makedirs(tdir)
        md = self.write_md(full_ticket())
        before, mtime = read_text(md), os.path.getmtime(md)
        with pushd(self.repo):
            ticket = lib.load_ticket(tdir)
            ticket["status"] = "in_review"
            lib.save_ticket(tdir, ticket)
            ticket["title"] = "Renamed"
            lib.save_ticket(tdir, ticket)
        self.assertEqual((read_text(md), os.path.getmtime(md)), (before, mtime))
        self.assertEqual(lib.read_json(os.path.join(tdir, "ticket.json"))["title"], "Renamed")

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

    def test_a_stale_tickets_path_setting_changes_nothing(self):
        """ADR-0102 removed the key; ADR-0128 removed the tree as a home. A
        consumer file that still carries it gets ticket.json like everyone."""
        self.write_settings({"ticket_prefix": "SHOP", "artifacts": {"tickets_path": None}})
        self.activate()
        tdir = self.tdir(TICKET)
        os.makedirs(tdir)
        with pushd(self.repo):
            lib.save_ticket(tdir, lib.new_ticket_doc(TICKET, "Widget", "task"))
        self.assertFalse(os.path.exists(self.md_path()))
        self.assertIn("ticket.json", os.listdir(tdir))

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

    def test_the_hook_scripts_create_and_flip_tickets_in_the_workspace(self):
        """End to end through the real CLIs: new-ticket.py writes ticket.json
        even with a docs tree present, step start flips the derived status,
        ticket show reads it back -- and the repo's tree is never touched."""
        self.activate()
        ticket = self.new_ticket("Ship the thing", "task")
        tdir = self.tdir(ticket)
        self.assertFalse(os.path.exists(self.md_path(ticket)))
        self.assertIn("ticket.json", os.listdir(tdir))
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
        self.assertEqual(os.listdir(self.docs_root()), [])

    def test_new_ticket_reports_the_file_it_wrote(self):
        """The caller gets the path in `ticket_document`: the partition's
        ticket.json, even when the repo has a docs/tickets/ tree."""
        self.activate()
        out = self.run_script("new-ticket.py", "--title", "Tracked", "--type", "task")
        self.assertEqual(out.returncode, 0, out.stderr)
        body = json.loads(out.stdout)
        self.assertEqual(body["ticket_document"],
                         os.path.join(body["partition"], "ticket.json"))
        self.assertTrue(os.path.isfile(body["ticket_document"]))
        self.assertEqual(os.listdir(self.docs_root()), [])

    def test_new_ticket_reports_ticket_json_when_the_tree_is_not_active(self):
        out = self.run_script("new-ticket.py", "--title", "Untracked", "--type", "task")
        self.assertEqual(out.returncode, 0, out.stderr)
        body = json.loads(out.stdout)
        self.assertEqual(body["ticket_document"],
                         os.path.join(body["partition"], "ticket.json"))


# ---------------------------------------------------------------------------
# Who commits the tracked documents (ADR 0090)
# ---------------------------------------------------------------------------

class TestCommitOwnership(unittest.TestCase):
    """Every document in the docs tree is a tracked file, so each one needs a
    committer -- and since ADR-0127 there is exactly one: /acs:create-pr. The
    Build skills publish into the working tree and record what they wrote
    (`states.files`); create-pr splits those paths into reviewable commits,
    the ticket docs folder first. These assertions keep a skill from quietly
    growing its own commit step back."""

    def skill(self, name):
        """The SKILL.md with whitespace runs folded, so a phrase check cannot
        fail merely because markdown word-wrap inserted a line break."""
        raw = read_text(os.path.join(REPO_ROOT, "plugins", "acs", "skills", name, "SKILL.md"))
        return " ".join(raw.split())

    def test_analyze_ticket_records_the_whole_docs_folder_and_commits_nothing(self):
        """ADR-0127: `acs.py analysis publish` writes the docs folder and
        records its paths for /acs:create-pr, which makes the ticket-docs
        commit; the controller itself never stages or commits
        (tests/acs/test_analysis_loop.py proves it)."""
        body = self.skill("analyze-requirements")
        self.assertIn("publication.files", body)
        source = read_text(os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts",
                                        "acs_lib", "analysis_publish.py"))
        self.assertNotIn('"commit"', source.split('"""', 2)[2])
        self.assertNotIn('"add"', source)

    def test_create_design_publishes_and_commits_nothing_on_any_branch(self):
        """ADR-0127: not on the default branch, and not on a ticket branch
        that happens to be checked out for a re-design either."""
        body = self.skill("create-tech-design")
        self.assertIn('cp "<partition>/steps/create-tech-design/tech-design.md" "<design_path>"', body)
        self.assertIn("never stages, commits or pushes (ADR-0127) — not on the default branch, and "
                      "not on a ticket branch", body)
        self.assertIn("`states.files`", body)
        self.assertNotRegex(body, r"commit `<design_path>` on it")

    def test_the_build_skills_leave_what_they_publish_uncommitted(self):
        """ADR-0127: only /acs:create-pr branches and commits. Each Build skill
        publishes into the working tree, records the path in `states.files`
        for create-pr's commit plan, and never runs a branch or commit step."""
        for name, artifact in (("analyze-requirements", "analysis.md"), ("create-impl-plan", "plan.md"),
                               ("create-api-contract", "api-contract.md"),
                               ("create-test-docs", "test-cases.md")):
            with self.subTest(skill=name):
                body = self.skill(name)
                self.assertIn("never stages, commits or pushes (ADR-0127)", body)
                self.assertIn("`states.files`", body)
                self.assertIn("`/acs:create-pr`", body)
                self.assertNotRegex(body, r"[Cc]ommit[^.]{0,120}on the ticket branch")
                self.assertNotIn("git checkout -b", body)
                self.assertIn(artifact, body)


# ---------------------------------------------------------------------------
# migrate
# ---------------------------------------------------------------------------

class TestMigrate(ArtifactsCase):
    """`artifacts migrate` is retired (ADR-0128); `artifacts show` reads the
    legacy tree as a fallback."""

    def setUp(self):
        super().setUp()
        self.a = self.partition("SHOP-1", description="A", acceptance_criteria=["one"])
        self.b = self.partition("SHOP-2", needs_design=True)
        os.makedirs(os.path.join(self.a, "phases", "code"))
        with open(os.path.join(self.a, "phases", "code", "plan.md"), "w") as fh:
            fh.write("# Plan A\n")
        legacy = os.path.join(self.docs_root(), "SHOP-2")
        os.makedirs(legacy)
        with open(os.path.join(legacy, "design.md"), "w") as fh:
            fh.write("# Design B\n")

    def test_migrate_is_retired_and_writes_nothing(self):
        for dry_run in (True, False):
            with self.subTest(dry_run=dry_run):
                report = artifacts.migrate(self.ws, REPO_ID, self.repo, dry_run=dry_run)
                self.assertTrue(report["retired"])
                self.assertEqual((report["migrated"], report["actions"]), ([], []))
                self.assertEqual(report["already"], ["SHOP-1", "SHOP-2"])
        self.assertIn("ticket.json", os.listdir(self.a))
        self.assertEqual(os.listdir(self.docs_root()), ["SHOP-2"])
        self.assertNotIn(artifacts.MOVED_POINTER_FILENAME, os.listdir(self.a))
        with self.assertRaises(lib.GateError):
            artifacts.migrate(self.ws, REPO_ID, None)

    def test_the_cli_reports_migrate_retired_and_show_reads_the_legacy_tree(self):
        out = self.run_script("acs.py", "artifacts", "migrate", "--dry-run")
        self.assertEqual(out.returncode, 0, out.stderr)
        body = json.loads(out.stdout)
        self.assertTrue(body["ok"] and body["retired"])
        self.assertEqual(body["migrated"], [])

        out = self.run_script("acs.py", "artifacts", "show", "--ticket", "SHOP-2")
        self.assertEqual(out.returncode, 0, out.stderr)
        shown = json.loads(out.stdout)
        self.assertTrue(shown["ok"])
        self.assertEqual(shown["source"], "ticket.json")
        self.assertEqual(shown["status"], "open")
        self.assertIsNone(shown["feature"])
        self.assertIsNone(shown["paths"]["tech-design.md"], "no feature: no write target")
        # ADR-0135: the legacy design.md is read where tech-design.md is absent.
        self.assertEqual(shown["artifacts"]["tech-design.md"],
                         os.path.join(self.docs_root(), "SHOP-2", "design.md"))
        self.assertNotIn("design.md", shown["paths"], "design.md is only a read fallback")
        self.assertEqual(shown["legacy_dir"], os.path.join(self.docs_root(), "SHOP-2"))
        self.assertIsNone(shown["artifacts"]["plan.md"])
        self.assertEqual(shown["ticket"]["id"], "SHOP-2")

        out = self.run_script("acs.py", "artifacts", "show", "--ticket", "SHOP-77")
        self.assertEqual(out.returncode, 2)
        self.assertIn("acs artifacts show:", out.stderr)

    def test_show_on_a_ticket_names_ticket_json_and_the_partition_plan(self):
        out = self.run_script("acs.py", "artifacts", "show", "--ticket", "SHOP-1")
        self.assertEqual(out.returncode, 0, out.stderr)
        shown = json.loads(out.stdout)
        self.assertEqual(shown["source"], "ticket.json")
        self.assertEqual(shown["artifacts"]["plan.md"],
                         os.path.join(self.a, "phases", "code", "plan.md"))


# ---------------------------------------------------------------------------
# The file-map guard: the docs tree is a control input
# ---------------------------------------------------------------------------

class TestGuardControlInput(FileMapGuardCase):

    def test_the_ticket_docs_tree_is_denied_even_when_declared(self):
        self.declare("docs/", "src/a.py")
        self.spawn_writer()
        for target in ("docs/tickets/%s/plan.md" % self.ticket,
                       "docs/tickets/OTHER-9/design.md",
                       os.path.join(self.repo, "docs", "tickets", self.ticket, "ticket.md")):
            with self.subTest(target=target):
                out = self.write_attempt(target)
                self.assertEqual(out.returncode, 2, out.stderr)
                self.assertIn("control input", out.stderr)
                self.assertIn("needs_input", out.stderr)
        self.assertEqual(self.write_attempt("docs/other.md").returncode, 0)

    def test_a_stale_tickets_path_null_does_not_lift_the_denial(self):
        """ADR-0102: the opt-out went with the key -- a consumer file that still
        carries it gets no unguarded ticket docs."""
        self.write_settings({"ticket_prefix": "SHOP", "tests": {"coverage": 90},
                             "artifacts": {"tickets_path": None}})
        self.declare("docs/")
        self.spawn_writer()
        self.assertEqual(self.write_attempt("docs/tickets/%s/plan.md" % self.ticket).returncode, 2)


if __name__ == "__main__":
    unittest.main()
