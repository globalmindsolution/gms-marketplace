"""Self-test for scripts/dev_install.py.

Every case runs against a throwaway `--cache-root`, so the suite never touches
a real Claude install. Pure filesystem work: no `claude`, no network, no cost.

    python3 -m unittest tests.acs.test_dev_install -v
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))

import dev_install as di  # noqa: E402


class TreeHashTest(unittest.TestCase):
    """The version has one job: change whenever the plugin does."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="acs-tree-")
        self.addCleanup(shutil.rmtree, self.dir, True)
        os.makedirs(os.path.join(self.dir, "skills", "code"))
        self._write("skills/code/SKILL.md", "body")
        self._write("README.md", "readme")

    def _write(self, rel, text):
        path = os.path.join(self.dir, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def test_identical_content_hashes_identically(self):
        first = di.tree_hash(self.dir)
        self.assertEqual(first, di.tree_hash(self.dir))

    def test_a_changed_byte_changes_the_hash(self):
        before = di.tree_hash(self.dir)
        self._write("skills/code/SKILL.md", "body!")
        self.assertNotEqual(before, di.tree_hash(self.dir))

    def test_a_rename_changes_the_hash(self):
        before = di.tree_hash(self.dir)
        os.rename(os.path.join(self.dir, "README.md"),
                  os.path.join(self.dir, "READ-ME.md"))
        self.assertNotEqual(before, di.tree_hash(self.dir),
                            "path is part of the digest, so a rename counts")

    def test_a_new_file_changes_the_hash(self):
        before = di.tree_hash(self.dir)
        self._write("skills/code/extra.md", "")
        self.assertNotEqual(before, di.tree_hash(self.dir))

    def test_bytecode_and_caches_are_ignored(self):
        before = di.tree_hash(self.dir)
        self._write("__pycache__/x.pyc", "junk")
        self._write("skills/code/x.pyc", "junk")
        self.assertEqual(before, di.tree_hash(self.dir),
                         "a stray .pyc must not mint a new version")

    def test_the_version_cannot_collide_with_a_release(self):
        v = di.dev_version(self.dir)
        self.assertTrue(v.startswith("0.4.10-dev."), v)
        self.assertTrue(di.is_dev(v))
        for release in ("0.4.9", "0.4.10", "1.0.0"):
            self.assertNotEqual(v, release)
            self.assertFalse(di.is_dev(release))


class InstallTest(unittest.TestCase):
    """Against a throwaway cache root, never a real one."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="acs-cache-")
        self.addCleanup(shutil.rmtree, self.root, True)
        self.registry_path = os.path.join(self.root, "installed_plugins.json")

    def _registry(self):
        with open(self.registry_path, encoding="utf-8") as fh:
            return json.load(fh)

    def _entries(self):
        return self._registry()["plugins"][di.KEY]

    def _seed_release(self, version="0.4.9"):
        path = os.path.join(self.root, "cache", di.MARKETPLACE, di.PLUGIN, version)
        os.makedirs(path, exist_ok=True)
        with open(self.registry_path, "w", encoding="utf-8") as fh:
            json.dump({"version": 2, "plugins": {di.KEY: [
                {"scope": "user", "installPath": path, "version": version,
                 "gitCommitSha": "deadbeef"}]}}, fh)
        return path

    def test_install_stages_the_tree_and_records_it(self):
        version, dest = di.install(self.root, quiet=True)
        self.assertTrue(os.path.isdir(os.path.join(dest, "skills")))
        self.assertEqual([e["version"] for e in self._entries()], [version])
        self.assertTrue(self._entries()[0]["devInstall"])

    def test_the_staged_copy_declares_the_dev_version(self):
        version, dest = di.install(self.root, quiet=True)
        with open(os.path.join(dest, ".claude-plugin", "plugin.json"),
                  encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["version"], version)

    def test_the_working_tree_is_never_rewritten(self):
        before = di.tree_hash(di.PLUGIN_SRC)
        di.install(self.root, quiet=True)
        self.assertEqual(before, di.tree_hash(di.PLUGIN_SRC),
                         "the version is rewritten in the STAGED copy only; "
                         "touching the tree would show up as a repo change")

    def test_reinstalling_the_same_tree_is_idempotent(self):
        v1, d1 = di.install(self.root, quiet=True)
        v2, d2 = di.install(self.root, quiet=True)
        self.assertEqual((v1, d1), (v2, d2))
        self.assertEqual(len(self._entries()), 1)

    def test_the_release_files_survive_but_it_stops_being_active(self):
        release = self._seed_release()
        version, _ = di.install(self.root, quiet=True)
        self.assertTrue(os.path.isdir(release),
                        "the released install's files must survive")
        self.assertEqual([e["version"] for e in self._entries()], [version],
                         "exactly one install may be listed, or the loader is "
                         "asked to choose between two of the same plugin")

    def test_only_one_dev_version_is_ever_installed(self):
        first, first_dest = di.install(self.root, quiet=True)
        # Pretend an older dev version is already staged.
        stale = os.path.join(self.root, "cache", di.MARKETPLACE, di.PLUGIN,
                             di.DEV_PREFIX + "000000000000")
        os.makedirs(stale, exist_ok=True)
        registry = self._registry()
        registry["plugins"][di.KEY].append(
            {"version": os.path.basename(stale), "installPath": stale})
        with open(self.registry_path, "w", encoding="utf-8") as fh:
            json.dump(registry, fh)

        again, _ = di.install(self.root, quiet=True)
        self.assertEqual(again, first)
        self.assertFalse(os.path.exists(stale), "the stale dev version must go")
        self.assertEqual([e["version"] for e in self._entries()], [first])

    def test_uninstall_removes_the_dev_version_and_restores_the_release(self):
        release = self._seed_release()
        version, dest = di.install(self.root, quiet=True)
        di.uninstall(self.root, quiet=True)
        self.assertFalse(os.path.exists(dest))
        self.assertTrue(os.path.isdir(release))
        self.assertEqual([e["version"] for e in self._entries()], ["0.4.9"])
        self.assertEqual(self._entries()[0]["gitCommitSha"], "deadbeef",
                         "the restored entry must be the original, not a rebuild")

    def test_uninstall_with_no_release_leaves_no_entry_behind(self):
        di.install(self.root, quiet=True)
        di.uninstall(self.root, quiet=True)
        self.assertNotIn(di.KEY, self._registry().get("plugins", {}))

    def test_uninstall_is_safe_to_repeat(self):
        self._seed_release()
        di.install(self.root, quiet=True)
        di.uninstall(self.root, quiet=True)
        di.uninstall(self.root, quiet=True)
        self.assertEqual([e["version"] for e in self._entries()], ["0.4.9"])

    def test_uninstall_on_a_clean_machine_does_not_explode(self):
        di.uninstall(self.root, quiet=True)
        self.assertEqual(self._registry().get("plugins", {}), {})

    def test_the_backup_key_does_not_outlive_the_dev_install(self):
        self._seed_release()
        di.install(self.root, quiet=True)
        self.assertIn("__dev_install_backup__", self._registry())
        di.uninstall(self.root, quiet=True)
        self.assertNotIn("__dev_install_backup__", self._registry())


class CliTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="acs-cli-")
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_install_then_uninstall_via_argv(self):
        self.assertEqual(di.main(["--cache-root", self.root, "--quiet"]), 0)
        # --status exists to print; --quiet governs install/uninstall only.
        self.assertEqual(di.main(["--cache-root", self.root, "--status"]), 0)
        self.assertEqual(
            di.main(["--cache-root", self.root, "--uninstall", "--quiet"]), 0)


if __name__ == "__main__":
    unittest.main()
