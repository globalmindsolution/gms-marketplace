"""Behavior tests for acs_lib.py's settings validation/resolution and repo-identity helpers.

Originating ticket: MAR-173. slugify's fallback/truncation arms, write_json's
serialization-failure unlink, _git's OSError-to-None fallback, main_repo_root's
bare-repo best-effort branch, repo_partition_id's segment-count branches,
validate_settings/validate_formats/validate_models's raise-GateError arms,
resolve_role_model's inherit-sentinel and per-skill-override precedence, and
resolve_template's four resolution branches were exercised by no test.

MAR-2 adds: default_state_root's 4-step git-plumbing resolution rule, the
inverted (in-repo-accepting) validate_settings workspace branch, and the
settings.schema.json workspace_path description rewrite.
"""

import inspect
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

TESTS_ACS = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(TESTS_ACS))
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


class TestDefaultStateRoot(unittest.TestCase):
    """default_state_root's 4-step git-plumbing resolution rule (D1-D3)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_checkout_root_resolves_to_dot_acs_state_machine(self):
        repo = _mkrepo(self.tmp, "repo")
        self.assertEqual(lib.default_state_root(repo), os.path.join(repo, ".acs", "state-machine"))

    def test_subdirectory_resolves_to_the_repo_root_not_the_subdirectory(self):
        repo = _mkrepo(self.tmp, "repo")
        sub = os.path.join(repo, "sub", "dir")
        os.makedirs(sub)
        self.assertEqual(lib.default_state_root(sub), os.path.join(repo, ".acs", "state-machine"))

    def test_linked_worktree_resolves_to_the_main_checkout(self):
        repo = _mkrepo(self.tmp, "repo")
        subprocess.run(["git", "-C", repo, "config", "user.email", "acs-test@example.com"],
                        check=True, capture_output=True)
        subprocess.run(["git", "-C", repo, "config", "user.name", "acs-test"],
                        check=True, capture_output=True)
        subprocess.run(["git", "-C", repo, "commit", "--allow-empty", "-q", "-m", "init"],
                        check=True, capture_output=True)
        worktree = os.path.join(self.tmp, "wt")
        subprocess.run(["git", "-C", repo, "worktree", "add", "-q", "-b", "wt-branch", worktree],
                        check=True, capture_output=True)
        main_result = os.path.realpath(lib.default_state_root(repo))
        wt_result = os.path.realpath(lib.default_state_root(worktree))
        self.assertEqual(main_result, wt_result)
        self.assertEqual(main_result, os.path.realpath(os.path.join(repo, ".acs", "state-machine")))

    def test_bare_repo_raises_gate_error_naming_the_override(self):
        bare = os.path.join(self.tmp, "bare.git")
        subprocess.run(["git", "init", "-q", "--bare", bare], check=True, capture_output=True)
        with self.assertRaises(lib.GateError) as ctx:
            lib.default_state_root(bare)
        msg = str(ctx.exception).replace(bare, "<cwd>")
        self.assertIn("workspace_path", msg)
        self.assertIn("bare git repository", msg)
        self.assertNotIn("not a git repository", msg)

    def test_non_git_directory_raises_gate_error(self):
        nongit = os.path.join(self.tmp, "not-a-repo")
        os.makedirs(nongit)
        with self.assertRaises(lib.GateError) as ctx:
            lib.default_state_root(nongit)
        msg = str(ctx.exception).replace(nongit, "<cwd>")
        self.assertIn("workspace_path", msg)
        self.assertIn("not a git repository", msg)
        self.assertNotIn("bare", msg)

    def test_empty_git_common_dir_raises_gate_error(self):
        # acs_lib is a package (MAR-522): acs_lib.repo bound this name at import
        # time, so patching the facade would leave the real one in place and
        # this branch would go uncovered while the test still passed.
        with mock.patch.object(lib.repo, "_git", side_effect=["false", ""]):
            with self.assertRaises(lib.GateError) as ctx:
                lib.default_state_root(self.tmp)
        self.assertIn("workspace_path", str(ctx.exception))

    def test_submodule_raises_gate_error_naming_git_submodule(self):
        child = _mkrepo(self.tmp, "child")
        subprocess.run(["git", "-C", child, "config", "user.email", "acs-test@example.com"],
                        check=True, capture_output=True)
        subprocess.run(["git", "-C", child, "config", "user.name", "acs-test"],
                        check=True, capture_output=True)
        subprocess.run(["git", "-C", child, "commit", "--allow-empty", "-q", "-m", "init"],
                        check=True, capture_output=True)
        parent = _mkrepo(self.tmp, "parent")
        subprocess.run(["git", "-C", parent, "config", "user.email", "acs-test@example.com"],
                        check=True, capture_output=True)
        subprocess.run(["git", "-C", parent, "config", "user.name", "acs-test"],
                        check=True, capture_output=True)
        subprocess.run(["git", "-C", parent, "commit", "--allow-empty", "-q", "-m", "init"],
                        check=True, capture_output=True)
        result = subprocess.run(
            ["git", "-c", "protocol.file.allow=always", "-C", parent, "submodule", "add", child, "sub-mod"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            self.skipTest("git submodule add unsupported in this environment: %s" % result.stderr)
        sub_path = os.path.join(parent, "sub-mod")
        with self.assertRaises(lib.GateError) as ctx:
            lib.default_state_root(sub_path)
        msg = str(ctx.exception)
        self.assertIn("git submodule", msg)
        self.assertIn("workspace_path", msg)

    def test_unusual_layout_without_a_superproject_raises_generic_gate_error(self):
        sepgit = os.path.join(self.tmp, "sepgit")
        worktree_dir = os.path.join(self.tmp, "separate-worktree")
        subprocess.run(["git", "init", "-q", "--separate-git-dir=" + sepgit, worktree_dir],
                        check=True, capture_output=True)
        with self.assertRaises(lib.GateError) as ctx:
            lib.default_state_root(worktree_dir)
        msg = str(ctx.exception)
        self.assertIn("workspace_path", msg)
        self.assertNotIn("submodule", msg)


class TestPathHelpersByteUnchanged(unittest.TestCase):
    """AC1: main_repo_root/checkout_root/repo_partition_id/checkout_id/settings_files
    must stay byte-unchanged by this ticket (design D6) -- pins each helper's exact
    source text as it read before MAR-2."""

    def test_existing_path_helpers_are_byte_unchanged(self):
        pinned = {
            "checkout_root": r'''def checkout_root(cwd):
    """Root of the current checkout/worktree."""
    return _git(["rev-parse", "--show-toplevel"], cwd)
''',
            "main_repo_root": r'''def main_repo_root(cwd):
    """Root of the *main* repository, even when cwd is inside a linked worktree."""
    common = _git(["rev-parse", "--git-common-dir"], cwd)
    if not common:
        return None
    if not os.path.isabs(common):
        common = os.path.join(cwd, common)
    common = os.path.normpath(common)
    if os.path.basename(common) == ".git":
        return os.path.dirname(common)
    return common  # bare-ish layouts; best effort
''',
            "repo_partition_id": r'''def repo_partition_id(cwd):
    """Stable per-repo identifier: derived from the git remote (owner-name), so every
    worktree of a repo resolves to the same partition; falls back to the main repo
    directory name when there is no remote."""
    remote = _git(["config", "--get", "remote.origin.url"], cwd)
    if remote:
        path = remote
        path = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", "", path)   # scheme
        path = re.sub(r"^[^/@]+@", "", path)                       # user@
        path = path.replace(":", "/")
        path = re.sub(r"\.git/?$", "", path)
        segments = [s for s in path.split("/") if s]
        if len(segments) >= 2:
            raw = "%s-%s" % (segments[-2], segments[-1])
        elif segments:
            raw = segments[-1]
        else:
            raw = None
        if raw:
            return re.sub(r"[^A-Za-z0-9._-]+", "-", raw)
    root = main_repo_root(cwd) or checkout_root(cwd)
    if root:
        return re.sub(r"[^A-Za-z0-9._-]+", "-", os.path.basename(root))
    return None
''',
            "checkout_id": r'''def checkout_id(cwd):
    """Stable per-checkout/worktree identifier (one pointer file per parallel session)."""
    root = checkout_root(cwd) or os.path.abspath(cwd)
    digest = hashlib.sha1(os.path.abspath(root).encode("utf-8")).hexdigest()[:8]
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", os.path.basename(root))
    return "%s-%s" % (base, digest)
''',
            "settings_files": r'''def settings_files(cwd):
    """Candidate settings files, least -> most specific. settings.local.json is
    machine-specific and gitignored; a linked worktree may not have its own copy,
    so the main checkout's local settings are also consulted."""
    candidates = []
    user = os.path.join(os.path.expanduser("~"), ".acs", "settings.json")
    candidates.append(user)
    main_root = main_repo_root(cwd)
    top = checkout_root(cwd)
    roots = []
    for root in (main_root, top):
        if root and root not in roots:
            roots.append(root)
    for root in roots:
        candidates.append(os.path.join(root, ".acs", "settings.json"))
    for root in roots:
        candidates.append(os.path.join(root, ".acs", "settings.local.json"))
    return candidates
