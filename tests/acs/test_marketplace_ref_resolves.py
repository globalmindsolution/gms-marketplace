#!/usr/bin/env python3
"""The marketplace entry must RESOLVE: an install has to find a plugin there.

This is the one property an install actually exercises, and nothing checked
it. On 2026-09-16 `acs@gms-marketplace` could not be installed at all:

    Failed to install plugin "acs@gms-marketplace": Subdirectory 'src/acs' not
    found in repository ... (ref: v0.4.9)

The entry was a `git-subdir` object carrying its own `url`, `path` and `ref`.
The plugin tree moved from `plugins/acs` to `src/acs` and the manifest's
`path` moved with it, but its `ref` still named tag `v0.4.9`, where the plugin
is at `plugins/acs`. Each field was individually correct and the pair was
unresolvable. `test_marketplace_consistency.py` checks name and version
agreement between the entry and `plugin.json`; it builds its own fixtures, so
it never asks whether this repo's advertised source resolves.

Two readers, two models, and the entry had to satisfy both. `ci.yml`'s
marketplace validator resolved `path` against the WORKING TREE and required a
plugin.json there; the installer resolved it AT `ref`. Moving the tree without
moving the ref left no value of `path` that worked for both — pointing it at
the released tree fixed the install and broke CI on the same day.

Then on 2026-09-17 the same entry broke a second way:

    Failed to clone repository for git-subdir source: warning: Could not find
    remote branch e7e633f1804... to clone.
    fatal: Remote branch e7e633f1804... not found in upstream origin

The 2026-09-16 fix pinned `ref` to a COMMIT on the default branch, which makes
`path` resolve — `git cat-file -t <sha>:src/acs` is happy. But the installer
does not `cat-file` the ref, it CLONES with it: `git clone --branch <ref>`,
which takes a branch or a tag and rejects a bare SHA. Resolvable and cloneable
are different properties, and only the first was tested.

WHAT CHANGED. The acs entry is now the relative string `./plugins/acs`, and
that REMOVES the dual-reader failure mode rather than re-testing it. A
relative source resolves from the marketplace checkout itself — the very tree
both readers already have in front of them — so there is no second coordinate
to fall out of step with the first: no `path`/`ref` pair, and nothing for a
directory move to make individually-correct-but-jointly-unresolvable. Pinning
moved up a level, from the plugin to the marketplace
(`claude plugin marketplace add <repo>@v0.5.0`), where one ref decides both
questions at once. The release cut no longer rewrites the source at all (see
`TheReleaseCutLeavesTheSourceAloneTest`).

So the property re-cut for that shape is the one that still guards an install:
the string names a directory that EXISTS in the working tree, that directory
carries `.claude-plugin/plugin.json`, and the entry round-trips — the name in
the manifest is the name the catalog advertises.

The at-ref and cloneable checks stay for the object shape, because a future
plugin may well be fetched from elsewhere and the two outages above are what
that shape costs when nobody looks. While every entry is relative those checks
iterate nothing, which is exactly the inert-guard mistake this whole file is
about — so `EveryEntryIsCheckedBySomethingTest` pins that no entry escapes
both, and fails loudly on a source shape neither one understands.

Offline and free: the ref checks ask the local clone, reading the ref through
`origin/<ref>` when the bare name is absent -- which is the normal case in a
`pull_request` checkout, detached at the merge ref with no local branches.
Where neither name resolves the check skips with that reason rather than
failing on an absence it cannot distinguish from a defect. `ci.yml` checks
out at `fetch-depth: 0` so that absence does not arise there; at the default
depth 1 it arose on every run, which is how #540 shipped green.
"""

import glob
import json
import os
import re
import subprocess
import sys
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MANIFEST = os.path.join(REPO_ROOT, ".claude-plugin", "marketplace.json")
SETTINGS = os.path.join(REPO_ROOT, ".acs", "settings.json")

