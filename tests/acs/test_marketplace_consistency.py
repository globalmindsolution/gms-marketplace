"""Regression tests for the 'Validate marketplace/plugin version consistency' step in ci.yml.

Mechanism: EXTRACT-AND-RUN (C-2 option A).
  In setUpClass, the ci.yml heredoc body for the consistency-validator step is
  extracted by locating the 'Validate marketplace/plugin version consistency' step,
  slicing the lines between the opening <<'EOF' marker and the matching EOF, and
  DEDENTING them.  The dedented body is written to a temp validator.py.

  Each test case builds a synthetic repo in a tempdir (.claude-plugin/marketplace.json
  plus, when needed, <path>/.claude-plugin/plugin.json) and runs:
    subprocess.run([sys.executable, validator_py], cwd=fixture, ...)
  asserting returncode + stderr/stdout substrings.

  Mandatory robustness guard: setUpClass asserts that the extracted body is
  non-empty AND contains the sentinel string 'git-subdir' (true after Edit 1
  lands).  If extraction drifts or Edit 1 is not yet applied, the guard fails
  loudly — this converts silent false-green into a visible red.

Coverage note: MAR-29 touches zero files under src/acs/ (only ci.yml and
this test file), so the 90% coverage gate against src/acs/ production code
is unaffected.

TDD: T2 and T4 are RED against the pre-Edit-1 ci.yml body (git-subdir entries
are silently skipped → name/version mismatches produce rc==0 instead of rc==1).
They turn GREEN after Edit 1 replaces the skip with a three-way branch.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CI_YML = os.path.join(REPO_ROOT, ".github", "workflows", "ci.yml")


def _extract_validator_body():
    """Locate the 'Validate marketplace/plugin version consistency' step in ci.yml,
    slice the heredoc body between <<'EOF' and the matching EOF, and DEDENT it.
    Returns the dedented body as a string.
    """
    with open(CI_YML, encoding="utf-8") as fh:
        lines = fh.readlines()

    step_name = "Validate marketplace/plugin version consistency"
    step_start = None
    for i, line in enumerate(lines):
        if step_name in line and "- name:" in line:
            step_start = i
            break

    if step_start is None:
        return ""

    # Find the <<'EOF' after the step name
    heredoc_start = None
    for i in range(step_start, min(step_start + 5, len(lines))):
        if "<<'EOF'" in lines[i]:
            heredoc_start = i
            break

    if heredoc_start is None:
        return ""

    # Slice lines from the line AFTER <<'EOF' up to (but not including) the EOF closer
    # The EOF closer is a line that is exactly spaces + "EOF\n" (no other content)
    body_lines = []
    for i in range(heredoc_start + 1, len(lines)):
        stripped = lines[i].rstrip("\n")
        # The heredoc EOF closer in ci.yml is "          EOF" (10 spaces + EOF)
        if stripped.strip() == "EOF" and stripped == " " * 10 + "EOF":
            break
        body_lines.append(lines[i])

    if not body_lines:
        return ""

    return textwrap.dedent("".join(body_lines))


def _git_init(tmp, ref):
    """Commit the fixture tree and make `ref` name that commit."""
    env = dict(os.environ,
               GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@e",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@e")
    run = lambda *a: subprocess.run(["git"] + list(a), cwd=tmp, env=env,
                                    capture_output=True, text=True, check=True)
    run("init", "--quiet", "-b", "main")
    run("add", "-A")
    run("commit", "--quiet", "-m", "fixture")
    if ref != "main":
        run("tag", ref)


class MarketplaceConsistencyTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Extract the validator body once; write to a shared temp file."""
        cls._tmpdir = tempfile.mkdtemp(prefix="acs-mktconsistency-")
        cls.validator_py = os.path.join(cls._tmpdir, "validator.py")

        body = _extract_validator_body()

        # Mandatory robustness guard: fail loudly if extraction drifted or Edit 1 not applied.
        if not body:
            raise AssertionError(
                "Extracted validator body from ci.yml is empty. "
                "Check that 'Validate marketplace/plugin version consistency' step "
                "with a <<'EOF' heredoc exists in .github/workflows/ci.yml."
            )
        if "git-subdir" not in body:
            raise AssertionError(
                "Extracted validator body does NOT contain the sentinel string 'git-subdir'. "
                "Edit 1 (three-way branch for git-subdir) must be applied to ci.yml before "
                "these tests will pass. This guard prevents silent false-green."
            )

        with open(cls.validator_py, "w", encoding="utf-8") as fh:
            fh.write(body)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._tmpdir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Helper: build a synthetic fixture repo in a tempdir
    # ------------------------------------------------------------------

    def _make_fixture(self, entry, plugin_path=None, plugin_json=None, plugin_root=None,
                      devin_json=None):
        """Create a synthetic repo dir with .claude-plugin/marketplace.json.

        If plugin_path is given, also writes plugin_path/.claude-plugin/plugin.json,
        and plugin_path/.devin-plugin/plugin.json when devin_json is given.
        Returns the path to the fixture directory (cleaned up via addCleanup).
        """
        tmp = tempfile.mkdtemp(prefix="acs-mktfixture-")
        self.addCleanup(shutil.rmtree, tmp, True)

        # The validator imports plugin_dirs() to find the plugin source dirs in
        # the TREE, so a fixture only stands in for a repo if it carries the
        # same helper the ci.yml checkout does.
        scripts_dir = os.path.join(tmp, ".github", "scripts")
        os.makedirs(scripts_dir)
        shutil.copy(
            os.path.join(REPO_ROOT, ".github", "scripts", "plugin_source_dirs.py"),
            scripts_dir,
        )

        metadata = {}
        if plugin_root is not None:
            metadata["pluginRoot"] = plugin_root

        mkt = {
            "name": "test-marketplace",
            "version": "1.0.0",
            "metadata": metadata,
            "plugins": [entry],
        }

        os.makedirs(os.path.join(tmp, ".claude-plugin"))
        with open(os.path.join(tmp, ".claude-plugin", "marketplace.json"), "w") as fh:
            json.dump(mkt, fh)

        if plugin_path is not None and plugin_json is not None:
            pj_dir = os.path.join(tmp, plugin_path, ".claude-plugin")
            os.makedirs(pj_dir, exist_ok=True)
            with open(os.path.join(pj_dir, "plugin.json"), "w") as fh:
                json.dump(plugin_json, fh)

            if devin_json is not None:
                dm_dir = os.path.join(tmp, plugin_path, ".devin-plugin")
                os.makedirs(dm_dir, exist_ok=True)
                with open(os.path.join(dm_dir, "plugin.json"), "w") as fh:
                    json.dump(devin_json, fh)

        # The validator judges a pinned entry AT its ref, because that is what
        # an install fetches -- so a fixture that only writes files on disk no
        # longer stands in for a repo. Commit the tree and name the ref, which
        # is also what makes these cases able to fail: the pre-2026-09-17
        # validator read the working tree and so could not tell a correct pair
        # from one whose path does not exist at the ref it advertises.
        ref = (entry.get("source") or {}).get("ref") if isinstance(entry.get("source"), dict) else None
        if ref:
            _git_init(tmp, ref)

        return tmp

    def _run(self, fixture_dir):
        return subprocess.run(
            [sys.executable, self.validator_py],
            cwd=fixture_dir,
            capture_output=True,
            text=True,
        )

    # ------------------------------------------------------------------
    # T1: git-subdir name match passes (AC-2)
    # ------------------------------------------------------------------

    def test_git_subdir_name_match_passes(self):
        """T1: git-subdir entry with matching plugin.json name → rc==0, no error."""
        entry = {
            "name": "myplugin",
            "source": {"source": "git-subdir", "url": "https://example.com/repo.git",
                       "path": "plugins/myplugin", "ref": "main"},
        }
        fixture = self._make_fixture(
            entry,
            plugin_path="plugins/myplugin",
            plugin_json={"name": "myplugin", "version": "1.0.0"},
        )
        out = self._run(fixture)
        self.assertEqual(out.returncode, 0, f"Expected rc==0. stderr={out.stderr!r}")
        self.assertIn("OK", out.stdout)

    # ------------------------------------------------------------------
    # T2: git-subdir name mismatch errors (AC-2) — RED pre-Edit-1
    # ------------------------------------------------------------------

    def test_git_subdir_name_mismatch_errors(self):
        """T2: git-subdir entry with mismatching plugin.json name → rc==1, stderr has mismatch.

        RED before Edit 1 (current ci.yml skips git-subdir → no error → rc==0 ≠ 1).
        GREEN after Edit 1 (three-way branch validates name).
        """
        entry = {
            "name": "myplugin",
            "source": {"source": "git-subdir", "url": "https://example.com/repo.git",
                       "path": "plugins/myplugin", "ref": "main"},
        }
        fixture = self._make_fixture(
            entry,
            plugin_path="plugins/myplugin",
            plugin_json={"name": "WRONG_NAME", "version": "1.0.0"},
        )
        out = self._run(fixture)
        self.assertEqual(out.returncode, 1, f"Expected rc==1. stderr={out.stderr!r} stdout={out.stdout!r}")
        self.assertIn("WRONG_NAME", out.stderr, f"Expected name mismatch in stderr. stderr={out.stderr!r}")

    # ------------------------------------------------------------------
    # T3: git-subdir version match passes (AC-3)
    # ------------------------------------------------------------------

    def test_git_subdir_version_match_passes(self):
        """T3: git-subdir entry declaring matching version → rc==0, no error."""
        entry = {
            "name": "myplugin",
            "version": "1.2.3",
            "source": {"source": "git-subdir", "url": "https://example.com/repo.git",
                       "path": "plugins/myplugin", "ref": "v1.2.3"},
        }
        fixture = self._make_fixture(
            entry,
            plugin_path="plugins/myplugin",
            plugin_json={"name": "myplugin", "version": "1.2.3"},
        )
        out = self._run(fixture)
        self.assertEqual(out.returncode, 0, f"Expected rc==0. stderr={out.stderr!r}")

    # ------------------------------------------------------------------
    # T4: git-subdir version mismatch errors (AC-3) — RED pre-Edit-1
    # ------------------------------------------------------------------

    def test_git_subdir_version_mismatch_errors(self):
        """T4: git-subdir entry declaring mismatching version → rc==1, stderr version error.

        RED before Edit 1 (git-subdir skipped → no version check → rc==0 ≠ 1).
        GREEN after Edit 1 (three-way branch validates version).
        """
        entry = {
            "name": "myplugin",
            "version": "1.0.0",
            "source": {"source": "git-subdir", "url": "https://example.com/repo.git",
                       "path": "plugins/myplugin", "ref": "v1.0.0"},
        }
        fixture = self._make_fixture(
            entry,
            plugin_path="plugins/myplugin",
            plugin_json={"name": "myplugin", "version": "9.9.9"},
        )
        out = self._run(fixture)
        self.assertEqual(out.returncode, 1, f"Expected rc==1. stderr={out.stderr!r} stdout={out.stdout!r}")
        self.assertIn("9.9.9", out.stderr, f"Expected version mismatch in stderr. stderr={out.stderr!r}")

    # ------------------------------------------------------------------
    # T5: git-subdir no entry-version skips version branch but enforces name (AC-3)
    # ------------------------------------------------------------------

    def test_git_subdir_no_entry_version_skips_version_branch(self):
        """T5: git-subdir entry with NO version key + plugin.json with version → rc==0,
        no version error; name check still fires (passes when names match).
        """
        entry = {
            "name": "myplugin",
            # No "version" key
            "source": {"source": "git-subdir", "url": "https://example.com/repo.git",
                       "path": "plugins/myplugin", "ref": "main"},
        }
        fixture = self._make_fixture(
            entry,
            plugin_path="plugins/myplugin",
            plugin_json={"name": "myplugin", "version": "0.5.0"},
        )
        out = self._run(fixture)
        self.assertEqual(out.returncode, 0, f"Expected rc==0. stderr={out.stderr!r}")
        # Confirm no version error
        self.assertNotIn("version", out.stderr.lower(),
                         f"Expected no version error. stderr={out.stderr!r}")

    # ------------------------------------------------------------------
    # T6: Non-git-subdir object sources skipped (AC-4)
    # ------------------------------------------------------------------

    def test_github_object_source_skipped(self):
        """T6_github: Entry with source.source=='github' and no local manifest → rc==0."""
        entry = {
            "name": "remoteplugin",
            "source": {"source": "github", "repo": "acme/plugin", "ref": "main"},
        }
        fixture = self._make_fixture(entry)
        out = self._run(fixture)
        self.assertEqual(out.returncode, 0, f"Expected rc==0. stderr={out.stderr!r}")
        # No missing-manifest error
        self.assertNotIn("plugin.json", out.stderr,
                         f"Expected no manifest error. stderr={out.stderr!r}")

    def test_url_object_source_skipped(self):
        """T6_url: Entry with source.source=='url' → rc==0, no local-manifest error."""
        entry = {
            "name": "urlplugin",
            "source": {"source": "url", "url": "https://example.com/plugin.tar.gz"},
        }
        fixture = self._make_fixture(entry)
        out = self._run(fixture)
        self.assertEqual(out.returncode, 0, f"Expected rc==0. stderr={out.stderr!r}")

    def test_npm_object_source_skipped(self):
        """T6_npm: Entry with source.source=='npm' → rc==0, no local-manifest error."""
        entry = {
            "name": "npmplugin",
            "source": {"source": "npm", "package": "@acme/plugin"},
        }
        fixture = self._make_fixture(entry)
        out = self._run(fixture)
        self.assertEqual(out.returncode, 0, f"Expected rc==0. stderr={out.stderr!r}")

    # ------------------------------------------------------------------
    # T7: String-path source unchanged (AC-5 regression guard)
    # ------------------------------------------------------------------

    def test_string_path_source_unchanged(self):
        """T7_string: String-path entry with matching name+version → rc==0 (AC-5)."""
        entry = {
            "name": "localplugin",
            "version": "2.0.0",
            "source": "plugins/localplugin",
        }
        fixture = self._make_fixture(
            entry,
            plugin_path="plugins/localplugin",
            plugin_json={"name": "localplugin", "version": "2.0.0"},
        )
        out = self._run(fixture)
        self.assertEqual(out.returncode, 0, f"Expected rc==0. stderr={out.stderr!r}")

    def test_string_path_name_mismatch_errors(self):
        """T7_string_mismatch: String-path entry with mismatching name → rc==1 (AC-5)."""
        entry = {
            "name": "localplugin",
            "source": "plugins/localplugin",
        }
        fixture = self._make_fixture(
            entry,
            plugin_path="plugins/localplugin",
            plugin_json={"name": "DIFFERENT_NAME", "version": "1.0.0"},
        )
        out = self._run(fixture)
        self.assertEqual(out.returncode, 1, f"Expected rc==1. stderr={out.stderr!r}")
        self.assertIn("DIFFERENT_NAME", out.stderr,
                      f"Expected name mismatch in stderr. stderr={out.stderr!r}")

    # ------------------------------------------------------------------
    # T8: Live acs smoke — real marketplace.json + real plugin.json (AC-2, AC-6)
    # ------------------------------------------------------------------

    def test_live_acs_entry_name_matches(self):
        """T8: Read the real marketplace.json and src/acs/.claude-plugin/plugin.json.
        Assert the acs entry's name matches the plugin.json name.
        This is the smoke test against the live repo state (AC-2, AC-6).
        """
        mkt_path = os.path.join(REPO_ROOT, ".claude-plugin", "marketplace.json")
        pj_path = os.path.join(REPO_ROOT, "src", "acs", ".claude-plugin", "plugin.json")

        with open(mkt_path, encoding="utf-8") as fh:
            mkt = json.load(fh)
        with open(pj_path, encoding="utf-8") as fh:
            pj = json.load(fh)

        # Find the acs entry
        acs_entry = None
        for entry in mkt.get("plugins", []):
            if entry.get("name") == "acs":
                acs_entry = entry
                break

        self.assertIsNotNone(acs_entry, "No 'acs' entry found in .claude-plugin/marketplace.json")
        entry_name = acs_entry.get("name")
        pj_name = pj.get("name")
        self.assertEqual(
            entry_name, pj_name,
            f"acs entry name '{entry_name}' != plugin.json name '{pj_name}'"
        )
        self.assertEqual(pj_name, "acs",
                         f"Expected plugin.json name to be 'acs', got '{pj_name}'")


