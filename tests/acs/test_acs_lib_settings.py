"""Behavior tests for acs_lib.py's settings validation/resolution and repo-identity helpers.

Originating ticket: MAR-173. slugify's fallback/truncation arms, write_json's
serialization-failure unlink, _git's OSError-to-None fallback, main_repo_root's
bare-repo best-effort branch, repo_partition_id's segment-count branches,
validate_settings/validate_formats/validate_models's raise-GateError arms,
resolve_role_model's inherit-sentinel and per-skill-override precedence, and
resolve_template's four resolution branches were exercised by no test.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

TESTS_ACS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS_ACS)

import acs_case  # noqa: E402

lib = acs_case.lib


def _mkrepo(parent, name):
    """A real (non-bare) git repo, no remote configured."""
    path = os.path.join(parent, name)
    os.makedirs(path)
    subprocess.run(["git", "init", "-q", path], check=True, capture_output=True)
    return path


class TestSlugify(unittest.TestCase):
    """403-404: lowercase/collapse, truncate+strip, empty/None/all-symbol fallback."""

    def test_lowercases_and_collapses_non_alphanumerics(self):
        self.assertEqual(lib.slugify("Hello, World!!"), "hello-world")

    def test_truncates_at_max_len_and_strips_trailing_hyphen(self):
        self.assertEqual(lib.slugify("ab cd ef", max_len=3), "ab")

    def test_falls_back_to_change_for_empty_none_or_all_symbols(self):
        self.assertEqual(lib.slugify(""), "change")
        self.assertEqual(lib.slugify(None), "change")
        self.assertEqual(lib.slugify("!!!"), "change")


class TestWriteJson(unittest.TestCase):
    """430: the finally-unlink runs when json.dump raises before os.replace."""

    def test_unlinks_temp_file_on_serialization_failure(self):
        tmp = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, tmp, True)
        target_dir = os.path.join(tmp, "sub")
        path = os.path.join(target_dir, "out.json")
        with self.assertRaises(TypeError):
            lib.write_json(path, {"bad": {1, 2, 3}})
        leftover = [n for n in os.listdir(target_dir) if n.startswith(".acs-tmp-")]
        self.assertEqual(leftover, [])


class TestGit(unittest.TestCase):
    """449-450: an OSError from subprocess.run (e.g. a non-existent cwd) returns None."""

    def test_returns_none_when_command_cannot_run(self):
        self.assertIsNone(lib._git(["status"], "/no/such/path/acs-test-xyz"))


class TestMainRepoRoot(unittest.TestCase):
    """475: a bare repo's --git-common-dir basename is not '.git' -> best-effort return."""

    def test_bare_repo_returns_git_common_dir_verbatim(self):
        tmp = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, tmp, True)
        bare = os.path.join(tmp, "bare-repo")
        subprocess.run(["git", "init", "-q", "--bare", bare], check=True, capture_output=True)
        self.assertEqual(lib.main_repo_root(bare), os.path.normpath(bare))


