#!/usr/bin/env python3
"""Reproducible stdlib-`trace` line-coverage harness for release_notes.py (MAR-129 spec 01,
settings-driven amendment).

The repo is Python 3.9+ stdlib-only (no pip) — the pip `coverage` package is NOT installed — so
coverage is measured with the stdlib `trace` module, mirroring tests/acs/cov_codeowners.py. This
harness drives a superset of test_release_notes.py's fixture matrix (config loading both modes,
validation failures, the JSON-pointer resolver + name-match selector, the two-phase resolve-then-
write bump, non-default tag/branch formats, plus the real gh_pr_list body via a subprocess.run
shim) under trace.Trace(count=1, trace=0), then reports:

    executed executable lines / total executable lines -> percentage  (gate: >= 90%)

Run:  python3 tests/acs/cov_release_notes.py  (exit 0 iff coverage >= GATE)
"""

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import trace

GATE = 90.0

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(_TESTS_DIR))
_SCRIPTS_DIR = os.path.join(_REPO_ROOT, "plugins", "acs", "hooks", "scripts")
_TARGET = os.path.join(_SCRIPTS_DIR, "release_notes.py")

if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)


def _load_target_fresh():
    """Import release_notes.py from source as a fresh module object (inside the tracer)."""
    sys.modules.pop("release_notes_cov_target", None)
    spec = importlib.util.spec_from_file_location("release_notes_cov_target", _TARGET)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["release_notes_cov_target"] = mod
    spec.loader.exec_module(mod)
    return mod


def _run_main(mod, argv):
    """Drive mod.main() in-process (sets sys.argv, catches its own sys.exit)."""
    real_argv = sys.argv[:]
    real_stdout, real_stderr = sys.stdout, sys.stderr
    sys.argv = ["release_notes.py"] + argv
    sys.stdout, sys.stderr = io.StringIO(), io.StringIO()
    try:
        try:
            mod.main()
            code = 0
        except SystemExit as exc:
            code = exc.code if exc.code is not None else 0
        out, err = sys.stdout.getvalue(), sys.stderr.getvalue()
    finally:
        sys.argv = real_argv
        sys.stdout, sys.stderr = real_stdout, real_stderr
    return code, out, err


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _write_json(path, data):
    _write(path, json.dumps(data, indent=2) + "\n")


def _read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _run(cmd, cwd, env=None):
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        raise RuntimeError("command failed: %s\n%s" % (cmd, result.stderr))
    return result


_MARKETPLACE = {
    "name": "gms-marketplace",
    "version": "0.4.1",
    "plugins": [
        {"name": "acs", "source": {"source": "git-subdir", "ref": "v0.4.1"}},
        {"name": "tabp", "source": {"source": "git-subdir"}},
    ],
}
_PLUGIN = {"name": "acs", "version": "0.4.1"}
_CHANGELOG = (
    "# Changelog\n\n## [Unreleased]\n\n## [0.4.1] - 2026-07-12\n\n### Added\n\n- prior entry\n"
)

