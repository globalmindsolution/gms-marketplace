"""acs_lib.migrate_settings and `acs.py settings migrate`.

migrate(data) rewrites ONE settings file's content to the current shape;
legacy_problems(settings) names what an old-shape object still carries; the
CLI reads every scope's file, reports, and writes only with --write.

Run:  python3 -m unittest tests.acs.test_migrate_settings -v
"""

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

TESTS_ACS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS_ACS)

import acs_case  # noqa: E402

lib = acs_case.lib
migrate_settings = lib.migrate_settings
migrate = migrate_settings.migrate
legacy_problems = migrate_settings.legacy_problems


class MigrateMappingsTest(unittest.TestCase):
    def test_test_coverage_percent_becomes_tests_coverage(self):
        new, notes = migrate({"test_coverage_percent": 80})
        self.assertEqual(new, {"tests": {"coverage": 80}})
        self.assertIn("test_coverage_percent -> tests.coverage", notes)

    def test_suites_become_tests_keys_and_drop_per_iteration(self):
        new, notes = migrate({"suites": {
            "smoke": {"command": "make smoke", "per_iteration": True},
            "api": {"command": "make api", "setup": "up"}}})
        self.assertNotIn("suites", new)
        self.assertEqual(new["tests"]["smoke"], {"command": "make smoke"})
        self.assertEqual(new["tests"]["api"], {"command": "make api", "setup": "up"})
        self.assertIn("suites.smoke -> tests.smoke", notes)
        self.assertIn("suites.api -> tests.api", notes)

    def test_e2e_alias_becomes_tests_e2e_and_drops_per_iteration(self):
        new, notes = migrate({"e2e": {"command": "npm run e2e", "teardown": "down",
                                      "per_iteration": False}})
        self.assertNotIn("e2e", new)
        self.assertEqual(new["tests"], {"e2e": {"command": "npm run e2e", "teardown": "down"}})
        self.assertIn("e2e -> tests.e2e", notes)

    def test_e2e_alias_wins_over_suites_e2e(self):
        new, _ = migrate({"suites": {"e2e": {"command": "from suites"}},
                          "e2e": {"command": "from alias"}})
        self.assertEqual(new["tests"]["e2e"], {"command": "from alias"})

    def test_ci_gate_command_and_setup_become_tests_unit(self):
        new, notes = migrate({"tests": {"command": "pytest --cov", "setup": "pip install ."}})
        self.assertEqual(new["tests"], {"unit": {"command": "pytest --cov", "setup": "pip install ."}})
        self.assertIn("tests.command/setup -> tests.unit", notes)

    def test_ci_gate_without_setup(self):
        new, _ = migrate({"tests": {"command": "pytest"}})
        self.assertEqual(new["tests"], {"unit": {"command": "pytest"}})

    def test_existing_tests_unit_is_not_overwritten_by_the_old_gate(self):
        new, _ = migrate({"tests": {"command": "old", "unit": {"command": "kept"}}})
        self.assertEqual(new["tests"]["unit"], {"command": "kept"})
        self.assertNotIn("command", new["tests"])

    def test_everything_together(self):
        old = {"ticket_prefix": "SHOP", "merge_strategy": "rebase",
               "test_coverage_percent": 75,
               "suites": {"smoke": {"command": "s"}},
               "e2e": {"command": "e"},
               "tests": {"command": "t", "setup": "p"}}
        new, _ = migrate(old)
        self.assertEqual(new, {
            "ticket_prefix": "SHOP", "merge_strategy": "rebase",
            "tests": {"coverage": 75, "smoke": {"command": "s"},
                      "e2e": {"command": "e"}, "unit": {"command": "t", "setup": "p"}}})
        self.assertEqual(legacy_problems(new), [])
        lib.validate_tests(new["tests"])

    def test_per_iteration_is_dropped_from_suites_already_under_tests(self):
        new, _ = migrate({"tests": {"command": "t", "e2e": {"command": "e", "per_iteration": True}}})
        self.assertEqual(new["tests"]["e2e"], {"command": "e"})

    def test_models_tiers_are_replaced_by_the_full_scaffold(self):
        new, notes = migrate({"models": {
            "planner": "opus", "executor": "sonnet", "verifier": "haiku",
            "overrides": {"code": "opus"},
            "code": {"implementer": {"model": "sonnet"}}}})
        for key in ("planner", "executor", "verifier", "overrides"):
            self.assertNotIn(key, new["models"])
        expected, _added = lib.models.merge_missing({"code": {"implementer": {"model": "sonnet"}}})
        self.assertEqual(new["models"], expected)
        self.assertEqual(new["models"]["code"]["implementer"], {"model": "sonnet"})
        self.assertGreater(len(new["models"]), 1)
        lib.validate_models(new["models"])
        self.assertTrue(any("models" in n for n in notes))

    def test_models_without_tier_keys_are_untouched(self):
        old = {"models": {"code": {"implementer": {"model": "sonnet"}}}}
        new, notes = migrate(old)
        self.assertEqual(new, old)
        self.assertEqual(notes, [])

    def test_removed_skills_leave_models(self):
        """ADR-0118: a scaffolded block still names the removed skills, which
        validate_models would refuse as unknown; migrate drops them and keeps
        the rest."""
        kept = {"code": {"implementer": {"model": "sonnet"}}}
        old = {"models": dict(kept, **{
            "create-project": {"scaffolder": {"model": "sonnet"}},
            "standardize-project": {"auditor": {"model": "opus"}},
            "create-requirements": {"author": {"model": "sonnet"}}})}
        new, notes = migrate(old)
        self.assertEqual(new, {"models": kept})
        lib.validate_models(new["models"])
        self.assertEqual(len(notes), 3, notes)
        self.assertTrue(all("ADR-0118" in n for n in notes), notes)

    def test_removed_create_docs_leaves_models(self):
        """ADR-0124: a scaffolded block names create-docs, which validate_models
        now refuses as unknown; migrate drops it, citing its own ADR."""
        kept = {"code": {"implementer": {"model": "sonnet"}}}
        old = {"models": dict(kept, **{
            "create-docs": {"author": {"model": "sonnet"}, "reviewer": {"model": "opus"}}})}
        new, notes = migrate(old)
        self.assertEqual(new, {"models": kept})
        lib.validate_models(new["models"])
        self.assertEqual(notes, ["removed models.create-docs (the skill was removed; ADR-0124)"])
        with self.assertRaises(lib.GateError):
            lib.validate_models(old["models"])

    def test_jira_provider_becomes_local_and_jira_subkeys_go(self):
        new, notes = migrate({"tracker": {"provider": "jira", "jira": {"project": "X"},
                                          "milestone": "v1"}})
        self.assertEqual(new["tracker"], {"provider": "local"})
        self.assertIn("removed tracker.jira", notes)
        self.assertIn("removed tracker.milestone", notes)
        self.assertTrue(any("jira -> local" in n for n in notes))

    def test_github_provider_survives(self):
        old = {"tracker": {"provider": "github", "github": {"project": 3}}}
        new, notes = migrate(old)
        self.assertEqual(new, old)
        self.assertEqual(notes, [])

    def test_retired_blocks_are_dropped(self):
        new, notes = migrate({"ticket_prefix": "SHOP", "formats": {"branch_name": "x"},
                              "enforcement": {}, "hook_gates": {}})
        self.assertEqual(new, {"ticket_prefix": "SHOP"})
        self.assertEqual(len(notes), 3)

    def test_input_is_not_mutated(self):
        old = {"test_coverage_percent": 80, "suites": {"a": {"command": "x", "per_iteration": True}},
               "tracker": {"provider": "jira"}}
        snapshot = copy.deepcopy(old)
        migrate(old)
        self.assertEqual(old, snapshot)

    def test_non_dict_input_yields_empty_settings(self):
        self.assertEqual(migrate(None), ({}, []))
        self.assertEqual(migrate([1]), ({}, []))


