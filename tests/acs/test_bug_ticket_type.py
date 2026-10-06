"""ADR-0138: `bug` is a ticket type, beside epic, story and task.

Pinned here, at the hook-library layer:

  * the registry and both schema enums name it (`TICKET_TYPES`,
    `ticket.schema.json`, `tickets-index.schema.json`);
  * a bug carries its own optional fields -- `severity` (critical|high|medium|
    low, separate from `priority`), `reproduction`, `expected`, `actual`,
    `environment` -- schema-validated, rendered in ticket.md's front-matter
    order, and refused on any other type;
  * `new-ticket.py --type bug` mints one with them, and `acs.py ticket save`
    validates the merged document;
  * the tracker sync's Type option (`TYPE_OPTIONS["bug"] = "Bug"`), with a
    board lacking it falling into the existing "option missing" finding;
  * the `bug-default` ticket template beside epic/story/task-default.

Run:  python3 -m unittest tests.acs.test_bug_ticket_type -v
"""

import json
import os
import sys
import unittest

TESTS_ACS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS_ACS)

import acs_case  # noqa: E402
from acs_case import AcsWorkspaceCase, lib  # noqa: E402

from acs_lib import artifacts, conventions, forge, schemasubset  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(TESTS_ACS))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
TEMPLATES = os.path.join(PLUGIN, "templates")
REPO_ID = "acme-shop"

BUG_FLAGS = ["--severity", "high",
             "--reproduction", "1. Open the cart\n2. Add the same item twice",
             "--expected", "quantity 2",
             "--actual", "two rows of quantity 1",
             "--environment", "v0.5.0, Firefox 140"]


def schema(name):
    with open(os.path.join(PLUGIN, "schemas", name), encoding="utf-8") as fh:
        return json.load(fh)


def bug_doc(**over):
    doc = lib.new_ticket_doc("SHOP-7", "Cart doubles a line", "bug")
    doc.update({"severity": "high", "reproduction": "1. a\n2. b", "expected": "x",
                "actual": "y", "environment": "v1"})
    doc.update(over)
    return doc


class RegistryTest(unittest.TestCase):

    def test_bug_is_a_ticket_type(self):
        self.assertEqual(lib.TICKET_TYPES, ["epic", "story", "task", "bug"])

    def test_both_schema_enums_name_every_ticket_type(self):
        self.assertEqual(schema("ticket.schema.json")["properties"]["type"]["enum"],
                         lib.TICKET_TYPES)
        index = schema("tickets-index.schema.json")
        entry = index["properties"]["tickets"]["additionalProperties"]
        self.assertEqual(entry["properties"]["type"]["enum"], lib.TICKET_TYPES)

    def test_the_bug_fields_and_severities(self):
        self.assertEqual(lib.BUG_FIELDS,
                         ("severity", "reproduction", "expected", "actual", "environment"))
        self.assertEqual(lib.BUG_SEVERITIES, ("critical", "high", "medium", "low"))


class SchemaTest(unittest.TestCase):

    def errors(self, doc):
        return schemasubset.schema_errors(schema("ticket.schema.json"), doc)

    def test_every_bug_field_is_declared(self):
        props = schema("ticket.schema.json")["properties"]
        for field in lib.BUG_FIELDS:
            self.assertIn(field, props)
        self.assertEqual(props["severity"]["enum"], list(lib.BUG_SEVERITIES))

    def test_a_bug_with_its_fields_validates(self):
        self.assertEqual(self.errors(bug_doc()), [])

    def test_an_unknown_severity_is_refused(self):
        self.assertTrue(self.errors(bug_doc(severity="blocker")))

    def test_a_non_string_bug_field_is_refused(self):
        for field in ("reproduction", "expected", "actual", "environment"):
            self.assertTrue(self.errors(bug_doc(**{field: ["a"]})), field)

    def test_jsonschema_agrees(self):
        try:
            import jsonschema
        except ImportError:  # pragma: no cover - CI installs it
            self.skipTest("jsonschema not installed")
        jsonschema.validate(bug_doc(), schema("ticket.schema.json"))
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(bug_doc(severity="p0"), schema("ticket.schema.json"))


