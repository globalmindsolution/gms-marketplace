"""workflows/phases.yaml is the skill registry: every plugins/acs/skills/<dir>
appears exactly once (counting the `aliases` key, which lists a directory
that forwards to a registered skill), only the five groups exist, and the
ship-eligible subset (build + test + ship minus merge-pr and release) is what
ship.yaml may name.

The registry is read through acs_lib.workflow.load_phases, which also
schema-checks the file (schemas/phases.schema.json) and refuses a skill
listed twice or an alias pointing nowhere -- each refusal names the line.

The six Build/Test skill directories (analyze-ticket, create-api-contract,
create-impl-plan, create-test-docs, create-e2e-tests, run-e2e-tests) arrive in
a later phase of the refactor, so the "every registry name has a directory"
direction is RED until they land. It is written anyway: the registry is the
contract those directories are built to.

Run:  python3 -m unittest tests.acs.test_phases_registry -v
"""

import collections
import json
import os
import shutil
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SKILLS_DIR = os.path.join(PLUGIN, "skills")
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
sys.path.insert(0, SCRIPTS)

import acs_lib as lib  # noqa: E402
from acs_lib import workflow  # noqa: E402

#: The grouping the refactor brief fixes (brief section 1).
EXPECTED_GROUPS = {
    "design": ["create-prd", "create-requirements", "create-architecture", "create-project",
               "create-principles", "create-standards", "create-quality", "create-operations",
               "create-docs", "standardize-project", "create-ticket", "create-design"],
    "build": ["analyze-ticket", "create-api-contract", "create-impl-plan", "create-test-docs",
              "code", "docs-sync"],
    "test": ["create-e2e-tests", "run-e2e-tests"],
    "ship": ["create-pr", "merge-pr", "release"],
    "utility": ["setup", "install-hooks", "update", "handoff", "metrics", "usage", "ship"],
}


def skill_dirs():
    return sorted(name for name in os.listdir(SKILLS_DIR)
                  if os.path.isdir(os.path.join(SKILLS_DIR, name)) and not name.startswith("."))