class TestRepoPartitionId(unittest.TestCase):
    """492-495, 498-501: single-segment remote, zero-segment remote, no remote, non-git dir."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_single_segment_remote_uses_that_segment(self):
        repo = _mkrepo(self.tmp, "one-seg")
        subprocess.run(["git", "-C", repo, "remote", "add", "origin", "myrepo.git"],
                        check=True, capture_output=True)
        self.assertEqual(lib.repo_partition_id(repo), "myrepo")

    def test_degenerate_remote_with_zero_segments_falls_through_to_directory(self):
        repo = _mkrepo(self.tmp, "zero-seg")
        subprocess.run(["git", "-C", repo, "remote", "add", "origin", "https://"],
                        check=True, capture_output=True)
        expected = re.sub(r"[^A-Za-z0-9._-]+", "-", os.path.basename(repo))
        self.assertEqual(lib.repo_partition_id(repo), expected)

    def test_no_remote_falls_back_to_repo_directory_basename(self):
        repo = _mkrepo(self.tmp, "no-remote")
        self.assertEqual(lib.repo_partition_id(repo), "no-remote")

    def test_non_git_directory_returns_none(self):
        nongit = os.path.join(self.tmp, "not-a-repo")
        os.makedirs(nongit)
        self.assertIsNone(lib.repo_partition_id(nongit))


class TestValidateSettings(unittest.TestCase):
    """582-585, 591, 597, 600, 607, 609: validate_settings's raise-GateError arms."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = _mkrepo(self.tmp, "repo")
        self.ws = os.path.join(self.tmp, "outside-ws")

    def test_rejects_workspace_path_inside_the_repo(self):
        inside = os.path.join(self.repo, "ws")
        with self.assertRaises(lib.GateError) as ctx:
            lib.validate_settings({"workspace_path": inside, "ticket_prefix": "SHOP"}, self.repo)
        self.assertIn("is inside the repository", str(ctx.exception))

    def test_rejects_missing_and_lowercase_ticket_prefix(self):
        for prefix in (None, "", "shop"):
            settings = {"workspace_path": self.ws}
            if prefix is not None:
                settings["ticket_prefix"] = prefix
            with self.assertRaises(lib.GateError) as ctx:
                lib.validate_settings(settings, self.repo)
            self.assertIn("ticket_prefix", str(ctx.exception))

    def test_rejects_out_of_range_coverage_percent(self):
        for bad in (150, 0, "ninety"):
            settings = {"workspace_path": self.ws, "ticket_prefix": "SHOP",
                        "test_coverage_percent": bad}
            with self.assertRaises(lib.GateError) as ctx:
                lib.validate_settings(settings, self.repo)
            self.assertIn("test_coverage_percent", str(ctx.exception))

    def test_rejects_unknown_merge_strategy(self):
        settings = {"workspace_path": self.ws, "ticket_prefix": "SHOP",
                     "merge_strategy": "octopus"}
        with self.assertRaises(lib.GateError) as ctx:
            lib.validate_settings(settings, self.repo)
        self.assertIn("merge_strategy", str(ctx.exception))

    def test_rejects_blank_e2e_setup_and_teardown(self):
        for key in ("setup", "teardown"):
            settings = {"workspace_path": self.ws, "ticket_prefix": "SHOP",
                        "e2e": {"command": "run", key: "  "}}
            with self.assertRaises(lib.GateError) as ctx:
                lib.validate_settings(settings, self.repo)
            self.assertIn("e2e.%s" % key, str(ctx.exception))

    def test_rejects_non_boolean_e2e_per_iteration(self):
        settings = {"workspace_path": self.ws, "ticket_prefix": "SHOP",
                     "e2e": {"command": "run", "per_iteration": "yes"}}
        with self.assertRaises(lib.GateError) as ctx:
            lib.validate_settings(settings, self.repo)
        self.assertIn("e2e.per_iteration", str(ctx.exception))


class TestValidateFormats(unittest.TestCase):
    """629, 649, 652: blank template, non-object formats.tickets, unknown ticket type."""

    def test_rejects_blank_template(self):
        with self.assertRaises(lib.GateError) as ctx:
            lib.validate_formats({"branch_name": "   "})
        self.assertIn("formats.branch_name", str(ctx.exception))

    def test_rejects_non_object_tickets(self):
        with self.assertRaises(lib.GateError) as ctx:
            lib.validate_formats({"tickets": "nope"})
        self.assertIn("formats.tickets", str(ctx.exception))

    def test_rejects_unknown_ticket_type_key(self):
        with self.assertRaises(lib.GateError) as ctx:
            lib.validate_formats({"tickets": {"bogus": {}}})
        self.assertIn("unknown ticket type", str(ctx.exception))


