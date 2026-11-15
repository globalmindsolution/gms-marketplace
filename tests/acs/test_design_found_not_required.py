"""Tickets carry no design flag; a design is FOUND, never required (ADR-0139).

The user runs /acs:create-tech-design by hand, so nothing records whether a
ticket "needs" a design any more. Pinned here, against real temp repos and
workspaces:

  * new-ticket.py writes no `needs_design` (epic or story), the index row has
    none, and `--needs-design` is gone -- argparse refuses it, exit 2;
  * an OLD ticket carrying the key still validates and loads, and the key
    decides nothing;
  * `requirements refine` refuses the key, naming ADR-0139, and an old run
    whose refined record still holds it is read with the key ignored;
  * `design_source` -- the ticket's own tech design (current or legacy
    `design.md` name), else its parent epic's, else none -- and the step-start
    `context.design = {exists, dir, source}`, ticketless runs included;
  * the create-tech-design gate admits a story with no flag;
  * an analysis README written under the old front-matter spec still validates.

Run:  python3 -m unittest tests.acs.test_design_found_not_required -v
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import REPO_ROOT, SCRIPTS, lib  # noqa: E402
from test_requirements import REPO_ID, RequirementsCase, decide_shared  # noqa: E402

from acs_lib import analysis_folder, requirements as R, schemasubset  # noqa: E402

sys.path.insert(0, SCRIPTS)
from front_matter_check import check_front_matter, parse_spec  # noqa: E402


def _schema(name):
    with open(os.path.join(REPO_ROOT, "plugins", "acs", "schemas", name), encoding="utf-8") as fh:
        return json.load(fh)


class TicketsCarryNoFlag(RequirementsCase):

    def test_no_writer_records_the_flag(self):
        for ttype in ("epic", "story", "task", "bug"):
            with self.subTest(type=ttype):
                tid = self.new_ticket("A %s" % ttype, ttype)
                self.assertNotIn("needs_design", lib.load_ticket(self.tdir(tid)))
                index = lib.read_json(lib.index_path(self.ws, REPO_ID))["tickets"][tid]
                self.assertNotIn("needs_design", index)
        self.assertNotIn("needs_design", lib.new_ticket_doc("SHOP-9", "t", "epic"))

    def test_the_schemas_no_longer_declare_it(self):
        ticket = _schema("ticket.schema.json")
        self.assertNotIn("needs_design", ticket["required"])
        self.assertNotIn("needs_design", ticket["properties"])
        row = _schema("tickets-index.schema.json")["properties"]["tickets"][
            "additionalProperties"]
        self.assertNotIn("needs_design", row["properties"])

    def test_the_cli_flag_is_gone(self):
        for value in ("true", "false"):
            with self.subTest(value=value):
                out = self.run_script("new-ticket.py", "--title", "T", "--type", "task",
                                      "--needs-design", value)
                self.assertEqual(out.returncode, 2, out.stdout + out.stderr)
                self.assertIn("--needs-design", out.stderr)
        self.assertFalse(os.path.isdir(self.tdir("SHOP-1")), "nothing was minted")

    def test_an_old_ticket_carrying_the_flag_still_validates_and_loads(self):
        tid = self.new_ticket("Old story", "story")
        tdir = self.tdir(tid)
        old = dict(lib.load_ticket(tdir), needs_design=True)
        lib.save_ticket(tdir, old)
        lib.update_index(self.ws, REPO_ID, old)
        loaded = lib.load_ticket(tdir)
        self.assertIs(loaded["needs_design"], True, "kept verbatim, not migrated")
        stored = lib.read_json(os.path.join(tdir, "ticket.json"))
        self.assertEqual(schemasubset.schema_errors(_schema("ticket.schema.json"), stored), [])
        index = lib.read_json(lib.index_path(self.ws, REPO_ID))
        self.assertEqual(
            schemasubset.schema_errors(_schema("tickets-index.schema.json"), index), [])
        self.assertNotIn("needs_design", index["tickets"][tid],
                         "a re-indexed row sheds the legacy key")
        # ...and it decides nothing: no design is "required" by it.
        self.assertEqual(lib.design_source(self.ctx(), tdir, loaded),
                         (False, None, None))


class RefineRefusesTheKey(RequirementsCase):

    def test_refine_refuses_needs_design_naming_the_adr(self):
        rdir = self.new_run({"kind": "prompt", "text": "x"})
        for value in (True, False):
            with self.subTest(value=value), self.assertRaises(lib.GateError) as caught:
                R.refine(rdir, self.ctx(), {"needs_design": value})
            self.assertIn("ADR-0139", str(caught.exception))
            self.assertIn("needs_design", str(caught.exception))
        self.assertNotIn("needs_design", R.REFINE_KEYS)
        self.assertFalse(os.path.exists(R.refined_path(rdir)))

    def test_the_cli_refuses_it_too(self):
        self.acs("step", "start", "--step", "analyze-requirements", "--args", "split it")
        out = self.acs("requirements", "refine", "--from", "-",
                       stdin=json.dumps({"needs_design": True}), code=2)
        self.assertIn("ADR-0139", out.stderr)

    def test_an_old_refined_record_is_read_with_the_key_ignored(self):
        tid = self.ticket()
        rdir = self.new_run({"kind": "ticket", "ticket_id": tid}, run_id=tid)
        R.materialise(rdir, self.ctx())
        lib.write_json(R.refined_path(rdir), {"needs_design": True, "feature": "wishlist",
                                              "refined_at": "2026-01-01T00:00:00Z"})
        summary = R.summary(rdir, self.ctx())
        self.assertNotIn("needs_design", summary)
        self.assertEqual(summary["feature"], "wishlist")
        report = R.refine(rdir, self.ctx(), {"acceptance_criteria": ["works"]})
        self.assertEqual(report["ticket_fields"], ["acceptance_criteria"])
        text = self.read(R.requirements_path(rdir))
        self.assertNotIn("needs_design", text)
        self.assertNotIn("needs_design", lib.load_ticket(self.tdir(tid)))
        self.assertEqual(lib.design_source(self.ctx(), self.tdir(tid),
                                           lib.load_ticket(self.tdir(tid)), rdir),
                         (False, None, None))


class DesignSource(RequirementsCase):
    """design_source: own tech design, else the parent epic's, else none."""

    def setUp(self):
        super().setUp()
        decide_shared(self)

    def lld(self, key, name="tech-design.md", feature="wishlist"):
        return self.write(os.path.join("docs", "architecture", "lld", feature, key, name),
                          "# Tech design\n")

    def source(self, tid, rdir=None):
        tdir = self.tdir(tid)
        return lib.design_source(self.ctx(), tdir, lib.load_ticket(tdir), rdir)

    def test_none_when_no_design_exists(self):
        tid = self.ticket()
        self.assertEqual(self.source(tid), (False, None, None))
        self.assertEqual(self.source(tid, self.ensure_run(tid)), (False, None, None))

    def test_the_tickets_own_design_is_found(self):
        tid = self.ticket()
        rdir = self.ensure_run(tid)
        path = self.lld(tid)
        self.assertEqual(self.source(tid, rdir), (True, os.path.dirname(path), "own"))
        self.assertEqual(self.source(tid), (True, os.path.dirname(path), "own"),
                         "found without the run named, too")

    def test_the_legacy_design_md_name_is_found(self):
        tid = self.ticket()
        path = self.lld(tid, name="design.md")
        self.assertEqual(self.source(tid, self.ensure_run(tid)),
                         (True, os.path.dirname(path), "own"))

    def test_a_child_reads_its_parent_epics_design(self):
        epic = self.ticket("Checkout", "epic")
        child = self.new_ticket("Child", "task", "--parent", epic)
        self.assertEqual(self.source(child), (False, None, None))
        self.ensure_run(epic)
        path = self.lld(epic)
        self.assertEqual(self.source(child, self.ensure_run(child)),
                         (True, os.path.dirname(path), "parent"))
        own = self.lld(child)
        self.assertEqual(self.source(child), (True, os.path.dirname(own), "own"),
                         "the child's own design wins over the epic's")

    def test_step_start_context_carries_design_for_ticket_and_ticketless_runs(self):
        tid = self.ticket(criteria=["a"])
        out = self.acs("step", "start", "--step", "create-impl-plan", "--args", tid)
        self.assertEqual(out["design"], {"exists": False, "dir": None, "source": None})
        self.assertNotIn("needs_design", out["requirements"])
        path = self.lld(tid)
        self.acs("step", "finish", "--step", "create-impl-plan", "--status",
                 "interrupted", "--stop-reason", "session_end")
        out = self.acs("step", "start", "--step", "create-impl-plan", "--args", tid)
        self.assertEqual(out["design"], {"exists": True, "dir": os.path.dirname(path),
                                         "source": "own"})

    def test_a_ticketless_runs_context_finds_its_own_design(self):
        first = self.acs("step", "start", "--step", "analyze-requirements",
                         "--args", "split the service")
        self.assertEqual(first["design"], {"exists": False, "dir": None, "source": None})
        self.acs("requirements", "refine", "--from", "-",
                 stdin=json.dumps({"feature": "orders"}))
        self.acs("step", "finish", "--step", "analyze-requirements", "--status",
                 "interrupted", "--stop-reason", "session_end")
        path = self.lld(first["run_id"], feature="orders")
        again = self.acs("step", "start", "--step", "analyze-requirements")
        self.assertEqual(again["run_id"], first["run_id"])
        self.assertEqual(again["design"], {"exists": True, "dir": os.path.dirname(path),
                                           "source": "own"})

    def test_the_old_name_is_gone(self):
        self.assertFalse(hasattr(lib, "design_requirement"))
        self.assertFalse(hasattr(R, "recorded_needs_design"))


