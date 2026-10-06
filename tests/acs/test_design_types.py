"""ADR-0120: the design-document catalog, the `design` settings block, the
/acs:setup question that sets it, and the ticket `features` field.

The catalog (acs_lib.design_types) is the source of truth: the settings schema's
enums and defaults are tested against it, never the other way round.
"""

import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_setup_wizard import WizardCase  # noqa: E402
from acs_case import AcsWorkspaceCase  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCHEMAS = os.path.join(REPO_ROOT, "plugins", "acs", "schemas")
sys.path.insert(0, os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts"))

import acs_lib as lib  # noqa: E402
import setup_wizard  # noqa: E402
from acs_lib import design_types as D  # noqa: E402


def schema(name):
    with open(os.path.join(SCHEMAS, name), encoding="utf-8") as fh:
        return json.load(fh)


class CatalogTest(unittest.TestCase):

    def test_defaults_are_the_default_on_types_in_catalog_order(self):
        defaults = D.defaults()
        for key, catalog in D.KINDS.items():
            self.assertEqual(defaults[key], [t for t, (_l, on) in catalog.items() if on])
            self.assertTrue(defaults[key], key)

    def test_the_always_on_hld_documents_are_not_selectable(self):
        for doc in D.HLD_ALWAYS:
            self.assertNotIn(doc, D.HLD_TYPES)

    def test_default_settings_carry_the_defaults(self):
        self.assertEqual(lib.DEFAULT_SETTINGS["design"], D.defaults())

    def test_defaults_returns_fresh_lists(self):
        D.defaults()["hld_types"].append("data-flow")
        self.assertNotIn("data-flow", D.defaults()["hld_types"])


class SchemaAgreesWithCatalogTest(unittest.TestCase):

    def setUp(self):
        self.block = schema("settings.schema.json")["properties"]["design"]

    def test_enums_and_defaults_are_the_catalog(self):
        for key, catalog in D.KINDS.items():
            prop = self.block["properties"][key]
            self.assertEqual(prop["items"]["enum"], list(catalog), key)
            self.assertEqual(prop["default"], D.defaults()[key], key)
            self.assertTrue(prop["uniqueItems"], key)

    def test_no_other_key_is_allowed(self):
        self.assertEqual(set(self.block["properties"]), set(D.KINDS))
        self.assertIs(self.block["additionalProperties"], False)


class ValidateDesignTest(unittest.TestCase):

    def test_accepts_defaults_opt_ins_and_empty_lists(self):
        for design in ({}, D.defaults(), {"hld_types": ["data-flow", "c4-context"]},
                       {"lld_types": ["class"]}, {"hld_types": [], "lld_types": []}):
            with self.subTest(design=design):
                D.validate_design(design)

    def test_refuses_an_unknown_type_naming_the_allowed_ones(self):
        with self.assertRaises(lib.GateError) as ctx:
            D.validate_design({"lld_types": ["sequence", "gantt"]})
        self.assertIn("gantt", str(ctx.exception))
        self.assertIn("sequence", str(ctx.exception))

    def test_refuses_a_wrong_shape(self):
        for design in ([], {"hld_types": "c4-context"}, {"hld_types": [1]},
                       {"diagrams": []}):
            with self.subTest(design=design):
                with self.assertRaises(lib.GateError):
                    D.validate_design(design)

    def test_validate_settings_runs_it(self):
        with self.assertRaises(lib.GateError):
            lib.validate_settings(dict(lib.DEFAULT_SETTINGS, design={"hld_types": ["x"]}),
                                  REPO_ROOT, require_workspace=False)


class NormaliseTest(unittest.TestCase):

    def test_catalog_order_and_no_duplicates(self):
        self.assertEqual(D.normalise(["state", "sequence", "state"], "lld_types"),
                         ["sequence", "state"])

    def test_unknown_ids_are_kept_last_for_validation_to_name(self):
        self.assertEqual(D.normalise(["gantt", "class"], "lld_types"), ["class", "gantt"])

    def test_block_normalises_known_lists_and_leaves_the_rest(self):
        self.assertEqual(D.normalise_block({"hld_types": ["deployment", "c4-context"],
                                            "other": 1}),
                         {"hld_types": ["c4-context", "deployment"], "other": 1})
        self.assertEqual(D.normalise_block("x"), "x")

    def test_settings_migrate_passes_the_block_through(self):
        block = {"design": {"hld_types": ["data-flow"]}}
        self.assertEqual(lib.migrate_settings.migrate(block), (block, []))


class SetupQuestionTest(WizardCase):

    def settings(self):
        path = os.path.join(self.repo, ".acs", "settings.json")
        return json.loads(self.read(".acs", "settings.json")) if os.path.exists(path) else {}

    def test_detect_offers_the_catalog_and_the_current_choice(self):
        design = setup_wizard.detect(self.repo)["design"]
        self.assertEqual(design["hld_always"], list(D.HLD_ALWAYS))
        offered = [entry["id"] for entry in design["catalog"]["lld_types"]]
        self.assertEqual(offered, list(D.LLD_TYPES))
        self.assertEqual(design["current"], D.defaults())

    def test_a_custom_choice_is_written_in_catalog_order(self):
        choice = ["data-flow"] + D.defaults()["hld_types"][::-1]
        out = self.apply(self.answers(settings={"design": {"hld_types": choice}}))
        self.assertTrue(out["ok"], out["errors"])
        self.assertEqual(self.settings()["design"],
                         {"hld_types": D.normalise(choice, "hld_types")})
        self.assertEqual(setup_wizard.detect(self.repo)["design"]["current"]["hld_types"],
                         D.normalise(choice, "hld_types"))

    def test_the_default_choice_in_any_order_writes_nothing(self):
        reordered = {key: ids[::-1] for key, ids in D.defaults().items()}
        out = self.apply(self.answers(settings={"design": reordered}))
        self.assertTrue(out["ok"], out["errors"])
        self.assertNotIn("design", self.settings())
        self.assertIn("design.hld_types", out["defaulted"])

    def test_choosing_the_defaults_again_removes_an_earlier_choice(self):
        self.apply(self.answers(settings={"design": {"lld_types": ["class"]}}))
        self.apply(self.answers(settings={"design": D.defaults()}))
        self.assertNotIn("design", self.settings())

    def test_an_unknown_type_is_refused_and_nothing_is_written(self):
        out = self.apply(self.answers(settings={"ticket_prefix": "SHOP",
                                                "design": {"lld_types": ["gantt"]}}))
        self.assertFalse(out["ok"])
        self.assertTrue(any("gantt" in e for e in out["errors"]), out["errors"])
        self.assertEqual(self.settings(), {})


class TicketFeaturesTest(AcsWorkspaceCase):

    def test_parse_features(self):
        self.assertEqual(lib.parse_features("wishlist, checkout,wishlist"),
                         ["wishlist", "checkout"])
        self.assertEqual(lib.parse_features(None), [])
        with self.assertRaises(lib.GateError) as ctx:
            lib.parse_features("Wishlist, gift cards")
        self.assertIn("Wishlist", str(ctx.exception))

    def test_new_ticket_records_features_on_the_ticket_and_the_index(self):
        out = self.run_script("new-ticket.py", "--title", "Wishlist API", "--type", "story",
                              "--features", "wishlist,saved-items")
        self.assertEqual(out.returncode, 0, out.stderr)
        tid = json.loads(out.stdout)["ticket_id"]
        self.assertEqual(lib.load_ticket(self.tdir(tid))["features"], ["wishlist", "saved-items"])
        index = lib.read_json(lib.index_path(self.ws, "acme-shop"))
        self.assertEqual(index["tickets"][tid]["features"], ["wishlist", "saved-items"])

    def test_a_ticket_with_no_features_carries_no_key(self):
        out = self.run_script("new-ticket.py", "--title", "Fix typo", "--type", "task")
        self.assertEqual(out.returncode, 0, out.stderr)
        tid = json.loads(out.stdout)["ticket_id"]
        self.assertNotIn("features", lib.load_ticket(self.tdir(tid)))

    def test_a_bad_slug_is_refused_and_nothing_is_minted(self):
        out = self.run_script("new-ticket.py", "--title", "X", "--type", "task",
                              "--features", "Gift Cards")
        self.assertEqual(out.returncode, 2)
        self.assertIn("--features", out.stderr)
        self.assertFalse(os.path.exists(lib.index_path(self.ws, "acme-shop")))

    def test_ticket_save_patches_features(self):
        """/acs:analyze-requirements confirms features with `acs.py ticket save`."""
        tid = self.new_ticket("Wishlist API", "story")
        out = self.run_script("acs.py", "ticket", "save", "--ticket", tid, "--from", "-",
                              stdin=json.dumps({"features": ["wishlist"]}))
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(lib.load_ticket(self.tdir(tid))["features"], ["wishlist"])
        index = lib.read_json(lib.index_path(self.ws, "acme-shop"))
        self.assertEqual(index["tickets"][tid]["features"], ["wishlist"])


class TicketSchemaTest(unittest.TestCase):

    def test_features_is_an_optional_unique_list_of_slugs(self):
        ticket = schema("ticket.schema.json")
        self.assertNotIn("features", ticket["required"])
        prop = ticket["properties"]["features"]
        self.assertEqual(prop["type"], "array")
        self.assertTrue(prop["uniqueItems"])
        self.assertEqual(prop["items"]["pattern"], lib.tickets_module.FEATURE_SLUG_RE.pattern)
        self.assertEqual(prop["default"], [])

    def test_the_index_declares_it(self):
        entry = schema("tickets-index.schema.json")["properties"]["tickets"][
            "additionalProperties"]["properties"]
        self.assertEqual(entry["features"]["type"], "array")

    def test_ticket_md_puts_features_after_children(self):
        order = lib.artifacts._FRONT_MATTER_ORDER
        self.assertEqual(order.index("features"), order.index("children") + 1)


class SkillsUseTheFieldTest(unittest.TestCase):
    """The prose that sets and confirms `features` names the slug helper and
    the CLI that writes it."""

    def body(self, *parts):
        with open(os.path.join(REPO_ROOT, "plugins", "acs", "skills", *parts),
                  encoding="utf-8") as fh:
            return " ".join(fh.read().split())

    def test_create_ticket_proposes_and_writes_features(self):
        """ADR-0138: the type author proposes them by the shared authoring
        rules, the coordinator writes them, and a breakdown's children inherit
        them unless narrowed with --features."""
        rules = self.body("create-ticket", "references", "authoring-rules.md")
        self.assertIn("`features` are the slugs of those PRD features", rules)
        self.assertIn('acs.py" slug --text', rules)
        self.assertIn("`features` (the confirmed PRD feature slugs",
                      self.body("create-ticket", "references", "materialize.md"))
        self.assertIn("--features <slugs>` only to narrow them",
                      self.body("breakdown-ticket", "SKILL.md"))

    def test_analyze_requirements_confirms_them_through_ticket_save(self):
        body = self.body("analyze-requirements", "SKILL.md")
        self.assertIn('{"features": ["wishlist"]}', body)

    def test_analyze_requirements_agents_check_and_verify_features(self):
        agents = os.path.join(REPO_ROOT, "plugins", "acs", "agents")
        with open(os.path.join(agents, "analyze-requirements-analyst.md"), encoding="utf-8") as fh:
            analyst = " ".join(fh.read().split())
        with open(os.path.join(agents, "analyze-requirements-impact-reviewer.md"),
                  encoding="utf-8") as fh:
            reviewer = " ".join(fh.read().split())
        self.assertIn("check `ticket.features`", analyst)
        self.assertIn("`features` correction", analyst)
        self.assertIn("a confirmed `features` correction is the ticket's `features` list",
                      reviewer)

    def test_setup_asks_the_design_question(self):
        body = self.body("setup", "SKILL.md")
        self.assertIn("**Design documents**", body)
        self.assertIn("`design.catalog`", body)


class SlugMatchesTheCliTest(unittest.TestCase):

    def test_acs_slug_makes_a_valid_feature_slug(self):
        out = subprocess.run([sys.executable, os.path.join(
            REPO_ROOT, "plugins", "acs", "hooks", "scripts", "acs.py"),
            "slug", "--text", "Saved Items & Wishlists"], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        slug = json.loads(out.stdout)["slug"]
        self.assertRegex(slug, lib.tickets_module.FEATURE_SLUG_RE)


if __name__ == "__main__":
    unittest.main()