#: Object sources fetched from somewhere else entirely. Nothing about them is
#: checkable from this clone, so they are named here rather than falling
#: through a shape check that would then be examining nothing.
REMOTE_SOURCES = {"github", "url", "npm"}


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


def manifest():
    with open(MANIFEST, encoding="utf-8") as fh:
        return json.load(fh)


def entries():
    """Every plugin entry in the catalog, whatever shape its source takes."""
    return list(manifest().get("plugins", []))


def relative_entries():
    """Entries whose source is a plain string: a path in THIS repository."""
    return [e for e in entries() if isinstance(e.get("source"), str)]


def pinned_entries():
    """Entries whose source is a git-subdir object carrying its own ref."""
    return [e for e in entries()
            if isinstance(e.get("source"), dict)
            and e["source"].get("source") == "git-subdir"]


def tree_path(entry):
    """Where a string source lands in this working tree, absolute.

    Mirrors what `ci.yml`'s validator does with the same value: the string is
    repo-root relative, and `metadata.pluginRoot` prefixes it unless the
    string is already explicitly rooted (`./` or `/`). Resolving it any other
    way here would re-create the two-readers problem inside the test suite.
    """
    rel = entry["source"]
    plugin_root = (manifest().get("metadata") or {}).get("pluginRoot")
    if plugin_root and not rel.startswith(("./", "/")):
        rel = os.path.join(plugin_root, rel)
    return os.path.normpath(os.path.join(REPO_ROOT, rel))


class EveryEntryIsCheckedBySomethingTest(unittest.TestCase):
    """No entry may sit in a shape that neither class below understands.

    Both shape checks loop over a filtered list, and a loop over an empty list
    passes. That is how a catalog could quietly acquire an entry nothing
    verifies -- the same inert-guard failure that let #540 ship green. This
    test is the one that cannot go quiet: it reads the WHOLE catalog.
    """

    def test_the_catalog_is_not_empty(self):
        self.assertTrue(entries(), "marketplace.json advertises no plugins at all")

    def test_no_entry_escapes_both_shape_checks(self):
        for entry in entries():
            src = entry.get("source")
            with self.subTest(plugin=entry.get("name")):
                if isinstance(src, str):
                    continue  # working-tree property, checked below
                self.assertIsInstance(
                    src, dict,
                    "source must be a relative path string or a source object")
                kind = src.get("source")
                self.assertIn(
                    kind, {"git-subdir"} | REMOTE_SOURCES,
                    "unknown source kind %r: no test in this file knows how to "
                    "decide whether it installs" % (kind,))
                if kind == "git-subdir":
                    self.assertTrue(src.get("path"),
                                    "a git-subdir source declares no path")


