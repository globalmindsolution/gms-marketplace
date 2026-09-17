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

Then on 2026-09-17 the same entry broke a second way, and this file did not
catch it either:

    Failed to clone repository for git-subdir source: warning: Could not find
    remote branch e7e633f1804... to clone.
    fatal: Remote branch e7e633f1804... not found in upstream origin

The 2026-09-16 fix pinned `ref` to a COMMIT on the default branch, which makes
`path` resolve — `git cat-file -t <sha>:src/acs` is happy, so every assertion
below passed. But the installer does not `cat-file` the ref, it CLONES with it:
`git clone --branch <ref>`, which accepts a branch or a tag and rejects a bare
SHA. Resolvable and cloneable are different properties, and only the first was
tested.

So a third constraint joins the two above: `ref` must NAME something — a branch
or a tag — never a raw SHA. Between releases that means the default branch;
`release.extra_refs` already rewrites it to `v{version}` at the cut, which is a
tag and therefore cloneable. Note there is currently no OLDER tag that would
work: `v0.4.9` predates the `plugins/acs` -> `src/acs` move, so `src/acs` does
not exist there. Until v0.5.0 is tagged, the default branch is the only value
that satisfies all three.

Offline and free: it asks the local clone, reading the ref through
`origin/<ref>` when the bare name is absent -- which is the normal case in a
`pull_request` checkout, detached at the merge ref with no local branches.
Where neither name resolves the check skips with that reason rather than
failing on an absence it cannot distinguish from a defect. `ci.yml` checks
out at `fetch-depth: 0` so that absence does not arise there; at the default
depth 1 it arose on every run, which is how #540 shipped green.
"""

import json
import os
import re
import subprocess
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MANIFEST = os.path.join(REPO_ROOT, ".claude-plugin", "marketplace.json")
SETTINGS = os.path.join(REPO_ROOT, ".acs", "settings.json")


def git(*args):
    return subprocess.run(["git"] + list(args), cwd=REPO_ROOT,
                          capture_output=True, text=True)


def resolve(ref):
    """The name to read `ref` through in THIS clone, or None if absent.

    A `pull_request` checkout is detached at the merge ref and carries no
    local branches, so a `ref` of `main` fails `rev-parse` while
    `origin/main` resolves -- and git does not DWIM the one into the other.
    Skipping on that absence made the checks below inert in CI on exactly
    the value the manifest holds between releases.
    """
    for name in (ref, "origin/" + ref):
        if git("rev-parse", "--verify", "--quiet", name + "^{commit}").returncode == 0:
            return name
    return None


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
                readable = resolve(ref)
                if readable is None:
                    self.skipTest("ref %r not present in this clone (shallow fetch?)" % ref)
                probe = git("cat-file", "-t", "%s:%s" % (readable, path))
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
                readable = resolve(ref)
                if readable is None:
                    self.skipTest("ref %r not present in this clone" % ref)
                target = "%s:%s/.claude-plugin/plugin.json" % (readable, path)
                self.assertEqual(
                    git("cat-file", "-e", target).returncode, 0,
                    "%s: no plugin.json at %s — the subdirectory resolves but "
                    "carries no plugin" % (name, target))


class TheRefMustBeCloneableTest(unittest.TestCase):
    """`git clone --branch <ref>` takes a branch or a tag, never a bare SHA.

    This is the property the 2026-09-17 install failure exercised. It is
    separate from "path resolves at ref": a commit SHA resolves fine and
    clones not at all, which is exactly how the previous fix passed every
    check in this file and still could not be installed.
    """

    #: A ref of 7-40 hex characters is a commit SHA by shape. Branch and tag
    #: names in this repo are not (`main`, `v0.4.9` both carry non-hex
    #: characters), so the shape alone decides it.
    SHA = re.compile(r"\A[0-9a-f]{7,40}\Z")

    def test_no_entry_pins_a_bare_sha(self):
        """Lexical on purpose: no git call, so it holds in a SHALLOW clone.

        The first draft of this test asked git to confirm the ref resolved
        before calling it a SHA. That inverted the guard exactly where it
        matters: `ci.yml` checks out at the default `fetch-depth: 1`, where
        `rev-parse` on an arbitrary SHA FAILS, the `and` chain short-circuits,
        and the assertion passes on the very value it exists to reject. A
        guard that cannot fail in CI is the mistake this whole file is about,
        so the check that carries the weight asks no questions it might not
        get an answer to.
        """
        for name, source in entries():
            ref = source.get("ref")
            with self.subTest(plugin=name):
                if not ref:
                    continue  # tracks the default branch; nothing to clone by name
                self.assertIsNone(
                    self.SHA.fullmatch(ref),
                    "%s: ref %r is a bare commit SHA. It resolves — every check "
                    "above passes — but the installer runs `git clone --branch "
                    "%s` and git refuses: 'Remote branch %s not found in "
                    "upstream origin'. Use a branch name (the default branch "
                    "between releases) or a tag." % (name, ref, ref, ref))

    def test_the_ref_names_a_branch_or_a_tag(self):
        """Best-effort companion: needs a clone that HAS the refs, so it skips
        in CI's shallow checkout. The lexical test above is the load-bearing
        one; this adds the case a SHA-shaped check cannot see — a ref that is
        neither hex nor an existing branch or tag, e.g. a deleted branch."""
        for name, source in entries():
            ref = source.get("ref")
            with self.subTest(plugin=name):
                if not ref:
                    continue
                is_branch = git("show-ref", "--verify", "--quiet",
                                "refs/heads/" + ref).returncode == 0
                is_tag = git("show-ref", "--verify", "--quiet",
                             "refs/tags/" + ref).returncode == 0
                is_remote = git("show-ref", "--verify", "--quiet",
                                "refs/remotes/origin/" + ref).returncode == 0
                if not (is_branch or is_tag or is_remote):
                    if resolve(ref) is None:
                        self.skipTest(
                            "ref %r not present in this clone (shallow fetch?)" % ref)
                self.assertTrue(
                    is_branch or is_tag or is_remote,
                    "%s: ref %r is not a branch or a tag in this clone, so "
                    "`git clone --branch %s` cannot resolve it."
                    % (name, ref, ref))


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
