"""MAR-114 — load_settings e2e->suites normalization + validate_settings suites
loop (AC-3, AC-4).

Behavioral unittest against acs_lib.load_settings/validate_settings directly.
AC-3 (MANDATORY, design R2): a configured e2e resolves into suites["e2e"]
byte-identically to the pre-change e2e block; a materially-different
suites.e2e/e2e collision surfaces a non-fatal warning and never raises
GateError (e2e wins); a no-e2e fixture invents no suites["e2e"].
AC-4: validate_settings validates every suites entry with the same per-entry
rules as e2e; DEFAULT_SETTINGS["suites"] == {}.

The helper module lives beside acs_lib.py; add that scripts dir to sys.path,
mirroring tests/acs/test_metrics_aggregate.py.

Run:  python3 -m unittest tests.acs.test_mar114_suites_normalization -v
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

_SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "plugins", "acs", "hooks", "scripts",
)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import acs_lib as lib  # noqa: E402  (after sys.path mutation)


def make_repo(tmp_root, settings):
    """A git-initialized repo dir with a project .acs/settings.json seeded
    with `settings`, so checkout_root/main_repo_root resolve (mirrors
    tests/acs/test_acs_plugin.py's git-init pattern for load_settings tests)."""
    repo = tempfile.mkdtemp(dir=tmp_root)
    subprocess.run(["git", "init", "-q", repo], check=True)
    os.makedirs(os.path.join(repo, ".acs"), exist_ok=True)
    with open(os.path.join(repo, ".acs", "settings.json"), "w", encoding="utf-8") as fh:
        json.dump(settings, fh)
    return repo


class Mar114NormalizationCase(unittest.TestCase):
    """AC-3: load_settings normalizes a present e2e into suites["e2e"]."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-mar114-norm-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_byte_identical_back_compat_no_suites_configured(self):
        """A settings fixture with only e2e (no suites key at all) resolves
        to result['suites']['e2e'] == result['e2e'] field-for-field (R2)."""
        repo = make_repo(self.tmp, {
            "e2e": {
                "command": "npm run test:e2e",
                "setup": "docker compose up -d --wait",
                "teardown": "docker compose down",
                "per_iteration": False,
            },
        })
        merged, _found = lib.load_settings(repo)
        self.assertIn("suites", merged)
        self.assertIn("e2e", merged["suites"])
        self.assertEqual(
            merged["suites"]["e2e"], merged["e2e"],
            "resolved suites['e2e'] must be byte-identical to the e2e block (AC-3/R2)",
        )
        self.assertEqual(merged["suites"]["e2e"]["command"], "npm run test:e2e")
        self.assertEqual(merged["suites"]["e2e"]["setup"], "docker compose up -d --wait")
        self.assertEqual(merged["suites"]["e2e"]["teardown"], "docker compose down")
        self.assertEqual(merged["suites"]["e2e"]["per_iteration"], False)

    def test_collision_surfaces_warning_not_gate_error_e2e_wins(self):
        """Both e2e and a hand-authored suites.e2e configured with materially
        different commands: load_settings must NOT raise, must surface a
        non-fatal warning, and e2e must win (overwrite suites['e2e'])."""
        repo = make_repo(self.tmp, {
            "e2e": {"command": "npm run test:e2e"},
            "suites": {"e2e": {"command": "make e2e"}},
        })
        try:
            merged, _found = lib.load_settings(repo)
        except lib.GateError as exc:
            self.fail("load_settings must never raise GateError on an e2e/suites.e2e collision (AC-3): %s" % exc)
        self.assertEqual(
            merged["suites"]["e2e"]["command"], "npm run test:e2e",
            "e2e must win over a separately-authored suites.e2e on collision (AC-3, design.md:409-410)",
        )
        warnings = merged.get("_settings_warnings", [])
        self.assertTrue(
            warnings,
            "a materially-different e2e/suites.e2e collision must surface a non-fatal warning (AC-3)",
        )
        self.assertTrue(
            any("e2e" in w and "suites" in w for w in warnings),
            "the collision warning must mention both e2e and suites: %r" % (warnings,),
        )

    def test_no_collision_when_suites_e2e_matches_e2e(self):
        """When suites.e2e is hand-authored identically to e2e (no material
        difference), no warning is required (not a collision)."""
        repo = make_repo(self.tmp, {
            "e2e": {"command": "npm run test:e2e"},
            "suites": {"e2e": {"command": "npm run test:e2e"}},
        })
        merged, _found = lib.load_settings(repo)
        self.assertEqual(merged["suites"]["e2e"]["command"], "npm run test:e2e")

    def test_no_e2e_configured_invents_no_suites_e2e(self):
        """With no e2e key present, load_settings must not invent a
        suites['e2e'] entry; other named suites configured directly are left
        untouched."""
        repo = make_repo(self.tmp, {
            "suites": {"lint": {"command": "npm run lint"}},
        })
        merged, _found = lib.load_settings(repo)
        self.assertNotIn("e2e", merged["suites"])
        self.assertEqual(merged["suites"]["lint"]["command"], "npm run lint")

    def test_no_e2e_no_suites_configured_stays_empty(self):
        """With neither e2e nor suites configured, suites resolves to the
        DEFAULT_SETTINGS empty-object seed."""
        repo = make_repo(self.tmp, {"ticket_prefix": "SHOP"})
        merged, _found = lib.load_settings(repo)
        self.assertEqual(merged["suites"], {})


class Mar114ValidateSettingsSuitesCase(unittest.TestCase):
    """AC-4: validate_settings validates every suites entry with the same
    per-entry rules as e2e; DEFAULT_SETTINGS['suites'] == {}."""

    def _base(self, **overrides):
        settings = {"test_coverage_percent": 90}
        settings.update(overrides)
        return settings

    def test_default_settings_has_suites_empty_object(self):
        self.assertEqual(lib.DEFAULT_SETTINGS["suites"], {})

    def test_accepts_well_formed_single_suite(self):
        settings = self._base(suites={"lint": {"command": "npm run lint"}})
        try:
            lib.validate_settings(settings, os.getcwd(), require_workspace=False)
        except lib.GateError as exc:
            self.fail("validate_settings must accept a well-formed suites entry: %s" % exc)

    def test_accepts_multiple_suites_with_optional_fields(self):
        settings = self._base(suites={
            "lint": {"command": "npm run lint"},
            "e2e": {
                "command": "npm run test:e2e",
                "setup": "docker compose up -d",
                "teardown": "docker compose down",
                "per_iteration": True,
            },
        })
        try:
            lib.validate_settings(settings, os.getcwd(), require_workspace=False)
        except lib.GateError as exc:
            self.fail("validate_settings must accept multiple well-formed suites entries: %s" % exc)

    def test_rejects_non_dict_suites(self):
        settings = self._base(suites=["not", "a", "dict"])
        with self.assertRaises(lib.GateError):
            lib.validate_settings(settings, os.getcwd(), require_workspace=False)

    def test_rejects_missing_command(self):
        settings = self._base(suites={"lint": {"setup": "npm ci"}})
        with self.assertRaises(lib.GateError) as ctx:
            lib.validate_settings(settings, os.getcwd(), require_workspace=False)
        self.assertIn("lint", str(ctx.exception))

    def test_rejects_empty_command(self):
        settings = self._base(suites={"lint": {"command": "   "}})
        with self.assertRaises(lib.GateError) as ctx:
            lib.validate_settings(settings, os.getcwd(), require_workspace=False)
        self.assertIn("lint", str(ctx.exception))

    def test_rejects_non_string_setup(self):
        settings = self._base(suites={"lint": {"command": "npm run lint", "setup": 123}})
        with self.assertRaises(lib.GateError) as ctx:
            lib.validate_settings(settings, os.getcwd(), require_workspace=False)
        self.assertIn("lint", str(ctx.exception))
        self.assertIn("setup", str(ctx.exception))

    def test_rejects_empty_teardown(self):
        settings = self._base(suites={"lint": {"command": "npm run lint", "teardown": ""}})
        with self.assertRaises(lib.GateError) as ctx:
            lib.validate_settings(settings, os.getcwd(), require_workspace=False)
        self.assertIn("lint", str(ctx.exception))
        self.assertIn("teardown", str(ctx.exception))

    def test_rejects_non_boolean_per_iteration(self):
        settings = self._base(suites={"lint": {"command": "npm run lint", "per_iteration": "yes"}})
        with self.assertRaises(lib.GateError) as ctx:
            lib.validate_settings(settings, os.getcwd(), require_workspace=False)
        self.assertIn("lint", str(ctx.exception))
        self.assertIn("per_iteration", str(ctx.exception))

    def test_existing_e2e_block_still_validates_independently(self):
        """A malformed raw e2e key still raises independently of the suites
        loop — regression-proof that the retained e2e block was not removed
        or folded into the suites loop."""
        settings = self._base(e2e={"setup": "docker compose up"})  # missing command
        with self.assertRaises(lib.GateError) as ctx:
            lib.validate_settings(settings, os.getcwd(), require_workspace=False)
        self.assertIn("e2e", str(ctx.exception))

    def test_well_formed_e2e_and_suites_both_pass(self):
        settings = self._base(
            e2e={"command": "npm run test:e2e"},
            suites={"lint": {"command": "npm run lint"}},
        )
        try:
            lib.validate_settings(settings, os.getcwd(), require_workspace=False)
        except lib.GateError as exc:
            self.fail("validate_settings must accept well-formed e2e + suites together: %s" % exc)


if __name__ == "__main__":
    unittest.main()
