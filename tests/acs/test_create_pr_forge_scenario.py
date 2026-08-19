"""MAR-68 -- the create_pr_forge scenario's decision logic: META/registration
(AC-1), the seeding sequence driven only through ForgeSandbox's public
methods (AC-2), PR facts sourced only from gh_json -- never session prose
(AC-3), the post-exit teardown assertion (AC-4), and the no-forge-target skip
contract (AC-5).

Every fixture is a fake ForgeSandbox substituted via mock.patch.object on the
scenario module's own bound names -- `claude` and `gh` are never invoked, and
no local git repo is cloned. Stdlib-only; no network, no `claude` process.

Run:  python3 -m unittest tests.acs.test_create_pr_forge_scenario -v
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sys.path.insert(0, os.path.join(REPO_ROOT, "evals", "acs"))
import harness                      # noqa: E402  (path-inserted, same resolution run_evals.py uses)
import scenarios                    # noqa: E402  (the package; resolves s08's `from harness import ...`)

s08 = scenarios.s08_create_pr_forge

DEFAULT_TITLE = "[FORGEAAAAAAAA-1] Forge smoke: trivial doc touch"

DEFAULT_PR_JSON = {
    "number": 42,
    "title": DEFAULT_TITLE,
    "body": (
        "## Summary\ntext\n\n## Ticket\ntext\n\n## Changes\ntext\n\n"
        "## Test plan\ntext\n"
    ),
    "labels": [{"name": "ACS"}],
    "state": "OPEN",
    "headRefName": "task/FORGEAAAAAAAA-1-forge-smoke",
    "baseRefName": "main",
}

DEFAULT_RUN_SKILL_ENVELOPE = {
    "ok": True, "is_error": False, "result": "done",
    "cost_usd": 0.2, "num_turns": 5, "raw": "{}", "stderr": "", "returncode": 0,
}


def make_fake_forge(run_skill_envelope=None, gh_json_value=None,
                    settings=None, fail_teardown=False):
    """Build a ForgeSandbox stand-in class, for
    mock.patch.object(s08, "ForgeSandbox", <returned class>). No clone, no
    `gh`, no `claude` -- every driving method is a canned, recorded stub."""
    run_skill_envelope = (dict(DEFAULT_RUN_SKILL_ENVELOPE) if run_skill_envelope is None
                          else dict(run_skill_envelope))
    gh_json_value = DEFAULT_PR_JSON if gh_json_value is None else gh_json_value
    settings = {} if settings is None else settings

    class _FakeForge:
        instances = []  # every constructed instance, for construction-count assertions

        def __init__(self, *args, **kwargs):
            self.init_args = (args, kwargs)
            self.run_script_calls = []
            self.run_skill_calls = []
            self.gh_json_calls = []
            self.commit_file_calls = []
            self.teardown_errors = []
            self.exited = False
            self._ticket_seq = 0
            type(self).instances.append(self)

        def __enter__(self):
            self.tmp = tempfile.mkdtemp(prefix="acs-fake-forge-")
            self.repo = os.path.join(self.tmp, "repo")
            os.makedirs(os.path.join(self.repo, ".acs"), exist_ok=True)
            with open(os.path.join(self.repo, ".acs", "settings.json"), "w",
                     encoding="utf-8") as fh:
                json.dump(settings, fh)
            self.run_id = "AAAAAAAA"
            self.prefix = "FORGE" + self.run_id
            self.owner_name = "acme/acs-eval"
            return self

        def __exit__(self, *exc):
            self.exited = True
            if fail_teardown:
                self.teardown_errors.append("simulated teardown failure")
            shutil.rmtree(self.tmp, ignore_errors=True)
            return False

        def run_script(self, script, *args, stdin=None):
            self.run_script_calls.append((script, args, stdin))
            if script == "new-ticket.py":
                self._ticket_seq += 1
                tid = "%s-%d" % (self.prefix, self._ticket_seq)
                return subprocess.CompletedProcess(
                    [], 0, stdout=json.dumps({"ticket_id": tid}), stderr="")
            if script == "pr-conventions.py":
                return subprocess.CompletedProcess([], 0, stdout=DEFAULT_TITLE + "\n", stderr="")
            return subprocess.CompletedProcess([], 0, stdout="", stderr="")

        def run_skill(self, prompt, **kwargs):
            self.run_skill_calls.append((prompt, kwargs))
            return dict(run_skill_envelope)

        def gh_json(self, *args):
            self.gh_json_calls.append(args)
            return dict(gh_json_value) if gh_json_value is not None else None

        def commit_file(self, rel, content, message, branch=None):
            self.commit_file_calls.append((rel, content, message, branch))

    return _FakeForge


class NeverConstructedForge:
    """A ForgeSandbox stand-in that only records how many times it was
    constructed -- T5.1 asserts this stays at 0 on the skip path."""
    calls = 0

    def __init__(self, *args, **kwargs):
        type(self).calls += 1

    def __enter__(self):
        raise AssertionError("NeverConstructedForge.__enter__ must not run")

    def __exit__(self, *exc):
        return False


class MetaAndRegistrationTest(unittest.TestCase):

    def test_meta_declares_the_forge_tier_scenario(self):
        self.assertEqual(s08.META["name"], "create_pr_forge")
        self.assertEqual(s08.META["tier"], "forge")
        self.assertTrue(s08.META.get("goal"))
        self.assertTrue(s08.META.get("summary"))

    def test_scenario_is_registered_in_the_run_order(self):
        self.assertIn(s08, scenarios.SCENARIOS)
        for mod in scenarios.SCENARIOS:
            self.assertTrue(hasattr(mod, "META"))
            self.assertTrue(hasattr(mod, "run"))


class DrivingSequenceTest(unittest.TestCase):
    """T2.4 -- the seeding sequence, the single paid call, and R-9 branch reach."""

    def test_run_drives_create_pr_for_the_seeded_ticket_on_the_run_branch(self):
        Fake = make_fake_forge()
        with mock.patch.object(s08, "resolve_forge_target", return_value="acme/acs-eval"), \
             mock.patch.object(s08, "ForgeSandbox", Fake):
            check = s08.run()

        self.assertTrue(check.passed, check.results)
        sb = Fake.instances[-1]

        # (a) exactly one run_skill call
        self.assertEqual(len(sb.run_skill_calls), 1)
        prompt, _ = sb.run_skill_calls[0]

        # (b) the prompt names /acs:create-pr and the seeded ticket id
        new_ticket_calls = [c for c in sb.run_script_calls if c[0] == "new-ticket.py"]
        self.assertEqual(len(new_ticket_calls), 1)
        seeded_ticket_id = "%s-1" % sb.prefix  # first allocation under this run's prefix
        self.assertIn("/acs:create-pr", prompt)
        self.assertIn(seeded_ticket_id, prompt)

        # (c) the seeded ticket branch embeds sb.run_id (teardown reach, R-9)
        branch_calls = [c for c in sb.commit_file_calls if c[3]]
        self.assertEqual(len(branch_calls), 1)
        seeded_branch = branch_calls[0][3]
        self.assertIn(sb.run_id, seeded_branch)
        self.assertIn(seeded_ticket_id, seeded_branch)

        # (d) both gate halves seeded: code AND docs-sync
        scripts_run = [c[0] for c in sb.run_script_calls]
        self.assertIn("new-ticket.py", scripts_run)
        self.assertEqual(
            scripts_run.count("skill-start.py"), 2,
            "expected skill-start.py to run twice (code, docs-sync): %r" % scripts_run)
        self.assertIn("post-code.py", scripts_run)
        self.assertIn("post-docs-sync.py", scripts_run)

        skill_start_calls = [c for c in sb.run_script_calls if c[0] == "skill-start.py"]
        skill_args = [c[1] for c in skill_start_calls]
        self.assertTrue(any("code" in a for a in skill_args))
        self.assertTrue(any("docs-sync" in a for a in skill_args))

        post_code_calls = [c for c in sb.run_script_calls if c[0] == "post-code.py"]
        self.assertEqual(len(post_code_calls), 1)
        post_code_stdin = json.loads(post_code_calls[0][2])
        self.assertIs(post_code_stdin["states"]["verifier_passed"], True)
        self.assertTrue(post_code_stdin["states"].get("branch"))


class NeverFakeGreenTest(unittest.TestCase):
    """T3.2 -- lying session prose vs a truthful API disagreement must FAIL."""

    def test_pr_facts_come_from_the_github_api_not_the_session_prose(self):
        lying_envelope = dict(DEFAULT_RUN_SKILL_ENVELOPE)
        lying_envelope["result"] = "Opened PR #999 with the ACS label and all sections"
        pr_missing_label = dict(DEFAULT_PR_JSON)
        pr_missing_label["labels"] = []

        Fake = make_fake_forge(run_skill_envelope=lying_envelope,
                               gh_json_value=pr_missing_label)
        with mock.patch.object(s08, "resolve_forge_target", return_value="acme/acs-eval"), \
             mock.patch.object(s08, "ForgeSandbox", Fake):
            check = s08.run()

        self.assertFalse(
            check.passed,
            "the lying session prose must not make a label-less PR pass")


class TitleLabelSectionAssertionsTest(unittest.TestCase):
    """T3.3 -- each fact fails independently on an API mismatch; all-correct passes."""

    def test_all_correct_fixture_passes(self):
        Fake = make_fake_forge()
        with mock.patch.object(s08, "resolve_forge_target", return_value="acme/acs-eval"), \
             mock.patch.object(s08, "ForgeSandbox", Fake):
            check = s08.run()
        self.assertTrue(check.passed, check.results)

    def test_title_label_and_section_assertions_each_fail_on_api_mismatch(self):
        cases = [
            ("wrong title", {"title": "[WRONG-1] not the rendered title"}),
            ("missing ACS label", {"labels": []}),
            ("missing Test plan section", {
                "body": "## Summary\ntext\n\n## Ticket\ntext\n\n## Changes\ntext\n"}),
        ]
        for label, overrides in cases:
            with self.subTest(case=label):
                pr = dict(DEFAULT_PR_JSON)
                pr.update(overrides)
                Fake = make_fake_forge(gh_json_value=pr)
                with mock.patch.object(s08, "resolve_forge_target",
                                       return_value="acme/acs-eval"), \
                     mock.patch.object(s08, "ForgeSandbox", Fake):
                    check = s08.run()
                self.assertFalse(check.passed, "%s must fail the Check" % label)


class TeardownAssertionTest(unittest.TestCase):
    """T4.1 -- the teardown check runs (and can only see teardown_errors) after
    __exit__ has actually run."""

    def _teardown_label_and_result(self, check):
        matches = [(label, ok) for label, ok, _ in check.results if "teardown" in label.lower()]
        self.assertEqual(len(matches), 1, check.results)
        return matches[0]

    def test_teardown_check_passes_when_clean(self):
        Fake = make_fake_forge(fail_teardown=False)
        with mock.patch.object(s08, "resolve_forge_target", return_value="acme/acs-eval"), \
             mock.patch.object(s08, "ForgeSandbox", Fake):
            check = s08.run()
        _, ok = self._teardown_label_and_result(check)
        self.assertTrue(ok)
        self.assertTrue(Fake.instances[-1].exited)

    def test_teardown_check_fails_when_teardown_left_errors(self):
        Fake = make_fake_forge(fail_teardown=True)
        with mock.patch.object(s08, "resolve_forge_target", return_value="acme/acs-eval"), \
             mock.patch.object(s08, "ForgeSandbox", Fake):
            check = s08.run()
        _, ok = self._teardown_label_and_result(check)
        self.assertFalse(ok)
        self.assertFalse(check.passed)
        # the error only exists because __exit__ appended it -- proves the
        # check was evaluated using post-exit state, not a pre-exit snapshot.
        self.assertTrue(Fake.instances[-1].exited)
        self.assertEqual(Fake.instances[-1].teardown_errors, ["simulated teardown failure"])


class SkipContractTest(unittest.TestCase):
    """T5.1, T5.2 -- ForgeConfigError before any construction; clean, documented skip."""

    def test_run_skips_with_a_documented_reason_when_no_forge_target_is_configured(self):
        NeverConstructedForge.calls = 0
        with mock.patch.object(s08, "resolve_forge_target",
                               side_effect=harness.ForgeConfigError("nope, not configured")), \
             mock.patch.object(s08, "ForgeSandbox", NeverConstructedForge):
            check = s08.run()

        self.assertTrue(check.passed)
        self.assertEqual(len(check.results), 1)
        label, ok, _ = check.results[0]
        self.assertTrue(ok)
        self.assertTrue(label.startswith("skipped"))
        self.assertIn("evals.forge_repo", label)
        self.assertIn("ACS_FORGE_REPO", label)
        self.assertEqual(NeverConstructedForge.calls, 0,
                         "ForgeSandbox must never be constructed on the skip path")

    def test_skip_path_records_no_pr_label_or_section_assertion(self):
        NeverConstructedForge.calls = 0
        with mock.patch.object(s08, "resolve_forge_target",
                               side_effect=harness.ForgeConfigError("nope")), \
             mock.patch.object(s08, "ForgeSandbox", NeverConstructedForge):
            check = s08.run()

        joined = " ".join(label for label, _, _ in check.results)
        for forbidden in ("PR", "label", "Summary", "Ticket", "Changes", "Test plan"):
            self.assertNotIn(forbidden, joined)


class RealRunnerSkipTest(unittest.TestCase):
    """T5.3 -- a real, $0, no-claude run of the shipped runner: a clean skip
    when no forge target is configured. Guarded against both config sources
    (env var and settings file) so it self-skips rather than spending money
    on any host where a forge target is actually configured; see
    RealRunnerSkipGuardTest immediately below, which proves the guard fires
    on each source and hard-codes this method's name to do so."""

    def test_runner_reports_the_scenario_as_a_clean_skip_when_unconfigured(self):
        env_target = os.environ.get("ACS_FORGE_REPO")
        if env_target:
            self.skipTest(
                "ACS_FORGE_REPO=%r is configured in the parent environment; "
                "this test only proves the unconfigured-repo skip path and "
                "must not spend money against a real forge target"
                % (env_target,)
            )
        try:
            settings_target = harness._forge_repo_from_settings(harness.REPO_ROOT)
        except Exception as exc:
            self.skipTest(
                "could not read evals.forge_repo from .acs/settings.json or "
                ".acs/settings.local.json (%r); a target may be configured "
                "and this test cannot prove otherwise" % (exc,)
            )
        if settings_target:
            self.skipTest(
                "evals.forge_repo=%r is configured in .acs/settings.json or "
                ".acs/settings.local.json; this test only proves the "
                "unconfigured-repo skip path and must not spend money "
                "against a real forge target" % (settings_target,)
            )

        env = dict(os.environ)
        env.pop("ACS_FORGE_REPO", None)
        env["ACS_EVAL_SOURCE"] = "1"
        result = subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "evals", "run_evals.py"),
             "--plugin", "acs", "--only", "create_pr_forge"],
            capture_output=True, text=True, cwd=REPO_ROOT, env=env,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("[PASS]", result.stdout)
        self.assertNotIn("FAILED", result.stdout)