if __name__ == "__main__":
    unittest.main()


class PathIsJudgedAtTheRefTest(MarketplaceConsistencyTest):
    """The 2026-09-16 break, as a test the validator must fail on.

    A directory move leaves `path` correct in the working tree and wrong at
    the tag the entry still advertises. The validator used to resolve `path`
    against the tree, so it saw a healthy plugin and passed, while every
    install asked for that path at the old tag and got nothing. Judging at the
    ref is what makes the two agree; this pins that it does.
    """

    def test_path_present_in_tree_but_absent_at_ref_is_rejected(self):
        entry = {
            "name": "myplugin",
            "source": {"source": "git-subdir", "url": "https://example.com/repo.git",
                       "path": "src/myplugin", "ref": "v1.0.0"},
        }
        # Commit the plugin at plugins/myplugin and tag it -- that is the
        # release. Then move it to src/myplugin in the tree WITHOUT re-tagging,
        # and point `path` at the new home: each field defensible alone, the
        # pair unresolvable, which is precisely what shipped.
        tmp = self._make_fixture(
            entry,
            plugin_path="plugins/myplugin",
            plugin_json={"name": "myplugin", "version": "1.0.0"},
        )
        os.renames(os.path.join(tmp, "plugins", "myplugin"),
                   os.path.join(tmp, "src", "myplugin"))
        out = self._run(tmp)
        self.assertEqual(
            out.returncode, 1,
            "validator passed a pair no install can resolve: 'src/myplugin' "
            "exists in the tree but not at tag v1.0.0. stdout=%r" % out.stdout)
        self.assertIn("no plugin.json", out.stderr)

    def test_the_same_pair_passes_once_the_ref_carries_the_move(self):
        """The other half: same move, ref advanced with it -> resolvable."""
        entry = {
            "name": "myplugin",
            "source": {"source": "git-subdir", "url": "https://example.com/repo.git",
                       "path": "src/myplugin", "ref": "v1.1.0"},
        }
        tmp = self._make_fixture(
            entry,
            plugin_path="src/myplugin",
            plugin_json={"name": "myplugin", "version": "1.0.0"},
        )
        out = self._run(tmp)
        self.assertEqual(out.returncode, 0,
                         "stderr=%r" % out.stderr)
        self.assertIn("OK", out.stdout)