class RelativeSourceResolvesInTheWorkingTreeTest(unittest.TestCase):
    """The property a relative source has instead of path-at-ref.

    A string source carries no ref and no path field, so "does `path` exist at
    `ref`" is not a question that can be asked of it -- and it no longer needs
    asking, because the install and CI read the same tree. What is left to get
    wrong is the tree itself: a moved or deleted directory, or one that holds
    no plugin. That is what these three check.
    """

    def test_the_source_names_a_directory_in_this_tree(self):
        for entry in relative_entries():
            with self.subTest(plugin=entry.get("name")):
                where = tree_path(entry)
                self.assertTrue(
                    os.path.isdir(where),
                    "%s: source '%s' names no directory in this tree (%s). An "
                    "install resolves the source from the marketplace checkout, "
                    "so it fails on exactly this absence."
                    % (entry.get("name"), entry["source"], where))

    def test_that_directory_carries_a_plugin_manifest(self):
        for entry in relative_entries():
            with self.subTest(plugin=entry.get("name")):
                target = os.path.join(tree_path(entry), ".claude-plugin", "plugin.json")
                self.assertTrue(
                    os.path.exists(target),
                    "%s: no plugin.json at %s — the directory resolves but "
                    "carries no plugin" % (entry.get("name"), target))

    def test_the_entry_round_trips_with_that_manifest(self):
        """The catalog's name is the plugin's name, and so is its version.

        Round-tripping is what makes the two halves one entry rather than two
        independent facts -- the shape of defect that made the entry
        individually-correct and jointly-broken in the first place.
        """
        for entry in relative_entries():
            with self.subTest(plugin=entry.get("name")):
                target = os.path.join(tree_path(entry), ".claude-plugin", "plugin.json")
                if not os.path.exists(target):
                    continue  # already failed, loudly, in the test above
                with open(target, encoding="utf-8") as fh:
                    plugin = json.load(fh)
                self.assertEqual(
                    plugin.get("name"), entry.get("name"),
                    "%s: plugin.json at %s names '%s'. The catalog entry and the "
                    "plugin it resolves to must agree, or an install advertises "
                    "one plugin and delivers another."
                    % (entry.get("name"), target, plugin.get("name")))
                if entry.get("version") is not None:
                    self.assertEqual(
                        entry["version"], plugin.get("version"),
                        "%s: entry version '%s' != plugin.json version '%s' — "
                        "plugin.json wins silently, so the catalog would lie."
                        % (entry.get("name"), entry["version"], plugin.get("version")))


class AdvertisedPathResolvesAtAdvertisedRefTest(unittest.TestCase):
    """The object-source property, kept for whatever is fetched from elsewhere.

    Inert while every entry is relative; `EveryEntryIsCheckedBySomethingTest`
    is what stops that from being a silence nobody notices.
    """

    def test_every_git_subdir_entry_resolves(self):
        for entry in pinned_entries():
            source = entry["source"]
            name, path, ref = entry.get("name"), source.get("path"), source.get("ref")
            with self.subTest(plugin=name):
                self.assertTrue(path, "%s declares no path" % name)
                # `path` is judged AT `ref` and nowhere else. It used to be
                # asserted against the working tree here too, mirroring
                # ci.yml -- and that pair of demands is unsatisfiable for the
                # whole window between a directory move and the cut that
                # publishes it, which is how 2026-09-16 broke: satisfying the
                # tree reader broke the installer, and every later fix traded
                # one for the other. ci.yml no longer asks that question (it
                # resolves at ref, and the lint steps discover the source tree
                # via .github/scripts/plugin_source_dirs.py), so neither does
                # this test.
                if not ref:
                    # No ref means the entry tracks the ref the marketplace
                    # itself was installed at, which is this tree.
                    self.assertTrue(
                        os.path.isdir(os.path.join(REPO_ROOT, path)),
                        "%s: unpinned git-subdir source resolves against this "
                        "tree, and '%s' is not there" % (name, path))
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
        for entry in pinned_entries():
            source = entry["source"]
            name, path, ref = entry.get("name"), source.get("path"), source.get("ref")
            with self.subTest(plugin=name):
                if not ref:
                    self.skipTest("entry tracks the marketplace's own ref")
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
    check in this file and still could not be installed. Only an object
    source can hold a ref, so this reaches nothing while every entry is
    relative -- which is the point of retiring that shape.
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
        for entry in pinned_entries():
            ref = entry["source"].get("ref")
            name = entry.get("name")
            with self.subTest(plugin=name):
                if not ref:
                    continue  # tracks the marketplace ref; nothing to clone by name
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
        for entry in pinned_entries():
            ref = entry["source"].get("ref")
            name = entry.get("name")
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