class TestValidateModels(unittest.TestCase):
    """659, 662-671, 675, 677-680: validate_models + its check_role closure."""

    def test_rejects_non_object_models(self):
        with self.assertRaises(lib.GateError) as ctx:
            lib.validate_models("nope")
        self.assertIn("models must be an object", str(ctx.exception))

    def test_rejects_blank_role_string(self):
        with self.assertRaises(lib.GateError) as ctx:
            lib.validate_models({"planner": "   "})
        self.assertIn("models.planner", str(ctx.exception))

    def test_rejects_unknown_key_in_role_object(self):
        with self.assertRaises(lib.GateError) as ctx:
            lib.validate_models({"planner": {"model": "opus", "bogus": 1}})
        self.assertIn("unknown key(s) bogus", str(ctx.exception))

    def test_rejects_role_value_that_is_neither_string_nor_object(self):
        with self.assertRaises(lib.GateError) as ctx:
            lib.validate_models({"planner": 5})
        self.assertIn("models.planner", str(ctx.exception))

    def test_accepts_a_top_level_string_role_and_a_top_level_object_role(self):
        lib.validate_models({"planner": "opus", "executor": {"model": "sonnet", "effort": "high"}})

    def test_rejects_non_object_skill_override(self):
        with self.assertRaises(lib.GateError) as ctx:
            lib.validate_models({"overrides": {"code": "nope"}})
        self.assertIn("models.overrides.code", str(ctx.exception))

    def test_accepts_a_per_skill_override_role(self):
        lib.validate_models({"overrides": {"code": {"executor": "sonnet"}}})


class TestResolveRoleModel(unittest.TestCase):
    """688-690, 695-697: as_obj's string/dict branches; inherit skipped; override wins."""

    def test_resolves_a_plain_string_role(self):
        settings = {"models": {"planner": "opus"}}
        self.assertEqual(lib.resolve_role_model(settings, "code", "planner"),
                          {"model": "opus", "effort": "inherit"})

    def test_resolves_an_object_role(self):
        settings = {"models": {"planner": {"model": "opus", "effort": "high"}}}
        self.assertEqual(lib.resolve_role_model(settings, "code", "planner"),
                          {"model": "opus", "effort": "high"})

    def test_inherit_sentinel_does_not_win(self):
        settings = {"models": {"planner": "inherit"}}
        self.assertEqual(lib.resolve_role_model(settings, "code", "planner"),
                          {"model": "inherit", "effort": "inherit"})

    def test_per_skill_override_overrides_the_role_default(self):
        settings = {"models": {"planner": "opus",
                                "overrides": {"code": {"planner": "sonnet"}}}}
        self.assertEqual(lib.resolve_role_model(settings, "code", "planner"),
                          {"model": "sonnet", "effort": "inherit"})


class TestResolveTemplate(unittest.TestCase):
    """707-714: built-in, repo-local, absolute-path, and unresolvable branches."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.plugin_root = os.path.join(self.tmp, "plugin")
        os.makedirs(self.plugin_root)
        self.repo_root = os.path.join(self.tmp, "repo")
        os.makedirs(os.path.join(self.repo_root, ".acs", "templates"))

    def test_resolves_a_builtin_name_to_the_plugin_templates_path(self):
        result = lib.resolve_template("pr-default", self.repo_root, self.plugin_root)
        self.assertEqual(result, os.path.join(self.plugin_root, "templates", "pr-default.md"))

    def test_resolves_a_repo_local_template(self):
        local = os.path.join(self.repo_root, ".acs", "templates", "custom.md")
        with open(local, "w") as fh:
            fh.write("x")
        self.assertEqual(lib.resolve_template("custom", self.repo_root, self.plugin_root), local)

    def test_resolves_an_absolute_existing_path(self):
        abs_path = os.path.join(self.tmp, "abs.md")
        with open(abs_path, "w") as fh:
            fh.write("x")
        self.assertEqual(lib.resolve_template(abs_path, self.repo_root, self.plugin_root), abs_path)

    def test_returns_none_for_an_unresolvable_value(self):
        self.assertIsNone(lib.resolve_template("nope", self.repo_root, self.plugin_root))


if __name__ == "__main__":
    unittest.main()