class MigrateIdempotenceTest(unittest.TestCase):
    OLD = {
        "ticket_prefix": "SHOP", "test_coverage_percent": 80,
        "suites": {"smoke": {"command": "s", "per_iteration": True}},
        "e2e": {"command": "e"}, "tests": {"command": "t", "setup": "p"},
        "models": {"planner": "opus"},
        "tracker": {"provider": "jira", "jira": {}}, "formats": {},
    }

    def test_migrating_twice_changes_nothing(self):
        once, notes = migrate(self.OLD)
        self.assertTrue(notes)
        twice, notes2 = migrate(once)
        self.assertEqual(twice, once)
        self.assertEqual(notes2, [])

    def test_clean_new_shape_file_is_unchanged(self):
        clean = {"ticket_prefix": "SHOP", "merge_strategy": "squash",
                 "tests": {"coverage": 90, "unit": {"command": "pytest"},
                           "e2e": {"command": "npm run e2e"}},
                 "tracker": {"provider": "github"}, "workflow": {"advisories": True}}
        new, notes = migrate(clean)
        self.assertEqual(new, clean)
        self.assertEqual(notes, [])

    def test_empty_file_is_unchanged(self):
        self.assertEqual(migrate({}), ({}, []))


class LegacyProblemsTest(unittest.TestCase):
    def test_clean_objects_have_no_problems(self):
        for settings in (None, {}, lib.DEFAULT_SETTINGS,
                         {"tests": {"coverage": 90, "unit": {"command": "x"}},
                          "models": {"code": {"implementer": {"model": "m"}}},
                          "tracker": {"provider": "github"}}):
            with self.subTest(settings=settings):
                self.assertEqual(legacy_problems(settings), [])

    def test_each_legacy_key_is_named(self):
        cases = [
            ({"test_coverage_percent": 80}, "test_coverage_percent"),
            ({"suites": {}}, "suites"),
            ({"e2e": {"command": "x"}}, "e2e"),
            ({"tests": {"command": "x"}}, "tests.command"),
            ({"tests": {"setup": "x"}}, "tests.setup"),
            ({"models": {"planner": "x"}}, "models.planner"),
            ({"models": {"executor": "x"}}, "models.planner"),
            ({"models": {"verifier": "x"}}, "models.planner"),
            ({"models": {"overrides": {}}}, "models.planner"),
            ({"tracker": {"provider": "jira"}}, "tracker.jira"),
            ({"tracker": {"jira": {}}}, "tracker.jira"),
            ({"models": {"create-project": {}}}, "models.create-project"),
            ({"models": {"standardize-project": {}}}, "models.standardize-project"),
            ({"models": {"create-requirements": {}}}, "models.create-requirements"),
            ({"models": {"create-docs": {}}}, "models.create-docs"),
        ]
        for settings, needle in cases:
            with self.subTest(settings=settings):
                problems = legacy_problems(settings)
                self.assertEqual(len(problems), 1, problems)
                self.assertIn(needle, problems[0])

    def test_one_problem_per_distinct_legacy_key(self):
        problems = legacy_problems({"test_coverage_percent": 1, "suites": {}, "e2e": {},
                                    "tests": {"command": "x"}, "models": {"planner": "x"},
                                    "tracker": {"provider": "jira"}})
        self.assertEqual(len(problems), 6)

    def test_a_suite_named_command_object_is_not_legacy(self):
        # tests.command as an OBJECT would be a suite named "command", not the old gate string.
        self.assertEqual(legacy_problems({"tests": {"command": {"command": "x"}}}), [])

    def test_migrated_output_has_no_problems(self):
        new, _ = migrate(MigrateIdempotenceTest.OLD)
        self.assertEqual(legacy_problems(new), [])