class CheckBugFieldsTest(unittest.TestCase):

    def test_a_valid_bug_passes(self):
        lib.check_bug_fields(bug_doc())

    def test_a_bug_without_its_optional_fields_passes(self):
        lib.check_bug_fields(lib.new_ticket_doc("SHOP-7", "t", "bug"))

    def test_a_bug_field_on_another_type_is_refused(self):
        doc = lib.new_ticket_doc("SHOP-7", "t", "story")
        doc["severity"] = "high"
        with self.assertRaisesRegex(lib.GateError, "severity.*only.*bug"):
            lib.check_bug_fields(doc)

    def test_a_bad_severity_is_refused(self):
        with self.assertRaisesRegex(lib.GateError, "severity"):
            lib.check_bug_fields(bug_doc(severity="urgent"))

    def test_a_non_string_field_is_refused(self):
        with self.assertRaisesRegex(lib.GateError, "expected"):
            lib.check_bug_fields(bug_doc(expected=3))

    def test_an_unknown_type_is_refused(self):
        with self.assertRaisesRegex(lib.GateError, "type"):
            lib.check_bug_fields(bug_doc(type="incident"))


class FrontMatterOrderTest(unittest.TestCase):

    def test_severity_sits_by_priority_and_the_report_after_due_date(self):
        order = artifacts._FRONT_MATTER_ORDER
        self.assertEqual(order.index("severity"), order.index("priority") + 1)
        tail = order[order.index("due_date") + 1:]
        self.assertEqual(tail[:4], ("reproduction", "expected", "actual", "environment"))

    def test_ticket_md_renders_the_bug_fields_in_order_and_round_trips(self):
        doc = bug_doc()
        text = artifacts.render_ticket_md(doc)
        keys = [line.split(":", 1)[0] for line in text.split("---")[1].strip().splitlines()
                if line and not line.startswith(" ") and not line.startswith("-")]
        positions = [keys.index(k) for k in ("priority", "severity", "due_date",
                                             "reproduction", "expected", "actual",
                                             "environment")]
        self.assertEqual(positions, sorted(positions))
        parsed = artifacts.parse_ticket_md(text)
        for field in lib.BUG_FIELDS:
            self.assertEqual(parsed[field], doc[field], field)


class NewTicketBugTest(AcsWorkspaceCase):

    def mint(self, *args):
        return self.run_script("new-ticket.py", "--title", "Cart doubles a line", *args)

    def test_a_bug_is_minted_with_its_fields(self):
        out = self.mint("--type", "bug", "--priority", "medium", *BUG_FLAGS)
        self.assertEqual(out.returncode, 0, out.stderr)
        tid = json.loads(out.stdout)["ticket_id"]
        ticket = lib.load_ticket(self.tdir(tid))
        self.assertEqual(ticket["type"], "bug")
        self.assertEqual(ticket["severity"], "high")
        self.assertEqual(ticket["priority"], "medium", "severity is not priority")
        self.assertEqual(ticket["reproduction"], "1. Open the cart\n2. Add the same item twice")
        self.assertEqual(ticket["expected"], "quantity 2")
        self.assertEqual(ticket["actual"], "two rows of quantity 1")
        self.assertEqual(ticket["environment"], "v0.5.0, Firefox 140")
        self.assertNotIn("needs_design", ticket, "tickets carry no design flag (ADR-0139)")
        self.assertEqual(schemasubset.schema_errors(schema("ticket.schema.json"), ticket), [])
        index = lib.read_json(lib.index_path(self.ws, REPO_ID))
        self.assertEqual(index["tickets"][tid]["type"], "bug")
        self.assertEqual(schemasubset.schema_errors(schema("tickets-index.schema.json"),
                                                    index), [])

    def test_a_bug_without_the_optional_fields_carries_none_of_them(self):
        out = self.mint("--type", "bug")
        self.assertEqual(out.returncode, 0, out.stderr)
        ticket = lib.load_ticket(self.tdir(json.loads(out.stdout)["ticket_id"]))
        for field in lib.BUG_FIELDS:
            self.assertNotIn(field, ticket)

    def test_a_bug_flag_on_another_type_exits_2_and_mints_nothing(self):
        before = lib.read_json(self._counters_path())
        out = self.mint("--type", "story", "--severity", "high")
        self.assertEqual(out.returncode, 2)
        self.assertIn("only apply to --type bug", out.stderr)
        self.assertEqual(lib.read_json(self._counters_path()), before)

    def test_an_unknown_severity_is_an_argparse_error(self):
        out = self.mint("--type", "bug", "--severity", "blocker")
        self.assertEqual(out.returncode, 2)
        self.assertIn("--severity", out.stderr)

    def test_a_bug_can_be_a_child_of_an_epic(self):
        epic = self.new_ticket("Checkout", "epic")
        out = self.mint("--type", "bug", "--parent", epic, "--severity", "low")
        self.assertEqual(out.returncode, 0, out.stderr)
        tid = json.loads(out.stdout)["ticket_id"]
        self.assertIn(tid, lib.load_ticket(self.tdir(epic))["children"])


