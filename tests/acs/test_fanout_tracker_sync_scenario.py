"""MAR-78 -- the fanout_tracker_sync eval scenario's re-grounded two-invocation
decision logic: META/registration (J1-J2), the two-`run_skill`-calls driving
sequence with only the second carrying `--fan-out` (J3), the creation run's
`children == []` guard (J4), the fan-out run's children/external assertions
(J5), the epic `external.key` stability guard across both runs (J6), the
no-forge-target skip contract (J7), and the None-safe summed cost (J8).

Every fixture is a fake `Sandbox` stand-in substituted via
`mock.patch.object` on the scenario module's own bound name -- `claude` is
never invoked, no `gh`, no network. Stdlib-only.

Run:  python3 -m unittest tests.acs.test_fanout_tracker_sync_scenario -v
"""

import os
import sys
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sys.path.insert(0, os.path.join(REPO_ROOT, "evals", "acs"))
import scenarios                    # noqa: E402  (the package; resolves s07's `from harness import ...`)

s07 = scenarios.s07_fanout_tracker_sync

DEFAULT_EPIC_EXTERNAL = {"provider": "github", "key": "900"}
DEFAULT_CHILD_EXTERNAL = {"provider": "github", "key": "901"}
DEFAULT_FAN_OUT_CHILDREN = ["EVAL-2", "EVAL-3"]

DEFAULT_RUN_SKILL_ENVELOPES = (
    {"ok": True, "is_error": False, "result": "done", "cost_usd": 0.3,
     "num_turns": 4, "raw": "{}", "stderr": "", "returncode": 0},
    {"ok": True, "is_error": False, "result": "done", "cost_usd": 0.4,
     "num_turns": 6, "raw": "{}", "stderr": "", "returncode": 0},
)


def make_fake_sandbox(run_skill_envelopes=None, creation_children=None,
                      fan_out_children=None, epic_external_before=None,
                      epic_external_after=None, child_externals=None):
    """Build a Sandbox stand-in class, for mock.patch.object(s07, "Sandbox",
    <returned class>). Stateful: ticket_json(epic, ...) returns the
    pre-fan-out epic (children == creation_children) before the second
    run_skill call, and the post-fan-out epic (children ==
    fan_out_children) after it -- so a scenario that asserts fanned-out
    children on the creation run itself fails."""
    envelopes = [dict(e) for e in (run_skill_envelopes or DEFAULT_RUN_SKILL_ENVELOPES)]
    creation_children = [] if creation_children is None else list(creation_children)
    fan_out_children = (list(DEFAULT_FAN_OUT_CHILDREN) if fan_out_children is None
                        else list(fan_out_children))
    before = (dict(DEFAULT_EPIC_EXTERNAL) if epic_external_before is None
             else (dict(epic_external_before) if epic_external_before else None))
    after = (before if epic_external_after is None
            else (dict(epic_external_after) if epic_external_after else None))
    if child_externals is None:
        child_externals = {cid: dict(DEFAULT_CHILD_EXTERNAL) for cid in fan_out_children}

    class _FakeSandbox:
        instances = []  # every constructed instance, for construction-count assertions

        def __init__(self, *args, **kwargs):
            self.init_args = (args, kwargs)
            self.run_skill_calls = []
            type(self).instances.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def run_skill(self, prompt, **kwargs):
            idx = len(self.run_skill_calls)
            self.run_skill_calls.append((prompt, kwargs))
            envelope = envelopes[idx] if idx < len(envelopes) else dict(envelopes[-1])
            return dict(envelope)

        def ticket_json(self, ticket, name):
            calls = len(self.run_skill_calls)
            if ticket == "EVAL-1":
                if calls < 2:
                    return {"type": "epic", "children": list(creation_children),
                            "external": dict(before) if before else None}
                return {"type": "epic", "children": list(fan_out_children),
                        "external": dict(after) if after else None}
            ext = child_externals.get(ticket)
            return {"external": dict(ext) if ext else None}

    return _FakeSandbox


class NeverConstructedSandbox:
    """A Sandbox stand-in that only records how many times it was
    constructed -- J7 asserts this stays at 0 on the skip path."""
    calls = 0

    def __init__(self, *args, **kwargs):
        type(self).calls += 1

    def __enter__(self):
        raise AssertionError("NeverConstructedSandbox.__enter__ must not run")

    def __exit__(self, *exc):
        return False


def _run_with_env_and_fake(fake, env_value="acme/42"):
    with mock.patch.dict(os.environ, {}, clear=False):
        if env_value is None:
            os.environ.pop("ACS_EVAL_GH_PROJECT", None)
        else:
            os.environ["ACS_EVAL_GH_PROJECT"] = env_value
        with mock.patch.object(s07, "Sandbox", fake):
            return s07.run()


