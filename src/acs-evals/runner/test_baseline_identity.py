#!/usr/bin/env python3
"""A version string cannot identify the build the goldens describe.

An unreleased source tree ships the same `plugin.json` version as the release
it supersedes -- both say 0.4.9 today -- so the old check,
`build.version == manifest.recorded_against`, read TRUE for the source the
dataset was recorded against AND for the released build it is 70 cases ahead
of. The off-baseline warning was silent in both directions, and `report.py`
rendered "recorded against acs 0.4.9" over a run that graded neither.

Run me: python3 runner/test_baseline_identity.py
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import fingerprint, skill_surface  # noqa: E402
from run_golden import baseline_mismatch  # noqa: E402


def make_build(skills):
    """A throwaway plugin root: {name: user_only} -> directory."""
    root = tempfile.mkdtemp()
    for name, user_only in skills.items():
        d = os.path.join(root, "skills", name)
        os.makedirs(d)
        head = "---\nname: %s\ndescription: x\n%s---\n" % (
            name, "disable-model-invocation: true\n" if user_only else "")
        with open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8") as fh:
            fh.write(head)
    return root


class _Build:
    def __init__(self, version, fp):
        self.version, self.fingerprint = version, fp


class SurfaceFingerprintTest(unittest.TestCase):

    def test_the_same_surface_hashes_the_same(self):
        a = make_build({"code": False, "ship": False})
        b = make_build({"ship": False, "code": False})   # different order
        self.assertEqual(fingerprint(a), fingerprint(b))

    def test_an_added_skill_changes_it(self):
        a = make_build({"code": False})
        b = make_build({"code": False, "project": False})
        self.assertNotEqual(fingerprint(a), fingerprint(b))

    def test_flipping_a_skill_to_user_only_changes_it(self):
        """The ADR 0091 fold, exactly: same skills, different invocability."""
        a = make_build({"create-quality": False})
        b = make_build({"create-quality": True})
        self.assertNotEqual(fingerprint(a), fingerprint(b))
        self.assertIn("create-quality:invocable", skill_surface(a))
        self.assertIn("create-quality:user-only", skill_surface(b))

    def test_a_root_with_no_skills_has_no_fingerprint(self):
        """None, not a hash of nothing -- an absent surface is not a match."""
        self.assertIsNone(fingerprint(tempfile.mkdtemp()))


class BaselineMismatchTest(unittest.TestCase):

    MANIFEST = {"recorded_against": "0.4.9",
                "recorded_against_fingerprint": "aaaa1111"}

    def test_same_version_and_surface_is_the_baseline(self):
        self.assertIsNone(
            baseline_mismatch(_Build("0.4.9", "aaaa1111"), self.MANIFEST))

    def test_a_different_version_mismatches(self):
        why = baseline_mismatch(_Build("0.4.8", "aaaa1111"), self.MANIFEST)
        self.assertIn("0.4.8", why)

    def test_the_same_version_with_a_different_surface_mismatches(self):
        """THE case the old check missed: source and its predecessor release."""
        why = baseline_mismatch(_Build("0.4.9", "bbbb2222"), self.MANIFEST)
        self.assertIsNotNone(why, "a build sharing the version but not the "
                                  "surface must not read as the baseline")
        self.assertIn("same version string, different build", why)
        self.assertIn("bbbb2222", why)
        self.assertIn("aaaa1111", why)

    def test_a_manifest_without_a_fingerprint_falls_back_to_version(self):
        """Older manifests keep working, at the old precision."""
        old = {"recorded_against": "0.4.9"}
        self.assertIsNone(baseline_mismatch(_Build("0.4.9", "bbbb2222"), old))
        self.assertIsNotNone(baseline_mismatch(_Build("0.4.8", "x"), old))

    def test_a_build_with_no_fingerprint_is_not_forced_to_mismatch(self):
        self.assertIsNone(baseline_mismatch(_Build("0.4.9", None), self.MANIFEST))


class TheShippedManifestNamesTheSourceItPinsTest(unittest.TestCase):

    def test_the_recorded_fingerprint_is_this_checkout_s_plugin(self):
        import json
        here = os.path.dirname(os.path.abspath(__file__))
        manifest = json.load(open(os.path.join(here, os.pardir, "dataset",
                                               "manifest.json")))
        source = os.path.join(here, os.pardir, os.pardir, os.pardir,
                              "plugins", "acs")
        if not os.path.isdir(source):
            self.skipTest("plugin source is not a sibling of this checkout")
        self.assertEqual(manifest.get("recorded_against_fingerprint"),
                         fingerprint(source),
                         "the goldens are recorded from this tree, so the "
                         "manifest must name its surface; re-record or stamp it")


if __name__ == "__main__":
    unittest.main()