class TestPhasesRegistry(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.phases = lib.load_phases()
        cls.names = lib.registered_skills(cls.phases) + sorted(lib.skill_aliases(cls.phases))

    def test_the_file_lives_where_the_resolver_expects(self):
        self.assertEqual(lib.phases_path(), os.path.join(PLUGIN, "workflows", "phases.yaml"))
        self.assertTrue(os.path.isfile(lib.phases_path()))

    def test_only_the_five_groups_in_order(self):
        self.assertEqual(tuple(self.phases["phases"]), workflow.PHASE_GROUPS)
        self.assertEqual(workflow.PHASE_GROUPS, ("design", "build", "test", "ship", "utility"))

    def test_the_groups_match_the_brief(self):
        self.assertEqual(self.phases["phases"], EXPECTED_GROUPS)

    def test_the_alias_key_maps_test_to_run_e2e_tests(self):
        self.assertEqual(lib.skill_aliases(self.phases), {"test": "run-e2e-tests"})

    def test_every_registry_name_appears_exactly_once(self):
        counts = collections.Counter(self.names)
        self.assertEqual([n for n, c in counts.items() if c != 1], [])

    def test_every_skill_directory_is_registered_exactly_once(self):
        """Counting the aliases key: the `test` directory is an alias, not a phase entry."""
        counts = collections.Counter(self.names)
        missing = [d for d in skill_dirs() if counts[d] != 1]
        self.assertEqual(missing, [], "skill dirs not registered exactly once: %s" % missing)

    def test_every_registry_name_has_a_skill_directory(self):
        """RED until the six Build/Test skill directories land (see the module docstring)."""
        dirs = set(skill_dirs())
        missing = [n for n in self.names if n not in dirs]
        self.assertEqual(missing, [], "registered without a skills/<dir>: %s" % missing)

    def test_hooked_and_unhooked_skill_lists_are_registered(self):
        for skill in list(lib.HOOKED_SKILLS) + list(lib.UNHOOKED_SKILLS):
            with self.subTest(skill=skill):
                self.assertIn(skill, self.names)

    def test_ship_eligible_skills_are_build_test_ship_minus_merge_pr_and_release(self):
        allowed = lib.allowed_ship_skills(self.phases)
        self.assertEqual(allowed, EXPECTED_GROUPS["build"] + EXPECTED_GROUPS["test"] + ["create-pr"])
        self.assertNotIn("merge-pr", allowed)
        self.assertNotIn("release", allowed)
        for skill in allowed:
            self.assertIn(lib.phase_of(skill, self.phases), workflow.SHIP_PHASES)

    def test_phase_of_resolves_skills_and_aliases(self):
        self.assertEqual(lib.phase_of("code", self.phases), "build")
        self.assertEqual(lib.phase_of("create-pr", self.phases), "ship")
        self.assertEqual(lib.phase_of("test", self.phases), "test")
        self.assertEqual(lib.phase_of("ship", self.phases), "utility")
        self.assertIsNone(lib.phase_of("not-a-skill", self.phases))

    def test_registered_skills_excludes_aliases(self):
        self.assertNotIn("test", lib.registered_skills(self.phases))
        self.assertIn("run-e2e-tests", lib.registered_skills(self.phases))

    def test_the_registry_validates_against_its_schema_with_jsonschema(self):
        """The stdlib subset validator in acs_lib.workflow is cross-checked
        against the real package so the two cannot disagree on the shipped file."""
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is not installed")
        with open(os.path.join(PLUGIN, "schemas", "phases.schema.json"), encoding="utf-8") as fh:
            schema = json.load(fh)
        jsonschema.validate(self.phases, schema)


class TestLoadPhasesRefusals(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-phases-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def _load(self, text):
        path = os.path.join(self.tmp, "phases.yaml")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return lib.load_phases(path)

    def assertRefuses(self, text, line, fragment):
        with self.assertRaises(lib.WorkflowError) as ctx:
            self._load(text)
        self.assertEqual(ctx.exception.line, line, str(ctx.exception))
        self.assertIn(fragment, str(ctx.exception))

    BASE = ("version: 1\n"            # 1
            "phases:\n"               # 2
            "  design: [a]\n"         # 3
            "  build: [b]\n"          # 4
            "  test: [c]\n"           # 5
            "  ship: [d]\n"           # 6
            "  utility: [e]\n")       # 7

    def test_a_minimal_registry_loads_with_empty_aliases(self):
        self.assertEqual(self._load(self.BASE)["aliases"], {})

    def test_a_skill_listed_twice_names_the_second_group(self):
        self.assertRefuses(self.BASE.replace("build: [b]", "build: [b, a]"), 4, "listed under both")

    def test_an_unknown_group_is_refused_at_its_line(self):
        self.assertRefuses(self.BASE + "  extra: [f]\n", 8, "unknown key 'extra'")

    def test_a_missing_group_is_refused(self):
        self.assertRefuses(self.BASE.replace("  utility: [e]\n", ""), 2, "missing required key 'utility'")

    def test_an_empty_group_is_refused(self):
        self.assertRefuses(self.BASE.replace("test: [c]", "test: []"), 5, "at least 1")

    def test_an_alias_to_an_unregistered_skill_is_refused(self):
        self.assertRefuses(self.BASE + "aliases:\n  z: nope\n", 9, "unregistered skill")

    def test_an_alias_that_is_also_a_skill_is_refused(self):
        self.assertRefuses(self.BASE + "aliases:\n  a: b\n", 9, "also a registered skill")

    def test_a_wrong_version_is_refused(self):
        self.assertRefuses(self.BASE.replace("version: 1", "version: 2"), 1, "must be 1")

    def test_a_parse_error_is_a_workflow_error_with_its_line(self):
        self.assertRefuses(self.BASE.replace("  ship: [d]", "  ship: {d}"), 6, "flow mapping")

    def test_a_missing_file_is_refused(self):
        with self.assertRaises(lib.WorkflowError):
            lib.load_phases(os.path.join(self.tmp, "absent.yaml"))


if __name__ == "__main__":
    unittest.main()
