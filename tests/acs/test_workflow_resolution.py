"""ship.yaml resolution and validation, plus the settings keys the workflow
layer reads.

Resolution: the consumer's <repo>/.acs/workflows/ship.yaml replaces the
plugin default WHOLESALE (no merge); absent, the plugin default applies.
`acs.py workflow show` prints {source, path, workflow}; `acs.py workflow
validate [--file PATH]` exits 0 with the step list or 2 with a line-numbered
reason. Every schema and semantic failure below asserts the LINE the error
names, because that is what a consumer editing an override gets to see.

Run:  python3 -m unittest tests.acs.test_workflow_resolution -v
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import AcsWorkspaceCase, SCRIPTS  # noqa: E402

sys.path.insert(0, SCRIPTS)
import acs_lib as lib  # noqa: E402

PLUGIN = os.path.dirname(os.path.dirname(SCRIPTS))

OVERRIDE = ("version: 1\n"
            "name: custom\n"
            "stop_after: only\n"
            "steps:\n"
            "  - id: only\n"
            "    skill: code\n")

#: A minimal valid document the failure cases mutate. Line numbers noted.
BASE = ("version: 1\n"             # 1
        "name: t\n"                # 2
        "stop_after: b\n"          # 3
        "steps:\n"                 # 4
        "  - id: a\n"              # 5
        "    skill: analyze-ticket\n"  # 6
        "  - id: b\n"              # 7
        "    skill: code\n"        # 8
        "    needs: [a]\n")        # 9


class TestResolution(AcsWorkspaceCase):

    def _override(self, text=OVERRIDE):
        path = lib.override_workflow_path(self.repo)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def test_default_when_no_override_exists(self):
        resolved = lib.resolve_workflow(self.repo)
        self.assertEqual(resolved["source"], "default")
        self.assertEqual(resolved["path"], os.path.join(PLUGIN, "workflows", "ship.yaml"))
        self.assertEqual(resolved["workflow"]["name"], "ship")
        self.assertEqual(sorted(resolved), ["path", "source", "workflow"])

    def test_override_replaces_the_default_wholesale(self):
        path = self._override()
        resolved = lib.resolve_workflow(self.repo)
        self.assertEqual(resolved["source"], "override")
        self.assertEqual(resolved["path"], path)
        self.assertEqual(path, os.path.join(self.repo, ".acs", "workflows", "ship.yaml"))
        self.assertEqual(resolved["workflow"]["name"], "custom")
        # No merge: the default's nine steps are gone, only the override's one remains.
        self.assertEqual([s["id"] for s in resolved["workflow"]["steps"]], ["only"])

    def test_resolve_without_a_checkout_falls_back_to_the_default(self):
        self.assertEqual(lib.resolve_workflow(None)["source"], "default")

    def test_the_default_is_the_validated_shipped_file(self):
        self.assertEqual(lib.resolve_workflow(self.repo)["path"], lib.default_workflow_path())

    def test_an_unparseable_override_is_a_workflow_error_with_its_line(self):
        path = self._override("version: 1\nname: x\nsteps: {a}\n")
        with self.assertRaises(lib.WorkflowError) as ctx:
            lib.resolve_workflow(self.repo)
        self.assertEqual(ctx.exception.line, 3)
        self.assertEqual(ctx.exception.path, path)

    def test_the_module_aliases_the_brief_names(self):
        self.assertIs(lib.workflow.resolve, lib.resolve_workflow)
        self.assertIs(lib.workflow.validate, lib.validate_workflow)
        self.assertIs(lib.workflow.next, lib.next_steps)


class TestValidationFailures(unittest.TestCase):
    """Each failure names its line. Library-level, over temp files."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-wf-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def _validate(self, text):
        path = os.path.join(self.tmp, "ship.yaml")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return lib.validate_workflow_file(path)

    def assertFailsAt(self, text, line, fragment):
        with self.assertRaises(lib.WorkflowError) as ctx:
            self._validate(text)
        self.assertEqual(ctx.exception.line, line, str(ctx.exception))
        self.assertIn(fragment, str(ctx.exception))
        self.assertIn(":%d: " % line, str(ctx.exception))

    def test_the_base_document_is_valid(self):
        self.assertEqual([s["id"] for s in self._validate(BASE)["steps"]], ["a", "b"])

    def test_unknown_top_level_key(self):
        self.assertFailsAt(BASE.replace("steps:\n", "bogus: 1\nsteps:\n"), 4, "unknown key 'bogus'")

    def test_wrong_version(self):
        self.assertFailsAt(BASE.replace("version: 1", "version: 2"), 1, "version: must be 1")

    def test_missing_name_is_reported_at_the_root(self):
        self.assertFailsAt(BASE.replace("name: t\n", ""), 1, "missing required key 'name'")

    def test_empty_steps(self):
        self.assertFailsAt("version: 1\nname: t\nsteps: []\n", 3, "at least 1")

    def test_document_that_is_not_a_mapping(self):
        self.assertFailsAt("- a\n", 1, "expected object, got array")

    def test_unknown_skill(self):
        self.assertFailsAt(BASE.replace("skill: code", "skill: merge-pr"), 8, "'merge-pr' is not one of")

    def test_missing_skill_is_reported_at_the_step(self):
        self.assertFailsAt(BASE.replace("    skill: code\n", ""), 7, "missing required key 'skill'")

    def test_unknown_step_key(self):
        self.assertFailsAt(BASE + "    foo: 1\n", 10, "unknown key 'foo'")

    def test_needs_naming_a_later_step(self):
        text = BASE.replace("    skill: analyze-ticket\n", "    skill: analyze-ticket\n    needs: [b]\n")
        self.assertFailsAt(text, 7, "'b' must name an EARLIER step")

    def test_needs_naming_an_unknown_step(self):
        self.assertFailsAt(BASE.replace("needs: [a]", "needs: [zzz]"), 9, "'zzz' must name an EARLIER step")

    def test_needs_naming_itself(self):
        self.assertFailsAt(BASE.replace("needs: [a]", "needs: [b]"), 9, "'b' must name an EARLIER step")

    def test_duplicate_needs(self):
        self.assertFailsAt(BASE.replace("needs: [a]", "needs: [a, a]"), 9, "items must be unique")

    def test_duplicate_step_id(self):
        self.assertFailsAt(BASE.replace("  - id: b\n", "  - id: a\n"), 7, "duplicate step id 'a'")

    def test_step_id_pattern(self):
        self.assertFailsAt(BASE.replace("  - id: b\n", "  - id: B\n"), 7, "does not match")

    def test_stop_after_must_be_a_step_id(self):
        self.assertFailsAt(BASE.replace("stop_after: b", "stop_after: zzz"), 3, "'zzz' is not a step id")

    def test_stop_after_defaults_to_create_pr_which_must_exist(self):
        text = BASE.replace("stop_after: b\n", "")
        with self.assertRaises(lib.WorkflowError) as ctx:
            self._validate(text)
        self.assertIn("'create-pr' is not a step id", str(ctx.exception))
        self.assertEqual(ctx.exception.line, 1)

    def test_unknown_when_predicate(self):
        self.assertFailsAt(BASE + "    when: nope\n", 10, "'nope' is not one of")

    def test_unknown_requires_predicate(self):
        self.assertFailsAt(BASE + "    requires: nope\n", 10, "'nope' is not one of")

    def test_every_known_predicate_is_accepted(self):
        for predicate in lib.PREDICATES:
            with self.subTest(predicate=predicate):
                self._validate(BASE + "    when: %s\n    requires: %s\n" % (predicate, predicate))

    def test_on_fail_relay_to_unknown(self):
        self.assertFailsAt(BASE + "    on_fail:\n      relay_to: zzz\n", 11, "'zzz' is not another step id")

    def test_on_fail_relay_to_self(self):
        self.assertFailsAt(BASE + "    on_fail:\n      relay_to: b\n", 11, "'b' is not another step id")

    def test_on_fail_requires_relay_to(self):
        self.assertFailsAt(BASE + "    on_fail:\n      max_loops: 1\n", 10, "missing required key 'relay_to'")

    def test_on_fail_max_loops_unknown_name(self):
        text = BASE + "    on_fail:\n      relay_to: a\n      max_loops: bogus_cap\n"
        self.assertFailsAt(text, 12, "does not match exactly one of the allowed forms")

    def test_on_fail_max_loops_accepts_an_integer_or_the_named_cap(self):
        self._validate(BASE + "    on_fail:\n      relay_to: a\n      max_loops: 3\n")
        self._validate(BASE + "    on_fail:\n      relay_to: a\n      max_loops: post_code_test_fix_loops_cap\n")

    def test_on_fail_max_loops_rejects_a_negative(self):
        text = BASE + "    on_fail:\n      relay_to: a\n      max_loops: -1\n"
        self.assertFailsAt(text, 12, "does not match exactly one")

    def test_on_replan_unknown(self):
        self.assertFailsAt(BASE + "    on_replan: zzz\n", 10, "'zzz' is not another step id")

    def test_on_replan_self(self):
        self.assertFailsAt(BASE + "    on_replan: b\n", 10, "'b' is not another step id")

    def test_boundary_enum(self):
        self.assertFailsAt(BASE + "    boundary: soft\n", 10, "'soft' is not one of")

    def test_exclusive_must_be_boolean(self):
        self.assertFailsAt(BASE + "    exclusive: yes\n", 10, "expected boolean, got string")

    def test_args_must_be_a_string(self):
        self.assertFailsAt(BASE + "    args: 3\n", 10, "expected string, got integer")

    def test_max_parallel_minimum(self):
        self.assertFailsAt(BASE.replace("name: t\n", "name: t\nmax_parallel: 0\n"), 3, "must be >= 1")

    def test_max_parallel_type(self):
        self.assertFailsAt(BASE.replace("name: t\n", "name: t\nmax_parallel: two\n"), 3,
                           "expected integer, got string")

    def test_a_parse_error_names_its_line(self):
        self.assertFailsAt(BASE.replace("    skill: code\n", "\tskill: code\n"), 8, "tab")

    def test_validate_without_lines_still_refuses(self):
        doc = lib.yamlsubset.loads(BASE.replace("stop_after: b", "stop_after: zzz"))
        with self.assertRaises(lib.WorkflowError) as ctx:
            lib.validate_workflow(doc)
        self.assertIsNone(ctx.exception.line)
        self.assertIn("stop_after", str(ctx.exception))

    def test_a_cycle_is_named_even_if_needs_were_not_ordered(self):
        """The ordering rule already forbids cycles; the explicit check still
        fires when it is bypassed (a doc validated after the ordering pass is
        patched away)."""
        steps = [{"id": "a", "skill": "code", "needs": ["b"]}, {"id": "b", "skill": "code", "needs": ["a"]}]
        with self.assertRaises(lib.WorkflowError) as ctx:
            lib.workflow._check_acyclic(steps, None, None)
        self.assertIn("cycle", str(ctx.exception))


