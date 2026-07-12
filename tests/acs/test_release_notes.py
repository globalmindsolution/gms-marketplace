"""Tests for plugins/acs/hooks/scripts/release_notes.py (MAR-129 spec 01, settings-driven amendment).

Pure stdlib (unittest, tempfile, json, os, subprocess, contextlib, unittest.mock). Drives the
status/draft/bump subcommands both as pure functions and through the CLI (main()), always via a
`--release-config` block (no test constructs a hardcoded-path invocation). `git` is exercised
against real, fully-offline scratch git repos (a working checkout plus a local bare "origin");
the single `gh pr list` seam (release_notes.gh_pr_list) is monkeypatched so no test depends on
`gh` authentication or network.
"""

import contextlib
import importlib
import io
import json
import os
import subprocess
import sys
import unittest
from tempfile import TemporaryDirectory
from unittest import mock

_SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "plugins", "acs", "hooks", "scripts",
)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

release_notes = importlib.import_module("release_notes")


# ---------------------------------------------------------------------------
# Fixture builders — mirror test_metrics_aggregate.py's synthesis style
# ---------------------------------------------------------------------------

MARKETPLACE = {
    "name": "gms-marketplace",
    "version": "0.4.1",
    "plugins": [
        {"name": "acs", "source": {"source": "git-subdir", "ref": "v0.4.1"}},
        {"name": "tabp", "source": {"source": "git-subdir"}},
    ],
}
PLUGIN = {"name": "acs", "version": "0.4.1"}

CHANGELOG_TEMPLATE = (
    "# Changelog\n"
    "\n"
    "## [Unreleased]\n"
    "\n"
    "## [0.4.1] - 2026-07-12\n"
    "\n"
    "### Added\n"
    "\n"
    "- prior entry\n"
)

# This marketplace's committed `release` profile #1 (`.acs/settings.json`) — reproduces today's
# exact three edits + CHANGELOG path (spec 01 "API/data changes").
PROFILE1_CONFIG = {
    "version_locations": [
        {"file": ".claude-plugin/marketplace.json", "pointer": "/version"},
        {"file": "plugins/acs/.claude-plugin/plugin.json", "pointer": "/version"},
    ],
    "extra_refs": [
        {"file": ".claude-plugin/marketplace.json",
         "selector": {"pointer": "/plugins", "match": {"name": "acs"}, "set": "source/ref"},
         "value_format": "v{version}"},
    ],
    "changelog_path": "plugins/acs/CHANGELOG.md",
    "tag_format": "v{version}",
    "base_branch": "main",
    "release_branch_format": "release/v{version}",
    "publish_driver": {"workflow": ".github/workflows/release.yml",
                        "trigger_paths": [".claude-plugin/marketplace.json"]},
}


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


