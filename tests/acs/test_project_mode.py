"""Tests for /acs:project's mode detection: the declared bootstrap-vs-standardize
predicate the design-phase entry-point fold gives the new umbrella.

`project_mode(settings, checkout_root)` is the `fanout_batches` precedent applied
to the two project legs: the decision is DECLARED data plus a disk read, never
skill prose, so the umbrella can state its reasoning and a test can pin it. The
mechanism is the same settings-path + sentinel-file pair the doc-bootstrap
constants use (`DOC_BOOTSTRAP_SETTINGS_KEY` / `DOC_BOOTSTRAP_SENTINEL`), read
through the same presence primitive -- not a second mechanism.

Run:  python3 -m unittest tests.acs.test_project_mode -v
"""

import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
sys.path.insert(0, SCRIPTS)

import acs_lib as lib  # noqa: E402

#: A fully configured settings document, so a bootstrap verdict can never be an
#: artifact of an unset path.
SETTINGS = {
    "architecture_path": "docs/architecture",
    "quality_path": "docs/quality",
    "operations_path": "docs/operations",
    "principles_path": "docs/principles",
    "standards_path": "docs/standards",
}


def _touch(path):
    os.makedirs(os.path.dirname(path) or path, exist_ok=True)
    open(path, "w").close()


class TempRootCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="acs-project-mode-")
        self.addCleanup(shutil.rmtree, self.root, True)

    def mode(self, settings=None):
        return lib.project_mode(settings if settings is not None else SETTINGS, self.root)

    def present_names(self, result):
        return sorted(row["name"] for row in result["evidence"] if row["present"])


class DeclaredEvidenceTableTest(unittest.TestCase):
    """The evidence is a declared table in the same shape as the doc-bootstrap
    pair -- two maps over one key set, resolved by lookup, never string-built."""

    def test_the_two_maps_share_one_key_set(self):
        self.assertEqual(set(lib.PROJECT_MODE_SETTINGS_KEY),
                         set(lib.PROJECT_MODE_SENTINEL))
        self.assertTrue(lib.PROJECT_MODE_SENTINEL, "the evidence table must not be empty")

    def test_the_two_modes_are_declared(self):
        self.assertEqual(lib.PROJECT_MODES, ("bootstrap", "standardize"))

    def test_every_sentinel_is_a_relative_path(self):
        for name, sentinel in lib.PROJECT_MODE_SENTINEL.items():
            with self.subTest(name=name):
                self.assertFalse(os.path.isabs(sentinel), sentinel)
                self.assertTrue(sentinel.strip(), name)

    def test_every_settings_key_is_a_real_settings_key_or_the_checkout_root(self):
        for name, key in lib.PROJECT_MODE_SETTINGS_KEY.items():
            with self.subTest(name=name):
                if key is not None:
                    self.assertIn(key, lib.DEFAULT_SETTINGS,
                                  "%s names a settings key that does not exist" % name)

    def test_the_doc_set_predicate_reads_the_same_primitive(self):
        """One mechanism, two callers: doc_set_present_on_disk and project_mode
        both resolve settings-path + sentinel through _sentinel_present."""
        self.assertTrue(callable(lib.setup_helpers._sentinel_present))


class EmptyRepoIsBootstrapTest(TempRootCase):
    def test_an_empty_repo_is_bootstrap(self):
        self.assertEqual(self.mode()["mode"], "bootstrap")

    def test_a_docs_only_repo_is_still_bootstrap(self):
        """The greenfield case: the architecture doc set create-project reads
        exists, but no project does yet."""
        _touch(os.path.join(self.root, "docs/architecture/hld/tech-stack.md"))
        _touch(os.path.join(self.root, "docs/architecture/hld/project-structure.md"))
        _touch(os.path.join(self.root, "README.md"))
        _touch(os.path.join(self.root, ".acs/settings.json"))
        self.assertEqual(self.mode()["mode"], "bootstrap")

    def test_the_bootstrap_evidence_reports_every_declared_row_as_absent(self):
        result = self.mode()
        self.assertEqual(sorted(row["name"] for row in result["evidence"]),
                         sorted(lib.PROJECT_MODE_SENTINEL))
        self.assertEqual(self.present_names(result), [])
        self.assertEqual(result["present"], [])
        self.assertEqual(sorted(result["absent"]), sorted(lib.PROJECT_MODE_SENTINEL))

    def test_the_bootstrap_reason_states_what_was_checked(self):
        reason = self.mode()["reason"]
        self.assertIn("no project", reason.lower())
        for sentinel in lib.PROJECT_MODE_SENTINEL.values():
            self.assertIn(sentinel, reason)


