#!/usr/bin/env python3
"""The marketplace entry must resolve: `path` has to EXIST at `ref`.

This is the one property an install actually exercises, and nothing checked
it. On 2026-09-16 `acs@gms-marketplace` could not be installed at all:

    Failed to install plugin "acs@gms-marketplace": Subdirectory 'src/acs' not
    found in repository ... (ref: v0.4.9)

The plugin tree moved from `plugins/acs` to `src/acs` and the manifest's
`path` moved with it, but its `ref` still named tag `v0.4.9`, where the plugin
is at `plugins/acs`. Each field was individually correct and the pair was
unresolvable. `test_marketplace_consistency.py` checks name and version
agreement between the entry and `plugin.json`; it builds its own fixtures, so
it never asks git whether this repo's advertised pair resolves.

Two readers, two models, and the entry must satisfy both. `ci.yml`'s
marketplace validator resolves `path` against the WORKING TREE and requires a
plugin.json there; the installer resolves it at `ref`. Moving the tree without
moving the ref leaves no value of `path` that works for both — pointing it at
the released tree fixed the install and broke CI on the same day.

So `path` follows the working tree, and `ref` is pinned to a commit on the
default branch where that path exists. The release cut replaces the SHA with
the new tag and re-asserts the path, together (`release.extra_refs` in
`.acs/settings.json` sets `source/ref` and `source/path`).

Offline and free: it asks the local clone. Where the ref is not present (a
shallow CI clone with no tags) the check skips with that reason rather than
failing on an absence it cannot distinguish from a defect.
"""

import json
import os
import subprocess
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MANIFEST = os.path.join(REPO_ROOT, ".claude-plugin", "marketplace.json")
SETTINGS = os.path.join(REPO_ROOT, ".acs", "settings.json")


def git(*args):
    return subprocess.run(["git"] + list(args), cwd=REPO_ROOT,
                          capture_output=True, text=True)


def entries():
    with open(MANIFEST, encoding="utf-8") as fh:
        doc = json.load(fh)
    out = []
    for plugin in doc.get("plugins", []):
        source = plugin.get("source")
        if isinstance(source, dict) and source.get("source") == "git-subdir":
            out.append((plugin["name"], source))
    return out


class AdvertisedPathResolvesAtAdvertisedRefTest(unittest.TestCase):

    def test_every_git_subdir_entry_resolves(self):
        found = entries()
        self.assertTrue(found, "no git-subdir plugin entries to check")
        for name, source in found:
            path = source.get("path")
            ref = source.get("ref")
            with self.subTest(plugin=name):
                self.assertTrue(path, "%s declares no path" % name)
                # Two readers, two models, and the manifest must satisfy both.
                # ci.yml's validator resolves `path` against the WORKING TREE
                # and requires a plugin.json there; the installer resolves it
                # at `ref`. With the tree moved and the ref stale, no value of
                # `path` satisfies both, which is how fixing one broke the
                # other on 2026-09-16.
                self.assertTrue(
                    os.path.isdir(os.path.join(REPO_ROOT, path)),
                    "%s: path %r does not exist in the working tree — ci.yml's "
                    "marketplace validator resolves it there and fails with "
                    "'has no plugin.json at %s/.claude-plugin/plugin.json'"
                    % (name, path, path))
                if not ref:
                    # No ref means the marketplace tracks the default branch,
                    # and the working-tree check above is the whole of it.
                    continue
                if git("rev-parse", "--verify", "--quiet", ref + "^{commit}").returncode != 0:
                    self.skipTest("ref %r not present in this clone (shallow fetch?)" % ref)
                probe = git("cat-file", "-t", "%s:%s" % (ref, path))
                self.assertEqual(
                    probe.returncode, 0,
                    "%s: '%s' does not exist at ref '%s' — an install of this "
                    "entry fails with exactly that message. Either the ref or "
                    "the path is stale; the manifest must describe the last "
                    "RELEASED tree." % (name, path, ref))
                self.assertEqual(
                    probe.stdout.strip(), "tree",
                    "%s: '%s' at ref '%s' is not a directory" % (name, path, ref))

    def test_the_plugin_manifest_is_present_at_that_path_and_ref(self):
        for name, source in entries():
            path, ref = source.get("path"), source.get("ref")
            with self.subTest(plugin=name):
                if not ref:
                    self.skipTest("entry tracks the default branch")
                if git("rev-parse", "--verify", "--quiet", ref + "^{commit}").returncode != 0:
                    self.skipTest("ref %r not present in this clone" % ref)
                target = "%s:%s/.claude-plugin/plugin.json" % (ref, path)
                self.assertEqual(
                    git("cat-file", "-e", target).returncode, 0,
                    "%s: no plugin.json at %s — the subdirectory resolves but "
                    "carries no plugin" % (name, target))


class TheCutMovesBothFieldsTogetherTest(unittest.TestCase):
    """The move that broke this is only safe if the release rewrites both."""

    @classmethod
    def setUpClass(cls):
        with open(SETTINGS, encoding="utf-8") as fh:
            cls.release = json.load(fh).get("release") or {}

    def test_extra_refs_rewrite_the_acs_ref_and_path(self):
        targets = {}
        for entry in self.release.get("extra_refs") or []:
            if entry.get("file") != ".claude-plugin/marketplace.json":
                continue
            selector = entry.get("selector") or {}
            if (selector.get("match") or {}).get("name") != "acs":
                continue
            targets[selector.get("set")] = entry.get("value_format")
        self.assertIn("source/ref", targets,
                      "the cut must re-point the marketplace ref at the new tag")
        self.assertIn("source/path", targets,
                      "the cut must also re-point the marketplace path: the "
                      "plugin tree moved to src/acs, so a tag cut without this "
                      "advertises a path that does not exist at it")
        self.assertEqual(targets["source/ref"], "v{version}")
        self.assertEqual(targets["source/path"], "src/acs")

    def test_the_source_tree_the_cut_will_point_at_exists_today(self):
        self.assertTrue(os.path.isdir(os.path.join(REPO_ROOT, "src", "acs")),
                        "the cut rewrites path to src/acs; it must exist")


if __name__ == "__main__":
    unittest.main(verbosity=2)