class RealRunnerSkipGuardTest(unittest.TestCase):
    """T6.1/T6.2 -- proves RealRunnerSkipTest's own guard fires on each of
    the two forge-target config sources. Coupled by name to
    test_runner_reports_the_scenario_as_a_clean_skip_when_unconfigured
    above; renaming that method breaks this test with a confusing error."""

    INNER_TEST_NAME = "test_runner_reports_the_scenario_as_a_clean_skip_when_unconfigured"

    def test_skip_test_skips_when_a_forge_target_is_configured_in_settings(self):
        with mock.patch.object(harness, "_forge_repo_from_settings",
                               return_value="acme/acs-eval"):
            result = unittest.TestResult()
            RealRunnerSkipTest(self.INNER_TEST_NAME).run(result)

        self.assertEqual(len(result.skipped), 1)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.failures, [])
        self.assertIn("evals.forge_repo", result.skipped[0][1])

    def test_skip_test_skips_when_the_forge_target_env_var_is_set(self):
        with mock.patch.dict(os.environ, {"ACS_FORGE_REPO": "acme/acs-eval"}):
            result = unittest.TestResult()
            RealRunnerSkipTest(self.INNER_TEST_NAME).run(result)

        self.assertEqual(len(result.skipped), 1)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.failures, [])
        self.assertIn("ACS_FORGE_REPO", result.skipped[0][1])


if __name__ == "__main__":
    unittest.main()