class ExistingProjectIsStandardizeTest(TempRootCase):
    def test_every_sentinel_present_is_standardize(self):
        for name, sentinel in lib.PROJECT_MODE_SENTINEL.items():
            key = lib.PROJECT_MODE_SETTINGS_KEY[name]
            base = "" if key is None else SETTINGS[key]
            _touch(os.path.join(self.root, base, sentinel))
        result = self.mode()
        self.assertEqual(result["mode"], "standardize")
        self.assertEqual(self.present_names(result), sorted(lib.PROJECT_MODE_SENTINEL))
        self.assertEqual(result["absent"], [])

    def test_the_standardize_evidence_carries_the_path_that_decided_it(self):
        _touch(os.path.join(self.root, "pyproject.toml"))
        result = self.mode()
        rows = {row["name"]: row for row in result["evidence"]}
        hit = [row for row in rows.values() if row["present"]]
        self.assertEqual(len(hit), 1, hit)
        self.assertEqual(hit[0]["path"], "pyproject.toml")
        self.assertIn("pyproject.toml", result["reason"])


class PartialEvidenceResolvesDeterministicallyTest(TempRootCase):
    """The partial case is pinned, not left to judgement: ANY single piece of
    declared evidence means the repo already has a project, so the mode is
    standardize -- the additive, idempotent leg. Failing the other way would
    point create-project at a repo its own greenfield scan refuses."""

    def test_one_sentinel_of_many_is_enough_for_standardize(self):
        for name, sentinel in sorted(lib.PROJECT_MODE_SENTINEL.items()):
            with self.subTest(name=name):
                root = tempfile.mkdtemp(prefix="acs-project-mode-one-")
                self.addCleanup(shutil.rmtree, root, True)
                key = lib.PROJECT_MODE_SETTINGS_KEY[name]
                base = "" if key is None else SETTINGS[key]
                _touch(os.path.join(root, base, sentinel))
                result = lib.project_mode(SETTINGS, root)
                self.assertEqual(result["mode"], "standardize")
                self.assertEqual(result["present"], [name])

    def test_the_partial_verdict_reports_both_sides(self):
        _touch(os.path.join(self.root, "package.json"))
        result = self.mode()
        self.assertEqual(result["mode"], "standardize")
        self.assertEqual(result["present"], ["node-packaging"])
        self.assertNotIn("node-packaging", result["absent"])
        self.assertEqual(len(result["present"]) + len(result["absent"]),
                         len(lib.PROJECT_MODE_SENTINEL))

    def test_the_same_tree_answers_the_same_way_twice(self):
        _touch(os.path.join(self.root, "go.mod"))
        self.assertEqual(self.mode(), self.mode())

    def test_evidence_rows_come_back_in_declared_name_order(self):
        result = self.mode()
        names = [row["name"] for row in result["evidence"]]
        self.assertEqual(names, sorted(lib.PROJECT_MODE_SENTINEL))


class SettingsPathedEvidenceTest(TempRootCase):
    """The settings-path half of the mechanism, exercised through a row declared
    by this test: every shipped row is checkout-root-relative today, but the
    column exists so a future row under a configured path is a data change.
    An unconfigured key must read ABSENT -- never widen to the checkout root."""

    ROW = "test-only-configured-evidence"

    def _with_row(self, key):
        return (mock.patch.dict(lib.PROJECT_MODE_SETTINGS_KEY, {self.ROW: key}),
                mock.patch.dict(lib.PROJECT_MODE_SENTINEL, {self.ROW: "marker.md"}))

    def test_a_configured_path_with_its_sentinel_is_present(self):
        _touch(os.path.join(self.root, "docs/quality/marker.md"))
        keys, sentinels = self._with_row("quality_path")
        with keys, sentinels:
            result = self.mode()
        self.assertEqual(result["mode"], "standardize")
        self.assertIn(self.ROW, result["present"])
        row = [r for r in result["evidence"] if r["name"] == self.ROW][0]
        self.assertEqual(row["path"], os.path.join("docs/quality", "marker.md"))

    def test_an_unset_settings_key_is_absent_not_checkout_root_relative(self):
        _touch(os.path.join(self.root, "marker.md"))
        keys, sentinels = self._with_row("quality_path")
        with keys, sentinels:
            result = self.mode(dict(SETTINGS, quality_path=None))
        self.assertEqual(result["mode"], "bootstrap")
        row = [r for r in result["evidence"] if r["name"] == self.ROW][0]
        self.assertFalse(row["present"])
        self.assertIsNone(row["path"])

    def test_a_missing_settings_document_is_absent_never_a_crash(self):
        keys, sentinels = self._with_row("quality_path")
        with keys, sentinels:
            result = lib.project_mode({}, self.root)
        self.assertEqual(result["mode"], "bootstrap")


class MissingCheckoutRootTest(TempRootCase):
    def test_a_checkout_root_that_does_not_exist_is_bootstrap(self):
        missing = os.path.join(self.root, "does-not-exist")
        self.assertEqual(lib.project_mode(SETTINGS, missing)["mode"], "bootstrap")


if __name__ == "__main__":
    unittest.main()