class TheReleaseCutLeavesTheSourceAloneTest(unittest.TestCase):
    """The cut used to rewrite the source; with a string source it must not.

    While the entry was a git-subdir object, `release.extra_refs` rewrote
    `source/ref` and `source/path` together, because a tag cut that moved one
    without the other is precisely the 2026-09-16 break. A relative string has
    neither field: an extra_ref that still set `source/ref` would replace the
    string with an object — rebuilding the two-coordinate shape the move
    retired, and advertising a `path` and `ref` nobody checked. So the cut's
    only business with this entry is the version, and it reaches that through
    `version_locations`, in the plugin manifest the entry resolves to.
    """

    @classmethod
    def setUpClass(cls):
        with open(SETTINGS, encoding="utf-8") as fh:
            cls.release = json.load(fh).get("release") or {}

    def _marketplace_extra_refs(self):
        return [e for e in (self.release.get("extra_refs") or [])
                if e.get("file") == ".claude-plugin/marketplace.json"]

    def test_no_extra_ref_writes_into_a_string_source(self):
        relative = {e.get("name") for e in relative_entries()}
        for extra in self._marketplace_extra_refs():
            selector = extra.get("selector") or {}
            target = (selector.get("match") or {}).get("name")
            with self.subTest(sets=selector.get("set"), plugin=target):
                if target not in relative:
                    continue
                self.assertFalse(
                    (selector.get("set") or "").startswith("source"),
                    "the cut sets '%s' on '%s', whose source is the relative "
                    "string '%s'. A string has no such field: writing one "
                    "turns the entry back into an object with a path and a ref "
                    "to keep in sync, which is the shape that made the plugin "
                    "uninstallable twice."
                    % (selector.get("set"), target,
                       next(e["source"] for e in relative_entries()
                            if e.get("name") == target)))

    def test_the_cut_bumps_the_manifest_the_entry_resolves_to(self):
        """The successor to "the cut moves both fields together".

        One coordinate is left, and the cut still has to hit it: the version
        in the plugin.json that the advertised directory holds. A cut that
        bumps the marketplace and not that file ships a catalog whose entry
        resolves to a stale plugin.
        """
        files = {loc if isinstance(loc, str) else loc.get("file")
                 for loc in (self.release.get("version_locations") or [])}
        self.assertIn(".claude-plugin/marketplace.json", files,
                      "the cut must bump the marketplace's own version")
        for entry in relative_entries():
            rel = os.path.relpath(tree_path(entry), REPO_ROOT)
            expected = os.path.join(rel, ".claude-plugin", "plugin.json")
            with self.subTest(plugin=entry.get("name")):
                self.assertIn(
                    expected, files,
                    "the cut does not bump %s, the plugin manifest the '%s' "
                    "entry resolves to" % (expected, entry.get("name")))


class TheLintStepsFindASourceTreeTest(unittest.TestCase):
    """ci.yml's per-plugin lint steps must have something to lint.

    Those five steps (schemas, settings, XSD, hook byte-compile, skill
    frontmatter) used to locate the plugin by reading `path` out of
    marketplace.json and `continue` when the directory was absent. Once
    `path` became ref-relative that was every run: five checks reporting
    success while validating nothing. They now ask
    .github/scripts/plugin_source_dirs.py instead, and it exits non-zero on
    an empty answer -- this pins that the answer is not empty, and that the
    directory it names really carries a plugin.
    """

    def test_discovery_names_a_real_plugin_tree(self):
        sys.path.insert(0, os.path.join(REPO_ROOT, ".github", "scripts"))
        from plugin_source_dirs import plugin_dirs

        dirs = plugin_dirs(REPO_ROOT)
        self.assertTrue(
            dirs,
            "no plugin source directory in the working tree — ci.yml's five "
            "per-plugin lint steps would each skip and still report success")
        for rel in dirs:
            with self.subTest(plugin_dir=rel):
                self.assertTrue(os.path.exists(os.path.join(
                    REPO_ROOT, rel, ".claude-plugin", "plugin.json")))
                self.assertTrue(
                    glob.glob(os.path.join(REPO_ROOT, rel, "skills", "*", "SKILL.md")),
                    "%s carries no skills — the frontmatter check would pass "
                    "over an empty set" % rel)


if __name__ == "__main__":
    unittest.main(verbosity=2)