''',
        }
        for name, expected_source in pinned.items():
            actual = inspect.getsource(getattr(lib, name))
            self.assertEqual(actual, expected_source, "helper %s changed" % name)


class TestSettingsSchemaWorkspacePathDoc(unittest.TestCase):
    """AC3: workspace_path's schema description documents the optional,
    in-repo-derived default and no longer claims an outside-repo requirement."""

    def test_settings_schema_workspace_path_is_documented_as_optional_and_in_repo(self):
        schema_path = os.path.join(REPO_ROOT, "plugins", "acs", "schemas", "settings.schema.json")
        with open(schema_path, "r", encoding="utf-8") as fh:
            schema = json.load(fh)
        description = schema["properties"]["workspace_path"]["description"]
        self.assertNotIn("outside the consumer repo", description)
        self.assertIn("state-machine", description)
        self.assertNotIn("workspace_path", schema.get("required", []))


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

    def test_accepts_an_explicit_workspace_path_inside_the_repo(self):
        inside = os.path.join(self.repo, "ws")
        result = lib.validate_settings({"workspace_path": inside, "ticket_prefix": "SHOP"}, self.repo)
        self.assertEqual(result, os.path.abspath(inside))

    def test_expands_user_home_in_an_explicit_override(self):
        fake_home = os.path.join(self.tmp, "home")
        os.makedirs(fake_home)
        with mock.patch.dict(os.environ, {"HOME": fake_home}):
            result = lib.validate_settings({"workspace_path": "~/ws", "ticket_prefix": "SHOP"}, self.repo)
            expected = os.path.abspath(os.path.expanduser("~/ws"))
        self.assertEqual(result, expected)

    def test_derives_the_in_repo_default_when_workspace_path_is_absent(self):
        result = lib.validate_settings({"ticket_prefix": "SHOP"}, self.repo)
        self.assertEqual(result, os.path.join(self.repo, ".acs", "state-machine"))

    def test_absent_workspace_path_in_a_bare_repo_raises_gate_error(self):
        bare = os.path.join(self.tmp, "bare.git")
        subprocess.run(["git", "init", "-q", "--bare", bare], check=True, capture_output=True)
        with self.assertRaises(lib.GateError):
            lib.validate_settings({"ticket_prefix": "SHOP"}, bare)

    def test_require_workspace_false_returns_none_and_never_derives(self):
        # acs_lib is a package (MAR-522): acs_lib.settings bound this name at import
        # time, so patching the facade would leave the real one in place and
        # this branch would go uncovered while the test still passed.
        with mock.patch.object(lib.settings, "default_state_root",
                               side_effect=AssertionError("must not derive")):
            result = lib.validate_settings({"ticket_prefix": "SHOP"}, self.repo, require_workspace=False)
        self.assertIsNone(result)

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

    def test_rejects_unknown_effort(self):
        with self.assertRaises(lib.GateError) as ctx:
            lib.validate_models({"planner": {"model": "opus", "effort": "turbo"}})
        message = str(ctx.exception)
        self.assertIn("models.planner.effort", message)
        self.assertIn("turbo", message)

    def test_rejects_non_object_overrides(self):
        with self.assertRaises(lib.GateError) as ctx:
            lib.validate_models({"overrides": "nope"})
        self.assertIn("models.overrides must be an object", str(ctx.exception))

    def test_rejects_unknown_override_skill(self):
        """`ship` spawns no subagents of its own, so it is not overridable."""
        with self.assertRaises(lib.GateError) as ctx:
            lib.validate_models({"overrides": {"ship": {"executor": "sonnet"}}})
        self.assertIn("models.overrides.ship: unknown skill", str(ctx.exception))

    def test_rejects_unknown_override_role(self):
        with self.assertRaises(lib.GateError) as ctx:
            lib.validate_models({"overrides": {"code": {"reviewer": "sonnet"}}})
        self.assertIn("models.overrides.code.reviewer: unknown role", str(ctx.exception))

    def test_override_skills_are_derived_from_hooked_skills(self):
        """The allowed-skill set is derived, never hand-listed: a skill added to
        HOOKED_SKILLS is overridable the same day."""
        self.assertEqual(sorted(lib.MODEL_OVERRIDE_SKILLS), sorted(lib.HOOKED_SKILLS))


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
