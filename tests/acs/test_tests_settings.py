"""The `tests` settings block: tests.coverage plus one object per named suite.

Covers DEFAULT_SETTINGS, validate_tests, coverage_target / test_suites, the
schema's `tests` property, and validate_settings refusing every legacy key with
a message that names `settings migrate`.

Run:  python3 -m unittest tests.acs.test_tests_settings -v
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

TESTS_ACS = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(TESTS_ACS))
sys.path.insert(0, TESTS_ACS)

import acs_case  # noqa: E402

lib = acs_case.lib

SCHEMA_PATH = os.path.join(REPO_ROOT, "plugins", "acs", "schemas", "settings.schema.json")


class DefaultsTest(unittest.TestCase):
    def test_default_coverage_is_90_under_tests(self):
        self.assertEqual(lib.DEFAULT_SETTINGS["tests"], {"coverage": 90})

    def test_legacy_top_level_keys_are_not_defaulted(self):
        for key in ("test_coverage_percent", "suites", "e2e"):
            self.assertNotIn(key, lib.DEFAULT_SETTINGS)


class ValidateTestsTest(unittest.TestCase):
    def test_accepts_coverage_only_and_empty(self):
        lib.validate_tests({})
        lib.validate_tests({"coverage": 90})
        lib.validate_tests({"coverage": 100})
        lib.validate_tests({"coverage": 0.5})

    def test_accepts_suites_with_optional_setup_teardown(self):
        lib.validate_tests({
            "coverage": 85,
            "unit": {"command": "pytest", "setup": "pip install -e ."},
            "e2e": {"command": "npm run e2e", "setup": "up", "teardown": "down"},
            "smoke": {"command": "make smoke"},
        })

    def test_rejects_coverage_out_of_range_or_wrong_type(self):
        for bad in (0, -1, 100.5, 150, "90", None, True):
            with self.subTest(coverage=bad):
                with self.assertRaises(lib.GateError) as ctx:
                    lib.validate_tests({"coverage": bad})
                self.assertIn("tests.coverage", str(ctx.exception))

    def test_rejects_suite_without_command(self):
        for suite in ({}, {"setup": "x"}, {"command": ""}, {"command": "  "}, {"command": 5}):
            with self.subTest(suite=suite):
                with self.assertRaises(lib.GateError) as ctx:
                    lib.validate_tests({"smoke": suite})
                self.assertIn("tests.smoke", str(ctx.exception))
                self.assertIn("command", str(ctx.exception))

    def test_rejects_blank_or_non_string_setup_and_teardown(self):
        for key in ("setup", "teardown"):
            for bad in ("", "   ", 3, None):
                with self.subTest(key=key, bad=bad):
                    with self.assertRaises(lib.GateError) as ctx:
                        lib.validate_tests({"e2e": {"command": "run", key: bad}})
                    self.assertIn("tests.e2e.%s" % key, str(ctx.exception))

    def test_rejects_non_dict_suite_and_non_dict_tests(self):
        with self.assertRaises(lib.GateError):
            lib.validate_tests({"e2e": "npm run e2e"})
        for bad in ("pytest", ["unit"], 90, None):
            with self.subTest(tests=bad):
                with self.assertRaises(lib.GateError) as ctx:
                    lib.validate_tests(bad)
                self.assertIn("tests must be an object", str(ctx.exception))


class HelpersTest(unittest.TestCase):
    def test_coverage_target_reads_tests_coverage(self):
        self.assertEqual(lib.coverage_target({"tests": {"coverage": 75}}), 75)

    def test_coverage_target_falls_back_to_default(self):
        for settings in (None, {}, {"tests": None}, {"tests": {}}, {"tests": {"unit": {"command": "x"}}}):
            with self.subTest(settings=settings):
                self.assertEqual(lib.coverage_target(settings), 90)

    def test_test_suites_is_every_key_but_coverage(self):
        tests = {"coverage": 80, "unit": {"command": "a"}, "e2e": {"command": "b"}}
        self.assertEqual(lib.test_suites({"tests": tests}),
                         {"unit": {"command": "a"}, "e2e": {"command": "b"}})

    def test_test_suites_empty_when_unset(self):
        for settings in (None, {}, {"tests": None}, {"tests": {"coverage": 90}}):
            with self.subTest(settings=settings):
                self.assertEqual(lib.test_suites(settings), {})

    def test_load_settings_surfaces_tests_over_defaults(self):
        tmp = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, tmp, True)
        subprocess.run(["git", "init", "-q", tmp], check=True)
        os.makedirs(os.path.join(tmp, ".acs"))
        with open(os.path.join(tmp, ".acs", "settings.json"), "w") as fh:
            json.dump({"tests": {"unit": {"command": "pytest"}}}, fh)
        merged, _found = lib.load_settings(tmp)
        self.assertEqual(merged["tests"]["coverage"], 90)
        self.assertEqual(lib.test_suites(merged), {"unit": {"command": "pytest"}})


class SchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            cls.schema = json.load(fh)
        cls.tests = cls.schema["properties"]["tests"]

    def test_top_level_properties(self):
        self.assertEqual(list(self.schema["properties"]),
                         ["ticket_prefix", "merge_strategy", "tests", "evals",
                          "workflow", "models", "tracker", "design", "release"])

    def test_legacy_blocks_are_gone_from_the_schema(self):
        for key in ("test_coverage_percent", "suites", "e2e"):
            self.assertNotIn(key, self.schema["properties"])

    def test_coverage_property(self):
        self.assertEqual(self.tests["type"], "object")
        coverage = self.tests["properties"]["coverage"]
        self.assertEqual(coverage["type"], "number")
        self.assertEqual(coverage["exclusiveMinimum"], 0)
        self.assertEqual(coverage["maximum"], 100)
        self.assertEqual(coverage["default"], lib.DEFAULT_SETTINGS["tests"]["coverage"])

    def test_every_other_key_is_a_suite_requiring_command(self):
        suite = self.tests["additionalProperties"]
        self.assertEqual(suite["type"], "object")
        self.assertEqual(suite["required"], ["command"])
        self.assertEqual(set(suite["properties"]), {"command", "setup", "teardown"})
        for key in ("command", "setup", "teardown"):
            self.assertEqual(suite["properties"][key]["type"], "string")
            self.assertEqual(suite["properties"][key]["minLength"], 1)
        self.assertNotIn("per_iteration", suite["properties"])

    def test_tracker_provider_enum_has_no_jira(self):
        provider = self.schema["properties"]["tracker"]["properties"]["provider"]
        self.assertEqual(provider["enum"], ["local", "github"])
        self.assertNotIn("jira", self.schema["properties"]["tracker"].get("properties", {}))


class LegacyRefusalTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(self.repo)
        subprocess.run(["git", "init", "-q", self.repo], check=True)

    def _refused(self, extra):
        settings = dict({"ticket_prefix": "SHOP"}, **extra)
        with self.assertRaises(lib.GateError) as ctx:
            lib.validate_settings(settings, self.repo)
        return str(ctx.exception)

    def test_each_legacy_shape_is_refused_naming_settings_migrate(self):
        cases = {
            "test_coverage_percent": {"test_coverage_percent": 80},
            "suites": {"suites": {"smoke": {"command": "x"}}},
            "e2e": {"e2e": {"command": "x"}},
            "tests.command": {"tests": {"command": "pytest"}},
            "tests.setup": {"tests": {"setup": "pip install ."}},
            "models tiers": {"models": {"planner": "opus"}},
            "models overrides": {"models": {"overrides": {}}},
            "jira provider": {"tracker": {"provider": "jira"}},
            "tracker.jira": {"tracker": {"provider": "local", "jira": {"project": "X"}}},
        }
        for name, extra in cases.items():
            with self.subTest(legacy=name):
                message = self._refused(extra)
                self.assertIn("settings migrate", message)

    def test_message_names_the_replacement(self):
        self.assertIn("tests.coverage", self._refused({"test_coverage_percent": 80}))
        self.assertIn("tests.e2e", self._refused({"e2e": {"command": "x"}}))
        self.assertIn("tests.unit", self._refused({"tests": {"command": "pytest"}}))

    def test_new_shape_is_accepted(self):
        settings = {"ticket_prefix": "SHOP",
                    "tests": {"coverage": 85, "unit": {"command": "pytest"},
                              "e2e": {"command": "npm run e2e"}},
                    "tracker": {"provider": "github"}}
        lib.validate_settings(settings, self.repo)

    def test_invalid_new_shape_is_rejected_by_validate_tests(self):
        with self.assertRaises(lib.GateError) as ctx:
            lib.validate_settings({"ticket_prefix": "SHOP", "tests": {"coverage": 150}}, self.repo)
        self.assertIn("tests.coverage", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