class TestWorkflowCli(AcsWorkspaceCase):

    def acs(self, *args, **kwargs):
        return self.run_script("acs.py", *args, **kwargs)

    def _override(self, text=OVERRIDE):
        path = lib.override_workflow_path(self.repo)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def _file(self, name, text):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def test_show_prints_the_default(self):
        res = self.acs("workflow", "show")
        self.assertEqual(res.returncode, 0, res.stderr)
        out = json.loads(res.stdout)
        self.assertEqual(sorted(out), ["ok", "path", "source", "workflow"])
        self.assertEqual(out["source"], "default")
        self.assertEqual(out["path"], lib.default_workflow_path())
        self.assertEqual(out["workflow"]["name"], "ship")

    def test_show_prints_the_override(self):
        path = self._override()
        out = json.loads(self.acs("workflow", "show").stdout)
        self.assertEqual(out["source"], "override")
        self.assertEqual(out["path"], path)
        self.assertEqual(out["workflow"]["name"], "custom")

    def test_show_refuses_an_unparseable_override_naming_the_line(self):
        path = self._override("version: 1\nname: x\nsteps:\n  - id: a\n    skill: &anchor code\n")
        res = self.acs("workflow", "show")
        self.assertEqual(res.returncode, 2)
        self.assertIn("%s:5: " % path, res.stderr)
        self.assertIn("anchor", res.stderr)

    def test_validate_exits_zero_for_the_default(self):
        res = self.acs("workflow", "validate")
        self.assertEqual(res.returncode, 0, res.stderr)
        out = json.loads(res.stdout)
        self.assertTrue(out["ok"])
        self.assertEqual(out["source"], "default")
        self.assertEqual(out["stop_after"], "create-pr")
        self.assertEqual(out["max_parallel"], 2)
        self.assertEqual(out["steps"][0], "analyze-ticket")
        self.assertEqual(out["steps"][-1], "create-pr")

    def test_validate_checks_the_override_when_present(self):
        path = self._override(OVERRIDE.replace("skill: code", "skill: release"))
        res = self.acs("workflow", "validate")
        self.assertEqual(res.returncode, 2)
        out = json.loads(res.stdout)
        self.assertEqual(out["ok"], False)
        self.assertEqual(out["source"], "override")
        self.assertEqual(out["line"], 6)
        self.assertIn("'release' is not one of", out["reason"])
        self.assertIn("acs workflow validate: %s:6: " % path, res.stderr)

    def test_validate_file_exits_two_with_the_line_numbered_reason(self):
        path = self._file("bad.yaml", BASE.replace("stop_after: b", "stop_after: nope"))
        res = self.acs("workflow", "validate", "--file", path)
        self.assertEqual(res.returncode, 2)
        self.assertIn("%s:3: stop_after: 'nope' is not a step id" % path, res.stderr)
        out = json.loads(res.stdout)
        self.assertEqual((out["ok"], out["source"], out["path"], out["line"]), (False, "file", path, 3))

    def test_validate_file_exits_zero_for_a_valid_file(self):
        path = self._file("good.yaml", BASE)
        res = self.acs("workflow", "validate", "--file", path)
        self.assertEqual(res.returncode, 0, res.stderr)
        out = json.loads(res.stdout)
        self.assertEqual(out["steps"], ["a", "b"])
        self.assertEqual(out["source"], "file")

    def test_validate_file_works_without_acs_settings(self):
        """A file check needs no configured workspace: a repo that has not run
        /acs:setup can still lint an override it is about to commit."""
        bare = os.path.join(self.tmp, "bare")
        os.makedirs(bare)
        import subprocess
        subprocess.run(["git", "init", "-q", bare], check=True)
        path = self._file("good2.yaml", BASE)
        res = self.acs("workflow", "validate", "--file", path, cwd=bare)
        self.assertEqual(res.returncode, 0, res.stderr)

    def test_validate_file_missing(self):
        res = self.acs("workflow", "validate", "--file", os.path.join(self.tmp, "absent.yaml"))
        self.assertEqual(res.returncode, 2)
        self.assertIn("cannot read", res.stderr)

    def test_the_group_without_a_subcommand_prints_usage(self):
        res = self.acs("workflow")
        self.assertEqual(res.returncode, 2)
        self.assertIn("usage", res.stderr.lower())
        self.assertIn("next", res.stderr)

    def test_help_lists_the_group(self):
        res = self.acs("--help")
        self.assertIn("workflow", res.stdout)