class TheReleaseCutWindowTest(MarketplaceConsistencyTest):
    """The cut writes ref=v{version} before that tag exists; CI must not block it.

    release.extra_refs rewrites source/ref and source/path in the release
    commit, and release.yml creates the tag only once that commit reaches
    main. So on the release PR the advertised ref names nothing yet. Judging
    that as a broken pair would make every release PR unmergeable -- the
    commit under test is precisely the one about to be tagged, so the tree is
    what the tag will capture.
    """

    def test_ref_that_does_not_exist_yet_is_judged_against_the_tree(self):
        entry = {
            "name": "acs",
            "source": {"source": "git-subdir", "url": "https://example.com/repo.git",
                       "path": "src/acs", "ref": "v0.5.0"},
        }
        tmp = self._make_fixture(
            entry,
            plugin_path="src/acs",
            plugin_json={"name": "acs", "version": "1.0.0"},
        )
        # _make_fixture tags the ref; drop it so the tag is genuinely absent,
        # which is the state a release PR is actually in.
        subprocess.run(["git", "tag", "-d", "v0.5.0"], cwd=tmp,
                       capture_output=True, check=True)
        out = self._run(tmp)
        self.assertEqual(out.returncode, 0,
                         "a release cut would be unmergeable. stderr=%r" % out.stderr)
        self.assertIn("does not exist yet", out.stdout)

    def test_but_a_ref_that_DOES_exist_is_still_judged_there(self):
        """The carve-out must not swallow the 2026-09-16 break."""
        entry = {
            "name": "myplugin",
            "source": {"source": "git-subdir", "url": "https://example.com/repo.git",
                       "path": "src/myplugin", "ref": "v1.0.0"},
        }
        tmp = self._make_fixture(
            entry,
            plugin_path="plugins/myplugin",
            plugin_json={"name": "myplugin", "version": "1.0.0"},
        )
        os.renames(os.path.join(tmp, "plugins", "myplugin"),
                   os.path.join(tmp, "src", "myplugin"))
        out = self._run(tmp)
        self.assertEqual(
            out.returncode, 1,
            "the release-cut carve-out swallowed the #540 break: v1.0.0 EXISTS "
            "and lacks src/myplugin, so this pair must still be rejected")