def _write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _read_text(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _run(cmd, cwd, env=None):
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        raise RuntimeError("command failed: %s\n%s" % (cmd, result.stderr))
    return result


def make_repo(root, changelog_text=CHANGELOG_TEMPLATE, marketplace=None, plugin=None,
              init_git=True, with_origin=True, base_branch="main"):
    """Build a scratch consumer-repo checkout: manifests (+ optional CHANGELOG, git, bare origin)."""
    _write_json(os.path.join(root, ".claude-plugin", "marketplace.json"), marketplace or MARKETPLACE)
    _write_json(os.path.join(root, "plugins", "acs", ".claude-plugin", "plugin.json"), plugin or PLUGIN)
    if changelog_text is not None:
        _write_text(os.path.join(root, "plugins", "acs", "CHANGELOG.md"), changelog_text)
    if init_git:
        _run(["git", "init", "-q"], root)
        _run(["git", "config", "user.email", "t@example.com"], root)
        _run(["git", "config", "user.name", "Test"], root)
        _run(["git", "add", "-A"], root)
        _run(["git", "commit", "-q", "-m", "init"], root)
        _run(["git", "branch", "-M", base_branch], root)
        if with_origin:
            bare = root + "-origin.git"
            _run(["git", "init", "-q", "--bare", bare], os.path.dirname(root))
            _run(["git", "remote", "add", "origin", bare], root)
            _run(["git", "push", "-q", "-u", "origin", base_branch], root)
    return root


def tag_repo(root, version, when=None, tag_name=None):
    """Create an annotated tag at HEAD (defaults to `v<version>`); `when` back-dates creatordate."""
    env = os.environ.copy()
    if when:
        env["GIT_COMMITTER_DATE"] = when
        env["GIT_AUTHOR_DATE"] = when
    _run(["git", "tag", "-a", tag_name or ("v%s" % version), "-m", version], root, env=env)


def commit_with_message(root, message):
    _run(["git", "commit", "-q", "--allow-empty", "-m", message], root)


def push_branch(root, branch):
    _run(["git", "push", "-q", "origin", "HEAD:refs/heads/%s" % branch], root)


def write_archive_ticket(workspace, ticket_id, title="A title", parent=None,
                          docs_only=False, ticket_type="story", description="",
                          merged=True, ended_at="2026-07-12T05:00:00Z",
                          updated_at="2099-01-01T00:00:00Z"):
    """Write <workspace>/archive/<ticket_id>/{ticket.json, merge-pr-state.json}.

    updated_at defaults far in the future so any test that accidentally consulted it (R6
    violation) would produce an obviously wrong "excluded"/"included" result.
    """
    tdir = os.path.join(workspace, "archive", ticket_id)
    _write_json(os.path.join(tdir, "ticket.json"), {
        "id": ticket_id, "title": title, "type": ticket_type, "parent": parent,
        "docs_only": docs_only, "description": description, "updated_at": updated_at,
    })
    if merged:
        _write_json(os.path.join(tdir, "merge-pr-state.json"), {
            "states": {"merged": True},
            "runs": [{"ended_at": ended_at}],
        })
    return tdir


def write_create_pr_state(workspace, ticket_id, number, url):
    tdir = os.path.join(workspace, "archive", ticket_id)
    _write_json(os.path.join(tdir, "create-pr-state.json"), {
        "states": {"pr": {"number": number, "url": url}},
    })


def mock_gh(return_value=None):
    return mock.patch.object(release_notes, "gh_pr_list", return_value=return_value)


def run_cli(argv):
    """Invoke release_notes.main(argv) capturing stdout/stderr and the exit code."""
    stdout, stderr = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            release_notes.main(argv)
        code = 0
    except SystemExit as exc:
        code = exc.code if exc.code is not None else 0
    return code, stdout.getvalue(), stderr.getvalue()


def rc_args(config=None):
    """`--release-config <json>` argv pair for a profile (defaults to profile #1)."""
    return ["--release-config", json.dumps(config if config is not None else PROFILE1_CONFIG)]


# ---------------------------------------------------------------------------
# AC-2 — subcommand shape, JSON, exit codes
# ---------------------------------------------------------------------------

class SubcommandShapeTest(unittest.TestCase):
    def test_status_well_formed_exits_0_with_expected_shape(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"))
            with mock_gh(None):
                code, out, err = run_cli(
                    ["status", "--version", "0.4.2", "--repo-root", root] + rc_args())
            self.assertEqual(code, 0)
            self.assertEqual(err, "")
            data = json.loads(out)
            self.assertEqual(set(data.keys()), {
                "manifests_at_target", "changelog_section_dated",
                "release_branch", "open_pr", "tag_exists",
            })
            self.assertIsInstance(data["manifests_at_target"], bool)
            self.assertIsInstance(data["changelog_section_dated"], bool)
            self.assertIsInstance(data["tag_exists"], bool)

    def test_draft_well_formed_exits_0_with_expected_shape(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"))
            workspace = os.path.join(tmp, "ws")
            code, out, err = run_cli([
                "draft", "--version", "0.4.2", "--repo-root", root, "--workspace", workspace,
            ] + rc_args())
            self.assertEqual(code, 0)
            self.assertEqual(err, "")
            data = json.loads(out)
            self.assertEqual(set(data.keys()), {
                "version", "since_tag", "tickets", "unreleased_covered",
                "unreleased_missing", "coverage", "draft_section",
            })
            self.assertIsInstance(data["tickets"], list)
            self.assertIsInstance(data["coverage"], dict)
            self.assertIsInstance(data["draft_section"], str)

    def test_bump_well_formed_exits_0_with_expected_shape(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"))
            workspace = os.path.join(tmp, "ws")
            with mock_gh(None):
                code, out, err = run_cli([
                    "bump", "--version", "0.4.2", "--repo-root", root,
                    "--workspace", workspace, "--dry-run",
                ] + rc_args())
            self.assertEqual(code, 0)
            self.assertEqual(err, "")
            data = json.loads(out)
            self.assertEqual(set(data.keys()), {"ok", "files_changed", "already_at_target"})
            self.assertIsInstance(data["files_changed"], list)
            self.assertIsInstance(data["ok"], bool)
            self.assertIsInstance(data["already_at_target"], bool)

    def test_no_subcommand_exits_2(self):
        code, _out, err = run_cli([])
        self.assertEqual(code, 2)

    def test_unknown_subcommand_exits_2(self):
        code, _out, err = run_cli(["frobnicate"])
        self.assertEqual(code, 2)

    def test_status_missing_version_exits_2(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"))
            code, _out, _err = run_cli(["status", "--repo-root", root] + rc_args())
            self.assertEqual(code, 2)

    def test_draft_missing_workspace_exits_2(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"))
            code, _out, _err = run_cli(
                ["draft", "--version", "0.4.2", "--repo-root", root] + rc_args())
            self.assertEqual(code, 2)

    def test_non_semver_version_exits_2_with_command_error_shape(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"))
            code, out, err = run_cli(
                ["status", "--version", "abc", "--repo-root", root] + rc_args())
            self.assertEqual(code, 2)
            self.assertEqual(out, "")
            payload = json.loads(err)
            self.assertEqual(set(payload.keys()), {"command", "error"})
            self.assertIn("abc", payload["error"])


class MissingOrMalformedFilesTest(unittest.TestCase):
    def test_missing_changelog_exits_2_for_all_three_subcommands(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"), changelog_text=None)
            workspace = os.path.join(tmp, "ws")

            code, _out, err = run_cli(
                ["status", "--version", "0.4.2", "--repo-root", root] + rc_args())
            self.assertEqual(code, 2)
            payload = json.loads(err)
            self.assertIn("CHANGELOG.md", payload["error"])

            code, _out, err = run_cli([
                "draft", "--version", "0.4.2", "--repo-root", root, "--workspace", workspace,
            ] + rc_args())
            self.assertEqual(code, 2)
            self.assertIn("CHANGELOG.md", json.loads(err)["error"])

            code, _out, err = run_cli([
                "bump", "--version", "0.4.2", "--repo-root", root, "--workspace", workspace,
            ] + rc_args())
            self.assertEqual(code, 2)
            self.assertIn("CHANGELOG.md", json.loads(err)["error"])

    def test_missing_manifest_exits_2_for_all_three_subcommands(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"))
            os.remove(os.path.join(root, "plugins", "acs", ".claude-plugin", "plugin.json"))
            workspace = os.path.join(tmp, "ws")

            code, _out, err = run_cli(
                ["status", "--version", "0.4.2", "--repo-root", root] + rc_args())
            self.assertEqual(code, 2)
            self.assertIn("plugin.json", json.loads(err)["error"])

            code, _out, err = run_cli([
                "draft", "--version", "0.4.2", "--repo-root", root, "--workspace", workspace,
            ] + rc_args())
            self.assertEqual(code, 2)

            code, _out, err = run_cli([
                "bump", "--version", "0.4.2", "--repo-root", root, "--workspace", workspace,
            ] + rc_args())
            self.assertEqual(code, 2)

    def test_malformed_json_manifest_exits_2(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"), init_git=False)
            _write_text(
                os.path.join(root, ".claude-plugin", "marketplace.json"), "{not valid json",
            )
            code, _out, err = run_cli(
                ["status", "--version", "0.4.2", "--repo-root", root] + rc_args())
            self.assertEqual(code, 2)
            self.assertIn("marketplace.json", json.loads(err)["error"])


# ---------------------------------------------------------------------------
# AC-2 — malformed/absent/mis-pointed --release-config exit-2 (NEW, regression-test constraint)
# ---------------------------------------------------------------------------

class ReleaseConfigValidationTest(unittest.TestCase):
    def test_missing_release_config_flag_exits_2(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"))
            code, _out, _err = run_cli(["status", "--version", "0.4.2", "--repo-root", root])
            self.assertEqual(code, 2)

    def test_non_json_non_file_release_config_exits_2(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"))
            code, out, err = run_cli([
                "status", "--version", "0.4.2", "--repo-root", root,
                "--release-config", "not json and not a real file path",
            ])
            self.assertEqual(code, 2)
            self.assertEqual(out, "")
            payload = json.loads(err)
            self.assertEqual(set(payload.keys()), {"command", "error"})

    def test_release_config_as_file_path_is_accepted(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"))
            config_path = os.path.join(tmp, "release-config.json")
            _write_json(config_path, PROFILE1_CONFIG)
            with mock_gh(None):
                code, out, _err = run_cli([
                    "status", "--version", "0.4.2", "--repo-root", root,
                    "--release-config", config_path,
                ])
            self.assertEqual(code, 0)
            self.assertIn("manifests_at_target", json.loads(out))

    def test_empty_object_release_config_exits_2_no_write(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"))
            market_path = os.path.join(root, ".claude-plugin", "marketplace.json")
            before = _read_text(market_path)
            code, _out, _err = run_cli([
                "status", "--version", "0.4.2", "--repo-root", root,
                "--release-config", "{}",
            ])
            self.assertEqual(code, 2)
            self.assertEqual(_read_text(market_path), before)

    def test_unresolvable_version_locations_pointer_exits_2_no_write_of_any_target_file(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"))
            workspace = os.path.join(tmp, "ws")
            paths = {
                "market": os.path.join(root, ".claude-plugin", "marketplace.json"),
                "plugin": os.path.join(root, "plugins", "acs", ".claude-plugin", "plugin.json"),
                "changelog": os.path.join(root, "plugins", "acs", "CHANGELOG.md"),
            }
            before = {k: _read_text(p) for k, p in paths.items()}

            bad_config = dict(PROFILE1_CONFIG, version_locations=[
                {"file": ".claude-plugin/marketplace.json", "pointer": "/version"},
                {"file": "plugins/acs/.claude-plugin/plugin.json", "pointer": "/nonexistent"},
            ])
            with mock_gh(None):
                code, _out, err = run_cli([
                    "bump", "--version", "0.4.2", "--repo-root", root, "--workspace", workspace,
                ] + rc_args(bad_config))
            self.assertEqual(code, 2)
            self.assertIn("error", json.loads(err))
            for k, p in paths.items():
                self.assertEqual(_read_text(p), before[k], "%s changed despite unresolvable pointer" % k)

    def test_extra_refs_selector_zero_match_exits_2_no_write(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"))
            workspace = os.path.join(tmp, "ws")
            market_path = os.path.join(root, ".claude-plugin", "marketplace.json")
            before = _read_text(market_path)

            bad_config = dict(PROFILE1_CONFIG, extra_refs=[
                {"file": ".claude-plugin/marketplace.json",
                 "selector": {"pointer": "/plugins", "match": {"name": "nonexistent-plugin"},
                              "set": "source/ref"},
                 "value_format": "v{version}"},
            ])
            with mock_gh(None):
                code, _out, _err = run_cli([
                    "bump", "--version", "0.4.2", "--repo-root", root, "--workspace", workspace,
                ] + rc_args(bad_config))
            self.assertEqual(code, 2)
            self.assertEqual(_read_text(market_path), before)

    def test_escaping_relative_file_path_exits_2(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"))
            bad_config = dict(PROFILE1_CONFIG, version_locations=[
                {"file": "../outside.json", "pointer": "/version"},
            ])
            code, _out, _err = run_cli(
                ["status", "--version", "0.4.2", "--repo-root", root] + rc_args(bad_config))
            self.assertEqual(code, 2)

    def test_escaping_absolute_file_path_exits_2(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"))
            bad_config = dict(PROFILE1_CONFIG, version_locations=[
                {"file": "/etc/passwd", "pointer": "/version"},
            ])
            code, _out, _err = run_cli(
                ["status", "--version", "0.4.2", "--repo-root", root] + rc_args(bad_config))
            self.assertEqual(code, 2)

    def test_unsupported_kind_exits_2(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"))
            bad_config = dict(PROFILE1_CONFIG, version_locations=[
                {"file": ".claude-plugin/marketplace.json", "pointer": "/version", "kind": "regex"},
            ])
            code, _out, _err = run_cli(
                ["status", "--version", "0.4.2", "--repo-root", root] + rc_args(bad_config))
            self.assertEqual(code, 2)


# ---------------------------------------------------------------------------
# NEW — name-match selector correctness (spec 01:464-469)
# ---------------------------------------------------------------------------

class NameMatchSelectorTest(unittest.TestCase):
    def test_target_acs_leaves_tabp_byte_identical(self):
        with TemporaryDirectory() as tmp:
            marketplace = {
                "name": "gms-marketplace",
                "version": "0.4.1",
                "plugins": [
                    {"name": "acs", "source": {"source": "git-subdir", "ref": "v0.4.1"}},
                    {"name": "tabp"},  # no 'source' key at all
                ],
            }
            root = make_repo(os.path.join(tmp, "repo"), marketplace=marketplace)
            workspace = os.path.join(tmp, "ws")

            with mock_gh(None):
                release_notes.bump("0.4.2", root, workspace, PROFILE1_CONFIG, today="2026-07-19")

            market = json.loads(_read_text(os.path.join(root, ".claude-plugin", "marketplace.json")))
            tabp_entry = next(p for p in market["plugins"] if p["name"] == "tabp")
            self.assertEqual(tabp_entry, {"name": "tabp"})

    def test_mismatched_name_target_with_no_source_key_exits_2_no_write(self):
        with TemporaryDirectory() as tmp:
            marketplace = {
                "name": "gms-marketplace",
                "version": "0.4.1",
                "plugins": [
                    {"name": "acs", "source": {"source": "git-subdir", "ref": "v0.4.1"}},
                    {"name": "tabp"},  # no 'source' key -> intermediate-segment-missing
                ],
            }
            root = make_repo(os.path.join(tmp, "repo"), marketplace=marketplace)
            workspace = os.path.join(tmp, "ws")
            market_path = os.path.join(root, ".claude-plugin", "marketplace.json")
            before = _read_text(market_path)

            bad_config = dict(PROFILE1_CONFIG, extra_refs=[
                {"file": ".claude-plugin/marketplace.json",
                 "selector": {"pointer": "/plugins", "match": {"name": "tabp"}, "set": "source/ref"},
                 "value_format": "v{version}"},
            ])
            with mock_gh(None):
                with self.assertRaises(release_notes.ReleaseNotesError):
                    release_notes.bump("0.4.2", root, workspace, bad_config, today="2026-07-19")

            self.assertEqual(_read_text(market_path), before)


# ---------------------------------------------------------------------------
# NEW — package.json-style generality fixture (spec 01:508-518)
# ---------------------------------------------------------------------------

class GeneralityFixtureTest(unittest.TestCase):
    def test_bump_package_json_repo_writes_only_configured_files(self):
        config = {
            "version_locations": [{"file": "package.json", "pointer": "/version"}],
            "extra_refs": [],
            "changelog_path": "CHANGELOG.md",
            "base_branch": "main",
            "tag_format": "v{version}",
            "release_branch_format": "release/v{version}",
        }
        with TemporaryDirectory() as tmp:
            root = os.path.join(tmp, "repo")
            _write_json(os.path.join(root, "package.json"), {"name": "thing", "version": "1.0.0"})
            _write_text(os.path.join(root, "CHANGELOG.md"),
                        "# Changelog\n\n## [Unreleased]\n\n## [1.0.0] - 2026-01-01\n\n"
                        "### Added\n\n- init\n")
            _run(["git", "init", "-q"], root)
            _run(["git", "config", "user.email", "t@example.com"], root)
            _run(["git", "config", "user.name", "Test"], root)
            _run(["git", "add", "-A"], root)
            _run(["git", "commit", "-q", "-m", "init"], root)
            _run(["git", "branch", "-M", "main"], root)

            workspace = os.path.join(tmp, "ws")

            with mock_gh(None):
                result = release_notes.bump("1.1.0", root, workspace, config, today="2026-02-02")

            self.assertTrue(result["ok"])
            self.assertEqual(sorted(result["files_changed"]), sorted(["package.json", "CHANGELOG.md"]))
            pkg = json.loads(_read_text(os.path.join(root, "package.json")))
            self.assertEqual(pkg["version"], "1.1.0")
            changelog = _read_text(os.path.join(root, "CHANGELOG.md"))
            self.assertIn("## [1.1.0] - 2026-02-02", changelog)
            self.assertFalse(os.path.exists(os.path.join(root, ".claude-plugin")))
            self.assertFalse(os.path.exists(os.path.join(root, "plugins")))


# ---------------------------------------------------------------------------
# AC-2 — bump atomicity, idempotency, dry-run
# ---------------------------------------------------------------------------

class BumpAtomicityTest(unittest.TestCase):
    def test_nothing_to_release_is_exit_0_no_write(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(
                os.path.join(tmp, "repo"),
                changelog_text=(
                    "# Changelog\n\n## [Unreleased]\n\n## [0.4.2] - 2026-07-19\n\n"
                    "### Added\n\n- already released\n"
                ),
                marketplace={**MARKETPLACE, "version": "0.4.2",
                             "plugins": [{"name": "acs",
                                          "source": {"source": "git-subdir", "ref": "v0.4.2"}},
                                         {"name": "tabp", "source": {"source": "git-subdir"}}]},
                plugin={"name": "acs", "version": "0.4.2"},
            )
            workspace = os.path.join(tmp, "ws")
            market_path = os.path.join(root, ".claude-plugin", "marketplace.json")
            plugin_path = os.path.join(root, "plugins", "acs", ".claude-plugin", "plugin.json")
            changelog_path = os.path.join(root, "plugins", "acs", "CHANGELOG.md")
            before = {p: _read_text(p) for p in (market_path, plugin_path, changelog_path)}
            before_mtimes = {p: os.path.getmtime(p) for p in before}

            with mock_gh(None):
                result = release_notes.bump("0.4.2", root, workspace, PROFILE1_CONFIG)

            self.assertEqual(result, {"ok": True, "files_changed": [], "already_at_target": True})
            for path, text in before.items():
                self.assertEqual(_read_text(path), text)
                self.assertEqual(os.path.getmtime(path), before_mtimes[path])

    def test_atomicity_crash_mid_write_leaves_original_intact(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"))
            workspace = os.path.join(tmp, "ws")
            market_path = os.path.join(root, ".claude-plugin", "marketplace.json")
            original = _read_text(market_path)

            with mock_gh(None), mock.patch("os.rename", side_effect=OSError("simulated crash")):
                with self.assertRaises(release_notes.ReleaseNotesError):
                    release_notes.bump("0.4.2", root, workspace, PROFILE1_CONFIG)

            self.assertEqual(_read_text(market_path), original)

    def test_real_bump_sets_both_versions_ref_and_leaves_tabp_untouched(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"))
            workspace = os.path.join(tmp, "ws")
            write_archive_ticket(workspace, "MAR-1", title="Add thing")

            with mock_gh(None):
                result = release_notes.bump(
                    "0.4.2", root, workspace, PROFILE1_CONFIG, today="2026-07-19")

            self.assertTrue(result["ok"])
            self.assertFalse(result["already_at_target"])
            self.assertEqual(sorted(result["files_changed"]), sorted([
                ".claude-plugin/marketplace.json",
                "plugins/acs/.claude-plugin/plugin.json",
                "plugins/acs/CHANGELOG.md",
            ]))

            market = json.loads(_read_text(os.path.join(root, ".claude-plugin", "marketplace.json")))
            plugin = json.loads(_read_text(
                os.path.join(root, "plugins", "acs", ".claude-plugin", "plugin.json")))
            self.assertEqual(market["version"], "0.4.2")
            self.assertEqual(plugin["version"], "0.4.2")
            acs_entry = next(p for p in market["plugins"] if p["name"] == "acs")
            self.assertEqual(acs_entry["source"]["ref"], "v0.4.2")
            tabp_entry = next(p for p in market["plugins"] if p["name"] == "tabp")
            self.assertNotIn("ref", tabp_entry["source"])

    def test_dry_run_reports_files_changed_without_writing(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"))
            workspace = os.path.join(tmp, "ws")
            market_path = os.path.join(root, ".claude-plugin", "marketplace.json")
            before = _read_text(market_path)

            with mock_gh(None):
                result = release_notes.bump(
                    "0.4.2", root, workspace, PROFILE1_CONFIG, dry_run=True)

            self.assertTrue(result["files_changed"])
            self.assertFalse(result["already_at_target"])
            self.assertEqual(_read_text(market_path), before)


# ---------------------------------------------------------------------------
# R-A2 (REQUIRED) — byte-equal profile-#1 regression (design.md:1291-1298)
# ---------------------------------------------------------------------------

class ProfileOneByteEqualRegressionTest(unittest.TestCase):
    """The settings-driven bump must reproduce the shipped hardcoded bump's exact byte output for
    this marketplace's `release` profile #1 — same JSON serialization convention (indent=2,
    ensure_ascii=False), same source.ref selector result, same CHANGELOG insertion point."""

    def test_bump_profile1_byte_equal_to_golden_baseline(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"))
            workspace = os.path.join(tmp, "ws")
            write_archive_ticket(workspace, "MAR-1", title="Add a widget")

            with mock_gh(None):
                release_notes.bump("0.4.2", root, workspace, PROFILE1_CONFIG, today="2026-07-19")

            market_path = os.path.join(root, ".claude-plugin", "marketplace.json")
            plugin_path = os.path.join(root, "plugins", "acs", ".claude-plugin", "plugin.json")
            changelog_path = os.path.join(root, "plugins", "acs", "CHANGELOG.md")

            golden_market = {
                "name": "gms-marketplace",
                "version": "0.4.2",
                "plugins": [
                    {"name": "acs", "source": {"source": "git-subdir", "ref": "v0.4.2"}},
                    {"name": "tabp", "source": {"source": "git-subdir"}},
                ],
            }
            golden_plugin = {"name": "acs", "version": "0.4.2"}
            golden_market_text = json.dumps(golden_market, indent=2, ensure_ascii=False) + "\n"
            golden_plugin_text = json.dumps(golden_plugin, indent=2, ensure_ascii=False) + "\n"
            golden_changelog_text = (
                "# Changelog\n"
                "\n"
                "## [Unreleased]\n"
                "\n"
                "## [0.4.2] - 2026-07-19\n"
                "\n"
                "### Added\n"
                "\n"
                "- MAR-1: Add a widget\n"
                "\n"
                "## [0.4.1] - 2026-07-12\n"
                "\n"
                "### Added\n"
                "\n"
                "- prior entry\n"
            )

            self.assertEqual(_read_text(market_path), golden_market_text)
            self.assertEqual(_read_text(plugin_path), golden_plugin_text)
            self.assertEqual(_read_text(changelog_path), golden_changelog_text)


# ---------------------------------------------------------------------------
# AC-3 — draft authority, coverage, never-empty
# ---------------------------------------------------------------------------

class DraftAuthorityTest(unittest.TestCase):
    def test_coverage_arithmetic_and_grouping_with_non_default_base_branch(self):
        # base_branch = "trunk" (not "main") — proves the since-tag boundary respects the config
        # field rather than a hardcoded "main" (spec 01:487-489).
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"),
                              changelog_text=(
                                  "# Changelog\n\n## [Unreleased]\n\n"
                                  "MAR-1 and MAR-2 done.\n\n## [0.4.1] - 2026-07-12\n\n"
                                  "### Added\n\n- prior\n"
                              ), base_branch="trunk")
            tag_repo(root, "0.4.1", when="2026-07-10T00:00:00+00:00")
            workspace = os.path.join(tmp, "ws")
            write_archive_ticket(workspace, "MAR-1", title="Epic child one", parent="MAR-100",
                                  ended_at="2026-07-11T00:00:00Z")
            write_archive_ticket(workspace, "MAR-2", title="Epic child two", parent="MAR-100",
                                  ended_at="2026-07-11T01:00:00Z")
            write_archive_ticket(workspace, "MAR-3", title="Standalone ticket", parent=None,
                                  ended_at="2026-07-11T02:00:00Z")
            write_archive_ticket(workspace, "MAR-100", title="Parent epic", ticket_type="epic",
                                  merged=False)

            config = dict(PROFILE1_CONFIG, base_branch="trunk")
            result = release_notes.build_draft("0.4.2", root, workspace, config, today="2026-07-19")

            self.assertEqual(result["coverage"], {"merged": 3, "covered": 2, "missing": 1})
            self.assertEqual(sorted(result["unreleased_covered"]), ["MAR-1", "MAR-2"])
            self.assertEqual(result["unreleased_missing"], ["MAR-3"])
            self.assertIn("Epic child one", result["draft_section"])
            self.assertIn("Epic child two", result["draft_section"])
            self.assertIn("Standalone ticket", result["draft_section"])
            self.assertIn("Parent epic", result["draft_section"])

    def test_never_empty_when_at_least_one_merged(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"))
            workspace = os.path.join(tmp, "ws")
            write_archive_ticket(workspace, "MAR-9", title="Add a widget")

            result = release_notes.build_draft(
                "0.4.2", root, workspace, PROFILE1_CONFIG, today="2026-07-19")

            self.assertGreaterEqual(result["coverage"]["merged"], 1)
            self.assertRegex(result["draft_section"], r"### \w+\n\n- ")

    def test_nothing_to_release_is_bare_dated_header(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"))
            workspace = os.path.join(tmp, "ws")

            result = release_notes.build_draft(
                "0.4.2", root, workspace, PROFILE1_CONFIG, today="2026-07-19")

            self.assertEqual(result["coverage"], {"merged": 0, "covered": 0, "missing": 0})
            self.assertEqual(result["draft_section"], "## [0.4.2] - 2026-07-19\n")

    def test_bootstrap_since_tag_null_includes_every_merged_ticket(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"))  # no tags at all
            workspace = os.path.join(tmp, "ws")
            write_archive_ticket(workspace, "MAR-1", title="Old ticket",
                                  ended_at="2000-01-01T00:00:00Z")

            result = release_notes.build_draft(
                "0.4.2", root, workspace, PROFILE1_CONFIG, today="2026-07-19")

            self.assertIsNone(result["since_tag"])
            self.assertEqual(result["coverage"]["merged"], 1)

    def test_pr_ref_resolution_primary_fallback_and_neither(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"))
            workspace = os.path.join(tmp, "ws")
            write_archive_ticket(workspace, "MAR-1", title="Has create-pr state")
            write_create_pr_state(workspace, "MAR-1", 250, "https://example/pull/250")

            write_archive_ticket(workspace, "MAR-2", title="Falls back to git log")
            commit_with_message(root, "MAR-2 add thing (#99)")

            write_archive_ticket(workspace, "MAR-3", title="Neither source resolves")

            result = release_notes.build_draft(
                "0.4.2", root, workspace, PROFILE1_CONFIG, today="2026-07-19")
            by_id = {t["id"]: t for t in result["tickets"]}

            self.assertEqual(by_id["MAR-1"]["pr_number"], 250)
            self.assertEqual(by_id["MAR-1"]["pr_url"], "https://example/pull/250")
            self.assertEqual(by_id["MAR-2"]["pr_number"], 99)
            self.assertIsNone(by_id["MAR-3"]["pr_number"])
            self.assertIsNone(by_id["MAR-3"]["pr_url"])
            self.assertEqual(result["coverage"]["merged"], 3)

    def test_categorization_fix_docs_only_and_default(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"))
            workspace = os.path.join(tmp, "ws")
            write_archive_ticket(workspace, "MAR-1", title="Fix flaky test")
            write_archive_ticket(workspace, "MAR-2", title="Refresh docs", docs_only=True)
            write_archive_ticket(workspace, "MAR-3", title="Add a widget")

            result = release_notes.build_draft(
                "0.4.2", root, workspace, PROFILE1_CONFIG, today="2026-07-19")
            by_id = {t["id"]: t for t in result["tickets"]}

            self.assertEqual(by_id["MAR-1"]["category"], "Fixed")
            self.assertEqual(by_id["MAR-2"]["category"], "Changed")
            self.assertEqual(by_id["MAR-3"]["category"], "Added")
            self.assertIn("### Fixed", result["draft_section"])
            self.assertIn("### Changed", result["draft_section"])
            self.assertIn("### Added", result["draft_section"])

    def test_category_with_zero_tickets_emits_no_heading(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"))
            workspace = os.path.join(tmp, "ws")
            write_archive_ticket(workspace, "MAR-1", title="Add a widget")

            result = release_notes.build_draft(
                "0.4.2", root, workspace, PROFILE1_CONFIG, today="2026-07-19")

            self.assertIn("### Added", result["draft_section"])
            self.assertNotIn("### Fixed", result["draft_section"])
            self.assertNotIn("### Changed", result["draft_section"])

    def test_merge_time_boundary_excludes_before_tag_includes_after(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"))
            tag_repo(root, "0.4.1", when="2026-07-01T00:00:00+00:00")
            workspace = os.path.join(tmp, "ws")
            write_archive_ticket(workspace, "MAR-1", title="Before the tag",
                                  ended_at="2026-06-30T00:00:00Z")
            write_archive_ticket(workspace, "MAR-2", title="After the tag",
                                  ended_at="2026-07-02T00:00:00Z")

            result = release_notes.build_draft(
                "0.4.2", root, workspace, PROFILE1_CONFIG, today="2026-07-19")
            ids = {t["id"] for t in result["tickets"]}

            self.assertNotIn("MAR-1", ids)
            self.assertIn("MAR-2", ids)

    def test_merge_time_boundary_ignores_ticket_updated_at(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"))
            tag_repo(root, "0.4.1", when="2026-07-01T00:00:00+00:00")
            workspace = os.path.join(tmp, "ws")
            # Late updated_at, EARLY merge ended_at -> must be excluded (R6: never updated_at).
            write_archive_ticket(workspace, "MAR-1", title="Late updated_at, early merge",
                                  ended_at="2026-06-30T00:00:00Z",
                                  updated_at="2026-12-31T00:00:00Z")

            result = release_notes.build_draft(
                "0.4.2", root, workspace, PROFILE1_CONFIG, today="2026-07-19")

            self.assertEqual(result["coverage"]["merged"], 0)

    def test_word_boundary_safety_mar_1_not_matched_by_mar_12(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(
                os.path.join(tmp, "repo"),
                changelog_text=(
                    "# Changelog\n\n## [Unreleased]\n\nMAR-12 done.\n\n"
                    "## [0.4.1] - 2026-07-12\n\n### Added\n\n- prior\n"
                ),
            )
            workspace = os.path.join(tmp, "ws")
            write_archive_ticket(workspace, "MAR-1", title="One")
            write_archive_ticket(workspace, "MAR-12", title="Twelve")

            result = release_notes.build_draft(
                "0.4.2", root, workspace, PROFILE1_CONFIG, today="2026-07-19")

            self.assertIn("MAR-1", result["unreleased_missing"])
            self.assertIn("MAR-12", result["unreleased_covered"])


# ---------------------------------------------------------------------------
# AC-4 — CHANGELOG structural round-trip
# ---------------------------------------------------------------------------

class ChangelogStructureTest(unittest.TestCase):
    def test_structural_round_trip_after_bump(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"))
            workspace = os.path.join(tmp, "ws")
            write_archive_ticket(workspace, "MAR-1", title="Add a widget")

            with mock_gh(None):
                release_notes.bump("0.4.2", root, workspace, PROFILE1_CONFIG, today="2026-07-19")

            text = _read_text(os.path.join(root, "plugins", "acs", "CHANGELOG.md"))
            unreleased_idx = text.index("## [Unreleased]")
            new_idx = text.index("## [0.4.2] - 2026-07-19")
            prior_idx = text.index("## [0.4.1] - 2026-07-12")
            self.assertLess(unreleased_idx, new_idx)
            self.assertLess(new_idx, prior_idx)
            # Immediately below Unreleased (only whitespace between).
            between = text[unreleased_idx + len("## [Unreleased]"):new_idx]
            self.assertEqual(between.strip(), "")
            self.assertIn("- prior entry", text)  # prior section preserved verbatim

    def test_preexisting_unreleased_prose_not_merged_forward(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(
                os.path.join(tmp, "repo"),
                changelog_text=(
                    "# Changelog\n\n## [Unreleased]\n\nSome pending notes.\n\n"
                    "## [0.4.1] - 2026-07-12\n\n### Added\n\n- prior entry\n"
                ),
            )
            workspace = os.path.join(tmp, "ws")
            write_archive_ticket(workspace, "MAR-1", title="Add a widget")

            with mock_gh(None):
                release_notes.bump("0.4.2", root, workspace, PROFILE1_CONFIG, today="2026-07-19")

            text = _read_text(os.path.join(root, "plugins", "acs", "CHANGELOG.md"))
            self.assertNotIn("Some pending notes.", text)
            self.assertIn("Add a widget", text)


# ---------------------------------------------------------------------------
# AC-6 — the four status signals, independently + combined
# ---------------------------------------------------------------------------

class StatusSignalsTest(unittest.TestCase):
    def test_manifests_at_target_requires_every_version_locations_entry(self):
        # 3-entry version_locations fixture with only 2 bumped -> False (generalizes the held
        # 2-file case; spec 01:524-526).
        with TemporaryDirectory() as tmp:
            root = make_repo(
                os.path.join(tmp, "repo"),
                marketplace={**MARKETPLACE, "version": "0.4.2"},
            )  # plugin.json still at 0.4.1
            with mock_gh(None):
                result = release_notes.compute_status("0.4.2", root, PROFILE1_CONFIG)
            self.assertFalse(result["manifests_at_target"])

            third_path = os.path.join(root, "extra-version.json")
            _write_json(third_path, {"version": "0.4.1"})
            config3 = dict(PROFILE1_CONFIG, version_locations=[
                {"file": ".claude-plugin/marketplace.json", "pointer": "/version"},
                {"file": "plugins/acs/.claude-plugin/plugin.json", "pointer": "/version"},
                {"file": "extra-version.json", "pointer": "/version"},
            ])
            with mock_gh(None):
                result3 = release_notes.compute_status("0.4.2", root, config3)
            self.assertFalse(result3["manifests_at_target"])

    def test_changelog_section_dated_requires_a_date(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(
                os.path.join(tmp, "repo"),
                changelog_text="# Changelog\n\n## [Unreleased]\n\n## [0.4.2]\n\nno date\n",
            )
            with mock_gh(None):
                result = release_notes.compute_status("0.4.2", root, PROFILE1_CONFIG)
            self.assertFalse(result["changelog_section_dated"])

            root2 = make_repo(
                os.path.join(tmp, "repo2"),
                changelog_text="# Changelog\n\n## [Unreleased]\n\n## [0.4.2] - 2026-07-19\n\nbody\n",
            )
            with mock_gh(None):
                result2 = release_notes.compute_status("0.4.2", root2, PROFILE1_CONFIG)
            self.assertTrue(result2["changelog_section_dated"])

    def test_release_branch_and_open_pr(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"))
            push_branch(root, "release/v0.4.2")

            with mock_gh({"number": 7, "url": "https://example/pull/7"}):
                result = release_notes.compute_status("0.4.2", root, PROFILE1_CONFIG)
            self.assertEqual(result["release_branch"], "release/v0.4.2")
            self.assertEqual(result["open_pr"], {"number": 7, "url": "https://example/pull/7"})

            root2 = make_repo(os.path.join(tmp, "repo2"))
            with mock_gh(None):
                result2 = release_notes.compute_status("0.4.2", root2, PROFILE1_CONFIG)
            self.assertIsNone(result2["release_branch"])
            self.assertIsNone(result2["open_pr"])

    def test_tag_exists(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"))
            tag_repo(root, "0.4.2")
            with mock_gh(None):
                result = release_notes.compute_status("0.4.2", root, PROFILE1_CONFIG)
            self.assertTrue(result["tag_exists"])

            root2 = make_repo(os.path.join(tmp, "repo2"))
            with mock_gh(None):
                result2 = release_notes.compute_status("0.4.2", root2, PROFILE1_CONFIG)
            self.assertFalse(result2["tag_exists"])

    def test_combined_idempotency_scenario(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(
                os.path.join(tmp, "repo"),
                changelog_text=(
                    "# Changelog\n\n## [Unreleased]\n\n## [0.4.2] - 2026-07-19\n\n"
                    "### Added\n\n- x\n"
                ),
                marketplace={**MARKETPLACE, "version": "0.4.2",
                             "plugins": [{"name": "acs",
                                          "source": {"source": "git-subdir", "ref": "v0.4.2"}},
                                         {"name": "tabp", "source": {"source": "git-subdir"}}]},
                plugin={"name": "acs", "version": "0.4.2"},
            )
            push_branch(root, "release/v0.4.2")

            with mock_gh({"number": 9, "url": "https://example/pull/9"}):
                result = release_notes.compute_status("0.4.2", root, PROFILE1_CONFIG)

            self.assertTrue(result["manifests_at_target"])
            self.assertTrue(result["changelog_section_dated"])
            self.assertEqual(result["release_branch"], "release/v0.4.2")
            self.assertEqual(result["open_pr"]["number"], 9)


class NonDefaultFormatsTest(unittest.TestCase):
    """AC-6 (spec 01:529-534): tag_format/release_branch_format render the actual probed
    strings — not the hardcoded v%s/release/v%s."""

    def test_status_signals_use_rendered_non_default_formats(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"))
            config = dict(PROFILE1_CONFIG, tag_format="release-{version}",
                          release_branch_format="cut/{version}")

            push_branch(root, "cut/0.4.2")
            tag_repo(root, "0.4.2", tag_name="release-0.4.2")

            with mock_gh({"number": 5, "url": "https://example/pull/5"}):
                result = release_notes.compute_status("0.4.2", root, config)

            self.assertEqual(result["release_branch"], "cut/0.4.2")
            self.assertTrue(result["tag_exists"])
            self.assertEqual(result["open_pr"], {"number": 5, "url": "https://example/pull/5"})

            # Sanity: the DEFAULT-format probe does NOT find these non-default refs.
            with mock_gh(None):
                default_result = release_notes.compute_status("0.4.2", root, PROFILE1_CONFIG)
            self.assertIsNone(default_result["release_branch"])
            self.assertFalse(default_result["tag_exists"])


# ---------------------------------------------------------------------------
# Regression (iter 2) — bump must preserve non-ASCII manifest content verbatim
# ---------------------------------------------------------------------------

class NonAsciiPreservationTest(unittest.TestCase):
    """The real marketplace.json has literal em-dashes (U+2014) in the acs AND tabp
    descriptions; a bump must NOT escape them to \\u2014 (which would churn the acs
    line and MUTATE the 'left untouched' tabp block into the human-reviewed PR)."""

    def test_bump_preserves_non_ascii_and_diff_is_minimal(self):
        import difflib
        with TemporaryDirectory() as tmp:
            root = make_repo(os.path.join(tmp, "repo"))
            # Overwrite marketplace.json with literal em-dashes in BOTH descriptions,
            # exactly as the real committed file stores them (UTF-8, not \uXXXX-escaped).
            market = {
                "name": "gms-marketplace",
                "version": "0.4.1",
                "plugins": [
                    {"name": "acs",
                     "source": {"source": "git-subdir", "ref": "v0.4.1"},
                     "description": "Autonomous Coding Skills — an agentic workflow — PR, merge."},
                    {"name": "tabp",
                     "source": {"source": "git-subdir"},
                     "description": "TABP toolkit — CV screening — fairness guardrails."},
                ],
            }
            market_path = os.path.join(root, ".claude-plugin", "marketplace.json")
            _write_text(market_path, json.dumps(market, indent=2, ensure_ascii=False) + "\n")
            before = _read_text(market_path)
            # Sanity: the fixture on disk carries literal em-dashes, not escapes.
            self.assertIn("—", before)
            self.assertNotIn("\\u2014", before)

            workspace = os.path.join(tmp, "ws")
            write_archive_ticket(workspace, "MAR-1", title="Add a widget")

            with mock_gh(None):
                release_notes.bump("0.4.2", root, workspace, PROFILE1_CONFIG, today="2026-07-19")

            after = _read_text(market_path)

            # (a) acs description em-dashes byte-preserved, never escaped to —.
            self.assertIn("Autonomous Coding Skills — an agentic workflow — PR, merge.", after)
            self.assertNotIn("\\u2014", after)

            # (b) the tabp description line is byte-identical to before the bump.
            self.assertIn("TABP toolkit — CV screening — fairness guardrails.", after)

            # (c) the ONLY changed lines vs the pre-bump file are the version + acs source.ref.
            diff = [ln for ln in difflib.ndiff(before.splitlines(), after.splitlines())
                    if ln.startswith("+ ") or ln.startswith("- ")]
            self.assertTrue(diff, "bump made no change to marketplace.json")
            for ln in diff:
                content = ln[2:]
                self.assertTrue('"version"' in content or '"ref"' in content,
                                "unexpected description/other churn: %r" % content)


if __name__ == "__main__":
    unittest.main()