class SettingsMigrateCliTest(acs_case.AcsWorkspaceCase):
    OLD = {"ticket_prefix": "SHOP", "test_coverage_percent": 80,
           "suites": {"smoke": {"command": "make smoke", "per_iteration": True}},
           "e2e": {"command": "npm run e2e"},
           "tests": {"command": "pytest", "setup": "pip install ."},
           "tracker": {"provider": "jira"}}

    def setUp(self):
        super().setUp()
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(self.home)
        self.env = dict(os.environ, HOME=self.home)
        self.write_settings(self.OLD)
        self.path = os.path.join(self.repo, ".acs", "settings.json")

    def _read(self):
        with open(self.path, encoding="utf-8") as fh:
            return json.load(fh)

    def _migrate(self, *args):
        result = self.run_script("acs.py", "settings", "migrate", *args, env=self.env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def _report_for(self, out):
        return [f for f in out["files"] if os.path.realpath(f["path"]) == os.path.realpath(self.path)][0]

    def test_dry_run_reports_and_leaves_the_file_alone(self):
        out = self._migrate()
        self.assertTrue(out["ok"])
        self.assertFalse(out["written"])
        report = self._report_for(out)
        self.assertTrue(report["changed"])
        self.assertTrue(report["notes"])
        self.assertIn(report["path"], out["changed"])
        self.assertEqual(self._read(), self.OLD)

    def test_write_rewrites_the_file_to_the_new_shape(self):
        out = self._migrate("--write")
        self.assertTrue(out["written"])
        self.assertTrue(self._report_for(out)["changed"])
        new = self._read()
        self.assertEqual(new["tests"], {"coverage": 80, "smoke": {"command": "make smoke"},
                                        "e2e": {"command": "npm run e2e"},
                                        "unit": {"command": "pytest", "setup": "pip install ."}})
        self.assertEqual(new["tracker"], {"provider": "local"})
        self.assertEqual(legacy_problems(new), [])
        with open(self.path, encoding="utf-8") as fh:
            self.assertTrue(fh.read().endswith("}\n"))

    def test_second_write_changes_nothing(self):
        self._migrate("--write")
        after_first = self._read()
        out = self._migrate("--write")
        self.assertEqual(out["changed"], [])
        self.assertFalse(self._report_for(out)["changed"])
        self.assertEqual(self._read(), after_first)

    def test_clean_file_is_reported_unchanged(self):
        clean = {"ticket_prefix": "SHOP", "tests": {"coverage": 90}}
        self.write_settings(clean)
        out = self._migrate("--write")
        self.assertEqual(out["changed"], [])
        self.assertEqual(self._read(), clean)

    def test_no_settings_files_is_ok(self):
        os.unlink(self.path)
        out = self._migrate()
        self.assertTrue(out["ok"])
        self.assertEqual(out["changed"], [])

    def test_non_object_file_is_reported_not_written(self):
        with open(self.path, "w") as fh:
            fh.write("[1, 2]")
        out = self._migrate("--write")
        report = self._report_for(out)
        self.assertFalse(report["changed"])
        self.assertIn("not a JSON object", report["notes"][0])
        with open(self.path) as fh:
            self.assertEqual(fh.read(), "[1, 2]")

    def test_old_shape_is_refused_by_a_gate_until_migrated(self):
        refused = self.pre("create-ticket")
        self.assertEqual(refused.returncode, 2)
        self.assertIn("settings migrate", refused.stderr)
        self._migrate("--write")
        self.assertEqual(self.pre("create-ticket").returncode, 0)


if __name__ == "__main__":
    unittest.main()