class TestSettingsKeys(AcsWorkspaceCase):
    """The three settings keys the workflow layer and the artifacts move read."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(PLUGIN, "schemas", "settings.schema.json"), encoding="utf-8") as fh:
            cls.schema = json.load(fh)
        cls.props = cls.schema["properties"]

    def test_schema_workflow_advisories_defaults_true(self):
        prop = self.props["workflow"]
        self.assertEqual(prop["type"], "object")
        self.assertEqual(prop["properties"]["advisories"], {"type": "boolean", "default": True})

    def test_schema_artifacts_tickets_path_is_string_or_null_defaulting_to_docs_tickets(self):
        prop = self.props["artifacts"]["properties"]["tickets_path"]
        self.assertEqual(prop["default"], "docs/tickets")
        self.assertIn({"type": "null"}, prop["oneOf"])
        self.assertIn({"type": "string", "minLength": 1}, prop["oneOf"])

    def test_schema_contracts_path_is_string_or_null_defaulting_to_docs_api(self):
        prop = self.props["contracts_path"]
        self.assertEqual(prop["default"], "docs/api")
        self.assertIn({"type": "null"}, prop["oneOf"])

    def test_default_settings_seed_the_three_keys(self):
        self.assertEqual(lib.DEFAULT_SETTINGS["workflow"], {"advisories": True})
        self.assertEqual(lib.DEFAULT_SETTINGS["artifacts"], {"tickets_path": "docs/tickets"})
        self.assertEqual(lib.DEFAULT_SETTINGS["contracts_path"], "docs/api")

    def test_load_settings_resolves_the_defaults(self):
        settings, _sources = lib.load_settings(self.repo)
        self.assertTrue(settings["workflow"]["advisories"])
        self.assertEqual(settings["artifacts"]["tickets_path"], "docs/tickets")
        self.assertEqual(settings["contracts_path"], "docs/api")

    def test_an_explicit_null_opts_out(self):
        self.write_settings({"ticket_prefix": "SHOP", "artifacts": {"tickets_path": None},
                             "contracts_path": None, "workflow": {"advisories": False}})
        settings, _sources = lib.load_settings(self.repo)
        self.assertIsNone(settings["artifacts"]["tickets_path"])
        self.assertIsNone(settings["contracts_path"])
        self.assertFalse(settings["workflow"]["advisories"])
        lib.validate_settings(settings, self.repo)

    def test_the_keys_validate_against_the_schema_with_jsonschema(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is not installed")
        for doc in ({"workflow": {"advisories": False}, "artifacts": {"tickets_path": None},
                     "contracts_path": None},
                    {"workflow": {"advisories": True}, "artifacts": {"tickets_path": "tickets"},
                     "contracts_path": "api"}):
            jsonschema.validate(doc, self.schema)
        for bad in ({"workflow": {"advisories": "yes"}}, {"artifacts": {"tickets_path": ""}},
                    {"contracts_path": 3}):
            with self.assertRaises(jsonschema.ValidationError):
                jsonschema.validate(bad, self.schema)


if __name__ == "__main__":
    unittest.main()
