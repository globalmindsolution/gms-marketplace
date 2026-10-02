"""`settings.models`: skill -> role -> {model, effort}, and the agents it produces.

Covers acs_lib.models (inventory, scaffold, validation, resolution) and
acs_lib.agent_sync (the generated `.claude/agents/acs-*.md` copies and the
names a coordinator spawns), plus the committed settings and schema that must
stay in step with the agents the plugin ships.

Run:  python3 -m unittest tests.acs.test_models_settings -v
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts"))

import acs_lib as lib  # noqa: E402
from acs_lib import agent_sync, models  # noqa: E402

SCHEMA = os.path.join(REPO_ROOT, "plugins", "acs", "schemas", "settings.schema.json")
SETTINGS = os.path.join(REPO_ROOT, ".acs", "settings.json")


class InventoryTest(unittest.TestCase):
    def test_every_agent_splits_into_a_shipped_skill_and_a_known_role(self):
        names = models.agent_names()
        self.assertEqual(len(names), 33)
        for name in names:
            skill, role = lib.split_agent_name(name)
            self.assertIsNotNone(skill, name)
            self.assertIn(role, lib.ROLE_KINDS, name)

    def test_inventory_covers_every_agent_once(self):
        total = sum(len(roles) for roles in models.inventory().values())
        self.assertEqual(total, len(models.agent_names()))

    def test_every_role_is_scaffolded(self):
        self.assertEqual(models.covered_roles(), sorted(lib.ROLE_KINDS))


class ScaffoldTest(unittest.TestCase):
    def test_scaffold_names_every_agent_with_explicit_values(self):
        scaffold = models.scaffold()
        for skill, roles in models.inventory().items():
            for role in roles:
                entry = scaffold[skill][role]
                self.assertTrue(entry["model"].startswith("claude-"), (skill, role))
                self.assertIn(entry["effort"], models.EFFORTS)
                self.assertNotEqual(entry["effort"], "inherit")

    def test_scaffold_validates(self):
        models.validate_models(models.scaffold())

    def test_merge_missing_adds_only_what_is_absent(self):
        mine = {"code": {"implementer": {"model": "opus"}}}
        merged, added = models.merge_missing(mine)
        self.assertEqual(merged["code"]["implementer"], {"model": "opus"})
        self.assertNotIn("code.implementer", added)
        self.assertIn("review-code.lens", added)

    def test_merge_missing_on_a_full_block_adds_nothing(self):
        _merged, added = models.merge_missing(models.scaffold())
        self.assertEqual(added, [])


class ValidationTest(unittest.TestCase):
    def test_absent_models_is_valid(self):
        models.validate_models(None)
        models.validate_models({})

    def test_unknown_skill_names_the_valid_ones(self):
        with self.assertRaises(lib.GateError) as ctx:
            models.validate_models({"nope": {}})
        self.assertIn("unknown skill", str(ctx.exception))
        self.assertIn("review-code", str(ctx.exception))

    def test_unknown_role_names_the_valid_ones(self):
        with self.assertRaises(lib.GateError) as ctx:
            models.validate_models({"code": {"lens": {}}})
        self.assertIn("unknown role", str(ctx.exception))
        self.assertIn("implementer", str(ctx.exception))

    def test_bad_fields_are_rejected(self):
        for bad in ({"effort": "extreme"}, {"model": ""}, {"model": 3}, {"x": 1}, "opus"):
            with self.subTest(bad=bad), self.assertRaises(lib.GateError):
                models.validate_models({"code": {"implementer": bad}})

    def test_inherit_is_valid_for_both_fields(self):
        models.validate_models({"code": {"implementer": {"model": "inherit", "effort": "inherit"}}})

    def test_validate_settings_runs_it(self):
        with self.assertRaises(lib.GateError):
            lib.validate_settings({"ticket_prefix": "X", "models": {"planner": {}}},
                                  REPO_ROOT, require_workspace=False)


class ResolveTest(unittest.TestCase):
    def test_a_set_entry_resolves(self):
        s = {"models": {"code": {"implementer": {"model": "sonnet", "effort": "low"}}}}
        self.assertEqual(models.resolve(s, "code", "implementer"),
                         {"model": "sonnet", "effort": "low"})

    def test_everything_else_inherits(self):
        for s in ({}, {"models": {}}, {"models": {"code": {}}},
                  {"models": {"code": {"implementer": {"model": "inherit"}}}}):
            with self.subTest(s=s):
                self.assertEqual(models.resolve(s, "code", "implementer"),
                                 {"model": None, "effort": None})

    def test_fields_are_independent(self):
        s = {"models": {"review-code": {"lens": {"effort": "max"}}}}
        self.assertEqual(models.resolve(s, "review-code", "lens"),
                         {"model": None, "effort": "max"})


class AgentSyncTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-sync-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.dir = agent_sync.project_agents_dir(self.tmp)

    def read(self, name):
        with open(os.path.join(self.dir, name + ".md"), encoding="utf-8") as fh:
            return fh.read()

    def test_full_scaffold_writes_one_copy_per_agent(self):
        out = agent_sync.sync({"models": models.scaffold()}, self.tmp)
        self.assertEqual(len(out["written"]), 33)
        self.assertEqual(sorted(os.listdir(self.dir)),
                         sorted(n + ".md" for n in out["written"]))

    def test_a_copy_is_the_plugin_agent_renamed_with_the_fields_set(self):
        agent_sync.sync({"models": {"code": {"implementer": {
            "model": "claude-sonnet-5-5", "effort": "medium"}}}}, self.tmp)
        text = self.read("acs-code-implementer")
        head = text.split("\n---\n", 1)[0].splitlines()
        self.assertIn("name: acs-code-implementer", head)
        self.assertIn("model: claude-sonnet-5-5", head)
        self.assertIn("effort: medium", head)
        self.assertIn("disallowedTools: Agent, Skill", head)
        self.assertIn(agent_sync.MARKER_PREFIX, text)
        with open(os.path.join(lib.agents_dir(), "code-implementer.md"),
                  encoding="utf-8") as fh:
            source = fh.read()
        self.assertIn(source.split("\n---\n", 1)[1].strip()[:200], text)

    def test_an_inheriting_entry_writes_nothing(self):
        out = agent_sync.sync({"models": {"code": {"implementer": {"model": "inherit"}}}}, self.tmp)
        self.assertEqual(out["written"], [])
        self.assertFalse(os.path.isdir(self.dir))

    def test_sync_is_idempotent(self):
        s = {"models": models.scaffold()}
        agent_sync.sync(s, self.tmp)
        again = agent_sync.sync(s, self.tmp)
        self.assertEqual(again["written"], [])
        self.assertEqual(len(again["unchanged"]), 33)

    def test_a_changed_value_rewrites_the_copy(self):
        agent_sync.sync({"models": {"code": {"implementer": {"effort": "low"}}}}, self.tmp)
        out = agent_sync.sync({"models": {"code": {"implementer": {"effort": "high"}}}}, self.tmp)
        self.assertEqual(out["written"], ["acs-code-implementer"])
        self.assertIn("effort: high", self.read("acs-code-implementer"))

    def test_a_cleared_entry_removes_only_the_generated_copy(self):
        agent_sync.sync({"models": {"code": {"implementer": {"effort": "low"}}}}, self.tmp)
        own = os.path.join(self.dir, "acs-my-own.md")
        with open(own, "w", encoding="utf-8") as fh:
            fh.write("---\nname: acs-my-own\n---\nmine\n")
        out = agent_sync.sync({"models": {}}, self.tmp)
        self.assertEqual(out["removed"], ["acs-code-implementer"])
        self.assertTrue(os.path.isfile(own), "a file without the marker is never removed")

    def test_a_person_s_file_by_a_generated_name_is_not_overwritten(self):
        os.makedirs(self.dir)
        path = os.path.join(self.dir, "acs-code-implementer.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("---\nname: acs-code-implementer\n---\nhand-written\n")
        out = agent_sync.sync({"models": {"code": {"implementer": {"effort": "low"}}}}, self.tmp)
        self.assertEqual(out["written"], [])
        self.assertIn("hand-written", self.read("acs-code-implementer"))

    def test_dry_run_writes_nothing(self):
        out = agent_sync.sync({"models": models.scaffold()}, self.tmp, dry_run=True)
        self.assertEqual(len(out["written"]), 33)
        self.assertFalse(os.path.isdir(self.dir))


class SpawnNamesTest(unittest.TestCase):
    def test_set_entries_spawn_the_generated_copy_and_the_rest_the_plugin_agent(self):
        s = {"models": {"create-prd": {"author": {"effort": "low"}}}}
        names = agent_sync.spawn_names(s, "create-prd")
        self.assertEqual(names["author"], "acs-create-prd-author")
        self.assertEqual(names["surveyor"], "acs:create-prd-surveyor")
        self.assertEqual(names["reviewer"], "acs:create-prd-reviewer")

    def test_a_delivery_leg_spawns_its_entry_point_s_agents(self):
        self.assertEqual(agent_sync.skill_for_step("code-small"), "code")
        self.assertEqual(agent_sync.skill_for_step("review-code"), "review-code")

    def test_both_spellings_parse_to_the_same_skill_and_role(self):
        for name in ("acs:review-code-lens", "acs-review-code-lens"):
            self.assertEqual(agent_sync.agent_name_parts(name), ("review-code", "lens"))
        self.assertEqual(agent_sync.agent_name_parts("other:review-code-lens"), (None, None))


class CommittedFilesTest(unittest.TestCase):
    def test_schema_models_property_matches_the_shipped_agents(self):
        with open(SCHEMA, encoding="utf-8") as fh:
            schema = json.load(fh)
        self.assertEqual(schema["properties"]["models"], models.schema_fragment())

    def test_repo_settings_models_cover_every_agent_and_validate(self):
        with open(SETTINGS, encoding="utf-8") as fh:
            block = json.load(fh)["models"]
        models.validate_models(block)
        _merged, missing = models.merge_missing(block)
        self.assertEqual(missing, [], "run `acs.py settings scaffold --write`")
        for skill, roles in block.items():
            for role, entry in roles.items():
                self.assertTrue(entry["model"].startswith("claude-"),
                                "%s.%s pins a model id, not an alias" % (skill, role))

    def test_hooks_match_both_agent_spellings(self):
        with open(os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "hooks.json"),
                  encoding="utf-8") as fh:
            hooks = json.load(fh)["hooks"]
        for event in ("SubagentStart", "SubagentStop"):
            self.assertEqual(hooks[event][0]["matcher"], "^acs[:-]")


if __name__ == "__main__":
    unittest.main()
