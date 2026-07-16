"""Unit tests for the e2e CI runner /acs:init Step 7f ships into consumer repos.

run-e2e.py (plugins/acs/templates/ci/run-e2e.py) runs in the consumer's CI
with ZERO acs dependencies — stdlib only. It reads the e2e command from the
committed `.acs/settings.json`, resolving it from EITHER `suites["e2e"]` OR
the raw `e2e` alias (the load-time normalization `acs_lib.load_settings`
performs for a Claude Code session does not happen in CI, so the runner
replicates the fallback itself). It runs optional `setup`, then `command`,
then optional `teardown` (always, in a `finally` block — a non-zero teardown
never flips a green `command` result to red), and exits with `command`'s
status (or 1 on a `setup` failure / missing settings / no resolvable command).
These tests drive it as a subprocess in throwaway repos, mirroring
test_run_tests.py's pattern exactly.

Run:  python3 -m unittest discover -s tests -v
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNNER = os.path.join(REPO_ROOT, "plugins", "acs", "templates", "ci", "run-e2e.py")


class RunE2eCase(unittest.TestCase):
    def run_in(self, settings=None):
        """Run the runner in a fresh throwaway repo; return (CompletedProcess, tmp_dir).
        tmp_dir is cleaned up automatically after the test."""
        tmp = tempfile.mkdtemp(prefix="acs-rune2e-")
        self.addCleanup(shutil.rmtree, tmp, True)
        if settings is not None:
            os.makedirs(os.path.join(tmp, ".acs"))
            with open(os.path.join(tmp, ".acs", "settings.json"), "w") as fh:
                json.dump(settings, fh)
        out = subprocess.run([sys.executable, RUNNER], cwd=tmp,
                             capture_output=True, text=True)
        return out, tmp

    # --- AC-2: green/red, fail-closed ---

    def test_green_command_exits_0(self):
        out, _ = self.run_in({"suites": {"e2e": {"command": "true"}}})
        self.assertEqual(out.returncode, 0, out.stderr)

    def test_red_command_exits_1(self):
        out, _ = self.run_in({"suites": {"e2e": {"command": "exit 3"}}})
        self.assertEqual(out.returncode, 1)
        self.assertIn("failed", out.stderr)

    # --- AC-2: dual-shape command resolution ---

    def test_resolves_via_suites_e2e(self):
        out, _ = self.run_in({"suites": {"e2e": {"command": 'test "$X" = "1"'}}})
        # command doesn't set X; proves the suites-shape resolves and RUNS
        # the command (red because $X is unset, not because resolution failed).
        self.assertEqual(out.returncode, 1, out.stderr)

    def test_resolves_via_raw_e2e_alias(self):
        # No `suites` key at all — the exact dogfood-repo shape.
        out, _ = self.run_in({"e2e": {"command": "true"}})
        self.assertEqual(out.returncode, 0, out.stderr)

    def test_suites_null_falls_back_to_e2e_alias(self):
        out, _ = self.run_in({"suites": None, "e2e": {"command": "true"}})
        self.assertEqual(out.returncode, 0, out.stderr)

    # --- AC-1: runner's own no-command guard (opt-in invariant, runner half) ---

    def test_missing_command_exits_1(self):
        out, _ = self.run_in({"suites": {}})
        self.assertEqual(out.returncode, 1)
        self.assertIn("e2e command", out.stderr)

    def test_missing_settings_file_exits_1(self):
        out, _ = self.run_in(None)
        self.assertEqual(out.returncode, 1)
        self.assertIn("settings.json", out.stderr)

    # --- runner contract: setup before command ---

    def test_setup_runs_before_command(self):
        out, _ = self.run_in({"suites": {"e2e": {
            "setup": "echo ok > marker",
            "command": "test -f marker",
        }}})
        self.assertEqual(out.returncode, 0, out.stderr)

    # --- teardown semantics (design.md:459-468) ---

    def test_setup_failure_still_attempts_teardown_then_exits_1(self):
        out, tmp = self.run_in({"suites": {"e2e": {
            "setup": "exit 4",
            "command": "true",
            "teardown": "echo done > teardown-marker",
        }}})
        self.assertEqual(out.returncode, 1, out.stderr)
        self.assertTrue(os.path.isfile(os.path.join(tmp, "teardown-marker")))

    def test_teardown_always_runs_on_success(self):
        out, tmp = self.run_in({"suites": {"e2e": {
            "command": "true",
            "teardown": "echo done > teardown-marker",
        }}})
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertTrue(os.path.isfile(os.path.join(tmp, "teardown-marker")))

    def test_teardown_always_runs_on_failure(self):
        out, tmp = self.run_in({"suites": {"e2e": {
            "command": "exit 2",
            "teardown": "echo done > teardown-marker",
        }}})
        self.assertEqual(out.returncode, 1)
        self.assertTrue(os.path.isfile(os.path.join(tmp, "teardown-marker")))

    def test_nonzero_teardown_does_not_flip_green_to_red(self):
        out, _ = self.run_in({"suites": {"e2e": {
            "command": "exit 0",
            "teardown": "exit 5",
        }}})
        self.assertEqual(out.returncode, 0, out.stderr)


if __name__ == "__main__":
    unittest.main()