class DevinManifestIsJudgedInTheTreeTest(MarketplaceConsistencyTest):
    """The Devin check must not be switched off by the entry's ref-relative path.

    `.devin-plugin/plugin.json` is a working-tree file; `path` is not a
    working-tree location. Resolving the first under the second made the whole
    check vanish the moment the two diverged -- which is the steady state
    between a directory move and the release cut that publishes it, and
    exactly where this repo sat: entry pinned at plugins/acs@v0.4.9, tree
    holding src/acs, so `rel + "/.devin-plugin"` named nothing and a wrong
    version passed green. The remedy is the one .github/scripts/
    plugin_source_dirs.py already exists to serve: ask the tree.

    Both halves are pinned, because a guard nobody tests failing is how this
    got in: the mismatch must fail, and the matching pair must still pass.
    """

    def _moved_tree_fixture(self, devin_json):
        """Entry pinned at the OLD path at a real tag; plugin moved in the tree."""
        entry = {
            "name": "myplugin",
            "source": {"source": "git-subdir", "url": "https://example.com/repo.git",
                       "path": "plugins/myplugin", "ref": "v1.0.0"},
        }
        tmp = self._make_fixture(
            entry,
            plugin_path="plugins/myplugin",
            plugin_json={"name": "myplugin", "version": "1.0.0"},
            devin_json=devin_json,
        )
        os.renames(os.path.join(tmp, "plugins", "myplugin"),
                   os.path.join(tmp, "src", "myplugin"))
        return tmp

    def test_version_mismatch_is_caught_although_path_is_ref_relative(self):
        tmp = self._moved_tree_fixture({"name": "myplugin", "version": "9.9.9"})
        out = self._run(tmp)
        self.assertEqual(
            out.returncode, 1,
            "the Devin version guard validated nothing: the tree holds "
            "src/myplugin at 9.9.9 against a Claude manifest at 1.0.0, while "
            "the entry's `path` (plugins/myplugin, ref-relative) names no "
            "directory in this tree. stdout=%r" % out.stdout)
        self.assertIn("one shared version", out.stderr)

    def test_name_mismatch_is_caught_in_the_same_shape(self):
        tmp = self._moved_tree_fixture({"name": "notmyplugin", "version": "1.0.0"})
        out = self._run(tmp)
        self.assertEqual(out.returncode, 1, "stdout=%r" % out.stdout)
        self.assertIn("notmyplugin", out.stderr)

    def test_the_matching_pair_still_passes(self):
        """The other half: same moved tree, versions and names agree."""
        tmp = self._moved_tree_fixture({"name": "myplugin", "version": "1.0.0"})
        out = self._run(tmp)
        self.assertEqual(out.returncode, 0, "stderr=%r" % out.stderr)
        self.assertIn("OK", out.stdout)