class TicketSaveTest(AcsWorkspaceCase):

    def save(self, tid, doc):
        return self.run_script("acs.py", "ticket", "save", "--ticket", tid,
                               stdin=json.dumps(doc))

    def test_bug_fields_are_written_by_a_save(self):
        tid = self.new_ticket("Cart doubles a line", "bug")
        out = self.save(tid, {"severity": "critical", "actual": "500"})
        self.assertEqual(out.returncode, 0, out.stderr)
        ticket = lib.load_ticket(self.tdir(tid))
        self.assertEqual((ticket["severity"], ticket["actual"]), ("critical", "500"))

    def test_a_bad_severity_is_refused_and_nothing_written(self):
        tid = self.new_ticket("Cart doubles a line", "bug")
        out = self.save(tid, {"severity": "p1"})
        self.assertEqual(out.returncode, 2)
        self.assertIn("severity", out.stderr)
        self.assertNotIn("severity", lib.load_ticket(self.tdir(tid)))

    def test_a_bug_field_on_a_story_is_refused(self):
        tid = self.new_ticket("Wishlist", "story")
        out = self.save(tid, {"expected": "x"})
        self.assertEqual(out.returncode, 2)
        self.assertIn("only", out.stderr)

    def test_an_unknown_type_is_refused(self):
        tid = self.new_ticket("Wishlist", "story")
        out = self.save(tid, {"type": "incident"})
        self.assertEqual(out.returncode, 2)

    def test_a_story_converts_to_an_epic_keeping_its_id(self):
        """breakdown-ticket's split conversion: a patch, then --parent works."""
        tid = self.new_ticket("Wishlist", "story", "--features", "wishlist")
        out = self.save(tid, {"type": "epic"})
        self.assertEqual(out.returncode, 0, out.stderr)
        ticket = lib.load_ticket(self.tdir(tid))
        self.assertEqual((ticket["id"], ticket["type"], ticket["features"]),
                         (tid, "epic", ["wishlist"]))
        child = self.new_ticket("Wishlist API", "task", "--parent", tid)
        self.assertEqual(lib.load_ticket(self.tdir(child))["features"], ["wishlist"])


class StepStartTypeTest(AcsWorkspaceCase):

    def test_step_start_allocate_accepts_bug(self):
        out = self.run_script("acs.py", "step", "start", "--step", "create-ticket",
                              "--allocate", "--type", "bug", "--title", "Cart bug")
        self.assertEqual(out.returncode, 0, out.stderr)
        tid = json.loads(out.stdout)["ticket_id"]
        self.assertEqual(lib.load_ticket(self.tdir(tid))["type"], "bug")

    def test_step_start_refuses_an_unknown_type(self):
        out = self.run_script("acs.py", "step", "start", "--step", "create-ticket",
                              "--allocate", "--type", "incident")
        self.assertEqual(out.returncode, 2)
        self.assertIn("--type", out.stderr)