class GateAdmitsAnyTicket(RequirementsCase):

    def test_create_tech_design_admits_a_story_with_no_flag(self):
        tid = self.new_ticket("Add user login", "story")
        out = self.pre("create-tech-design", tid)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertNotIn("blocked", out.stderr)


class LegacyAnalysisFrontMatter(unittest.TestCase):

    def test_the_spec_says_nothing_about_design(self):
        for spec in (analysis_folder.FRONT_MATTER_SPEC,
                     analysis_folder.FEATURE_FRONT_MATTER_SPEC):
            self.assertNotIn("design", spec)
        self.assertEqual(analysis_folder.FRONT_MATTER_SPEC,
                         "ticket: str; ready_for_planning: bool")
        self.assertEqual(analysis_folder.FEATURE_FRONT_MATTER_SPEC,
                         "feature: str; ready_for_planning: bool")

    def test_a_legacy_readme_with_the_recommendation_still_validates(self):
        legacy = "---\nticket: SHOP-1\nready_for_planning: true\n---\n\n# Analysis\n"
        for extra in ("needs_design_recommendation: true\n",
                      "needs_design_recommendation: not-a-bool\n"):
            with self.subTest(extra=extra):
                text = legacy.replace("---\n\n", extra + "---\n\n")
                self.assertEqual(check_front_matter(
                    text, parse_spec(analysis_folder.FRONT_MATTER_SPEC),
                    ticket="SHOP-1"), [])


if __name__ == "__main__":
    unittest.main()