_PROFILE1_CONFIG = {
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


def _make_repo(root, changelog_text=_CHANGELOG, marketplace=None, plugin=None, with_origin=True,
               base_branch="main"):
    _write_json(os.path.join(root, ".claude-plugin", "marketplace.json"), marketplace or _MARKETPLACE)
    _write_json(os.path.join(root, "plugins", "acs", ".claude-plugin", "plugin.json"),
                plugin or _PLUGIN)
    if changelog_text is not None:
        _write(os.path.join(root, "plugins", "acs", "CHANGELOG.md"), changelog_text)
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


def _tag_repo(root, version, when=None, tag_name=None):
    env = os.environ.copy()
    if when:
        env["GIT_COMMITTER_DATE"] = when
        env["GIT_AUTHOR_DATE"] = when
    _run(["git", "tag", "-a", tag_name or ("v%s" % version), "-m", version], root, env=env)


def _write_archive_ticket(workspace, ticket_id, title="A title", parent=None, docs_only=False,
                           description="", merged=True, ended_at="2026-07-12T05:00:00Z",
                           updated_at="2099-01-01T00:00:00Z"):
    tdir = os.path.join(workspace, "archive", ticket_id)
    _write_json(os.path.join(tdir, "ticket.json"), {
        "id": ticket_id, "title": title, "type": "story", "parent": parent,
        "docs_only": docs_only, "description": description, "updated_at": updated_at,
    })
    if merged:
        _write_json(os.path.join(tdir, "merge-pr-state.json"),
                    {"states": {"merged": True}, "runs": [{"ended_at": ended_at}]})
    return tdir


def _write_create_pr_state(workspace, ticket_id, number, url):
    _write_json(os.path.join(workspace, "archive", ticket_id, "create-pr-state.json"),
                {"states": {"pr": {"number": number, "url": url}}})


class _FakeResult:
    def __init__(self, returncode, stdout):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = ""


def _drive():
    """Fresh-import release_notes.py and exercise every branch — all inside the traced call."""
    mod = _load_target_fresh()
    tmp = tempfile.mkdtemp(prefix="acs-cov-release-notes-")
    _real_gh_pr_list = mod.gh_pr_list
    try:
        mod.gh_pr_list = lambda repo_root, rendered_branch: None  # default: no gh auth needed

        # --- status: well-formed, all-false signals ---
        root1 = _make_repo(os.path.join(tmp, "repo1"))
        result = mod.compute_status("0.4.2", root1, _PROFILE1_CONFIG)
        assert result["manifests_at_target"] is False
        assert result["tag_exists"] is False
        assert result["release_branch"] is None
        assert result["open_pr"] is None

        # --- status: manifests_at_target true only when EVERY version_locations entry matches ---
        root2 = _make_repo(os.path.join(tmp, "repo2"),
                            marketplace={**_MARKETPLACE, "version": "0.4.2"})
        assert mod.compute_status("0.4.2", root2, _PROFILE1_CONFIG)["manifests_at_target"] is False
        _write_json(os.path.join(root2, "extra-version.json"), {"version": "0.4.1"})
        config3 = dict(_PROFILE1_CONFIG, version_locations=[
            {"file": ".claude-plugin/marketplace.json", "pointer": "/version"},
            {"file": "plugins/acs/.claude-plugin/plugin.json", "pointer": "/version"},
            {"file": "extra-version.json", "pointer": "/version"},
        ])
        assert mod.compute_status("0.4.2", root2, config3)["manifests_at_target"] is False

        # --- status: changelog_section_dated true/false ---
        root3 = _make_repo(os.path.join(tmp, "repo3"),
                            changelog_text="# Changelog\n\n## [Unreleased]\n\n## [0.4.2]\n\nx\n")
        assert mod.compute_status("0.4.2", root3, _PROFILE1_CONFIG)["changelog_section_dated"] is False
        root3b = _make_repo(os.path.join(tmp, "repo3b"),
                             changelog_text="# Changelog\n\n## [Unreleased]\n\n"
                                            "## [0.4.2] - 2026-07-19\n\nx\n")
        assert mod.compute_status("0.4.2", root3b, _PROFILE1_CONFIG)["changelog_section_dated"] is True

        # --- status: release_branch + tag_exists true paths ---
        root4 = _make_repo(os.path.join(tmp, "repo4"))
        _run(["git", "push", "-q", "origin", "HEAD:refs/heads/release/v0.4.2"], root4)
        _tag_repo(root4, "0.4.2")
        mod.gh_pr_list = lambda repo_root, rendered_branch: {"number": 7, "url": "https://x/7"}
        result4 = mod.compute_status("0.4.2", root4, _PROFILE1_CONFIG)
        assert result4["release_branch"] == "release/v0.4.2"
        assert result4["open_pr"] == {"number": 7, "url": "https://x/7"}
        assert result4["tag_exists"] is True
        mod.gh_pr_list = lambda repo_root, rendered_branch: None

        # --- status: non-default tag_format/release_branch_format render the probed strings ---
        root4b = _make_repo(os.path.join(tmp, "repo4b"))
        _run(["git", "push", "-q", "origin", "HEAD:refs/heads/cut/0.4.2"], root4b)
        _tag_repo(root4b, "0.4.2", tag_name="release-0.4.2")
        nondefault_config = dict(_PROFILE1_CONFIG, tag_format="release-{version}",
                                  release_branch_format="cut/{version}")
        mod.gh_pr_list = lambda repo_root, rendered_branch: {"number": 5, "url": "https://x/5"}
        result4b = mod.compute_status("0.4.2", root4b, nondefault_config)
        assert result4b["release_branch"] == "cut/0.4.2"
        assert result4b["tag_exists"] is True
        mod.gh_pr_list = lambda repo_root, rendered_branch: None
        default_result4b = mod.compute_status("0.4.2", root4b, _PROFILE1_CONFIG)
        assert default_result4b["release_branch"] is None
        assert default_result4b["tag_exists"] is False

        # --- CLI: well-formed status/draft/bump(--dry-run) exit 0, incl. --release-config as a
        #     file path (the second config-load attempt) ---
        ws_empty = os.path.join(tmp, "ws_empty")
        config_file = os.path.join(tmp, "release-config.json")
        _write_json(config_file, _PROFILE1_CONFIG)
        code, out, _err = _run_main(mod, [
            "status", "--version", "0.4.2", "--repo-root", root1, "--release-config", config_file,
        ])
        assert code == 0
        assert set(json.loads(out).keys()) == {
            "manifests_at_target", "changelog_section_dated", "release_branch", "open_pr", "tag_exists",
        }
        code, out, _err = _run_main(mod, [
            "draft", "--version", "0.4.2", "--repo-root", root1, "--workspace", ws_empty,
            "--release-config", json.dumps(_PROFILE1_CONFIG),
        ])
        assert code == 0
        code, out, _err = _run_main(mod, [
            "bump", "--version", "0.4.2", "--repo-root", root1, "--workspace", ws_empty, "--dry-run",
            "--release-config", json.dumps(_PROFILE1_CONFIG),
        ])
        assert code == 0
        assert json.loads(out)["already_at_target"] is False

        # --- CLI malformed invocations: exit 2 ---
        code, _out, _err = _run_main(mod, [])
        assert code == 2
        code, _out, _err = _run_main(mod, ["frobnicate"])
        assert code == 2
        code, _out, _err = _run_main(mod, [
            "status", "--repo-root", root1, "--release-config", json.dumps(_PROFILE1_CONFIG),
        ])
        assert code == 2
        code, _out, err = _run_main(mod, [
            "status", "--version", "abc", "--repo-root", root1,
            "--release-config", json.dumps(_PROFILE1_CONFIG),
        ])
        assert code == 2
        payload = json.loads(err)
        assert set(payload.keys()) == {"command", "error"}

        # --- CLI --release-config: missing flag / non-JSON-non-file / malformed shapes -> exit 2 ---
        code, _out, _err = _run_main(mod, ["status", "--version", "0.4.2", "--repo-root", root1])
        assert code == 2
        code, _out, err = _run_main(mod, [
            "status", "--version", "0.4.2", "--repo-root", root1,
            "--release-config", "neither json nor a file",
        ])
        assert code == 2
        assert "error" in json.loads(err)
        code, _out, _err = _run_main(mod, [
            "status", "--version", "0.4.2", "--repo-root", root1, "--release-config", "{}",
        ])
        assert code == 2
        code, _out, _err = _run_main(mod, [
            "status", "--version", "0.4.2", "--repo-root", root1,
            "--release-config", json.dumps([1, 2, 3]),
        ])
        assert code == 2
        bad_file = os.path.join(tmp, "bad-release-config.json")
        _write(bad_file, "{not valid json")
        code, _out, _err = _run_main(mod, [
            "status", "--version", "0.4.2", "--repo-root", root1, "--release-config", bad_file,
        ])
        assert code == 2

        # --- validate_release_config: every required-field/shape branch, directly ---
        def _invalid(overrides):
            cfg = dict(_PROFILE1_CONFIG)
            cfg.update(overrides)
            try:
                mod.validate_release_config(cfg, root1)
                return False
            except mod.ReleaseNotesError:
                return True

        assert _invalid({"version_locations": []})
        assert _invalid({"version_locations": "not-a-list"})
        assert _invalid({"version_locations": ["not-a-dict"]})
        assert _invalid({"version_locations": [{"pointer": "/version"}]})  # missing file
        assert _invalid({"version_locations": [{"file": "x.json"}]})  # missing pointer
        assert _invalid({"version_locations": [
            {"file": "x.json", "pointer": "/version", "kind": "regex"}]})
        assert _invalid({"version_locations": [{"file": "../escape.json", "pointer": "/version"}]})
        assert _invalid({"version_locations": [{"file": "/abs/escape.json", "pointer": "/version"}]})
        assert _invalid({"extra_refs": "not-a-list"})
        assert _invalid({"extra_refs": ["not-a-dict"]})
        assert _invalid({"extra_refs": [{"selector": {}, "value_format": "v{version}"}]})  # no file
        assert _invalid({"extra_refs": [
            {"file": "x.json", "selector": "not-a-dict", "value_format": "v{version}"}]})
        assert _invalid({"extra_refs": [
            {"file": "x.json", "selector": {"pointer": "", "match": {"name": "a"}, "set": "a/b"},
             "value_format": "v{version}"}]})  # empty selector.pointer
        assert _invalid({"extra_refs": [
            {"file": "x.json", "selector": {"pointer": "/plugins", "match": {}, "set": "a/b"},
             "value_format": "v{version}"}]})  # empty match
        assert _invalid({"extra_refs": [
            {"file": "x.json", "selector": {"pointer": "/plugins", "match": {"name": "acs"}},
             "value_format": "v{version}"}]})  # missing set
        assert _invalid({"extra_refs": [
            {"file": "x.json", "selector": {"pointer": "/plugins", "match": {"name": "acs"},
                                             "set": "a/b"},
             "value_format": "no-placeholder"}]})
        assert _invalid({"changelog_path": ""})
        assert _invalid({"changelog_path": 5})
        assert _invalid({"tag_format": "no-placeholder"})
        assert _invalid({"base_branch": ""})
        assert _invalid({"release_branch_format": "no-placeholder"})
        assert _invalid({"publish_driver": "not-a-dict"})
        assert mod.validate_release_config(dict(_PROFILE1_CONFIG), root1) is None  # valid -> no raise
        assert mod.validate_release_config(
            dict(_PROFILE1_CONFIG, publish_driver=None), root1) is None  # optional field absent

        # --- _resolve_release_config_value: literal JSON + file-path attempts ---
        assert mod._resolve_release_config_value(json.dumps({"a": 1})) == {"a": 1}
        assert mod._resolve_release_config_value(config_file) == _PROFILE1_CONFIG
        try:
            mod._resolve_release_config_value("neither-json-nor-a-file")
            raised = False
        except mod.ReleaseNotesError:
            raised = True
        assert raised is True

        # --- pointer_get / pointer_set: nested + list navigation, success and failure ---
        nested = {"a": {"b": [{"c": 1}, {"c": 2}]}}
        assert mod.pointer_get(nested, "/a/b/1/c", "x") == 2
        assert mod.pointer_get(nested, "/a/b/1", "x") == {"c": 2}  # last segment is a list index
        mod.pointer_set(nested, "/a/b/0/c", 99, "x")
        assert nested["a"]["b"][0]["c"] == 99
        for bad_pointer in (
            "no-leading-slash",       # invalid pointer syntax
            "/missing/foo",          # intermediate dict segment missing
            "/a/missing",            # last dict segment missing
            "/a/b/9",                # last segment: list index out of range
            "/a/b/9/c",              # intermediate segment: list index out of range
            "/a/b/notanindex/c",     # intermediate segment: not a valid list index
        ):
            try:
                mod.pointer_get(nested, bad_pointer, "x")
                raised = False
            except mod.ReleaseNotesError:
                raised = True
            assert raised is True, bad_pointer
        try:
            mod.pointer_get({"a": "scalar"}, "/a/b", "x")
            raised = False
        except mod.ReleaseNotesError:
            raised = True
        assert raised is True
        try:
            mod.pointer_get({"a": "scalar"}, "/a/b/c", "x")  # intermediate segment cannot descend
            raised = False
        except mod.ReleaseNotesError:
            raised = True
        assert raised is True

        # --- relative_pointer_set: success + each failure branch ---
        target = {"source": {"ref": "old"}}
        mod.relative_pointer_set(target, "source/ref", "new", "x")
        assert target["source"]["ref"] == "new"
        for bad_target, bad_path in (
            ({}, "source/ref"),                    # missing intermediate segment
            ({"source": "not-a-dict"}, "source/ref"),  # intermediate not a dict
            ("not-a-dict", "ref"),                 # single segment, final container not a dict
        ):
            try:
                mod.relative_pointer_set(bad_target, bad_path, "v", "x")
                raised = False
            except mod.ReleaseNotesError:
                raised = True
            assert raised is True

        # --- _find_selector_match: hit and miss ---
        array = [{"name": "acs"}, {"name": "tabp"}]
        assert mod._find_selector_match(array, {"name": "acs"}) is array[0]
        assert mod._find_selector_match(array, {"name": "missing"}) is None

        # --- _render_format: narrow single-token substitution ---
        assert mod._render_format("v{version}", "1.2.3") == "v1.2.3"

        # --- _distinct_manifest_files: dedup across version_locations + extra_refs, incl. an
        #     extra_refs file NOT already named by version_locations ---
        assert mod._distinct_manifest_files(_PROFILE1_CONFIG) == [
            ".claude-plugin/marketplace.json", "plugins/acs/.claude-plugin/plugin.json",
        ]
        assert mod._distinct_manifest_files({
            "version_locations": [{"file": "a.json", "pointer": "/v"}],
            "extra_refs": [{"file": "b.json", "selector": {}, "value_format": "v{version}"}],
        }) == ["a.json", "b.json"]

        # --- bump: extra_refs selector pointer resolving to a non-list -> ReleaseNotesError ---
        root_badptr = _make_repo(os.path.join(tmp, "repo_badptr"))
        bad_selector_config = dict(_PROFILE1_CONFIG, extra_refs=[
            {"file": ".claude-plugin/marketplace.json",
             "selector": {"pointer": "/name", "match": {"name": "acs"}, "set": "source/ref"},
             "value_format": "v{version}"},
        ])
        ws_badptr = os.path.join(tmp, "ws_badptr")
        try:
            mod.bump("0.4.2", root_badptr, ws_badptr, bad_selector_config)
            raised = False
        except mod.ReleaseNotesError:
            raised = True
        assert raised is True

        # --- missing CHANGELOG / missing / malformed manifest -> exit 2 ---
        root_no_chg = _make_repo(os.path.join(tmp, "repo_no_chg"), changelog_text=None)
        code, _out, err = _run_main(mod, [
            "status", "--version", "0.4.2", "--repo-root", root_no_chg,
            "--release-config", json.dumps(_PROFILE1_CONFIG),
        ])
        assert code == 2
        assert "CHANGELOG.md" in json.loads(err)["error"]

        root_no_manifest = _make_repo(os.path.join(tmp, "repo_no_manifest"))
        os.remove(os.path.join(root_no_manifest, "plugins", "acs", ".claude-plugin", "plugin.json"))
        code, _out, err = _run_main(mod, [
            "draft", "--version", "0.4.2", "--repo-root", root_no_manifest, "--workspace", ws_empty,
            "--release-config", json.dumps(_PROFILE1_CONFIG),
        ])
        assert code == 2

        root_bad_json = _make_repo(os.path.join(tmp, "repo_bad_json"))
        _write(os.path.join(root_bad_json, ".claude-plugin", "marketplace.json"), "{not valid")
        code, _out, err = _run_main(mod, [
            "bump", "--version", "0.4.2", "--repo-root", root_bad_json, "--workspace", ws_empty,
            "--release-config", json.dumps(_PROFILE1_CONFIG),
        ])
        assert code == 2

        # --- draft: coverage arithmetic, grouping, PR-ref resolution, categorization, custom
        #     base_branch (proves the since-tag boundary respects the config field) ---
        root5 = _make_repo(os.path.join(tmp, "repo5"),
                            changelog_text=(
                                "# Changelog\n\n## [Unreleased]\n\nMAR-1 and MAR-2 done.\n\n"
                                "## [0.4.1] - 2026-07-12\n\n### Added\n\n- prior\n"
                            ), base_branch="trunk")
        _tag_repo(root5, "0.4.1", when="2026-07-10T00:00:00+00:00")
        config5 = dict(_PROFILE1_CONFIG, base_branch="trunk")
        ws5 = os.path.join(tmp, "ws5")
        _write_archive_ticket(ws5, "MAR-1", title="Fix flaky epic child", parent="MAR-100",
                               ended_at="2026-07-11T00:00:00Z")
        _write_create_pr_state(ws5, "MAR-1", 250, "https://example/pull/250")
        _write_archive_ticket(ws5, "MAR-2", title="Docs epic child", parent="MAR-100",
                               docs_only=True, ended_at="2026-07-11T01:00:00Z")
        _write_archive_ticket(ws5, "MAR-100", title="Parent epic", merged=False)
        _write_archive_ticket(ws5, "MAR-3", title="Standalone add", parent=None,
                               ended_at="2026-07-11T02:00:00Z")
        _run(["git", "commit", "-q", "--allow-empty", "-m", "MAR-3 add thing (#99)"], root5)
        draft5 = mod.build_draft("0.4.2", root5, ws5, config5, today="2026-07-19")
        assert draft5["coverage"] == {"merged": 3, "covered": 2, "missing": 1}
        assert "### Fixed" in draft5["draft_section"]
        assert "### Changed" in draft5["draft_section"]
        assert "### Added" in draft5["draft_section"]
        by_id = {t["id"]: t for t in draft5["tickets"]}
        assert by_id["MAR-1"]["pr_number"] == 250
        assert by_id["MAR-3"]["pr_number"] == 99

        # --- draft: neither PR source resolves ---
        _write_archive_ticket(ws5, "MAR-4", title="No PR anywhere", ended_at="2026-07-11T03:00:00Z")
        draft5b = mod.build_draft("0.4.2", root5, ws5, config5, today="2026-07-19")
        by_id2 = {t["id"]: t for t in draft5b["tickets"]}
        assert by_id2["MAR-4"]["pr_number"] is None
        assert by_id2["MAR-4"]["pr_url"] is None

        # --- draft: nothing to release (bare header) ---
        root6 = _make_repo(os.path.join(tmp, "repo6"))
        ws6 = os.path.join(tmp, "ws6")
        draft6 = mod.build_draft("0.4.2", root6, ws6, _PROFILE1_CONFIG, today="2026-07-19")
        assert draft6["draft_section"] == "## [0.4.2] - 2026-07-19\n"
        assert draft6["coverage"] == {"merged": 0, "covered": 0, "missing": 0}

        # --- draft: bootstrap since_tag None ---
        root7 = _make_repo(os.path.join(tmp, "repo7"))  # no tags
        ws7 = os.path.join(tmp, "ws7")
        _write_archive_ticket(ws7, "MAR-9", title="Old one", ended_at="2000-01-01T00:00:00Z")
        draft7 = mod.build_draft("0.4.2", root7, ws7, _PROFILE1_CONFIG, today="2026-07-19")
        assert draft7["since_tag"] is None
        assert draft7["coverage"]["merged"] == 1

        # --- draft: merge-time boundary (before/after tag; ignores updated_at) ---
        root8 = _make_repo(os.path.join(tmp, "repo8"))
        _tag_repo(root8, "0.4.1", when="2026-07-01T00:00:00+00:00")
        ws8 = os.path.join(tmp, "ws8")
        _write_archive_ticket(ws8, "MAR-1", title="Before tag", ended_at="2026-06-30T00:00:00Z",
                               updated_at="2026-12-31T00:00:00Z")
        _write_archive_ticket(ws8, "MAR-2", title="After tag", ended_at="2026-07-02T00:00:00Z")
        draft8 = mod.build_draft("0.4.2", root8, ws8, _PROFILE1_CONFIG, today="2026-07-19")
        ids8 = {t["id"] for t in draft8["tickets"]}
        assert "MAR-1" not in ids8
        assert "MAR-2" in ids8

        # --- draft: word-boundary safety ---
        root9 = _make_repo(os.path.join(tmp, "repo9"),
                            changelog_text=(
                                "# Changelog\n\n## [Unreleased]\n\nMAR-12 done.\n\n"
                                "## [0.4.1] - 2026-07-12\n\n### Added\n\n- prior\n"
                            ))
        ws9 = os.path.join(tmp, "ws9")
        _write_archive_ticket(ws9, "MAR-1", title="One")
        _write_archive_ticket(ws9, "MAR-12", title="Twelve")
        draft9 = mod.build_draft("0.4.2", root9, ws9, _PROFILE1_CONFIG, today="2026-07-19")
        assert "MAR-1" in draft9["unreleased_missing"]
        assert "MAR-12" in draft9["unreleased_covered"]

        # --- archive skip: unmerged / malformed entries never surfaced ---
        root10 = _make_repo(os.path.join(tmp, "repo10"))
        ws10 = os.path.join(tmp, "ws10")
        _write_archive_ticket(ws10, "MAR-20", title="Never merged", merged=False)
        os.makedirs(os.path.join(ws10, "archive", "MAR-21"), exist_ok=True)
        _write(os.path.join(ws10, "archive", "MAR-21", "merge-pr-state.json"), "{not json")
        os.makedirs(os.path.join(ws10, "archive", "MAR-22", "merge-pr-state.json"))  # a directory, unreadable
        draft10 = mod.build_draft("0.4.2", root10, ws10, _PROFILE1_CONFIG, today="2026-07-19")
        assert draft10["coverage"]["merged"] == 0

        # --- bump: real bump sets both versions + ref, leaves tabp untouched ---
        root11 = _make_repo(os.path.join(tmp, "repo11"))
        ws11 = os.path.join(tmp, "ws11")
        _write_archive_ticket(ws11, "MAR-30", title="Add a widget")
        result11 = mod.bump("0.4.2", root11, ws11, _PROFILE1_CONFIG, today="2026-07-19")
        assert result11["ok"] is True
        assert result11["already_at_target"] is False
        market11 = json.loads(_read(os.path.join(root11, ".claude-plugin", "marketplace.json")))
        assert market11["version"] == "0.4.2"
        acs_entry = next(p for p in market11["plugins"] if p["name"] == "acs")
        assert acs_entry["source"]["ref"] == "v0.4.2"
        tabp_entry = next(p for p in market11["plugins"] if p["name"] == "tabp")
        assert "ref" not in tabp_entry["source"]
        text11 = _read(os.path.join(root11, "plugins", "acs", "CHANGELOG.md"))
        assert "## [Unreleased]" in text11
        assert "## [0.4.2] - 2026-07-19" in text11
        assert "## [0.4.1] - 2026-07-12" in text11

        # --- bump: a non-marketplace (package.json-style) repo — proves generality ---
        root_pkg = os.path.join(tmp, "repo_pkg")
        _write_json(os.path.join(root_pkg, "package.json"), {"name": "thing", "version": "1.0.0"})
        _write(os.path.join(root_pkg, "CHANGELOG.md"),
               "# Changelog\n\n## [Unreleased]\n\n## [1.0.0] - 2026-01-01\n\n### Added\n\n- init\n")
        _run(["git", "init", "-q"], root_pkg)
        _run(["git", "config", "user.email", "t@example.com"], root_pkg)
        _run(["git", "config", "user.name", "Test"], root_pkg)
        _run(["git", "add", "-A"], root_pkg)
        _run(["git", "commit", "-q", "-m", "init"], root_pkg)
        _run(["git", "branch", "-M", "main"], root_pkg)
        pkg_config = {
            "version_locations": [{"file": "package.json", "pointer": "/version"}],
            "extra_refs": [],
            "changelog_path": "CHANGELOG.md",
            "base_branch": "main",
            "tag_format": "v{version}",
            "release_branch_format": "release/v{version}",
        }
        ws_pkg = os.path.join(tmp, "ws_pkg")
        result_pkg = mod.bump("1.1.0", root_pkg, ws_pkg, pkg_config, today="2026-02-02")
        assert sorted(result_pkg["files_changed"]) == sorted(["package.json", "CHANGELOG.md"])
        pkg_after = json.loads(_read(os.path.join(root_pkg, "package.json")))
        assert pkg_after["version"] == "1.1.0"

        # --- bump: name-match selector correctness (tabp untouched; mismatched-name-target fails) ---
        root_nm = _make_repo(os.path.join(tmp, "repo_nm"),
                              marketplace={
                                  "name": "gms-marketplace", "version": "0.4.1",
                                  "plugins": [
                                      {"name": "acs", "source": {"source": "git-subdir", "ref": "v0.4.1"}},
                                      {"name": "tabp"},
                                  ],
                              })
        ws_nm = os.path.join(tmp, "ws_nm")
        mod.bump("0.4.2", root_nm, ws_nm, _PROFILE1_CONFIG, today="2026-07-19")
        market_nm = json.loads(_read(os.path.join(root_nm, ".claude-plugin", "marketplace.json")))
        tabp_nm = next(p for p in market_nm["plugins"] if p["name"] == "tabp")
        assert tabp_nm == {"name": "tabp"}

        root_nm2 = _make_repo(os.path.join(tmp, "repo_nm2"),
                               marketplace={
                                   "name": "gms-marketplace", "version": "0.4.1",
                                   "plugins": [
                                       {"name": "acs", "source": {"source": "git-subdir", "ref": "v0.4.1"}},
                                       {"name": "tabp"},
                                   ],
                               })
        ws_nm2 = os.path.join(tmp, "ws_nm2")
        mismatched_config = dict(_PROFILE1_CONFIG, extra_refs=[
            {"file": ".claude-plugin/marketplace.json",
             "selector": {"pointer": "/plugins", "match": {"name": "tabp"}, "set": "source/ref"},
             "value_format": "v{version}"},
        ])
        try:
            mod.bump("0.4.2", root_nm2, ws_nm2, mismatched_config, today="2026-07-19")
            raised = False
        except mod.ReleaseNotesError:
            raised = True
        assert raised is True

        # --- bump: extra_refs selector matching zero elements -> ReleaseNotesError, no write ---
        root_zero = _make_repo(os.path.join(tmp, "repo_zero"))
        ws_zero = os.path.join(tmp, "ws_zero")
        zero_match_config = dict(_PROFILE1_CONFIG, extra_refs=[
            {"file": ".claude-plugin/marketplace.json",
             "selector": {"pointer": "/plugins", "match": {"name": "nope"}, "set": "source/ref"},
             "value_format": "v{version}"},
        ])
        try:
            mod.bump("0.4.2", root_zero, ws_zero, zero_match_config, today="2026-07-19")
            raised = False
        except mod.ReleaseNotesError:
            raised = True
        assert raised is True

        # --- bump: unresolvable version_locations pointer -> no partial write across the set ---
        root_partial = _make_repo(os.path.join(tmp, "repo_partial"))
        ws_partial = os.path.join(tmp, "ws_partial")
        partial_config = dict(_PROFILE1_CONFIG, version_locations=[
            {"file": ".claude-plugin/marketplace.json", "pointer": "/version"},
            {"file": "plugins/acs/.claude-plugin/plugin.json", "pointer": "/nonexistent"},
        ])
        market_partial_path = os.path.join(root_partial, ".claude-plugin", "marketplace.json")
        before_partial = _read(market_partial_path)
        try:
            mod.bump("0.4.2", root_partial, ws_partial, partial_config, today="2026-07-19")
            raised = False
        except mod.ReleaseNotesError:
            raised = True
        assert raised is True
        assert _read(market_partial_path) == before_partial

        # --- bump: pre-existing Unreleased prose not merged forward ---
        root12 = _make_repo(os.path.join(tmp, "repo12"),
                             changelog_text=(
                                 "# Changelog\n\n## [Unreleased]\n\nSome pending notes.\n\n"
                                 "## [0.4.1] - 2026-07-12\n\n### Added\n\n- prior entry\n"
                             ))
        ws12 = os.path.join(tmp, "ws12")
        _write_archive_ticket(ws12, "MAR-31", title="Add a widget")
        mod.bump("0.4.2", root12, ws12, _PROFILE1_CONFIG, today="2026-07-19")
        text12 = _read(os.path.join(root12, "plugins", "acs", "CHANGELOG.md"))
        assert "Some pending notes." not in text12

        # --- bump: nothing to release (already at target) -> no write ---
        root13 = _make_repo(
            os.path.join(tmp, "repo13"),
            changelog_text=("# Changelog\n\n## [Unreleased]\n\n## [0.4.2] - 2026-07-19\n\n"
                             "### Added\n\n- x\n"),
            marketplace={**_MARKETPLACE, "version": "0.4.2",
                         "plugins": [{"name": "acs", "source": {"source": "git-subdir", "ref": "v0.4.2"}},
                                     {"name": "tabp", "source": {"source": "git-subdir"}}]},
            plugin={"name": "acs", "version": "0.4.2"},
        )
        ws13 = os.path.join(tmp, "ws13")
        before13 = _read(os.path.join(root13, ".claude-plugin", "marketplace.json"))
        result13 = mod.bump("0.4.2", root13, ws13, _PROFILE1_CONFIG)
        assert result13 == {"ok": True, "files_changed": [], "already_at_target": True}
        assert _read(os.path.join(root13, ".claude-plugin", "marketplace.json")) == before13

        # --- bump: atomicity — a crash mid-write leaves the original manifest intact ---
        root14 = _make_repo(os.path.join(tmp, "repo14"))
        ws14 = os.path.join(tmp, "ws14")
        market14_path = os.path.join(root14, ".claude-plugin", "marketplace.json")
        original14 = _read(market14_path)
        real_rename = os.rename
        os.rename = lambda *a, **k: (_ for _ in ()).throw(OSError("simulated crash"))
        try:
            try:
                mod.bump("0.4.2", root14, ws14, _PROFILE1_CONFIG)
                raised = False
            except mod.ReleaseNotesError:
                raised = True
        finally:
            os.rename = real_rename
        assert raised is True
        assert _read(market14_path) == original14

        # --- bump: CLI atomicity-crash path also exercised (stderr JSON shape) ---
        root15 = _make_repo(os.path.join(tmp, "repo15"))
        ws15 = os.path.join(tmp, "ws15")
        os.rename = lambda *a, **k: (_ for _ in ()).throw(OSError("simulated crash"))
        try:
            code, _out, err = _run_main(mod, [
                "bump", "--version", "0.4.2", "--repo-root", root15, "--workspace", ws15,
                "--release-config", json.dumps(_PROFILE1_CONFIG),
            ])
        finally:
            os.rename = real_rename
        assert code == 2
        assert "error" in json.loads(err)

        # --- bump: --dry-run reports files_changed without writing ---
        root16 = _make_repo(os.path.join(tmp, "repo16"))
        ws16 = os.path.join(tmp, "ws16")
        market16_path = os.path.join(root16, ".claude-plugin", "marketplace.json")
        before16 = _read(market16_path)
        result16 = mod.bump("0.4.2", root16, ws16, _PROFILE1_CONFIG, dry_run=True)
        assert result16["files_changed"]
        assert _read(market16_path) == before16

        # --- bump: no '## [Unreleased]' heading in CHANGELOG -> ReleaseNotesError ---
        root17 = _make_repo(os.path.join(tmp, "repo17"),
                             changelog_text="# Changelog\n\n## [0.4.1] - 2026-07-12\n\nbody\n")
        ws17 = os.path.join(tmp, "ws17")
        try:
            mod.bump("0.4.2", root17, ws17, _PROFILE1_CONFIG)
            raised17 = False
        except mod.ReleaseNotesError:
            raised17 = True
        assert raised17 is True

        # --- gh_pr_list real body: success / empty list / non-zero / malformed JSON ---
        mod.gh_pr_list = _real_gh_pr_list  # restore the real function; only subprocess.run is faked below
        real_subprocess_run = mod.subprocess.run
        try:
            mod.subprocess.run = lambda *a, **k: _FakeResult(
                0, json.dumps([{"number": 7, "url": "https://x/7"}]))
            assert mod.gh_pr_list(root1, "release/v0.4.2") == {"number": 7, "url": "https://x/7"}

            mod.subprocess.run = lambda *a, **k: _FakeResult(0, json.dumps([]))
            assert mod.gh_pr_list(root1, "release/v0.4.2") is None

            mod.subprocess.run = lambda *a, **k: _FakeResult(1, "")
            assert mod.gh_pr_list(root1, "release/v0.4.2") is None

            mod.subprocess.run = lambda *a, **k: _FakeResult(0, "not json")
            assert mod.gh_pr_list(root1, "release/v0.4.2") is None
        finally:
            mod.subprocess.run = real_subprocess_run

        # --- white-box: render_draft_section / categorize / _is_valid_version direct calls ---
        assert mod.render_draft_section("0.4.2", "2026-07-19", [], lambda pid: pid) == \
            "## [0.4.2] - 2026-07-19\n"
        assert mod.categorize({"title": "Fix a bug", "description": ""}) == "Fixed"
        assert mod.categorize({"title": "x", "description": "", "docs_only": True}) == "Changed"
        assert mod.categorize({"title": "Add feature", "description": ""}) == "Added"
        assert mod._is_valid_version("1.2.3") is True
        assert mod._is_valid_version("abc") is False
        assert mod._is_valid_version("") is False
        assert mod._parse_iso(None) is None
        assert mod._parse_iso("not-a-date") is None
        assert mod._parse_iso("2026-07-12T04:07:39Z") is not None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _count_from_cover(cover_path):
    """Parse a trace .cover file: count executed/total executable lines and collect misses."""
    import re
    executed = 0
    total = 0
    missed = []
    line_no = 0
    with open(cover_path, "r", encoding="utf-8") as fh:
        for raw in fh:
            line_no += 1
            if raw.startswith(">>>>>>"):
                total += 1
                missed.append((line_no, raw[6:].rstrip("\n")))
            else:
                m = re.match(r"\s*(\d+):", raw)
                if m:
                    total += 1
                    executed += 1
    return executed, total, missed


def main():
    covdir = tempfile.mkdtemp(prefix="acs-cov-release-notes-")
    try:
        tracer = trace.Trace(count=1, trace=0)
        devnull = open(os.devnull, "w")
        real_stdout = sys.stdout
        sys.stdout = devnull
        try:
            tracer.runfunc(_drive)
        finally:
            sys.stdout = real_stdout
            devnull.close()
        results = tracer.results()
        results.write_results(summary=False, coverdir=covdir)

        cover_file = None
        for name in os.listdir(covdir):
            if name == "release_notes.cover":
                cover_file = os.path.join(covdir, name)
                break
        if cover_file is None:
            print("ERROR: no release_notes .cover produced in %s" % covdir)
            return 2

        executed, total, missed = _count_from_cover(cover_file)
        pct = (executed * 100.0 / total) if total else 0.0
        print("release_notes.py coverage: %d/%d executable lines = %.1f%% (gate %.0f%%)"
              % (executed, total, pct, GATE))
        if missed:
            print("missed lines (>>>>>> in trace .cover):")
            for ln, src in missed:
                print("  L%d: %s" % (ln, src.strip()))
        else:
            print("missed lines: none")
        result = {"executed": executed, "total": total, "percent": round(pct, 1),
                  "gate": GATE, "passed": pct >= GATE,
                  "missed": [ln for ln, _ in missed]}
        print(json.dumps(result))
        return 0 if pct >= GATE else 1
    finally:
        shutil.rmtree(covdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