class ForgeTypeOptionTest(unittest.TestCase):

    def fill(self, options):
        fields = {"fields": [{"id": "f-type", "name": "Type", "dataType": "SINGLE_SELECT",
                              "options": options}]}
        items = {"items": [{"id": "item-9", "projectId": "PVT_1",
                            "content": {"url": "https://example.invalid/issues/9"}}]}
        gh = lib.Gh(responses={"gh project item-add": (0, "", ""),
                               "gh project item-list": (0, json.dumps(items), ""),
                               "gh project field-list": (0, json.dumps(fields), ""),
                               "gh project item-edit": (0, "", "")})
        findings = []
        lib.project_fill(gh, {"tracker": {"github": {"owner": "acme", "project_number": 7}}},
                         {"id": "SHOP-1", "type": "bug", "title": "t"},
                         "https://example.invalid/issues/9", lib.TICKET_STATUS_OPTIONS,
                         "project", findings)
        return gh, " | ".join(f["message"] for f in findings)

    def test_bug_maps_to_the_bug_option(self):
        self.assertEqual(forge.TYPE_OPTIONS["bug"], "Bug")
        self.assertEqual(sorted(forge.TYPE_OPTIONS), sorted(lib.TICKET_TYPES))

    def test_a_board_with_a_bug_option_sets_it(self):
        gh, _messages = self.fill([{"id": "opt-bug", "name": "Bug"}])
        self.assertTrue([c for c in gh.calls if "opt-bug" in c])

    def test_a_board_without_one_is_the_existing_option_missing_finding(self):
        gh, messages = self.fill([{"id": "opt-task", "name": "Task"}])
        self.assertIn("Type field defines no option 'Bug'", messages)
        self.assertFalse([c for c in gh.calls if "f-type" in c])


class TemplateTest(unittest.TestCase):

    def test_every_ticket_type_has_a_template(self):
        self.assertEqual(sorted(conventions.TICKET_TEMPLATES), sorted(lib.TICKET_TYPES))
        self.assertEqual(conventions.TICKET_TEMPLATES["bug"], "bug-default")
        for name in conventions.TICKET_TEMPLATES.values():
            self.assertTrue(os.path.isfile(os.path.join(TEMPLATES, name + ".md")), name)

    def test_the_bug_template_carries_the_report_and_the_regression_criterion(self):
        with open(os.path.join(TEMPLATES, "bug-default.md"), encoding="utf-8") as fh:
            body = fh.read()
        headings = [line[3:].strip() for line in body.splitlines() if line.startswith("## ")]
        self.assertEqual(headings, ["Summary", "Steps to reproduce", "Expected behaviour",
                                    "Actual behaviour",
                                    "Environment", "Severity", "Suspected area",
                                    "Acceptance criteria", "Notes"])
        self.assertRegex(body, r"(?i)regression test reproduces the bug.{0,40}fails before "
                               r"the fix.{0,20}passes after")
        tail = {}
        for name in conventions.TICKET_TEMPLATES.values():
            with open(os.path.join(TEMPLATES, name + ".md"), encoding="utf-8") as fh:
                tail[name] = fh.read().rstrip("\n").splitlines()[-1]
        self.assertEqual(set(tail.values()), {"acs-ticket: {ticket_id}"}, tail)
        self.assertIn("acs-ticket: {ticket_id}", body)
        self.assertIn("bug-default", body)

    def test_a_bug_title_is_untagged(self):
        self.assertEqual(conventions.ticket_title("bug", "Cart doubles"), "Cart doubles")


if __name__ == "__main__":
    unittest.main()