class MetaAndRegistrationTest(unittest.TestCase):

    def test_meta_declares_the_forge_tier_scenario(self):
        self.assertEqual(s07.META["name"], "fanout_tracker_sync")
        self.assertEqual(s07.META["tier"], "forge")
        self.assertTrue(s07.META.get("goal"))
        self.assertTrue(s07.META.get("summary"))

    def test_scenario_is_registered_in_the_run_order(self):
        self.assertIn(s07, scenarios.SCENARIOS)
        for mod in scenarios.SCENARIOS:
            self.assertTrue(hasattr(mod, "META"))
            self.assertTrue(hasattr(mod, "run"))


class DrivingSequenceTest(unittest.TestCase):

    def test_run_drives_two_invocations_and_only_the_second_carries_the_flag(self):
        Fake = make_fake_sandbox()
        check = _run_with_env_and_fake(Fake)

        self.assertTrue(check.passed, check.results)
        sb = Fake.instances[-1]

        self.assertEqual(len(sb.run_skill_calls), 2)
        prompt1, _ = sb.run_skill_calls[0]
        prompt2, _ = sb.run_skill_calls[1]

        self.assertIn("/acs:create-ticket", prompt1)
        self.assertNotIn("--fan-out", prompt1)

        self.assertIn("--fan-out", prompt2)
        self.assertIn("EVAL-1", prompt2)


class CreationRunChildrenTest(unittest.TestCase):

    def test_creation_run_children_must_be_empty(self):
        Fake = make_fake_sandbox(creation_children=["EVAL-2", "EVAL-3"])
        check = _run_with_env_and_fake(Fake)
        self.assertFalse(check.passed, check.results)


class FanOutChildExternalTest(unittest.TestCase):

    def test_fan_out_run_children_and_child_external_are_asserted(self):
        Fake = make_fake_sandbox()
        check = _run_with_env_and_fake(Fake)
        self.assertTrue(check.passed, check.results)

        cases = [
            ("external none", {"EVAL-2": None, "EVAL-3": dict(DEFAULT_CHILD_EXTERNAL)}),
            ("wrong provider", {"EVAL-2": {"provider": "jira", "key": "1"},
                                "EVAL-3": dict(DEFAULT_CHILD_EXTERNAL)}),
            ("empty key", {"EVAL-2": {"provider": "github", "key": ""},
                           "EVAL-3": dict(DEFAULT_CHILD_EXTERNAL)}),
        ]
        for label, child_externals in cases:
            with self.subTest(case=label):
                BadFake = make_fake_sandbox(child_externals=child_externals)
                bad_check = _run_with_env_and_fake(BadFake)
                self.assertFalse(bad_check.passed, "%s must fail the Check" % label)


class EpicExternalStabilityTest(unittest.TestCase):

    def test_epic_external_key_must_not_change_across_the_two_runs(self):
        Fake = make_fake_sandbox(epic_external_after={"provider": "github", "key": "DIFFERENT"})
        check = _run_with_env_and_fake(Fake)
        self.assertFalse(check.passed, check.results)


class SkipContractTest(unittest.TestCase):

    def test_run_skips_cleanly_without_the_gh_project_env_var(self):
        NeverConstructedSandbox.calls = 0
        check = _run_with_env_and_fake(NeverConstructedSandbox, env_value=None)

        self.assertTrue(check.passed)
        self.assertEqual(len(check.results), 1)
        label, ok, _ = check.results[0]
        self.assertTrue(ok)
        self.assertTrue(label.startswith("skipped"))
        self.assertIn("ACS_EVAL_GH_PROJECT", label)
        self.assertEqual(NeverConstructedSandbox.calls, 0,
                         "Sandbox must never be constructed on the skip path")


class CostTest(unittest.TestCase):

    def test_cost_sums_both_paid_sessions(self):
        envelopes = (
            {"ok": True, "is_error": False, "result": "done", "cost_usd": 0.25,
             "num_turns": 3, "raw": "{}", "stderr": "", "returncode": 0},
            {"ok": True, "is_error": False, "result": "done", "cost_usd": 0.55,
             "num_turns": 5, "raw": "{}", "stderr": "", "returncode": 0},
        )
        Fake = make_fake_sandbox(run_skill_envelopes=envelopes)
        check = _run_with_env_and_fake(Fake)
        self.assertTrue(check.passed, check.results)
        self.assertAlmostEqual(check.cost, 0.80)

    def test_cost_is_none_safe_when_one_session_is_missing_cost(self):
        envelopes = (
            {"ok": True, "is_error": False, "result": "done", "cost_usd": None,
             "num_turns": 3, "raw": "{}", "stderr": "", "returncode": 0},
            {"ok": True, "is_error": False, "result": "done", "cost_usd": 0.55,
             "num_turns": 5, "raw": "{}", "stderr": "", "returncode": 0},
        )
        Fake = make_fake_sandbox(run_skill_envelopes=envelopes)
        check = _run_with_env_and_fake(Fake)
        self.assertTrue(check.passed, check.results)
        self.assertAlmostEqual(check.cost, 0.55)


if __name__ == "__main__":
    unittest.main()
